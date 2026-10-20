"""
GrowPulse — workflow orchestrator
=================================
End-to-end run:

  Step 0  Data quality gate : blank/duplicate/date/rating/source checks -> cleaned rows
  Step 1  Review intelligence: 5 themes, top 3, 3 verbatim quotes, fee-confusion detection
  Step 2  Weekly product pulse: <=250-word internal note   -> output/weekly_pulse_<date>.md
  Step 3  Fee explainer      : <=6 bullets + 2 official links + Last checked
  Step 4  MCP (approval-gated, server-side HMAC token) -> notes doc + email draft

CLI:
    python src\\workflow.py                    # interactive approval
    python src\\workflow.py --approve          # auto-approve (demo/CI)
    python src\\workflow.py --reject           # demo the rejection path
    python src\\workflow.py --llm              # AI-draft observation/actions/bullets via Groq
                                               # (needs GROQ_API_KEY; validated + fallback)

The Streamlit app (app.py) imports run_steps() + build_mcp_payload() so the UI
and the CLI run the identical pipeline.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows console safety

sys.path.insert(0, str(Path(__file__).resolve().parent))

from review_intelligence import analyze                  # noqa: E402
from generators import (                                 # noqa: E402
    build_weekly_pulse, build_fee_explainer, word_count, PULSE_WORD_LIMIT,
)
from data_quality import clean_and_validate, print_report  # noqa: E402
from mcp_client import run_mcp_actions                   # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "output"
RECIPIENTS = "product-team@groww.internal, support-leads@groww.internal"


# --------------------------------------------------------------------------------------
# Pipeline (importable by the Streamlit app)
# --------------------------------------------------------------------------------------


def run_steps(csv_path: str | Path, week_ending: str | None = None,
              use_llm: bool = False, llm_model: str | None = None, verbose: bool = True) -> dict:
    """Steps 0-3. Returns artifacts + MCP payload; writes files under output/."""

    def say(msg: str = "") -> None:
        if verbose:
            print(msg)

    week_ending = week_ending or date.today().isoformat()
    OUTPUT_DIR.mkdir(exist_ok=True)

    # ---------------------------------------------------------------- Step 0
    say("=" * 78)
    say("STEP 0 — DATA QUALITY GATE")
    say("=" * 78)
    import csv as _csv
    with open(csv_path, newline="", encoding="utf-8") as fh:
        raw_rows = list(_csv.DictReader(fh))
    clean_rows, dq = clean_and_validate(raw_rows)
    print_report(dq)
    if not dq["clean"]:
        raise SystemExit("Data quality gate FAILED — see report above.")
    (OUTPUT_DIR / "data_quality_report.json").write_text(json.dumps(dq, indent=2), encoding="utf-8")

    # analysis needs datetime objects; keep dict rows as-is (analyzer re-reads list[dict])
    from review_intelligence import Review, cluster_reviews, detect_fee_confusion, pick_quote, MAX_THEMES, TOP_N_THEMES, NUM_QUOTES
    reviews = [
        Review(review_id=r["review_id"], date=r["date"], source=r["source"], rating=r["rating"],
               review_text=r["review_text"], app_version=r.get("app_version", ""),
               user_segment=r.get("user_segment", ""))
        for r in clean_rows
    ]

    # ---------------------------------------------------------------- Step 1
    say("\n" + "=" * 78)
    say("STEP 1 — REVIEW INTELLIGENCE")
    say("=" * 78)
    clusters = cluster_reviews(reviews)
    theme_rows = []
    for theme, members in clusters.items():
        if theme == "Other":
            continue
        theme_rows.append({
            "theme": theme,
            "review_count": len(members),
            "share": round(len(members) / len(reviews), 2),
            "avg_rating": round(sum(m.rating for m in members) / len(members), 1),
        })
    top_themes = theme_rows[:TOP_N_THEMES]

    quotes = []
    for theme_row in top_themes:
        q = pick_quote(clusters[theme_row["theme"]])
        if q:
            quotes.append({"theme": theme_row["theme"], "review_id": q.review_id, "date": q.date,
                           "source": q.source, "rating": q.rating, "quote": q.review_text})
    if len(quotes) < NUM_QUOTES:  # top up from next-largest clusters
        for theme, members in clusters.items():
            if theme == "Other" or any(q["theme"] == theme for q in quotes):
                continue
            q = pick_quote(members)
            if q:
                quotes.append({"theme": theme, "review_id": q.review_id, "date": q.date,
                               "source": q.source, "rating": q.rating, "quote": q.review_text})
            if len(quotes) >= NUM_QUOTES:
                break

    fee_issue = detect_fee_confusion(reviews)
    dates = sorted(r.date for r in reviews)
    from datetime import date as _date
    insights = {
        "source_csv": str(csv_path),
        "review_window": {"start": dates[0], "end": dates[-1],
                          "weeks": round((_date.fromisoformat(dates[-1]) - _date.fromisoformat(dates[0])).days / 7, 1)},
        "total_reviews": len(reviews),
        "themes_clustered": min(len(theme_rows), MAX_THEMES),
        "other_count": len(clusters.get("Other", [])),
        "theme_cap": MAX_THEMES,
        "themes": theme_rows[:MAX_THEMES],
        "top_themes": top_themes,
        "quotes": quotes[:NUM_QUOTES],
        "fee_issue": fee_issue,
    }

    say(f"Loaded {insights['total_reviews']} reviews "
        f"({insights['review_window']['start']} -> {insights['review_window']['end']}, "
        f"~{insights['review_window']['weeks']} weeks) from {insights['source_csv']}")
    say(f"Clustered into {insights['themes_clustered']} themes (cap {insights['theme_cap']}"
        f"{', plus unclustered \"Other\"' if insights.get('other_count') else ''}):")
    for t in insights["themes"]:
        marker = "  <- TOP" if t in insights["top_themes"] else ""
        say(f"  - {t['theme']:<38} {t['review_count']:>3} reviews  avg {t['avg_rating']}★  "
            f"share {t['share']*100:.0f}%{marker}")

    say(f"\nFee-confusion detection (score = mentions × confusion-rate) -> {fee_issue['fee']}")
    for row in fee_issue["mention_ranking"]:
        say(f"    {row['fee']:<45} mentions={row['mentions']:>3}  confused={row['confusion_mentions']:>3}  "
            f"rate={row['confusion_rate']:.0%}  score={row['score']:.2f}")
    say("\nVerbatim quotes selected:")
    for q in insights["quotes"]:
        say(f"  [{q['theme']}] {q['source']} {q['rating']}★ {q['date']}: \"{q['quote'][:90]}...\"")
    (OUTPUT_DIR / "insights.json").write_text(json.dumps(insights, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---------------------------------------------------------------- Steps 2+3 (optional LLM)
    llm_log: list[str] = []
    llm_used = {"pulse": False, "explainer": False}
    if use_llm:
        import llm as _llm
        if not _llm.is_available():
            llm_log.append("GROQ_API_KEY not available — using deterministic generators.")
        else:
            import ai_drafts
            say("\n[llm] drafting pulse observation/actions via Groq ...")
            pulse_draft, log = ai_drafts.draft_pulse(insights, week_ending, model=llm_model)
            llm_log += log
            say("\n".join(f"  [llm] {l}" for l in log))
            say("[llm] drafting fee explainer bullets via Groq ...")
            from generators import SOURCES
            source_facts = [
                {"title": SOURCES["groww_exit_load_help"]["title"], "fact": "Exit load is a fee payable to the mutual fund house for exiting a fund before a specified period; an approximate value is shown while placing the redeem order."},
                {"title": SOURCES["groww_mf_fees_blog"]["title"], "fact": "Fund houses commonly charge around 1% exit load on redemption within a year; rates are scheme-specific."},
                {"title": SOURCES["groww_redeem_charges_help"]["title"], "fact": "On redemption, exit load (and STT for equity-oriented funds) is deducted from the proceeds."},
            ]
            bullets_draft, log2 = ai_drafts.draft_explainer(fee_issue, source_facts, week_ending, model=llm_model)
            llm_log += log2
            say("\n".join(f"  [llm] {l}" for l in log2))
            llm_used = {"pulse": pulse_draft is not None, "explainer": bullets_draft is not None}

    # ---------------------------------------------------------------- Step 2
    say("\n" + "=" * 78)
    say("STEP 2 — WEEKLY PRODUCT PULSE (internal, <=250 words)")
    say("=" * 78)
    pulse, wc = build_weekly_pulse(insights, week_ending)   # deterministic base (also the fallback)
    if llm_used["pulse"]:
        pulse = pulse_draft                                 # validated by ai_drafts._validate_pulse
        wc = word_count(pulse)
    assert wc <= PULSE_WORD_LIMIT, f"Pulse too long: {wc} words"
    say(pulse)
    say(f"[word count: {wc}/{PULSE_WORD_LIMIT}]")
    pulse_path = OUTPUT_DIR / f"weekly_pulse_{week_ending}.md"
    pulse_path.write_text(pulse, encoding="utf-8")

    # ---------------------------------------------------------------- Step 3
    say("=" * 78)
    say("STEP 3 — FEE EXPLAINER (customer-facing support snippet)")
    say("=" * 78)
    explainer = build_fee_explainer(
        insights, last_checked=week_ending,
        bullets_override=(bullets_draft if llm_used["explainer"] else None))
    say(explainer["markdown"])
    say(f"[bullets: {len(explainer['bullets'])}/6 | official links: {len(explainer['source_links'])}]")
    explainer_path = OUTPUT_DIR / f"fee_explainer_{week_ending}.md"
    explainer_path.write_text(explainer["markdown"], encoding="utf-8")

    payload = build_mcp_payload(insights, pulse, explainer, fee_issue, week_ending)
    payload_path = OUTPUT_DIR / "mcp_payload.json"
    payload_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "insights": insights, "dq": dq, "pulse": pulse, "pulse_wc": wc,
        "explainer": explainer, "payload": payload, "week_ending": week_ending,
        "files": {"pulse": str(pulse_path), "explainer": str(explainer_path),
                  "insights": str(OUTPUT_DIR / "insights.json"), "payload": str(payload_path),
                  "dq_report": str(OUTPUT_DIR / "data_quality_report.json")},
        "llm_log": llm_log, "llm_used": llm_used,
    }


def build_mcp_payload(insights: dict, pulse: str, explainer: dict, fee_issue: dict,
                      week_ending: str) -> dict:
    fee_summary = (
        f"{fee_issue['fee']} is the most misunderstood charge: {fee_issue['mentions']} mentions, "
        f"{fee_issue['confusion_mentions']} with explicit confusion signals "
        f"(users discover it post-redemption)."
    )
    return {
        "notes_target": "product_pulse/product_notes.md",
        "drafts_target": "output/drafts/",
        "arguments": {
            "append_to_product_notes": {
                "date": week_ending,
                "top_themes": [
                    {"theme": t["theme"], "review_count": t["review_count"], "avg_rating": t["avg_rating"]}
                    for t in insights["top_themes"]
                ],
                "weekly_pulse": pulse,
                "identified_fee_issue": {
                    "fee": fee_issue["fee"],
                    "mentions": fee_issue["mentions"],
                    "confusion_mentions": fee_issue["confusion_mentions"],
                    "summary": fee_summary,
                },
                "explanation_bullets": explainer["bullets"],
                "source_links": explainer["source_links"],
            },
            "create_email_draft": {
                "to": RECIPIENTS,
                "subject": f"Weekly Product Pulse + Customer Clarification — week ending {week_ending}",
                "body": (
                    f"Hi team,\n\n"
                    f"## 1. Weekly product pulse (week ending {week_ending})\n\n{pulse}\n"
                    f"## 2. Fee explanation (reusable support snippet)\n\n"
                    f"Use the text below verbatim when users raise this in tickets/chats.\n\n"
                    f"{explainer['markdown']}\n"
                    f"—\nGenerated by the GrowPulse review-insight workflow. Sources are official. "
                    f"This is a draft for review before sending.\n"
                ),
            },
        },
    }


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="GrowPulse: reviews -> insights -> pulse + explainer -> MCP (approval-gated)")
    ap.add_argument("--csv", default=str(REPO_ROOT / "data" / "groww_reviews.csv"))
    ap.add_argument("--date", default=None, help="Week-ending date (default: today)")
    ap.add_argument("--approve", action="store_true", help="Auto-approve MCP actions")
    ap.add_argument("--reject", action="store_true", help="Auto-reject MCP actions")
    ap.add_argument("--llm", action="store_true", help="AI-draft via Groq (validated, with fallback)")
    ap.add_argument("--model", default=None, help="Groq model id (default from env/llm.py)")
    ns = ap.parse_args()

    artifacts = run_steps(ns.csv, week_ending=ns.date, use_llm=ns.llm, llm_model=ns.model)
    fee_issue = artifacts["insights"]["fee_issue"]

    print("\n" + "=" * 78)
    print("STEP 4 — MCP ACTIONS (approval-gated, server-side token)")
    print("=" * 78)
    decision = "approve" if ns.approve else "reject" if ns.reject else None
    outcome = run_mcp_actions(artifacts["payload"], decision=decision)

    print("\n" + "=" * 78)
    print("RUN SUMMARY")
    print("=" * 78)
    for label, path in artifacts["files"].items():
        print(f"  {label:<14}: {path}")
    print(f"  pulse          : {artifacts['pulse_wc']} words")
    print(f"  fee issue      : {fee_issue['fee']} ({fee_issue['mentions']} mentions, "
          f"{fee_issue['confusion_mentions']} confused)")
    if artifacts["llm_log"]:
        print(f"  llm            : {'drafts used' if any(artifacts['llm_used'].values()) else 'fallback used'}")
    print(f"  approval log   : {OUTPUT_DIR / 'approval_log.json'}")
    print(f"  mcp audit log  : {OUTPUT_DIR / 'mcp_audit_log.jsonl'}")
    print(f"  MCP decision   : {'APPROVED — tools executed once' if outcome['approved'] else 'REJECTED — no tool executed'}")
    if outcome["approved"]:
        print(f"  Notes doc      : {REPO_ROOT / 'product_pulse' / 'product_notes.md'} (entry appended)")
        print(f"  Email drafts   : {REPO_ROOT / 'output' / 'drafts'} (draft only, not sent)")
    return 0 if outcome["approved"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
