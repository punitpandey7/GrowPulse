"""
GrowPulse — Streamlit app 🚀
============================
Colorful, public-friendly web UI for the whole workflow:

    data quality -> review intelligence -> weekly pulse -> fee explainer
    -> APPROVAL-GATED MCP actions (notes doc + email draft, never sent)

Local:      streamlit run app.py            (http://localhost:8501)
Deploy:     Streamlit Community Cloud (set GROQ_API_KEY in Secrets, see README)

The CLI (src/workflow.py) and this app import the SAME pipeline, so the UI can
never drift from the code the checks run against.
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

from workflow import run_steps          # noqa: E402
from mcp_client import run_mcp_actions  # noqa: E402

st.set_page_config(page_title="GrowPulse 💹", page_icon="📈", layout="wide")

# ----------------------------------------------------------------------------------
# Colorful theme (works on light & dark backgrounds)
# ----------------------------------------------------------------------------------

st.markdown(
    """
<style>
    .gp-hero {
        background: linear-gradient(120deg, #FF6B6B 0%, #A06CD5 55%, #4ECDC4 100%);
        border-radius: 18px; padding: 26px 30px; margin-bottom: 10px;
    }
    .gp-hero h1 { color: white; margin: 0; font-size: 2.1rem; }
    .gp-hero p  { color: #FFF7E6; margin: 6px 0 0 0; font-size: 1.02rem; }
    .gp-card {
        border-radius: 14px; padding: 16px 18px; background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.12); border-top: 4px solid #FF6B6B;
        margin-bottom: 8px;
    }
    .gp-card.teal   { border-top-color: #4ECDC4; }
    .gp-card.yellow { border-top-color: #FFE66D; }
    .gp-card.purple { border-top-color: #A06CD5; }
    .gp-card .num   { font-size: 1.9rem; font-weight: 700; color: #FF6B6B; }
    .gp-card.teal   .num { color: #4ECDC4; }
    .gp-card.yellow .num { color: #FFE66D; }
    .gp-card.purple .num { color: #C9A8FF; }
    .gp-card .lbl   { font-size: 0.86rem; opacity: 0.85; }
    .gp-quote {
        border-left: 4px solid #4ECDC4; border-radius: 8px;
        background: rgba(78,205,196,0.08); padding: 10px 14px; margin: 6px 0;
    }
    .gp-quote.coral { border-left-color: #FF6B6B; background: rgba(255,107,107,0.08); }
    .gp-quote.gold  { border-left-color: #FFE66D; background: rgba(255,230,109,0.08); }
    .gp-quote .src  { font-size: 0.8rem; opacity: 0.75; }
    .gp-ok    { color: #4ECDC4; font-weight: 600; }
    .gp-bad   { color: #FF6B6B; font-weight: 600; }
    div[data-testid="stMetricValue"] { font-size: 1.55rem; }
</style>
    """,
    unsafe_allow_html=True,
)


def kpi(num: str, label: str, color: str = "") -> str:
    return f'<div class="gp-card {color}"><div class="num">{num}</div><div class="lbl">{label}</div></div>'


# ----------------------------------------------------------------------------------
# Sidebar — controls
# ----------------------------------------------------------------------------------

with st.sidebar:
    st.markdown("## ⚙️ Controls")
    source = st.radio("Reviews data", ["📦 Sample dataset (Groww)", "📁 Upload my CSV"], horizontal=False)
    uploaded = None
    if source.startswith("📁"):
        uploaded = st.file_uploader("CSV with review_id,date,source,rating,review_text",
                                    type="csv")
    week_ending = st.date_input("Week ending", value=date.today())

    st.markdown("---")
    st.markdown("### 🤖 AI drafting (optional)")
    groq_key = st.text_input("Groq API key", type="password",
                             help="From your GROQ_API_KEY (kept in memory for this tab only). "
                                  "Leave empty to use the deterministic writers.")
    use_llm = st.checkbox("Use Groq to draft observation/actions/bullets", value=False)
    llm_model = st.text_input("Groq model", value=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"))
    if groq_key:
        os.environ["GROQ_API_KEY"] = groq_key  # session-only export for llm.py

    run_clicked = st.button("🚀  Run analysis", type="primary", use_container_width=True)

# ----------------------------------------------------------------------------------
# Hero
# ----------------------------------------------------------------------------------

st.markdown(
    '<div class="gp-hero"><h1>📈 GrowPulse</h1>'
    "<p>Where Groww reviews go critical — raw public reviews in, weekly product pulse + "
    "fee clarification out. Nothing leaves the building without a human approval. ⚛️</p></div>",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------------
# Run the pipeline (identical code path as the CLI)
# ----------------------------------------------------------------------------------

if run_clicked:
    with st.spinner("Reading reviews, checking data quality, clustering themes, drafting outputs ..."):
        try:
            if uploaded is not None:
                with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as tf:
                    tf.write(uploaded.getvalue().decode("utf-8"))
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

artifacts = st.session_state.get("artifacts")
if not artifacts:
    st.info("👈 Set your options and hit **Run analysis** to turn reviews into a product pulse.")
    st.stop()

insights = artifacts["insights"]
fee = insights["fee_issue"]
dq = artifacts["dq"]

# ----------------------------------------------------------------------------------
# KPI row
# ----------------------------------------------------------------------------------

top = insights["top_themes"][0]
c1, c2, c3, c4, c5 = st.columns(5)
c1.markdown(kpi(str(insights["total_reviews"]), "Reviews analysed (clean)"), unsafe_allow_html=True)
c2.markdown(kpi(f"{insights['review_window']['weeks']}w", f"{insights['review_window']['start']} → {insights['review_window']['end']}", "teal"), unsafe_allow_html=True)
c3.markdown(kpi(str(insights["themes_clustered"]), f"themes · top: {top['theme'].split(' ')[0]}…", "purple"), unsafe_allow_html=True)
c4.markdown(kpi(f"{fee['confusion_mentions']}/{fee['mentions']}", f"confused about {fee['fee'].split(' ')[0].lower()}…", "yellow"), unsafe_allow_html=True)
c5.markdown(kpi(f"{artifacts['pulse_wc']}/250", "pulse words", "teal"), unsafe_allow_html=True)

tab_themes, tab_pulse, tab_fee, tab_gate, tab_dq = st.tabs(
    ["📊 Themes & Quotes", "📝 Weekly Pulse", "💰 Fee Explainer", "🔐 Approve & Log", "🧪 Data Quality"]
)

# ----------------------------------------------------------------------------------
# Tab 1 — themes & quotes
# ----------------------------------------------------------------------------------

with tab_themes:
    left, right = st.columns([3, 2])
    with left:
        st.markdown("### Theme clustering (max 5, strongest match wins)")
        chart_data = {t["theme"]: t["review_count"] for t in insights["themes"]}
        if insights.get("other_count"):
            chart_data["(unclustered)"] = insights["other_count"]
        st.bar_chart(chart_data, height=320)
        st.caption(f"{insights['other_count']} reviews match no theme and stay unclustered — "
                   "a bucket that absorbs everything stops meaning anything.")
    with right:
        st.markdown("### Top 3 themes")
        for i, t in enumerate(insights["top_themes"], 1):
            st.markdown(
                f"**{i}. {t['theme']}** — {t['review_count']} reviews · "
                f"{t['share']*100:.0f}% · avg {t['avg_rating']}★")
    st.markdown("### 🗣️ Three verbatim quotes")
    colors = ["coral", "", "gold"]
    for i, q in enumerate(insights["quotes"]):
        cls = colors[i % 3]
        st.markdown(
            f'<div class="gp-quote {cls}">“{q["quote"]}”'
            f'<div class="src">— {q["theme"]} · {q["source"]}, {q["rating"]}★, {q["date"]} ({q["review_id"]})</div></div>',
            unsafe_allow_html=True,
        )

# ----------------------------------------------------------------------------------
# Tab 2 — weekly pulse
# ----------------------------------------------------------------------------------

with tab_pulse:
    st.markdown("### 📝 Weekly Product Pulse (internal, ≤250 words)")
    pct = min(artifacts["pulse_wc"] / 250, 1.0)
    st.progress(pct, text=f"{artifacts['pulse_wc']} / 250 words")
    st.markdown(artifacts["pulse"])
    st.download_button("⬇️ Download pulse (.md)", artifacts["pulse"],
                       file_name=f"weekly_pulse_{artifacts['week_ending']}.md", mime="text/markdown")

# ----------------------------------------------------------------------------------
# Tab 3 — fee explainer
# ----------------------------------------------------------------------------------

with tab_fee:
    st.markdown("### 💰 Fee explainer — reusable support snippet")
    st.info(f"Detected from reviews: **{fee['fee']}** — {fee['mentions']} mentions, "
            f"{fee['confusion_mentions']} with explicit confusion signals "
            f"({fee['confusion_mentions']/max(fee['mentions'],1):.0%} of mentions), score "
            f"{fee['mention_ranking'][0]['score']:.1f} (mentions × confusion-rate).")
    st.markdown(artifacts["explainer"]["markdown"])
    st.download_button("⬇️ Download explainer (.md)", artifacts["explainer"]["markdown"],
                       file_name=f"fee_explainer_{artifacts['week_ending']}.md", mime="text/markdown")

# ----------------------------------------------------------------------------------
# Tab 4 — approval gate + MCP
# ----------------------------------------------------------------------------------

with tab_gate:
    st.markdown("### 🔐 MCP approval gate")
    st.caption("The MCP server enforces the gate itself: a tool call without a single-use "
               "HMAC approval token returns a preview and writes nothing. Approving executes "
               "each tool EXACTLY ONCE. Email is drafted, never sent.")

    payload = artifacts["payload"]
    p1, p2 = st.columns(2)
    with p1:
        st.markdown("#### Tool 1 · `append_to_product_notes`")
        a = payload["arguments"]["append_to_product_notes"]
        st.code(f"date: {a['date']}\n"
                + "top_themes: " + ", ".join(f"{t['theme']} ({t['review_count']})" for t in a["top_themes"])
                + f"\nweekly_pulse: {len(a['weekly_pulse'].split())} words"
                + f"\nidentified_fee_issue: {a['identified_fee_issue']['fee']} "
                f"({a['identified_fee_issue']['mentions']} mentions)"
                + f"\nexplanation_bullets: {len(a['explanation_bullets'])}"
                + f"\nsource_links: {len(a['source_links'])}", language="text")
    with p2:
        st.markdown("#### Tool 2 · `create_email_draft` (never sends)")
        b = payload["arguments"]["create_email_draft"]
        st.code(f"to: {b['to']}\nsubject: {b['subject']}\nbody: {len(b['body'].split())} words "
                f"(pulse + support snippet)", language="text")

    outcome = st.session_state.get("mcp_outcome")
    b1, b2 = st.columns(2)
    approve = b1.button("✅  Approve & execute via MCP", type="primary",
                        disabled=outcome is not None, use_container_width=True)
    reject = b2.button("❌  Reject (nothing is written)", disabled=outcome is not None,
                       use_container_width=True)

    if approve or reject:
        with st.spinner("Talking to the MCP server ..." if approve else "Recording rejection ..."):
            outcome = run_mcp_actions(payload, decision="approve" if approve else "reject",
                                      verbose=False, prove_gate=approve)
            st.session_state["mcp_outcome"] = outcome

    if outcome is not None:
        if outcome["approved"]:
            st.success("✅ Approved — both tools executed exactly once. See the live transcript below.")
            for r in outcome["results"]:
                st.markdown(f"**{r['tool']}** → {r['result']}")
            d1, d2 = st.columns(2)
            notes = (REPO_ROOT / "product_pulse" / "product_notes.md").read_text(encoding="utf-8")
            with d1:
                st.markdown("#### 📄 Notes doc (last appended entry)")
                st.code(notes[-2200:], language="markdown")
            with d2:
                st.markdown("#### ✉️ Email draft created (NOT sent)")
                drafts = sorted((REPO_ROOT / "output" / "drafts").glob("*.md"))
                if drafts:
                    st.code(drafts[-1].read_text(encoding="utf-8")[:2600], language="markdown")
        else:
            st.error("❌ Rejected — no MCP tool was executed, nothing was written anywhere.")

        st.markdown("#### 🧾 Live MCP transcript")
        for line in outcome["transcript"]:
            arrow = "🟢" if line["dir"] == "→" else "🔵"
            detail = f" — {line['detail']}" if line.get("detail") else ""
            st.markdown(f"`{arrow} {line['dir']} {line['kind']}` **{line['tool']}** → `{line['status']}`{detail}")

# ----------------------------------------------------------------------------------
# Tab 5 — data quality & logs
# ----------------------------------------------------------------------------------

with tab_dq:
    st.markdown("### 🧪 Data quality gate (Step 0, runs before every analysis)")
    checks = [
        ("Rows in → clean rows out", f"{dq['total_input']} → {dq['total_output']}", dq["total_output"] == dq["total_input"]),
        ("Blank required fields dropped", str(dq["blank_dropped"]), dq["blank_dropped"] == 0),
        ("Duplicate review_id dropped", str(dq["duplicate_id_dropped"]), dq["duplicate_id_dropped"] == 0),
        ("Duplicate content dropped", str(dq["duplicate_text_dropped"]), dq["duplicate_text_dropped"] == 0),
        ("Bad dates dropped", str(dq["bad_date_dropped"]), dq["bad_date_dropped"] == 0),
        ("Invalid ratings dropped", str(dq["bad_rating_dropped"]), dq["bad_rating_dropped"] == 0),
        ("Unknown sources dropped", str(dq["unknown_source_dropped"]), dq["unknown_source_dropped"] == 0),
        ("Too-short text dropped", str(dq["short_text_dropped"]), dq["short_text_dropped"] == 0),
        ("Encoding artifacts flagged", str(dq["encoding_flagged"]), dq["encoding_flagged"] == 0),
    ]
    for name, val, ok in checks:
        icon = "✅" if ok else "❌"
        st.markdown(f"{icon} **{name}** — `{val}`")
    st.caption(f"Window {dq['date_min']} → {dq['date_max']} (~{dq['weeks_spanned']} weeks) · "
               f"ratings {dq['rating_distribution']} · sources {dq['source_distribution']}")

    if artifacts["llm_log"]:
        st.markdown("### 🤖 AI drafting log")
        for l in artifacts["llm_log"]:
            st.markdown(f"- {l}")

    audit = REPO_ROOT / "output" / "mcp_audit_log.jsonl"
    if audit.exists():
        st.markdown("### 🧾 MCP server audit log")
        st.code(audit.read_text(encoding="utf-8")[-2000:], language="json")

st.markdown("---")
st.caption("GrowPulse · approval-gated MCP · draft-only email · deterministic core with optional "
           "Groq AI drafting · not affiliated with or endorsed by Groww. Nothing here is investment advice.")
