"""
GrowPulse MCP server — Model Context Protocol (stdio transport, JSON-RPC 2.0)
=============================================================================
Implements the MCP handshake (initialize / notifications/initialized / tools/list /
tools/call, protocol 2024-11-05) with two tools:

  1. append_to_product_notes  — appends this week's entry to the internal
                                product notes document (Markdown).
  2. create_email_draft       — creates an email DRAFT file (.md + .eml with
                                X-Unsent: 1). It never sends mail — by design.

APPROVAL GATE (enforced server-side, not by client courtesy)
------------------------------------------------------------
A tools/call WITHOUT an approval_token does not execute. It returns:

    { "status": "approval_required",
      "approval_token": "<hmac>",          # HMAC-SHA256(secret, tool|canonical-args)
      "preview": "<what will be written>" }

The human reviews the preview. Resending the SAME arguments plus the token
executes the tool once. Properties, each verifiable:

  * the token is an HMAC of the exact arguments — an approval for one payload
    cannot be reused to write a DIFFERENT payload (tamper -> refused)
  * tokens are SINGLE-USE — replays are refused, so retries cannot double-append
  * the secret is minted per process — tokens do not survive a restart
  * every call (requested / executed / refused) is appended to an audit log

Run standalone:   python src\\mcp_server.py
Configuration:    GROWW_NOTES_PATH, GROWW_DRAFTS_DIR, GROWW_AUDIT_LOG (env)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # MCP stdio transport speaks UTF-8
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "growpulse-mcp", "version": "2.0.0"}

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTES_PATH = Path(os.environ.get("GROWW_NOTES_PATH", REPO_ROOT / "product_pulse" / "product_notes.md"))
DRAFTS_DIR = Path(os.environ.get("GROWW_DRAFTS_DIR", REPO_ROOT / "output" / "drafts"))
AUDIT_LOG = Path(os.environ.get("GROWW_AUDIT_LOG", REPO_ROOT / "output" / "mcp_audit_log.jsonl"))

# per-process approval secret + used-token registry
_APPROVAL_SECRET = secrets.token_hex(16)
_USED_TOKENS: set[str] = set()

# --------------------------------------------------------------------------------------
# Tool definitions (JSON Schema)
# --------------------------------------------------------------------------------------

TOOLS = [
    {
        "name": "append_to_product_notes",
        "description": (
            "Append the weekly product pulse entry to the internal product notes "
            "document. Input: review window date, top themes, weekly pulse text, "
            "identified fee issue, explanation bullets, source links. "
            "Approval-gated: call once without approval_token to obtain a preview "
            "and a single-use token bound to these exact arguments."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["date", "top_themes", "weekly_pulse", "identified_fee_issue", "explanation_bullets", "source_links"],
            "properties": {
                "date": {"type": "string", "description": "Week-ending date (ISO, YYYY-MM-DD)"},
                "top_themes": {
                    "type": "array",
                    "description": "Top themes with review counts",
                    "items": {
                        "type": "object",
                        "properties": {
                            "theme": {"type": "string"},
                            "review_count": {"type": "integer"},
                            "avg_rating": {"type": "number"},
                        },
                    },
                },
                "weekly_pulse": {"type": "string", "description": "The <=250-word weekly product pulse (Markdown)"},
                "identified_fee_issue": {
                    "type": "object",
                    "properties": {
                        "fee": {"type": "string"},
                        "mentions": {"type": "integer"},
                        "confusion_mentions": {"type": "integer"},
                        "summary": {"type": "string"},
                    },
                },
                "explanation_bullets": {"type": "array", "items": {"type": "string"}},
                "source_links": {"type": "array", "items": {"type": "string"}},
                "approval_token": {"type": "string", "description": "Single-use HMAC token from the approval_required response"},
            },
        },
    },
    {
        "name": "create_email_draft",
        "description": (
            "Create an email draft file (.md + .eml with X-Unsent: 1) with the "
            "given subject and body. NEVER sends email. Approval-gated: call once "
            "without approval_token to obtain a preview and a single-use token."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["to", "subject", "body"],
            "properties": {
                "to": {"type": "string", "description": "Recipient alias(es), comma separated"},
                "subject": {"type": "string"},
                "body": {"type": "string", "description": "Markdown/plain-text body incl. weekly pulse + fee snippet"},
                "approval_token": {"type": "string", "description": "Single-use HMAC token from the approval_required response"},
            },
        },
    },
]

# --------------------------------------------------------------------------------------
# Approval tokens
# --------------------------------------------------------------------------------------


def _canonical(args: dict) -> str:
    return json.dumps(args, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _mint_token(tool_name: str, args: dict) -> str:
    msg = f"{tool_name}|{_canonical(args)}".encode("utf-8")
    return hmac.new(_APPROVAL_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()[:32]


def _verify_token(tool_name: str, args: dict, token: str | None) -> str | None:
    """Return None if valid, else the refusal reason."""
    if not token:
        return "missing approval_token"
    if not hmac.compare_digest(_mint_token(tool_name, args), token):
        return "token does not match these exact arguments (payload edited or forged)"
    if token in _USED_TOKENS:
        return "token already used (replays are refused; request a fresh approval)"
    return None


def _audit(event: str, tool: str, detail: str = "") -> None:
    try:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": datetime.now().isoformat(timespec="seconds"),
                "event": event, "tool": tool, "detail": detail,
            }, ensure_ascii=False) + "\n")
    except OSError:
        pass


# --------------------------------------------------------------------------------------
# Renderers (shared by preview and execution)
# --------------------------------------------------------------------------------------


def _render_entry(args: dict) -> str:
    themes = args["top_themes"]
    fee = args["identified_fee_issue"]
    theme_lines = "\n".join(
        f"- {t['theme']} — {t['review_count']} reviews (avg {t.get('avg_rating', 'n/a')}★)" for t in themes
    )
    bullet_lines = "\n".join(f"- {b}" for b in args["explanation_bullets"])
    source_lines = "\n".join(f"- {u}" for u in args["source_links"])
    return (
        f"\n---\n\n## Week ending {args['date']}\n\n"
        f"### Top themes\n{theme_lines}\n\n"
        f"### Identified fee issue\n"
        f"**{fee.get('fee', 'n/a')}** — {fee.get('mentions', 0)} mentions, "
        f"{fee.get('confusion_mentions', 0)} with explicit confusion signals. "
        f"{fee.get('summary', '')}\n\n"
        f"### Weekly product pulse\n{args['weekly_pulse'].strip()}\n\n"
        f"### Fee explanation (support snippet)\n{bullet_lines}\n\n"
        f"### Sources\n{source_lines}\n\n"
        f"*Logged via MCP by {SERVER_INFO['name']} on {datetime.now().isoformat(timespec='seconds')}*\n"
    )


def _preview(name: str, args: dict) -> str:
    if name == "append_to_product_notes":
        entry = _render_entry(args)
        head = entry[:600]
        return (f"APPEND to {NOTES_PATH.name}:\n{head}"
                f"\n… (+{len(entry) - len(head)} more characters)")
    body = args.get("body", "")
    return (f"CREATE email draft (NOT sent)\nTo: {args.get('to', '')}\nSubject: {args.get('subject', '')}\n\n"
            f"{body[:500]}" + (f"\n… (+{len(body) - 500} more characters)" if len(body) > 500 else ""))


# --------------------------------------------------------------------------------------
# Tool implementations (execute ONLY after token verification)
# --------------------------------------------------------------------------------------


def _tool_append_to_product_notes(args: dict) -> str:
    NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = _render_entry(args)
    if NOTES_PATH.exists():
        existing = NOTES_PATH.read_text(encoding="utf-8")
        NOTES_PATH.write_text(existing.rstrip() + "\n" + entry, encoding="utf-8")
    else:
        NOTES_PATH.write_text(f"# Product Notes — Weekly Pulse Log\n{entry}", encoding="utf-8")
    return f"Appended week ending {args['date']} to {NOTES_PATH} ({len(entry.split())} words added)."


def _tool_create_email_draft(args: dict) -> str:
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = "".join(c if c.isalnum() else "-" for c in args["subject"][:40]).strip("-")
    md_path = DRAFTS_DIR / f"draft-{stamp}-{slug}.md"
    eml_path = DRAFTS_DIR / f"draft-{stamp}-{slug}.eml"

    md_path.write_text(
        f"# Email draft (NOT SENT)\n\n- **To:** {args['to']}\n- **Subject:** {args['subject']}\n"
        f"- **Status:** draft only — requires human review before sending\n\n---\n\n{args['body']}\n",
        encoding="utf-8",
    )
    eml_path.write_text(
        f"To: {args['to']}\r\nSubject: {args['subject']}\r\nX-Unsent: 1\r\nX-Status: DRAFT (not sent)\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n\r\n{args['body']}\r\n",
        encoding="utf-8",
    )
    return f"Email draft created (not sent): {md_path.name} (+{eml_path.name}, X-Unsent:1)."


TOOL_IMPL = {
    "append_to_product_notes": _tool_append_to_product_notes,
    "create_email_draft": _tool_create_email_draft,
}

# --------------------------------------------------------------------------------------
# JSON-RPC 2.0 / MCP dispatcher
# --------------------------------------------------------------------------------------


def _respond(id_, result=None, error=None) -> dict:
    msg = {"jsonrpc": "2.0", "id": id_}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    return msg


def _text_result(payload: dict, is_error: bool = False) -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=1)}],
        "isError": is_error,
        "_meta": {"approvalRequired": payload.get("status") == "approval_required"},
    }


def handle_request(req: dict) -> dict | None:
    method = req.get("method")
    id_ = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        return _respond(
            id_,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
                "instructions": (
                    "Tools log the weekly product pulse and create an email draft. "
                    "Both are approval-gated SERVER-SIDE: a tools/call without approval_token "
                    "returns a preview and a single-use HMAC token bound to the exact arguments. "
                    "create_email_draft never sends mail."
                ),
            },
        )

    if method == "notifications/initialized":
        return None  # notification: no response

    if method == "ping":
        return _respond(id_, {})

    if method == "tools/list":
        return _respond(id_, {"tools": TOOLS})

    if method == "tools/call":
        name = params.get("name")
        args = dict(params.get("arguments") or {})
        if name not in TOOL_IMPL:
            return _respond(id_, error={"code": -32602, "message": f"Unknown tool: {name}"})

        token = args.pop("approval_token", None)

        # ---- gate: no token -> preview + token, nothing written --------------------
        if token is None:
            _audit("approval_required", name, f"args_keys={sorted(args)}")
            return _respond(id_, _text_result({
                "status": "approval_required",
                "tool": name,
                "approval_token": _mint_token(name, args),
                "preview": _preview(name, args),
                "message": "Nothing was written. Show the preview to a human. "
                           "Resend the SAME arguments plus approval_token to execute.",
            }))

        # ---- gate: bad/replayed/forged token -> refused -----------------------------
        reason = _verify_token(name, args, token)
        if reason is not None:
            _audit("refused", name, reason)
            return _respond(id_, _text_result({"status": "refused", "tool": name, "reason": reason}, is_error=True))

        # ---- approved exactly once -> execute -----------------------------------------
        _USED_TOKENS.add(token)
        try:
            text = TOOL_IMPL[name](args)
            _audit("executed", name, text)
            return _respond(id_, _text_result({"status": "executed", "tool": name, "result": text}))
        except Exception as exc:  # tool errors are in-band per MCP
            _audit("error", name, str(exc))
            return _respond(id_, _text_result({"status": "error", "tool": name, "error": str(exc)}, is_error=True))

    if id_ is not None:
        return _respond(id_, error={"code": -32601, "message": f"Method not found: {method}"})
    return None


def main() -> None:
    print(f"[mcp-server] {SERVER_INFO['name']} v{SERVER_INFO['version']} listening on stdio "
          f"(notes -> {NOTES_PATH}, server-side approval gate active)", file=sys.stderr, flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle_request(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
