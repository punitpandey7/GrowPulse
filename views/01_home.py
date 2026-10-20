"""
GrowPulse — Home
================
Welcome, KPI overview and quick links. Rendered inside the app frame (app.py).
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent


def kpi(num: str, label: str, color: str = "") -> str:
    cls = f"gp-card {color}" if color else "gp-card"
    return f'<div class="{cls}"><div class="num">{num}</div><div class="lbl">{label}</div></div>'


st.markdown(
    '<div class="gp-hero"><h1>📈 GrowPulse</h1>'
    "<p>Raw Groww reviews in — weekly product pulse, fee clarification and an "
    "approval-gated MCP log out. Nothing is written without a human sign-off.</p></div>",
    unsafe_allow_html=True,
)

artifacts = st.session_state.get("artifacts")
if not artifacts:
    st.info("👈 Choose a data source and hit **Run analysis** in the sidebar. "
            "The sample corpus is already included.")
    st.markdown("### 🧭 What's inside")
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        st.markdown("""
- **📊 Insights** — themes ranked by 1-2★ pain, 4-week trends, verbatim quotes
- **📝 Pulse** — ≤250-word weekly note, every constraint checked live
- **💰 Fee Explainer** — ≤6 bullets, 2 official links, “Last checked” date
        """)
    with c2:
        st.markdown("""
- **🔐 Approve & Log** — approval-gated MCP write (notes doc + email draft, never sent)
- **📜 History** — recorded decisions and the server's append-only audit log
- **🧪 Checks** — data-quality gate, distributions, AI drafting log
        """)
    st.stop()

insights = artifacts["insights"]
fee = insights["fee_issue"]
dq = artifacts["dq"]

top = insights["top_themes"][0] if insights["top_themes"] else {"theme": "—"}
c1, c2, c3, c4, c5 = st.columns(5)
c1.markdown(kpi(f"{insights['total_reviews']:,}", "Clean reviews analysed", "purple"), unsafe_allow_html=True)
c2.markdown(kpi(f"{insights['review_window']['weeks']}w",
                f"{insights['review_window']['start']} → {insights['review_window']['end']}", "teal"),
            unsafe_allow_html=True)
c3.markdown(kpi(str(insights["themes_clustered"]), f"themes · top: {top['theme']}", "green"),
            unsafe_allow_html=True)
c4.markdown(kpi(f"{fee['confusion_mentions']}/{fee['mentions']}",
                f"confused about {fee['fee'].split(' ')[0].lower()} load", "yellow"), unsafe_allow_html=True)
c5.markdown(kpi(f"{artifacts['pulse_wc']}/250", "words in weekly pulse", "teal"),
            unsafe_allow_html=True)
st.caption(f"Source: `{Path(insights['source_csv']).name}` · quality gate "
           f"{dq['total_input']:,} → {dq['total_output']:,} clean rows")

st.markdown("### 🧭 Explore the results")
qc1, qc2, qc3 = st.columns(3, gap="medium")
qc4, qc5, qc6 = st.columns(3, gap="medium")

links = [
    (qc1, "📊 Insights", "Themes ranked by pain · trends · verbatim quotes", "views/02_insights.py"),
    (qc2, "📝 Weekly Pulse", "≤250-word internal note with live checks", "views/03_pulse.py"),
    (qc3, "💰 Fee Explainer", "≤6 bullets · 2 official links · last-checked date", "views/04_fee_explainer.py"),
    (qc4, "🔐 Approve & Log", "Approval-gated MCP write · draft-only email", "views/05_approve.py"),
    (qc5, "📜 History", "Recorded decisions · server audit log", "views/06_history.py"),
    (qc6, "🧪 Checks", "Data quality gate · distributions · AI log", "views/07_checks.py"),
]
for col, title, desc, path in links:
    with col:
        st.page_link(path, label=title)
        st.caption(desc)

st.markdown("### 📌 Overview")
st.markdown(
    f'<span class="gp-chip">📅 Week ending {artifacts["week_ending"]}</span>'
    f'<span class="gp-chip">⭐ {insights["themes_clustered"]} themes clustered</span>'
    f'<span class="gp-chip">🔍 {fee["mentions"]} fee mentions</span>'
    f'<span class="gp-chip">💬 {fee["confusion_mentions"]} confusion signals</span>'
    f'<span class="gp-chip">📊 {dq["total_output"]:,} clean rows</span>',
    unsafe_allow_html=True,
)

st.divider()
st.caption("GrowPulse · approval-gated MCP · draft-only email · deterministic core with optional "
           "Groq drafting · not affiliated with or endorsed by Groww · nothing here is investment advice.")
