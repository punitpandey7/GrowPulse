"""
GrowPulse — Approve
===================
Approval-gated MCP actions.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from mcp_client import run_mcp_actions, check_connection  # noqa: E402

st.set_page_config(page_title="GrowPulse - Approve", layout="wide")
st.markdown(
    """
<style>
    .block-container { padding-top: 1.0rem; padding-bottom: 2rem; max-width: 1200px; }
    .stApp { background: radial-gradient(1200px 600px at 80% -10%, #F0F9FF 0%, #F8FAFC 55%, #F8FAFC 100%); }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 12px; border-color: #E5E7EB; }
</style>
""",
    unsafe_allow_html=True,
)

artifacts = st.session_state.get("artifacts")
if not artifacts:
    st.warning("Run analysis from **Home** first.")
    st.page_link("app.py", label="Go to Home")
    st.stop()

st.markdown("### Approve & Log")
st.caption("MCP server refuses to write until it receives a single-use token bound to the exact payload. Email is drafted, never sent.")

payload = artifacts["payload"]

# Connection check
if st.button("Check MCP connection", help="Handshake + tools/list only — no tool is called, nothing is written"):
    with st.spinner("Connecting to the MCP server ..."):
        st.session_state["mcp_conn"] = check_connection()
conn = st.session_state.get("mcp_conn")
if conn is not None:
    if conn["ok"]:
        st.success(f"Connected — {conn['server'].get('name', 'growpulse-mcp')} v{conn['server'].get('version', '?')} · tools: {', '.join(conn['tools'])} · approval gate {'ACTIVE' if conn['gate_active'] else 'state unknown'}")
    else:
        st.error(f"Connection failed: {conn['error']}")

p1, p2 = st.columns(2, gap="large")
with p1, st.container(border=True):
    st.markdown("**Tool 1 · append_to_product_notes**")
    a = payload["arguments"]["append_to_product_notes"]
    st.code(f"date: {a['date']}\n" + "top_themes: " + ", ".join(f"{t['theme']} ({t['review_count']})" for t in a["top_themes"]) + f"\nweekly_pulse: {len(a['weekly_pulse'].split())} words\nidentified_fee_issue: {a['identified_fee_issue']['fee']} ({a['identified_fee_issue']['mentions']} mentions)\nexplanation_bullets: {len(a['explanation_bullets'])}\nsource_links: {len(a['source_links'])}", language="text")
with p2, st.container(border=True):
    st.markdown("**Tool 2 · create_email_draft** (never sends)")
    b = payload["arguments"]["create_email_draft"]
    st.code(f"to: {b['to']}\nsubject: {b['subject']}\nbody: {len(b['body'].split())} words", language="text")

outcome = st.session_state.get("mcp_outcome")
left, right = st.columns(2, gap="large")
approve = left.button("Approve & execute via MCP", type="primary", disabled=outcome is not None, use_container_width=True)
reject = right.button("Reject — write nothing", disabled=outcome is not None, use_container_width=True)

if approve or reject:
    with st.spinner("Talking to the MCP server ..." if approve else "Recording rejection ..."):
        st.session_state["mcp_outcome"] = run_mcp_actions(payload, decision="approve" if approve else "reject", verbose=False, prove_gate=approve)
        outcome = st.session_state["mcp_outcome"]

if outcome is not None:
    if outcome["approved"]:
        st.success("Approved — both tools executed exactly once.")
        for r in outcome["results"]:
            st.markdown(f"**`{r['tool']}`** → {r['result']}")
        d1, d2 = st.columns(2, gap="large")
        notes_path = REPO_ROOT / "product_pulse" / "product_notes.md"
        if notes_path.exists():
            notes = notes_path.read_text(encoding="utf-8")
            with d1, st.container(border=True):
                st.markdown("**Notes doc — last appended entry**")
                chunks = notes.split("\n---\n")
                st.code(chunks[-1].strip() if chunks else notes[-2000:], language="markdown")
        drafts_dir = REPO_ROOT / "output" / "drafts"
        if drafts_dir.exists():
            drafts = sorted(drafts_dir.glob("*.md"))
            if drafts:
                with d2, st.container(border=True):
                    st.markdown("**Email draft — created, not sent**")
                    st.code(drafts[-1].read_text(encoding="utf-8")[:2400], language="markdown")
                    eml = drafts[-1].with_suffix(".eml")
                    if eml.exists():
                        st.download_button("Download .eml (X-Unsent: 1)", eml.read_bytes(), file_name=eml.name, mime="message/rfc822")
    else:
        st.error("Rejected — no MCP tool was executed and nothing was written.")

    n_events = len(outcome["transcript"])
    with st.expander(f"Live MCP transcript — {n_events} events", expanded=outcome["approved"]):
        for line in outcome["transcript"]:
            detail = f" — {line['detail']}" if line.get("detail") else ""
            st.markdown(f"`{line['dir']} {line['kind']}` **{line['tool']}** → `{line['status']}`{detail}")
