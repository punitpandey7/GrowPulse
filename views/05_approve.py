"""
GrowPulse — Approve & Log
=========================
Approval-gated MCP actions.
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent

from mcp_client import check_connection, run_mcp_actions  # noqa: E402

artifacts = st.session_state.get("artifacts")
if not artifacts:
    st.warning("🔐 No analysis results yet. Please run the analysis from the **Home** page first.")
    st.page_link("views/01_home.py", label="⬅️ Go to Home to run analysis")
    st.stop()

st.markdown("## 🔐 Approve & Log")
st.caption("The MCP server refuses to write until it receives a single-use token bound to the "
           "exact payload. Email is drafted, never sent.")

payload = artifacts["payload"]

# Zero-side-effect connectivity probe (handshake + tools/list, never a tool call)
if st.button("🔌 Check MCP connection",
             help="Handshake + tools/list only — no tool is called, nothing is written"):
    with st.spinner("Connecting to the MCP server ..."):
        st.session_state["mcp_conn"] = check_connection()
conn = st.session_state.get("mcp_conn")
if conn is not None:
    if conn["ok"]:
        st.success(f"✅ Connected — **{conn['server'].get('name', 'growpulse-mcp')}** "
                   f"v{conn['server'].get('version', '?')} · tools: "
                   f"`{', '.join(conn['tools'])}` · approval gate "
                   f"{'ACTIVE' if conn['gate_active'] else 'state unknown'}")
    else:
        st.error(f"❌ Connection failed: {conn['error']}")

p1, p2 = st.columns(2, gap="large")
with p1, st.container(border=True):
    st.markdown("**📝 Tool 1 · `append_to_product_notes`**")
    a = payload["arguments"]["append_to_product_notes"]
    st.code(f"date: {a['date']}\n"
            + "top_themes: " + ", ".join(f"{t['theme']} ({t['review_count']})" for t in a["top_themes"])
            + f"\nweekly_pulse: {len(a['weekly_pulse'].split())} words"
            + f"\nidentified_fee_issue: {a['identified_fee_issue']['fee']} "
              f"({a['identified_fee_issue']['mentions']} mentions)"
            + f"\nexplanation_bullets: {len(a['explanation_bullets'])}"
            + f"\nsource_links: {len(a['source_links'])}", language="text")
with p2, st.container(border=True):
    st.markdown("**📧 Tool 2 · `create_email_draft`** (never sends)")
    b = payload["arguments"]["create_email_draft"]
    st.code(f"to: {b['to']}\nsubject: {b['subject']}\n"
            f"body: {len(b['body'].split())} words (pulse + support snippet)", language="text")

outcome = st.session_state.get("mcp_outcome")
left, right = st.columns(2, gap="large")
approve = left.button("✅ Approve & execute via MCP", type="primary",
                      disabled=outcome is not None, use_container_width=True)
reject = right.button("❌ Reject — write nothing", disabled=outcome is not None,
                      use_container_width=True)

if approve or reject:
    with st.spinner("Talking to the MCP server ..." if approve else "Recording rejection ..."):
        st.session_state["mcp_outcome"] = run_mcp_actions(
            payload, decision="approve" if approve else "reject",
            verbose=False, prove_gate=approve)
        outcome = st.session_state["mcp_outcome"]

if outcome is not None:
    if outcome["approved"]:
        st.success("✅ Approved — both tools executed exactly once.")
        for r in outcome["results"]:
            st.markdown(f"**`{r['tool']}`** → {r['result']}")
        d1, d2 = st.columns(2, gap="large")
        notes = (REPO_ROOT / "product_pulse" / "product_notes.md").read_text(encoding="utf-8")
        with d1, st.container(border=True):
            st.markdown("**📋 Notes doc — last appended entry**")
            chunks = notes.split("\n---\n")
            st.code(chunks[-1].strip() if chunks else notes[-2000:], language="markdown")
        with d2, st.container(border=True):
            st.markdown("**📧 Email draft — created, not sent**")
            drafts = sorted((REPO_ROOT / "output" / "drafts").glob("*.md"))
            if drafts:
                st.code(drafts[-1].read_text(encoding="utf-8")[:2400], language="markdown")
                eml = drafts[-1].with_suffix(".eml")
                if eml.exists():
                    st.download_button("⬇️ Download .eml (X-Unsent: 1)", eml.read_bytes(),
                                       file_name=eml.name, mime="message/rfc822")
    else:
        st.error("❌ Rejected — no MCP tool was executed and nothing was written.")

    n_events = len(outcome["transcript"])
    with st.expander(f"🧾 Live MCP transcript — {n_events} events", expanded=outcome["approved"]):
        for line in outcome["transcript"]:
            detail = f" — {line['detail']}" if line.get("detail") else ""
            st.markdown(f"`{line['dir']} {line['kind']}` **{line['tool']}** → "
                        f"`{line['status']}`{detail}")

approval_log = REPO_ROOT / "output" / "approval_log.json"
if approval_log.exists():
    try:
        entries = json.loads(approval_log.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        entries = []
    with st.expander(f"📚 Run history — {len(entries)} recorded decisions", expanded=False):
        for e in reversed(entries[-15:]):
            icon = "✅" if e.get("decision") == "approved" else "❌"
            st.markdown(f"- {icon} `{e.get('timestamp', '?')}` — **{e.get('decision', '?')}** · "
                        f"{', '.join(e.get('tools_requested', []))}")
        st.caption("output/approval_log.json (written by the client) · "
                   "output/mcp_audit_log.jsonl (append-only, written by the server)")
