"""
GrowPulse — Fee Explainer
=========================
Customer-facing fee explainer with checks.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

st.set_page_config(page_title="GrowPulse - Fee Explainer", layout="wide")
st.markdown(
    """
<style>
    .block-container { padding-top: 1.0rem; padding-bottom: 2rem; max-width: 1200px; }
    .stApp { background: radial-gradient(1200px 600px at 80% -10%, #F0F9FF 0%, #F8FAFC 55%, #F8FAFC 100%); }
    .gp-banner { border-radius: 12px; padding: 13px 16px; margin: 4px 0 10px 0; background: linear-gradient(90deg, rgba(245,158,11,0.12) 0%, rgba(251,191,36,0.08) 100%); border: 1px solid rgba(245,158,11,0.45); font-size: .93rem; color: #92400E; }
    .gp-banner b { color: #92400E; }
    .gp-chip { display: inline-block; padding: 2px 10px; margin: 0 6px 4px 0; border-radius: 999px; background: #F3F4F6; border: 1px solid #E5E7EB; font-size: .76rem; color: #4B5563; }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 12px; border-color: #E5E7EB; }
</style>
""",
    unsafe_allow_html=True,
)


def chip_row(items: list[str]) -> None:
    st.markdown("".join(f'<span class="gp-chip">{i}</span>' for i in items), unsafe_allow_html=True)


artifacts = st.session_state.get("artifacts")
if not artifacts:
    st.warning("Run analysis from **Home** first.")
    st.page_link("Home.py", label="Go to Home")
    st.stop()

insights = artifacts["insights"]
fee = insights["fee_issue"]
exp = artifacts["explainer"]
exp_md = exp["markdown"]

col_l, col_r = st.columns([4.6, 1.1], vertical_alignment="bottom")
with col_l:
    st.markdown("### Fee explainer")
    st.caption("Customer-facing support snippet · facts only, no advice · ≤6 bullets, 2 official links, last-checked date")
with col_r:
    st.download_button("Download .md", exp_md, file_name=f"fee_explainer_{artifacts['week_ending']}.md", mime="text/markdown", use_container_width=True)

st.markdown(
    f'<div class="gp-banner">Detected from the reviews: <b>{fee["fee"]}</b> — '
    f'{fee["mentions"]} mentions, {fee["confusion_mentions"]} carrying explicit confusion signals '
    f'({fee["confusion_mentions"]/max(fee["mentions"],1):.0%} of mentions). Detection score {fee["mention_ranking"][0]["score"]:.1f}.</div>',
    unsafe_allow_html=True,
)

rate = fee["confusion_mentions"] / max(fee["mentions"], 1)
strength = "strong" if rate >= 0.6 else "moderate" if rate >= 0.3 else "weak"
fee_checks = [
    (f"{len(exp['bullets'])} / 6 bullets", 1 <= len(exp["bullets"]) <= 6),
    (f"{len(exp['source_links'])} / 2 official links", len(exp["source_links"]) >= 2),
    ("last-checked date present", artifacts["week_ending"] in exp_md),
    ("no advice language", not re.search(r"we recommend|you should (buy|sell|invest)|guaranteed returns", exp_md, re.I)),
]
chip_row([f"{'OK' if ok else 'FAIL'} {name}" for name, ok in fee_checks])
st.caption(f"Confusion signal: **{strength}** — {rate:.0%} of mentions carry explicit confusion language. Facts only, tied to official sources.")

with st.container(border=True):
    st.markdown(exp_md)
