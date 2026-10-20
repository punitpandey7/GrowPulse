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
    .stApp { background: radial-gradient(1400px 700px at 10% -20%, #EEF6FF 0%, #F8FAFC 40%, #F7F9FC 100%); }
    header[data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #F8FAFF 0%, #F6F8FB 100%); border-right: 1px solid #E6EBF5; }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px; border-color: #E6EBF5; background: #FFFFFF; box-shadow: 0 10px 40px -24px rgba(15,23,42,0.8); }
    [data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2, [data-testid="stMarkdownContainer"] h3 { color: #0F172A; letter-spacing: -.2px; }
    .stCaption { color: #475569 !important; }
</style>
""",
    unsafe_allow_html=True,
)

artifacts = st.session_state.get("artifacts")
if not artifacts:
    st.warning("📜 No analysis results yet. Please run the analysis from the **Home** page first.")
    st.page_link("app.py", label="⬅️ Go to Home to run analysis")
    st.stop()

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
                if decision == "approved":
                    st.markdown(f"**✅ APPROVED** — {ts}")
                elif decision == "rejected":
                    st.markdown(f"**❌ REJECTED** — {ts}")
                else:
                    st.markdown(f"**📝 {decision.upper()}** — {ts}")
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
