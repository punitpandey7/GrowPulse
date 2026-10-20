"""
GrowPulse — Home
================
Landing page: data source + controls, run analysis, overview KPIs and quick summary.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "src"))

# Streamlit Community Cloud: pick up App settings -> Secrets (same KEY=VALUE names as .env)
try:
    _secrets = st.secrets.to_dict()
except Exception:
    _secrets = {}
for _k in ("GROQ_API_KEY", "GROQ_MODEL"):
    if _secrets.get(_k):
        os.environ.setdefault(_k, _secrets[_k])

from workflow import run_steps  # noqa: E402

st.set_page_config(page_title="GrowPulse", layout="wide", initial_sidebar_state="expanded")

# CSS
st.markdown(
    """
<style>
    .block-container { padding-top: 1.0rem; padding-bottom: 2rem; max-width: 1200px; }
    .stApp { background: radial-gradient(1400px 700px at 10% -20%, #EEF6FF 0%, #F8FAFC 40%, #F7F9FC 100%); }
    header[data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #F8FAFF 0%, #F6F8FB 100%); border-right: 1px solid #E6EBF5; }
    .gp-hero {
        background: linear-gradient(90deg, rgba(37,99,235,0.14) 0%, rgba(14,165,233,0.10) 60%, rgba(34,197,94,0.06) 100%);
        border: 1px solid rgba(37,99,235,0.32); border-radius: 16px;
        padding: 20px 26px; margin: 0 0 16px 0; box-shadow: 0 10px 40px -18px rgba(37,99,235,0.6);
    }
    .gp-hero h1 { color: #0F172A; margin: 0; font-size: 2.0rem; font-weight: 700; letter-spacing: -.4px; }
    .gp-hero p  { color: #334155; margin: 8px 0 0 0; font-size: .99rem; max-width: 860px; }
    .gp-card {
        border-radius: 14px; padding: 16px 20px; background: linear-gradient(180deg, #FFFFFF 0%, #FBFDFF 100%);
        border: 1px solid #E6EBF5; border-top: 3px solid #2563EB;
        box-shadow: 0 10px 40px -20px rgba(15,23,42,0.9);
        min-height: 104px; display: flex; flex-direction: column; justify-content: center;
    }
    .gp-card.teal   { border-top-color: #0EA5E9; }
    .gp-card.green  { border-top-color: #22C55E; }
    .gp-card.amber  { border-top-color: #F59E0B; }
    .gp-card.violet { border-top-color: #8B5CF6; }
    .gp-card .num   { font-size: 1.8rem; font-weight: 700; color: #0F172A; line-height: 1.15; }
    .gp-card .lbl   { font-size: .83rem; color: #475569; margin-top: 6px; }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px; border-color: #E6EBF5; background: #FFFFFF; box-shadow: 0 10px 40px -24px rgba(15,23,42,0.8); }
    div[data-testid="stMetricValue"] { font-size: 1.5rem; color: #0F172A; }
    [data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2, [data-testid="stMarkdownContainer"] h3 { color: #0F172A; letter-spacing: -.2px; }
    .stCaption { color: #475569 !important; }
    .gp-chip { display: inline-block; padding: 2px 10px; margin: 0 6px 4px 0; border-radius: 999px; background: linear-gradient(90deg, rgba(37,99,235,0.10) 0%, rgba(14,165,233,0.08) 100%); border: 1px solid rgba(37,99,235,0.35); font-size: .76rem; color: #1E3A8A; }
</style>
""",
    unsafe_allow_html=True,
)


def kpi(num: str, label: str, color: str = "") -> str:
    cls = "gp-card " + color if color else "gp-card"
    return f'<div class="{cls}"><div class="num">{num}</div><div class="lbl">{label}</div></div>'


# Sidebar
with st.sidebar:
    st.markdown("## GrowPulse")
    st.caption("Weekly product pulse from app reviews")
    st.divider()
    
    st.markdown("**Data source**")
    source = st.radio("Reviews data", ["Sample dataset (1,200 Groww reviews)", "Upload my CSV"],
                      label_visibility="collapsed")
    uploaded = None
    if source == "Upload my CSV":
        uploaded = st.file_uploader("CSV: review_id, date, source, rating, review_text",
                                    type="csv",
                                    help="Extra columns are ignored. Bad rows are dropped and reported.")
    st.date_input("Report week ending", value=date.today(), key="week_ending")
    
    st.divider()
    with st.expander("Advanced — AI drafting (optional)", expanded=False):
        st.caption("Deterministic writers are the default. Add a Groq key for optional LLM drafting.")
        groq_key = st.text_input("Groq API key", type="password",
                                 help="Kept in memory for this session only. Or set GROQ_API_KEY in .env / Streamlit Secrets.")
        use_llm = st.checkbox("Use Groq for drafting", value=False)
        llm_model = st.text_input("Groq model", value=os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"))
        if groq_key:
            os.environ["GROQ_API_KEY"] = groq_key
        if use_llm and not (groq_key or os.environ.get("GROQ_API_KEY")):
            st.warning("No key set — will use deterministic writers.")
    if not use_llm:
        st.caption("AI drafting: off (deterministic writers)")
    
    st.divider()
    run_clicked = st.button("Run analysis", type="primary", use_container_width=True)

# Hero
st.markdown(
    '<div class="gp-hero"><h1>GrowPulse</h1>'
    "<p>Weekly product pulse from app reviews, with a fact-checked fee explainer and a human approval step before anything is published.</p></div>",
    unsafe_allow_html=True,
)

# Run analysis
if run_clicked:
    with st.spinner("Checking data quality, clustering themes, drafting outputs ..."):
        try:
            if uploaded is not None:
                with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as tf:
                    tf.write(uploaded.getvalue())
                    csv_path = tf.name
            else:
                csv_path = str(REPO_ROOT / "data" / "groww_reviews.csv")
            artifacts = run_steps(csv_path, week_ending=st.session_state["week_ending"].isoformat(),
                                  use_llm=use_llm, llm_model=llm_model or None, verbose=False)
            st.session_state["artifacts"] = artifacts
            st.session_state.pop("mcp_outcome", None)
        except SystemExit as exc:
            st.error(f"Pipeline stopped: {exc}")
        except Exception as exc:
            st.exception(exc)

artifacts = st.session_state.get("artifacts")
if not artifacts:
    st.info("Start here: choose **Data source** in the sidebar → click **Run analysis**. Once results are ready, use the pages above to explore Insights, Pulse, Fee Explainer, Approve & Log, History and Checks.")
    st.markdown("### What you'll get")
    c1, c2, c3 = st.columns(3)
    with c1, st.container(border=True):
        st.markdown("**Themes & pain points**")
        st.caption("Pain ranked by 1–2★ volume with 4-week trends and verbatim quotes.")
    with c2, st.container(border=True):
        st.markdown("**Weekly pulse**")
        st.caption("≤250 words with top themes, quotes, key observation and 3 actions.")
    with c3, st.container(border=True):
        st.markdown("**Approval-gated MCP**")
        st.caption("Notes doc + email draft only — never sent, enforced by server-side HMAC tokens.")
    st.stop()

insights = artifacts["insights"]
fee = insights["fee_issue"]
dq = artifacts["dq"]

# KPI row
top = insights["top_themes"][0] if insights["top_themes"] else {"theme": "—"}
c1, c2, c3, c4, c5 = st.columns(5)
c1.markdown(kpi(f"{insights['total_reviews']:,}", "Reviews analysed", "violet"), unsafe_allow_html=True)
c2.markdown(kpi(f"{insights['review_window']['weeks']}w", f"{insights['review_window']['start']} → {insights['review_window']['end']}", "teal"), unsafe_allow_html=True)
c3.markdown(kpi(str(insights["themes_clustered"]), f"themes · top: {top['theme']}", "green"), unsafe_allow_html=True)
c4.markdown(kpi(f"{fee['confusion_mentions']}/{fee['mentions']}", f"confused about {fee['fee'].split(' ')[0].lower()} load", "amber"), unsafe_allow_html=True)
c5.markdown(kpi(f"{artifacts['pulse_wc']}/250", "words in weekly pulse", "teal"), unsafe_allow_html=True)
st.caption(f"Source: `{Path(insights['source_csv']).name}` · quality gate {dq['total_input']:,} → {dq['total_output']:,} clean rows")

# Overview
st.markdown("### Overview")
col1, col2 = st.columns([2, 1], gap="large")
with col1:
    with st.container(border=True):
        st.markdown("**Where the pain is** — ranked by 1-2★ volume")
        pain = sorted(insights["themes"], key=lambda t: (-t.get("lowstar", 0), -t["review_count"]))
        for i, t in enumerate(pain, 1):
            tr = t.get("trend") or {}
            st.markdown(f"**{i}. {t['theme']}**")
            base = f"{t.get('lowstar', 0)} of {t['review_count']} reviews are 1-2★ ({t.get('lowstar_share', 0) * 100:.0f}%)"
            if tr.get("meaningful"):
                arrow = {"worse": "▲", "better": "▼", "flat": "→"}.get(tr["direction"], "→")
                st.caption(f"{base} · last 4w {arrow} {tr['recent_4w']} vs {tr['prev_4w']} before ({tr['delta_pct']:+d}%) — {tr['direction']}")
            else:
                st.caption(f"{base}")
            if i < len(pain):
                st.divider()

with col2:
    with st.container(border=True):
        st.markdown("**Latest run**")
        st.markdown(f"- Week ending: **{artifacts['week_ending']}**")
        st.markdown(f"- Pulse: **{artifacts['pulse_wc']}/250** words")
        st.markdown(f"- Fee focus: **{fee['fee']}** ({fee['confusion_mentions']}/{fee['mentions']} confused)")
        st.markdown(f"- MCP: approval-gated (drafts only, never sent)")
    with st.container(border=True):
        st.markdown("**Quick links**")
        st.page_link("pages/01_Insights.py", label="View all themes & quotes")
        st.page_link("pages/02_Pulse.py", label="Read the weekly pulse")
        st.page_link("pages/03_Fee_Explainer.py", label="See the fee explainer")
        st.page_link("pages/04_Approve.py", label="Approve & publish via MCP")
        st.page_link("pages/05_History.py", label="View run history")
        st.page_link("pages/06_Checks.py", label="Check data quality")
