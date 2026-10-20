"""
GrowPulse — Pulse
=================
Weekly product pulse + live checks.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

st.set_page_config(page_title="GrowPulse - Pulse", layout="wide")
st.markdown(
    """
<style>
    .block-container { padding-top: 1.0rem; padding-bottom: 2rem; max-width: 1200px; }
    .stApp { background: radial-gradient(1200px 600px at 80% -10%, #F0F9FF 0%, #F8FAFC 55%, #F8FAFC 100%); }
    .gp-chip { display: inline-block; padding: 2px 10px; margin: 0 6px 4px 0; border-radius: 999px; background: #F3F4F6; border: 1px solid #E5E7EB; font-size: .76rem; color: #4B5563; }
    div[data-testid="stProgress"] div[data-testid="stProgressBar"] > div { background-color: #2563EB; }
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
    st.page_link("app.py", label="Go to Home")
    st.stop()

insights = artifacts["insights"]
fee = insights["fee_issue"]
pulse_text = artifacts["pulse"]

col_l, col_r = st.columns([4.6, 1.1], vertical_alignment="bottom")
with col_l:
    st.markdown("### Weekly product pulse")
    st.caption("Internal · top themes, verbatim quotes, one key observation, three action ideas · ≤250 words")
with col_r:
    st.download_button("Download .md", pulse_text, file_name=f"weekly_pulse_{artifacts['week_ending']}.md", mime="text/markdown", use_container_width=True)

chip_row([f"Week ending {artifacts['week_ending']}", f"{artifacts['pulse_wc']} / 250 words", f"{insights['total_reviews']:,} reviews", "Audience: product + support"])
st.progress(min(artifacts["pulse_wc"] / 250, 1.0), text=f"{artifacts['pulse_wc']} / 250 words")

# Live checks
quote_hits = sum(1 for q in insights["quotes"] if q["quote"] in pulse_text)
n_actions = len(re.findall(r"(?m)^\d+\.\s", pulse_text))
fee_named = (not fee.get("detected")) or (fee["fee"] in pulse_text)
checks = [
    (f"within 250 words ({artifacts['pulse_wc']}/250)", artifacts["pulse_wc"] <= 250),
    (f"{quote_hits}/{len(insights['quotes'])} quotes verbatim in text", quote_hits == len(insights["quotes"])),
    (f"{n_actions} numbered action ideas", n_actions >= 3),
    ("key observation present", "**Key observation:**" in pulse_text),
    ("detected fee named", fee_named),
]
with st.container(border=True):
    st.markdown(f"**{'All checks passed' if all(ok for _, ok in checks) else 'Some checks failed'}** — counted by code against the rendered text")
    chip_row([f"{'OK' if ok else 'FAIL'} {name}" for name, ok in checks])

with st.container(border=True):
    st.markdown(pulse_text)
