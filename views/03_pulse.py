"""
GrowPulse — Pulse
=================
Weekly product pulse + live checks.
"""
from __future__ import annotations

import re

import streamlit as st


def chip_row(items: list[str], cls_map: dict | None = None) -> None:
    html = ""
    for item in items:
        cls = "gp-chip"
        if cls_map and item in cls_map:
            cls += " " + cls_map[item]
        html += f'<span class="{cls}">{item}</span>'
    st.markdown(html, unsafe_allow_html=True)


artifacts = st.session_state.get("artifacts")
if not artifacts:
    st.warning("📝 No analysis results yet. Please run the analysis from the **Home** page first.")
    st.page_link("views/01_home.py", label="⬅️ Go to Home to run analysis")
    st.stop()

insights = artifacts["insights"]
fee = insights["fee_issue"]
pulse_text = artifacts["pulse"]

st.markdown("## 📝 Weekly Product Pulse")
st.caption("Internal · top themes, verbatim quotes, one key observation, three action ideas · ≤250 words")

col_l, col_r = st.columns([4.6, 1.1], vertical_alignment="bottom")
with col_r:
    st.download_button("⬇️ Download .md", pulse_text,
                       file_name=f"weekly_pulse_{artifacts['week_ending']}.md",
                       mime="text/markdown", use_container_width=True)

chip_row([f"📅 Week ending {artifacts['week_ending']}",
          f"📊 {artifacts['pulse_wc']} / 250 words",
          f"🔍 {insights['total_reviews']:,} reviews",
          "👥 Audience: product + support"])
st.progress(min(artifacts["pulse_wc"] / 250, 1.0), text=f"📊 {artifacts['pulse_wc']} / 250 words")

# Live checks — every constraint verified by code against the actual text
quote_hits = sum(1 for q in insights["quotes"] if q["quote"] in pulse_text)
n_actions = len(re.findall(r"(?m)^\d+\.\s", pulse_text))
fee_named = (not fee.get("detected")) or (fee["fee"] in pulse_text)
checks = [
    (f"✅ Within 250 words ({artifacts['pulse_wc']}/250)", artifacts["pulse_wc"] <= 250),
    (f"✅ {quote_hits}/{len(insights['quotes'])} quotes verbatim in text", quote_hits == len(insights["quotes"])),
    (f"✅ {n_actions} numbered action ideas", n_actions >= 3),
    ("✅ Key observation present", "**Key observation:**" in pulse_text),
    ("✅ Detected fee named", fee_named),
]
all_pass = all(ok for _, ok in checks)
with st.container(border=True):
    st.markdown(f"**{'✅ All checks passed' if all_pass else '❌ Some checks failed'}** "
                "— counted by code against the rendered text")
    chip_row([name for name, _ in checks], {name: ("pass" if ok else "fail") for name, ok in checks})
    if not all_pass:
        st.error("One or more checks failed — fix before shipping this pulse.")

with st.container(border=True):
    st.markdown(pulse_text)
