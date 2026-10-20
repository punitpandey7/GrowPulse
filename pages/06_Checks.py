"""
GrowPulse — Checks
==================
Data quality gate, distributions, audit logs.
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent

st.set_page_config(page_title="GrowPulse - Checks", layout="wide")
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

dq = artifacts["dq"]

st.markdown("### Data quality")
st.caption("Step 0 runs before every analysis — offending rows are dropped and counted, never silently kept.")

checks = [
    ("Rows in → clean out", f"{dq['total_input']:,} → {dq['total_output']:,}", dq["total_output"] == dq["total_input"]),
    ("Blank required fields dropped", dq["blank_dropped"], dq["blank_dropped"] == 0),
    ("Duplicate review_id dropped", dq["duplicate_id_dropped"], dq["duplicate_id_dropped"] == 0),
    ("Duplicate content dropped", dq["duplicate_text_dropped"], dq["duplicate_text_dropped"] == 0),
    ("Bad dates dropped", dq["bad_date_dropped"], dq["bad_date_dropped"] == 0),
    ("Invalid ratings dropped", dq["bad_rating_dropped"], dq["bad_rating_dropped"] == 0),
    ("Unknown sources dropped", dq["unknown_source_dropped"], dq["unknown_source_dropped"] == 0),
    ("Too-short text dropped", dq["short_text_dropped"], dq["short_text_dropped"] == 0),
    ("Encoding artifacts flagged", dq["encoding_flagged"], dq["encoding_flagged"] == 0),
]

left, right = st.columns([1.2, 1], gap="large")
with left, st.container(border=True):
    st.markdown("**Checks**")
    for name, val, ok in checks:
        st.markdown(f"{'PASS' if ok else 'FAIL'} {name} — `{val}`")

with right, st.container(border=True):
    st.markdown("**Distributions**")
    st.markdown(f"**Window** {dq['date_min']} → {dq['date_max']} (~{dq['weeks_spanned']} weeks)")
    st.markdown("**Ratings**")
    for star in sorted(dq.get("rating_distribution", {}), reverse=True):
        st.markdown(f"- {star}★ · {dq['rating_distribution'][star]}")
    st.markdown("**Sources**")
    for src, cnt in sorted(dq.get("source_distribution", {}).items(), key=lambda x: -x[1]):
        st.markdown(f"- {src} · {cnt}")

if artifacts["llm_log"]:
    with st.expander("AI drafting log", expanded=False):
        for line in artifacts["llm_log"]:
            st.markdown(f"- {line}")

audit = REPO_ROOT / "output" / "mcp_audit_log.jsonl"
if audit.exists():
    with st.expander("MCP server audit log (append-only)", expanded=False):
        st.code(audit.read_text(encoding="utf-8")[-3000:], language="json")
