"""
GrowPulse — Insights
====================
Themes ranked by 1-2 star volume with trends, verbatim quotes.
"""
from __future__ import annotations

import streamlit as st

artifacts = st.session_state.get("artifacts")
if not artifacts:
    st.warning("🔍 No analysis results yet. Please run the analysis from the **Home** page first.")
    st.page_link("views/01_home.py", label="⬅️ Go to Home to run analysis")
    st.stop()

insights = artifacts["insights"]
fee = insights["fee_issue"]

st.markdown("## 📊 Insights")
st.caption(f"{insights['total_reviews']:,} reviews clustered into {insights['themes_clustered']} themes · "
           f"pain-ranked by 1-2★ volume with 4-week trends")

left, right = st.columns([3, 2], gap="large")
with left, st.container(border=True):
    st.markdown("**📈 Reviews per theme**")
    chart_data = {t["theme"]: t["review_count"] for t in insights["themes"]}
    if insights.get("other_count"):
        chart_data["(unclustered)"] = insights["other_count"]
    st.bar_chart(chart_data, height=320)
    st.caption("Reviews that match no theme stay unclustered — a bucket that absorbs "
               "everything stops being a signal.")

with right, st.container(border=True):
    st.markdown("**🔥 Where the pain is** — ranked by 1-2★ volume")
    pain = sorted(insights["themes"],
                  key=lambda t: (-t.get("lowstar", 0), -t["review_count"]))
    for i, t in enumerate(pain, 1):
        tr = t.get("trend") or {}
        st.markdown(f"**{i}. {t['theme']}**")
        base = (f"{t.get('lowstar', 0)} of {t['review_count']} reviews are 1-2★ "
                f"({t.get('lowstar_share', 0) * 100:.0f}%)")
        if tr.get("meaningful"):
            arrow = {"worse": "🔴 ▲", "better": "🟢 ▼", "flat": "🟡 →"}.get(tr["direction"], "→")
            st.caption(f"{base} · last 4w {arrow} {tr['recent_4w']} vs {tr['prev_4w']} before "
                       f"({tr['delta_pct']:+d}%) — {tr['direction']}")
        else:
            st.caption(f"{base} · trend n/a (needs an 8+ week window)")
        if i < len(pain):
            st.divider()
    st.caption("Ranked by the number of 1-2 star reviews, not by theme size — a big happy "
               "theme outranks nothing here. Trend compares the last 4 weeks with the 4 before.")

st.markdown("### 💬 Verbatim quotes")
st.caption("Untouched review text — each quote carries its id, source and date.")
qcols = st.columns(3, gap="medium")
for i, q in enumerate(insights["quotes"]):
    with qcols[i % 3]:
        st.markdown(
            f'<div class="gp-quote">“{q["quote"]}”'
            f'<div class="src">— {q["theme"]}<br>{q["source"]}, {q["rating"]}★, '
            f'{q["date"]}<br>id {q["review_id"]}</div></div>',
            unsafe_allow_html=True,
        )
