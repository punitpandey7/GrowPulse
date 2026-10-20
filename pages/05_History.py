"""
GrowPulse — History
===================
Run history from approval log.
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent

st.set_page_config(page_title="GrowPulse - History", layout="wide")
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

st.markdown("### History")
st.caption("Decisions recorded by the MCP client (output/approval_log.json)")

approval_log = REPO_ROOT / "output" / "approval_log.json"
if approval_log.exists():
    try:
        entries = json.loads(approval_log.read_text(encoding="utf-8"))
    except Exception:
        entries = []
    if not entries:
        st.info("No approval history yet.")
    else:
        for e in reversed(entries):
            decision = e.get("decision", "?")
            ts = e.get("timestamp", "?")
            tools = ", ".join(e.get("tools_requested", []))
            detail = e.get("detail", "")
            with st.container(border=True):
                st.markdown(f"**{decision.upper()}** — {ts}")
                st.caption(f"Tools: {tools}")
                if detail:
                    st.caption(detail)
else:
    st.info("No approval log found yet. Run and approve/reject from the Approve page.")

st.divider()
st.markdown("### Server audit log")
audit = REPO_ROOT / "output" / "mcp_audit_log.jsonl"
if audit.exists():
    st.caption("Append-only log written by src/mcp_server.py (requested / executed / refused)")
    st.code(audit.read_text(encoding="utf-8")[-4000:], language="json")
else:
    st.info("No audit log yet.")
