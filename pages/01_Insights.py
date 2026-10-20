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
    .stApp { background: radial-gradient(1200px 600px at 80% -10%, #F0F9FF 0%, #F8FAFC 55%, #F8FAFC 100%); }
    .gp-quote { border-left: 3px solid #2563EB; border-radius: 10px; background: #FFFFFF; border: 1px solid #E5E7EB; padding: 12px 14px; min-height: 168px; font-size: .92rem; line-height: 1.5; color: #1F2937; }
    .gp-quote .src { font-size: .76rem; color: #6B7280; margin-top: 10px; }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 12px; border-color: #E5E7EB; }
</style>
""",
    unsafe_allow_html=True,
)

artifacts = st.session_state.get("artifacts")
if not artifacts:
    st.warning("Run analysis from **Home** first.")
    st.page_link("Home.py", label="Go to Home")
    st.stop()

insights = artifacts["insights"]

st.markdown("### Insights")
st.caption(f"{insights['total_reviews']:,} reviews clustered into {insights['themes_clustered']} themes (strongest match wins)")

left, right = st.columns([3, 2], gap="large")
with left, st.container(border=True):
    st.markdown("**Reviews per theme**")
    chart_data = {t["theme"]: t["review_count"] for t in insights["themes"]}
    if insights.get("other_count"):
        chart_data["(unclustered)"] = insights["other_count"]
    st.bar_chart(chart_data, height=320)

with right, st.container(border=True):
    st.markdown("**Where the pain is** — ranked by 1-2★ volume")
    pain = sorted(insights["themes"], key=lambda t: (-t.get("lowstar", 0), -t["review_count"]))
    for i, t in enumerate(pain, 1):
        tr = t.get("trend") or {}
        st.markdown(f"**{i}. {t['theme']}**")
        base = f"{t.get('lowstar', 0)} of {t['review_count']} reviews are 1-2★ ({t.get('lowstar_share', 0) * 100:.0f}%) · avg {t['avg_rating']}★"
        if tr.get("meaningful"):
            arrow = {"worse": "▲", "better": "▼", "flat": "→"}.get(tr["direction"], "→")
            st.caption(f"{base} · last 4w {arrow} {tr['recent_4w']} vs {tr['prev_4w']} before ({tr['delta_pct']:+d}%) — {tr['direction']}")
        else:
            st.caption(f"{base} · trend n/a")
        if i < len(pain):
            st.divider()
    st.caption("Ranked by the number of 1-2 star reviews, not by theme size.")

st.markdown("### Verbatim quotes")
st.caption("Untouched review text — each quote carries its id, source and date.")
qcols = st.columns(3, gap="medium")
for i, q in enumerate(insights["quotes"]):
    with qcols[i % 3]:
        st.markdown(
            f'<div class="gp-quote">“{q["quote"]}”'
            f'<div class="src">— {q["theme"]}<br>{q["source"]}, {q["rating"]}★, {q["date"]}<br>id {q["review_id"]}</div></div>',
            unsafe_allow_html=True,
        )
