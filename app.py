"""
GrowPulse — Streamlit app
=========================
Colorful, user-friendly UI for the full workflow:

    data quality -> review intelligence -> weekly pulse -> fee explainer
    -> APPROVAL-GATED MCP actions (notes doc + email draft, never sent)

Local:   streamlit run app.py            (http://localhost:8501)
Deploy:  Streamlit Community Cloud — set GROQ_API_KEY in App settings -> Secrets.

The CLI (src/workflow.py) and this app import the SAME pipeline, so the UI can
never drift from the code the checks run against.

Navigation uses st.navigation(): the entrypoint is a shared frame, so
st.session_state["artifacts"] survives page switches (unlike raw URL links).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "src"))

# Streamlit Community Cloud: pick up App settings -> Secrets (same KEY=VALUE
# names as .env). Locally, .env (gitignored) or the sidebar paste box applies.
# No secrets file present must never crash the app.
try:
    _secrets = st.secrets.to_dict()
except Exception:
    _secrets = {}
for _k in ("GROQ_API_KEY", "GROQ_MODEL"):
    if _secrets.get(_k):
        os.environ.setdefault(_k, _secrets[_k])

st.set_page_config(page_title="GrowPulse", layout="wide",
                   initial_sidebar_state="expanded")

# ── Shared styling (applies to every page through the frame) ─────────────────
st.markdown(
    """
<style>
    .block-container { padding-top: 1.6rem; padding-bottom: 2.5rem; max-width: 1240px; }
    .stApp { background: radial-gradient(1400px 700px at 10% -20%, #EEF6FF 0%, #F8FAFC 45%, #F7F9FC 100%); }
    header[data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #F8FAFF 0%, #F6F8FB 100%); border-right: 1px solid #E6EBF5; }

    .gp-hero {
        background: linear-gradient(135deg, #FF6B6B 0%, #A06CD5 50%, #4ECDC4 100%);
        border-radius: 18px; padding: 28px 32px; margin: 0 0 20px 0;
        box-shadow: 0 12px 40px -12px rgba(160,108,213,0.5);
    }
    .gp-hero h1 { color: #fff; margin: 0; font-size: 2.2rem; font-weight: 800; letter-spacing: -.5px; text-shadow: 0 2px 8px rgba(0,0,0,0.15); }
    .gp-hero p  { color: #FFF7E6; margin: 10px 0 0 0; font-size: 1.05rem; max-width: 880px; }

    .gp-card {
        border-radius: 14px; padding: 18px 22px; background: #FFFFFF;
        border: 1px solid #E6EBF5; border-top: 4px solid #FF6B6B;
        box-shadow: 0 4px 20px -8px rgba(15,23,42,0.12);
        min-height: 108px; display: flex; flex-direction: column; justify-content: center;
    }
    .gp-card.teal   { border-top-color: #4ECDC4; }
    .gp-card.yellow { border-top-color: #FFE66D; }
    .gp-card.purple { border-top-color: #A06CD5; }
    .gp-card.green  { border-top-color: #22C55E; }
    .gp-card .num   { font-size: 1.9rem; font-weight: 700; color: #0F172A; line-height: 1.15; }
    .gp-card.teal   .num { color: #0D9488; }
    .gp-card.yellow .num { color: #B45309; }
    .gp-card.purple .num { color: #7C3AED; }
    .gp-card.green  .num { color: #16A34A; }
    .gp-card .lbl   { font-size: .85rem; color: #475569; margin-top: 6px; }

    .gp-quote { border-left: 4px solid #4ECDC4; border-radius: 12px; background: #FFFFFF; border: 1px solid #E6EBF5; padding: 16px 18px; min-height: 172px; font-size: .94rem; line-height: 1.55; color: #1F2937; box-shadow: 0 4px 20px -10px rgba(15,23,42,0.12); }
    .gp-quote .src { font-size: .78rem; color: #6B7280; margin-top: 10px; }

    .gp-banner { border-radius: 14px; padding: 16px 20px; margin: 8px 0 16px 0; background: linear-gradient(90deg, rgba(245,158,11,0.14) 0%, rgba(251,191,36,0.10) 100%); border: 1px solid rgba(245,158,11,0.45); font-size: .95rem; color: #92400E; }
    .gp-banner b { color: #92400E; }

    .gp-chip { display: inline-block; padding: 4px 14px; margin: 0 8px 8px 0; border-radius: 999px; background: linear-gradient(90deg, rgba(37,99,235,0.10) 0%, rgba(14,165,233,0.08) 100%); border: 1px solid rgba(37,99,235,0.30); font-size: .8rem; color: #1E3A8A; font-weight: 500; }
    .gp-chip.pass { background: linear-gradient(90deg, rgba(34,197,94,0.12) 0%, rgba(16,185,129,0.08) 100%); border-color: rgba(34,197,94,0.40); color: #166534; }
    .gp-chip.fail { background: linear-gradient(90deg, rgba(239,68,68,0.12) 0%, rgba(220,38,38,0.08) 100%); border-color: rgba(239,68,68,0.40); color: #991B1B; }

    div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px; border-color: #E6EBF5; background: #FFFFFF; box-shadow: 0 4px 20px -10px rgba(15,23,42,0.10); }
    div[data-testid="stTabs"] button[data-baseweb="tab"] { font-weight: 600; }
    div[data-testid="stMetricValue"] { font-size: 1.5rem; color: #0F172A; }
    div[data-testid="stProgress"] div[data-testid="stProgressBar"] > div { background-color: #2563EB; }
    [data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2, [data-testid="stMarkdownContainer"] h3 { color: #0F172A; letter-spacing: -.2px; }
    .stCaption { color: #475569 !important; }
</style>
""",
    unsafe_allow_html=True,
)

# ── Pages ────────────────────────────────────────────────────────────────────
# st.navigation keeps st.session_state alive across page switches. Switching by
# raw URL would create a new session and lose the run artifacts — the bug that
# made Insights/Pulse/... look broken after an analysis.

pages = [
    st.Page("views/01_home.py", title="Home", icon="🏠", default=True),
    st.Page("views/02_insights.py", title="Insights", icon="📊"),
    st.Page("views/03_pulse.py", title="Pulse", icon="📝"),
    st.Page("views/04_fee_explainer.py", title="Fee Explainer", icon="💰"),
    st.Page("views/05_approve.py", title="Approve & Log", icon="🔐"),
    st.Page("views/06_history.py", title="History", icon="📜"),
    st.Page("views/07_checks.py", title="Checks", icon="🧪"),
]

nav = st.navigation(pages, position="sidebar")

# ── Sidebar controls (shared across every page) ──────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Controls")

    st.markdown("**📦 Data source**")
    source = st.radio("Reviews data", ["Sample dataset (1,200 Groww reviews)", "Upload my CSV"],
                      label_visibility="collapsed")
    uploaded = None
    if source == "Upload my CSV":
        uploaded = st.file_uploader("CSV: review_id, date, source, rating, review_text",
                                    type="csv",
                                    help="Extra columns are ignored. Bad rows (blanks, duplicates, "
                                         "bad dates/ratings, unknown sources, too-short text) are "
                                         "dropped and reported in the Checks page.")

    # Streamlit Community Cloud runs in UTC, so date.today() there can be a day
    # behind the user's local date. Prefer IST (the review corpus and audience are
    # India-based) so the "week ending" reads correctly for the team.
    _IST = timezone(timedelta(hours=5, minutes=30))
    _default_end = datetime.now(_IST).date()
    week_ending = st.date_input("📅 Report week ending", value=_default_end, key="week_ending")
    st.caption("Used in the pulse, the fee explainer's “Last checked” and the MCP log date.")

    st.divider()
    with st.expander("🤖 Advanced — AI drafting (optional)", expanded=False):
        st.caption("The deterministic writers are the default. Add a Groq key to let an LLM "
                   "draft the observation, action ideas and explainer bullets — every draft is "
                   "validated against the data and silently falls back if it fails.")
        groq_key = st.text_input("Groq API key", type="password",
                                 help="Kept in memory for this session only. Or set "
                                      "GROQ_API_KEY in .env / Streamlit Secrets.")
        use_llm = st.checkbox("Use Groq for drafting", value=False)
        llm_model = st.text_input("Groq model", value=os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"))
        if groq_key:
            os.environ["GROQ_API_KEY"] = groq_key  # session-only export for llm.py
        if use_llm and not (groq_key or os.environ.get("GROQ_API_KEY")):
            st.warning("No key set — the run will use the deterministic writers.")
    if not use_llm:
        st.caption("AI drafting: **off** (deterministic writers)")

    st.divider()
    run_clicked = st.button("🚀 Run analysis", type="primary", use_container_width=True)

# ── Pipeline run (identical code path as the CLI) ────────────────────────────

if run_clicked:
    import tempfile

    from workflow import run_steps

    with st.spinner("Checking data quality, clustering themes, drafting outputs ..."):
        try:
            if uploaded is not None:
                with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as tf:
                    tf.write(uploaded.getvalue())
                    csv_path = tf.name
            else:
                csv_path = str(REPO_ROOT / "data" / "groww_reviews.csv")
            artifacts = run_steps(csv_path, week_ending=week_ending.isoformat(),
                                  use_llm=use_llm, llm_model=llm_model or None, verbose=False)
            st.session_state["artifacts"] = artifacts
            st.session_state.pop("mcp_outcome", None)
        except SystemExit as exc:
            st.error(f"Pipeline stopped: {exc}")
        except Exception as exc:
            st.exception(exc)

# ── Render the selected page ─────────────────────────────────────────────────

nav.run()
