"""
GrowPulse — Insights
====================
Themes ranked by 1-2 star volume with trends, verbatim quotes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

st.set_page_config(page_title="GrowPulse - Insights", layout="wide")
st.markdown(
    """
<style>
    .block-container { padding-top: 1.0rem; padding-bottom: 2rem; max-width: 1200px; }
    .stApp { background: radial-gradient(1400px 700px at 10% -20%, #EEF6FF 0%, #F8FAFC 40%, #F7F9FC 100%); }
    header[data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #F8FAFF 0%, #F6F8FB 100%); border-right: 1px solid #E6EBF5; }
    .gp-quote { border-left: 3px solid #2563EB; border-radius: 12px; background: linear-gradient(180deg, #FFFFFF 0%, #FBFDFF 100%); border: 1px solid #E6EBF5; padding: 14px 16px; min-height: 168px; font-size: .94rem; line-height: 1.55; color: #1F2937; box-shadow: 0 10px 40px -24px rgba(15,23,42,0.8); }
    .gp-quote .src { font-size: .76rem; color: #6B7280; margin-top: 10px; }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px; border-color: #E6EBF5; background: #FFFFFF; box-shadow: 0 10px 40px -24px rgba(15,23,42,0.8); }
    [data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2, [data-testid="stMarkdownContainer"] h3 { color: #0F172A; letter-spacing: -.2px; }
    .stCaption { color: #475569 !important; }
</style>
""",
    unsafe_allow_html=True,
)

artifacts = st.session_state.get("artifacts")
if not artifacts:
    st.warning("🔍 No analysis results yet. Please run the analysis from the **Home** page first.")
    st.page_link("app.py", label="⬅️ Go to Home to run analysis")
    st.stop()