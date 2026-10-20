"""
GrowPulse MCP client + approval gate
====================================
Spawns the MCP server (src/mcp_server.py) as a subprocess, performs the MCP
handshake, then drives the SERVER-SIDE approval flow:

  1. tools/call WITHOUT a token        -> server returns preview + single-use HMAC
                                          token, writes nothing
  2. human reads the preview, decides  -> y/N at the terminal (or --approve/--reject)
  3. tools/call WITH the token         -> server executes exactly once

After execution the client optionally PROVES the gate in front of the user:
it replays the used token and sends a tampered payload — the server refuses both.

Every request/response pair is captured as a transcript (shown in the CLI and
in the Streamlit "Approve & log" tab).

CLI:
    python src\\mcp_client.py --payload output\\mcp_payload.json          # interactive y/N
    python src\\mcp_client.py --payload output\\mcp_payload.json --approve
    python src\\mcp_client.py --payload output\\mcp_payload.json --reject
"""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows console safety

PROTOCOL_VERSION = "2024-11-05"
REPO_ROOT = Path(__file__).resolve().parent.parent
APPROVAL_LOG = REPO_ROOT / "output" / "approval_log.json"


class MCPClient:
    """Minimal MCP client over the stdio transport (newline-delimited JSON-RPC)."""

    def __init__(self, server_path: Path):
        self.proc = subprocess.Popen(
            [sys.executable, str(server_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        self._id = 0
        self.stderr_lines: list[str] = []
        # drain server stderr in a daemon thread so the pipe never blocks
        def _drain() -> None:
            for line in self.proc.stderr:
                self.stderr_lines.append(line.rstrip())
        threading.Thread(target=_drain, daemon=True).start()

    def _send(self, msg: dict) -> None:
        self.proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def request(self, method: str, params: dict | None = None, timeout: float = 15.0) -> dict:
        self._id += 1
        req_id = self._id
        self._send({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}})
        result: dict = {}

        def _read() -> None:
            nonlocal result
            line = self.proc.stdout.readline()
            if line:
                msg = json.loads(line)
                if msg.get("id") == req_id:
                    result = msg

        t = threading.Thread(target=_read, daemon=True)
        t.start()
        t.join(timeout)
        if not result:
            if self.proc.poll() is not None:
                raise RuntimeError("MCP server process died (see server stderr)")
            raise TimeoutError(f"No response for {method} within {timeout}s")
        if "error" in result:
            raise RuntimeError(f"{method} failed: {result['error']}")
        return result.get("result", {})

    def notify(self, method: str, params: dict | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def initialize(self) -> dict:
        result = self.request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "growpulse-workflow-client", "version": "2.0.0"},
            },
        )
        self.notify("notifications/initialized")
        return result

    def list_tools(self) -> list[dict]:
        return self.request("tools/list").get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> dict:
        """Return the parsed JSON payload the server puts in the text content."""
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        content = result.get("content", [])
        text = "\n".join(c.get("text", "") for c in content)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {"status": "raw", "text": text}
        payload["_isError"] = bool(result.get("isError"))
        return payload

    def close(self) -> None:
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        self.proc.terminate()


# --------------------------------------------------------------------------------------
# Approval gate (client side: ask the human. server side: enforce the token)
# --------------------------------------------------------------------------------------


def show_approval_prompt(preview_blocks: list[dict], decision: str | None = None) -> bool:
    print("\n" + "=" * 78)
    print("MCP APPROVAL GATE — server returned these previews, nothing is written yet")
    print("=" * 78)
    for item in preview_blocks:
        print(f"\n  ▸ {item['tool']}")
        for line in item["preview"].splitlines():
            print(f"    {line}")
    print("\n" + "-" * 78)
    print("  Approving executes each tool EXACTLY ONCE (single-use HMAC token).")
    print("  Email is drafted, never sent. Reject leaves every tool untouched.")
    print("-" * 78)

    if decision == "approve":
        print("Decision: APPROVE (via --approve flag)")
        return True
    if decision == "reject":
        print("Decision: REJECT (via --reject flag)")
        return False
    try:
        answer = input("Approve these MCP actions? [y/N] ").strip().lower()
    except EOFError:
        answer = ""
    return answer in ("y", "yes")


def log_approval(decision: str, tools: list[str], detail: str = "") -> None:
    APPROVAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    if APPROVAL_LOG.exists():
        try:
            entries = json.loads(APPROVAL_LOG.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            entries = []
    entries.append(
        {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "decision": decision,
            "tools_requested": tools,
            "detail": detail,
        }
    )
    APPROVAL_LOG.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


# --------------------------------------------------------------------------------------
# Workflow-facing helper
# --------------------------------------------------------------------------------------


def run_mcp_actions(payload: dict, decision: str | None = None, verbose: bool = True,
                    prove_gate: bool = True) -> dict:
    """Full approval flow against the MCP server. Returns:
       {"approved": bool, "results": [...], "transcript": [...]}"""

    def say(msg: str = "") -> None:
        if verbose:
            print(msg)

    tools = list(payload["arguments"].keys())
    client = MCPClient(REPO_ROOT / "src" / "mcp_server.py")
    transcript: list[dict] = []
    try:
        info = client.initialize()
        server = info.get("serverInfo", {})
        say(f"\n✓ MCP handshake with '{server.get('name')}' v{server.get('version')} "
            f"(protocol {info.get('protocolVersion')}) — server-side approval gate active")
        available = [t["name"] for t in client.list_tools()]
        say(f"✓ Tools exposed by server: {', '.join(available)}")

        # ---- step 1: request approval (no token; server writes nothing) -------------
        approvals: dict[str, dict] = {}
        preview_blocks: list[dict] = []
        for name in tools:
            resp = client.call_tool(name, copy.deepcopy(payload["arguments"][name]))
            transcript.append({"dir": "→", "tool": name, "kind": "call (no token)", "status": resp.get("status")})
            transcript.append({"dir": "←", "tool": name, "kind": "server", "status": resp.get("status")})
            if resp.get("status") != "approval_required":
                say(f"  ! {name}: expected approval_required, got {resp.get('status')}")
                return {"approved": False, "results": [], "transcript": transcript}
            approvals[name] = resp["approval_token"]
            preview_blocks.append({"tool": name, "preview": resp["preview"]})

        # ---- step 2: the human decides ------------------------------------------------
        approved = show_approval_prompt(preview_blocks, decision=decision)
        log_approval("approved" if approved else "rejected", tools,
                     detail=payload["arguments"].get("create_email_draft", {}).get("subject", ""))
        if not approved:
            say("\n✖ Rejected. No MCP tool was executed. Nothing was logged or drafted.")
            return {"approved": False, "results": [], "transcript": transcript}

        # ---- step 3: resend WITH the single-use token -> execution ----------------------
        results = []
        for name in tools:
            args = copy.deepcopy(payload["arguments"][name])
            args["approval_token"] = approvals[name]
            say(f"▸ Calling {name} (with approval token) ...")
            resp = client.call_tool(name, args)
            transcript.append({"dir": "→", "tool": name, "kind": "call (with token)", "status": resp.get("status")})
            transcript.append({"dir": "←", "tool": name, "kind": "server", "status": resp.get("status"),
                               "detail": resp.get("result", resp.get("reason", ""))[:160]})
            say(f"  → {resp.get('result', resp.get('reason'))}")
            results.append({"tool": name, "status": resp.get("status"), "result": resp.get("result", "")})

        # ---- step 4: prove the gate (replay + tamper, both refused server-side) ----------
        if prove_gate and tools:
            name = tools[0]
            replay = copy.deepcopy(payload["arguments"][name])
            replay["approval_token"] = approvals[name]
            r1 = client.call_tool(name, replay)
            transcript.append({"dir": "→", "tool": name, "kind": "PROOF: replay used token", "status": r1.get("status")})
            transcript.append({"dir": "←", "tool": name, "kind": "PROOF: replay", "status": r1.get("status"),
                               "detail": r1.get("reason", "")})

            tampered = copy.deepcopy(payload["arguments"][name])
            tampered["date"] = "1999-01-01"          # edit one field after approval
            tampered["approval_token"] = approvals[name]
            r2 = client.call_tool(name, tampered)
            transcript.append({"dir": "→", "tool": name, "kind": "PROOF: tampered payload", "status": r2.get("status")})
            transcript.append({"dir": "←", "tool": name, "kind": "PROOF: tamper", "status": r2.get("status"),
                               "detail": r2.get("reason", "")})
            say(f"\n✓ Gate proof — replay: {r1.get('status')} ({r1.get('reason', '')[:60]}), "
                f"tampered payload: {r2.get('status')} ({r2.get('reason', '')[:60]})")

        return {"approved": True, "results": results, "transcript": transcript}
    finally:
        client.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Approval-gated MCP client")
    ap.add_argument("--payload", required=True, help="JSON file with MCP tool arguments")
    ap.add_argument("--approve", action="store_true", help="Auto-approve (for demos/CI)")
    ap.add_argument("--reject", action="store_true", help="Auto-reject (for demos/CI)")
    ns = ap.parse_args()

    payload = json.loads(Path(ns.payload).read_text(encoding="utf-8"))
    decision = "approve" if ns.approve else "reject" if ns.reject else None
    outcome = run_mcp_actions(payload, decision=decision)
    sys.exit(0 if outcome["approved"] else 2)
