"""
GrowPulse — Fee Explainer
=========================
Customer-facing fee explainer with checks.
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
    st.warning("💰 No analysis results yet. Please run the analysis from the **Home** page first.")
    st.page_link("views/01_home.py", label="⬅️ Go to Home to run analysis")
    st.stop()

insights = artifacts["insights"]
fee = insights["fee_issue"]
exp = artifacts["explainer"]
exp_md = exp["markdown"]

st.markdown("## 💰 Fee Explainer")
st.caption("Customer-facing support snippet · facts only, no advice · ≤6 bullets, 2 official links, last-checked date")

col_l, col_r = st.columns([4.6, 1.1], vertical_alignment="bottom")
with col_r:
    st.download_button("⬇️ Download .md", exp_md,
                       file_name=f"fee_explainer_{artifacts['week_ending']}.md",
                       mime="text/markdown", use_container_width=True)

st.markdown(
    f'<div class="gp-banner">🔍 Detected from the reviews: <b>{fee["fee"]}</b> — '
    f'{fee["mentions"]} mentions, {fee["confusion_mentions"]} carrying explicit confusion signals '
    f'({fee["confusion_mentions"]/max(fee["mentions"],1):.0%} of mentions). '
    f'Detection score {fee["mention_ranking"][0]["score"]:.1f} '
    f'(mentions × confusion-rate).</div>',
    unsafe_allow_html=True,
)

chip_row([f"📊 {len(exp['bullets'])} / 6 bullets",
          f"🔗 {len(exp['source_links'])} official sources",
          f"📅 Last checked {artifacts['week_ending']}"])

rate = fee["confusion_mentions"] / max(fee["mentions"], 1)
strength = "strong 🟢" if rate >= 0.6 else "moderate 🟡" if rate >= 0.3 else "weak 🔴"
fee_checks = [
    (f"✅ {len(exp['bullets'])} / 6 bullets", 1 <= len(exp["bullets"]) <= 6),
    (f"✅ {len(exp['source_links'])} / 2 official links", len(exp["source_links"]) >= 2),
    ("✅ Last-checked date present", artifacts["week_ending"] in exp_md),
    ("✅ No advice language",
     not re.search(r"we recommend|you should (buy|sell|invest)|guaranteed returns", exp_md, re.I)),
]
chip_row([name for name, _ in fee_checks], {name: ("pass" if ok else "fail") for name, ok in fee_checks})
st.caption(f"Confusion signal: **{strength}** — {rate:.0%} of the {fee['mentions']} fee "
           f"mentions carry explicit confusion language; treat this as the best-supported "
           f"fee guess, not a measured majority. Every bullet is tied to an official "
           f"Groww/AMFI source and is reusable verbatim in tickets and chats.")

with st.container(border=True):
    st.markdown(exp_md)
