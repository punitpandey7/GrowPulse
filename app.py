"""
GrowPulse — Streamlit app
=========================
Colorful, public-friendly UI for the full workflow:

    data quality -> review intelligence -> weekly pulse -> fee explainer
    -> APPROVAL-GATED MCP actions (notes doc + email draft, never sent)

Local:   streamlit run app.py            (http://localhost:8501)
Deploy:  Streamlit Community Cloud — set GROQ_API_KEY in App settings -> Secrets.

The CLI (src/workflow.py) and this app import the SAME pipeline, so the UI can
never drift from the code the checks run against.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from datetime import date
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

from workflow import run_steps            # noqa: E402
from mcp_client import run_mcp_actions, check_connection  # noqa: E402

st.set_page_config(page_title="GrowPulse", layout="wide",
                   initial_sidebar_state="expanded")

# ----------------------------------------------------------------------------------
# Styling — colorful, but aligned: all cards share height, panels share borders
# ----------------------------------------------------------------------------------

st.markdown(
    """
<style>
    /* clean light canvas — set in .streamlit/config.toml, reinforced here */
    .block-container { padding-top: 1.1rem; padding-bottom: 2rem; max-width: 1180px; }
    .stApp { background-color: #FFFFFF; }
    header[data-testid="stHeader"] { background: transparent; }

    /* clean light canvas with soft tint */
    .block-container { padding-top: 1.0rem; padding-bottom: 2rem; max-width: 1200px; }
    .stApp { background: radial-gradient(1200px 600px at 80% -10%, #F0F9FF 0%, #F8FAFC 55%, #F8FAFC 100%); }
    header[data-testid="stHeader"] { background: transparent; }

    /* hero: subtle pill with accent */
    .gp-hero {
        background: linear-gradient(90deg, rgba(37,99,235,0.10) 0%, rgba(14,165,233,0.06) 100%);
        border: 1px solid rgba(37,99,235,0.28); border-radius: 14px;
        padding: 18px 24px; margin: 0 0 14px 0;
    }
    .gp-hero h1 { color: #0F172A; margin: 0; font-size: 1.95rem; font-weight: 700; letter-spacing: -.3px; }
    .gp-hero p  { color: #475569; margin: 6px 0 0 0; font-size: .97rem; max-width: 820px; }

    /* KPI cards: colorful, consistent height */
    .gp-card {
        border-radius: 12px; padding: 14px 18px; background: #FFFFFF;
        border: 1px solid #E5E7EB; border-top: 3px solid #2563EB;
        box-shadow: 0 1px 1px rgba(15,23,42,0.01), 0 1px 2px rgba(15,23,42,0.02);
        min-height: 100px; display: flex; flex-direction: column; justify-content: center;
    }
    .gp-card.teal   { border-top-color: #0EA5E9; }
    .gp-card.green  { border-top-color: #22C55E; }
    .gp-card.amber  { border-top-color: #F59E0B; }
    .gp-card.violet { border-top-color: #8B5CF6; }
    .gp-card .num   { font-size: 1.7rem; font-weight: 700; color: #0F172A; line-height: 1.15; }
    .gp-card .lbl   { font-size: .82rem; color: #475569; margin-top: 4px; }

    .gp-quote {
        border-left: 3px solid #0D9488; border-radius: 10px;
        background: #FFFFFF; border-top: 1px solid #E6E9ED;
        border-right: 1px solid #E6E9ED; border-bottom: 1px solid #E6E9ED;
        padding: 12px 14px; min-height: 168px; font-size: .92rem; line-height: 1.5;
        color: #1F2937;
    }
    .gp-quote .src  { font-size: .76rem; color: #6B7280; margin-top: 10px; }

    .gp-banner {
        border-radius: 10px; padding: 13px 16px; margin: 4px 0 10px 0;
        background: #F7F8FA; border: 1px solid #E6E9ED; border-left: 3px solid #0D9488;
        font-size: .93rem; color: #374151;
    }
    .gp-banner b { color: #0B7A70; }

    .gp-chip {
        display: inline-block; padding: 2px 10px; margin: 0 6px 4px 0; border-radius: 999px;
        background: #F3F4F6; border: 1px solid #E5E7EB; font-size: .76rem; color: #4B5563;
    }

    /* Streamlit internals: soft borders, dark metric values */
    div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 10px; border-color: #E6E9ED; }
    div[data-testid="stMetricValue"] { font-size: 1.45rem; color: #101418; }
    div[data-testid="stProgress"] div[data-testid="stProgressBar"] > div { background-color: #0D9488; }

    h3 { margin-bottom: .15rem; }
</style>
    """,
    unsafe_allow_html=True,
)


def kpi(num: str, label: str, color: str = "") -> str:
    cls = "gp-card " + color if color else "gp-card"
    return f'<div class="{cls}"><div class="num">{num}</div><div class="lbl">{label}</div></div>'


def tab_header(title: str, subtitle: str, download: tuple | None = None) -> None:
    """Same header pattern on every tab: title + caption left, action right."""
    left, right = st.columns([4.6, 1.1], vertical_alignment="bottom")
    with left:
        st.markdown(f"### {title}")
        st.caption(subtitle)
    with right:
        if download:
            label, data, filename = download
            st.download_button(label, data, file_name=filename, mime="text/markdown",
                               use_container_width=True)


def chip_row(items: list[str]) -> None:
    st.markdown("".join(f'<span class="gp-chip">{i}</span>' for i in items), unsafe_allow_html=True)


# ----------------------------------------------------------------------------------
# Sidebar — data source first, advanced/AI tucked away (deterministic is the default)
# ----------------------------------------------------------------------------------

with st.sidebar:
    st.markdown("Controls")

    st.markdown("**Data source**")
    source = st.radio("Reviews data", ["Sample dataset (1,200 Groww reviews)", "Upload my CSV"],
                      label_visibility="collapsed")
    uploaded = None
    if source == "Upload my CSV":
        uploaded = st.file_uploader("CSV: review_id, date, source, rating, review_text",
                                    type="csv",
                                    help="Extra columns are ignored. Bad rows (blanks, duplicates, "
                                         "bad dates/ratings, unknown sources, too-short text) are "
                                         "dropped and reported in the Data Quality tab.")
    st.date_input("Report week ending", value=date.today(), key="week_ending")

    st.divider()
    with st.expander("Advanced — AI drafting (optional)", expanded=False):
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
    run_clicked = st.button("Run analysis", type="primary", use_container_width=True)

# ----------------------------------------------------------------------------------
# Hero
# ----------------------------------------------------------------------------------

st.markdown(
    '<div class="gp-hero"><h1>GrowPulse</h1>'
    "<p>Raw Groww reviews in — weekly product pulse, fee clarification and an "
    "approval-gated MCP log out. Nothing is written without a human sign-off.</p></div>",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------------
# Pipeline run (identical code path as the CLI)
# ----------------------------------------------------------------------------------

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
    st.info("Choose a data source and hit **Run analysis**. The sample corpus is already included.")
    st.stop()

insights = artifacts["insights"]
fee = insights["fee_issue"]
dq = artifacts["dq"]

# ----------------------------------------------------------------------------------
# KPI row
# ----------------------------------------------------------------------------------

top = insights["top_themes"][0] if insights["top_themes"] else {"theme": "—"}
c1, c2, c3, c4, c5 = st.columns(5)
c1.markdown(kpi(f"{insights['total_reviews']:,}", "Clean reviews analysed", "violet"), unsafe_allow_html=True)
c2.markdown(kpi(f"{insights['review_window']['weeks']}w",
                f"{insights['review_window']['start']} → {insights['review_window']['end']}", "teal"),
            unsafe_allow_html=True)
c3.markdown(kpi(str(insights["themes_clustered"]), f"themes · top: {top['theme']}", "green"),
            unsafe_allow_html=True)
c4.markdown(kpi(f"{fee['confusion_mentions']}/{fee['mentions']}",
                f"confused about {fee['fee'].split(' ')[0].lower()} load", "amber"), unsafe_allow_html=True)
c5.markdown(kpi(f"{artifacts['pulse_wc']}/250", "words in the weekly pulse", "teal"),
            unsafe_allow_html=True)
st.caption(f"Source: `{Path(insights['source_csv']).name}` · quality gate "
           f"{dq['total_input']:,} → {dq['total_output']:,} clean rows")

tab_themes, tab_pulse, tab_fee, tab_gate, tab_dq = st.tabs(
    ["Themes & Quotes", "Weekly Pulse", "Fee Explainer", "Approve & Log", "Data Quality"]
)

# ----------------------------------------------------------------------------------
# Tab 1 — themes & quotes
# ----------------------------------------------------------------------------------

with tab_themes:
    tab_header("Theme breakdown", f"{insights['total_reviews']:,} reviews clustered into "
                                  f"{insights['themes_clustered']} themes (strongest match wins)")
    left, right = st.columns([3, 2], gap="large")
    with left, st.container(border=True):
        st.markdown("**Reviews per theme**")
        chart_data = {t["theme"]: t["review_count"] for t in insights["themes"]}
        if insights.get("other_count"):
            chart_data["(unclustered)"] = insights["other_count"]
        st.bar_chart(chart_data, height=300)
        st.caption("Reviews that match no theme stay unclustered — a bucket that absorbs "
                   "everything stops being a signal.")
    with right, st.container(border=True):
        st.markdown("**Where the pain is** — ranked by 1-2★ volume")
        pain = sorted(insights["themes"],
                      key=lambda t: (-t.get("lowstar", 0), -t["review_count"]))
        for i, t in enumerate(pain, 1):
            tr = t.get("trend") or {}
            st.markdown(f"**{i}. {t['theme']}**")
            base = (f"{t.get('lowstar', 0)} of {t['review_count']} reviews are 1-2★ "
                    f"({t.get('lowstar_share', 0) * 100:.0f}%)")
            if tr.get("meaningful"):
                arrow = {"worse": "▲", "better": "▼", "flat": "→"}.get(tr["direction"], "→")
                st.caption(f"{base} · last 4w {arrow} {tr['recent_4w']} vs {tr['prev_4w']} before "
                           f"({tr['delta_pct']:+d}%) — {tr['direction']}")
            else:
                st.caption(f"{base} · trend n/a (needs an 8+ week window)")
            if i < len(pain):
                st.divider()
        st.caption("Ranked by the number of 1-2 star reviews, not by theme size — a big happy "
                   "theme outranks nothing here. Trend compares the last 4 weeks with the 4 before.")

    st.markdown("#### Verbatim quotes")
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

# ----------------------------------------------------------------------------------
# Tab 2 — weekly pulse
# ----------------------------------------------------------------------------------

with tab_pulse:
    tab_header("Weekly product pulse", "Internal · top themes, verbatim quotes, one key "
                                       "observation, three action ideas · ≤250 words",
               download=("Download .md", artifacts["pulse"],
                         f"weekly_pulse_{artifacts['week_ending']}.md"))
    chip_row([f"Week ending {artifacts['week_ending']}",
              f"{artifacts['pulse_wc']} / 250 words",
              f"{insights['total_reviews']:,} reviews",
              "Audience: product + support"])
    st.progress(min(artifacts["pulse_wc"] / 250, 1.0), text=f"{artifacts['pulse_wc']} / 250 words")

    # live checks — every constraint verified by code against the actual text
    pulse_text = artifacts["pulse"]
    quote_hits = sum(1 for q in insights["quotes"] if q["quote"] in pulse_text)
    n_actions = len(re.findall(r"(?m)^\d+\.\s", pulse_text))
    fee_named = (not fee.get("detected")) or (fee["fee"] in pulse_text)
    checks = [
        (f"within 250 words ({artifacts['pulse_wc']}/250)", artifacts["pulse_wc"] <= 250),
        (f"{quote_hits}/{len(insights['quotes'])} quotes verbatim in text",
         quote_hits == len(insights["quotes"])),
        (f"{n_actions} numbered action ideas", n_actions >= 3),
        ("key observation present", "**Key observation:**" in pulse_text),
        ("detected fee named", fee_named),
    ]
    with st.container(border=True):
        st.markdown(f"**{'✅' if all(ok for _, ok in checks) else '❌'} Live checks** "
                    "(counted by code against the rendered text)")
        chip_row([f"{'✅' if ok else '❌'} {name}" for name, ok in checks])
        if not all(ok for _, ok in checks):
            st.error("One or more checks failed — fix before shipping this pulse.")
    with st.container(border=True):
        st.markdown(artifacts["pulse"])

# ----------------------------------------------------------------------------------
# Tab 3 — fee explainer
# ----------------------------------------------------------------------------------

with tab_fee:
    tab_header("Fee explainer", "Customer-facing support snippet · facts only, no advice · "
                                "≤6 bullets, 2 official links, last-checked date",
               download=("Download .md", artifacts["explainer"]["markdown"],
                         f"fee_explainer_{artifacts['week_ending']}.md"))
    st.markdown(
        f'<div class="gp-banner">Detected from the reviews: <b>{fee["fee"]}</b> — '
        f'{fee["mentions"]} mentions, {fee["confusion_mentions"]} carrying explicit confusion '
        f'signals ({fee["confusion_mentions"]/max(fee["mentions"],1):.0%} of mentions). '
        f'Detection score {fee["mention_ranking"][0]["score"]:.1f} '
        f'(mentions × confusion-rate).</div>',
        unsafe_allow_html=True,
    )
    chip_row([f"{len(artifacts['explainer']['bullets'])} / 6 bullets",
              f"{len(artifacts['explainer']['source_links'])} official sources",
              f"Last checked {artifacts['week_ending']}"])
    with st.container(border=True):
        st.markdown(artifacts["explainer"]["markdown"])

    exp = artifacts["explainer"]
    exp_md = exp["markdown"]
    rate = fee["confusion_mentions"] / max(fee["mentions"], 1)
    strength = "strong" if rate >= 0.6 else "moderate" if rate >= 0.3 else "weak"
    fee_checks = [
        (f"{len(exp['bullets'])} / 6 bullets", 1 <= len(exp["bullets"]) <= 6),
        (f"{len(exp['source_links'])} / 2 official links", len(exp["source_links"]) >= 2),
        ("last-checked date present", artifacts["week_ending"] in exp_md),
        ("no advice language",
         not re.search(r"we recommend|you should (buy|sell|invest)|guaranteed returns",
                       exp_md, re.I)),
    ]
    chip_row([f"{'✅' if ok else '❌'} {name}" for name, ok in fee_checks])
    st.caption(f"Confusion signal: **{strength}** — {rate:.0%} of the {fee['mentions']} fee "
               f"mentions carry explicit confusion language; treat this as the best-supported "
               f"fee guess, not a measured majority. Every bullet is tied to an official "
               f"Groww/AMFI source and is reusable verbatim in tickets and chats.")

# ----------------------------------------------------------------------------------
# Tab 4 — approval gate + MCP
# ----------------------------------------------------------------------------------

with tab_gate:
    tab_header("Approval gate", "The MCP server refuses to write until it receives a single-use "
                                "token bound to the exact payload. Email is drafted, never sent.")
    payload = artifacts["payload"]

    # zero-side-effect connectivity probe (handshake + tools/list, never a tool call)
    if st.button("Check MCP connection", help="Handshake + tools/list only — no tool is called, nothing is written"):
        with st.spinner("Connecting to the MCP server ..."):
            st.session_state["mcp_conn"] = check_connection()
    conn = st.session_state.get("mcp_conn")
    if conn is not None:
        if conn["ok"]:
            st.success(f"Connected — **{conn['server'].get('name', 'growpulse-mcp')}** "
                       f"v{conn['server'].get('version', '?')} · tools: "
                       f"`{', '.join(conn['tools'])}` · approval gate "
                       f"{'ACTIVE' if conn['gate_active'] else 'state unknown'}")
        else:
            st.error(f"Connection failed: {conn['error']}")

    p1, p2 = st.columns(2, gap="large")
    with p1, st.container(border=True):
        st.markdown("**Tool 1 · `append_to_product_notes`**")
        a = payload["arguments"]["append_to_product_notes"]
        st.code(f"date: {a['date']}\n"
                + "top_themes: " + ", ".join(f"{t['theme']} ({t['review_count']})" for t in a["top_themes"])
                + f"\nweekly_pulse: {len(a['weekly_pulse'].split())} words"
                + f"\nidentified_fee_issue: {a['identified_fee_issue']['fee']} "
                  f"({a['identified_fee_issue']['mentions']} mentions)"
                + f"\nexplanation_bullets: {len(a['explanation_bullets'])}"
                + f"\nsource_links: {len(a['source_links'])}", language="text")
    with p2, st.container(border=True):
        st.markdown("**Tool 2 · `create_email_draft`** (never sends)")
        b = payload["arguments"]["create_email_draft"]
        st.code(f"to: {b['to']}\nsubject: {b['subject']}\n"
                f"body: {len(b['body'].split())} words (pulse + support snippet)", language="text")

    outcome = st.session_state.get("mcp_outcome")
    left, right = st.columns(2, gap="large")
    approve = left.button("Approve & execute via MCP", type="primary",
                          disabled=outcome is not None, use_container_width=True)
    reject = right.button("Reject — write nothing", disabled=outcome is not None,
                          use_container_width=True)

    if approve or reject:
        with st.spinner("Talking to the MCP server ..." if approve else "Recording rejection ..."):
            st.session_state["mcp_outcome"] = run_mcp_actions(
                payload, decision="approve" if approve else "reject",
                verbose=False, prove_gate=approve)
            outcome = st.session_state["mcp_outcome"]

    if outcome is not None:
        if outcome["approved"]:
            st.success("Approved — both tools executed exactly once.")
            for r in outcome["results"]:
                st.markdown(f"**`{r['tool']}`** → {r['result']}")
            d1, d2 = st.columns(2, gap="large")
            notes = (REPO_ROOT / "product_pulse" / "product_notes.md").read_text(encoding="utf-8")
            with d1, st.container(border=True):
                st.markdown("**Notes doc — last appended entry**")
                chunks = notes.split("\n---\n")
                st.code(chunks[-1].strip() if chunks else notes[-2000:], language="markdown")
            with d2, st.container(border=True):
                st.markdown("**Email draft — created, not sent**")
                drafts = sorted((REPO_ROOT / "output" / "drafts").glob("*.md"))
                if drafts:
                    st.code(drafts[-1].read_text(encoding="utf-8")[:2400], language="markdown")
                    eml = drafts[-1].with_suffix(".eml")
                    if eml.exists():
                        st.download_button("Download .eml (X-Unsent: 1)", eml.read_bytes(),
                                           file_name=eml.name, mime="message/rfc822")
        else:
            st.error("Rejected — no MCP tool was executed and nothing was written.")

        n_events = len(outcome["transcript"])
        with st.expander(f"Live MCP transcript — {n_events} events", expanded=outcome["approved"]):
            for line in outcome["transcript"]:
                detail = f" — {line['detail']}" if line.get("detail") else ""
                st.markdown(f"`{line['dir']} {line['kind']}` **{line['tool']}** → "
                            f"`{line['status']}`{detail}")

    approval_log = REPO_ROOT / "output" / "approval_log.json"
    if approval_log.exists():
        try:
            entries = json.loads(approval_log.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            entries = []
        with st.expander(f"Run history — {len(entries)} recorded decisions", expanded=False):
            for e in reversed(entries[-15:]):
                st.markdown(f"- `{e.get('timestamp', '?')}` — **{e.get('decision', '?')}** · "
                            f"{', '.join(e.get('tools_requested', []))}")
            st.caption("output/approval_log.json (written by the client) · "
                       "output/mcp_audit_log.jsonl (append-only, written by the server)")

# ----------------------------------------------------------------------------------
# Tab 5 — data quality
# ----------------------------------------------------------------------------------

with tab_dq:
    tab_header("Data quality gate", "Step 0 runs before every analysis; offending rows are "
                                    "dropped and counted, never silently kept.")
    checks = [
        ("Rows in → clean out", f"{dq['total_input']:,} → {dq['total_output']:,}",
         dq["total_output"] == dq["total_input"]),
        ("Blank required fields dropped", dq["blank_dropped"], dq["blank_dropped"] == 0),
        ("Duplicate review_id dropped", dq["duplicate_id_dropped"], dq["duplicate_id_dropped"] == 0),
        ("Duplicate content dropped", dq["duplicate_text_dropped"], dq["duplicate_text_dropped"] == 0),
        ("Bad dates dropped", dq["bad_date_dropped"], dq["bad_date_dropped"] == 0),
        ("Invalid ratings dropped", dq["bad_rating_dropped"], dq["bad_rating_dropped"] == 0),
        ("Unknown sources dropped", dq["unknown_source_dropped"], dq["unknown_source_dropped"] == 0),
        ("Too-short text dropped", dq["short_text_dropped"], dq["short_text_dropped"] == 0),
        ("Encoding artifacts flagged", dq["encoding_flagged"], dq["encoding_flagged"] == 0),
    ]
    left, right = st.columns([1.2, 1], gap="large")
    with left, st.container(border=True):
        st.markdown("**Checks**")
        for name, val, ok in checks:
            st.markdown(f"{'✅' if ok else '❌'} {name} — `{val}`")
    with right, st.container(border=True):
        st.markdown("**Distributions**")
        st.markdown(f"**Window** {dq['date_min']} → {dq['date_max']} (~{dq['weeks_spanned']} weeks)")
        st.markdown("**Ratings**")
        for star in sorted(dq.get("rating_distribution", {}), reverse=True):
            st.markdown(f"- {star}★ · {dq['rating_distribution'][star]}")
        st.markdown("**Sources**")
        for src, cnt in sorted(dq.get("source_distribution", {}).items(), key=lambda x: -x[1]):
            st.markdown(f"- {src} · {cnt}")

    if artifacts["llm_log"]:
        with st.expander("AI drafting log", expanded=False):
            for line in artifacts["llm_log"]:
                st.markdown(f"- {line}")

    audit = REPO_ROOT / "output" / "mcp_audit_log.jsonl"
    if audit.exists():
        with st.expander("MCP server audit log (append-only)", expanded=False):
            st.code(audit.read_text(encoding="utf-8")[-3000:], language="json")

st.divider()
st.caption("GrowPulse · approval-gated MCP · draft-only email · deterministic core with optional "
           "Groq drafting · not affiliated with or endorsed by Groww · nothing here is investment advice.")
