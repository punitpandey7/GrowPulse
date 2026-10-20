"""
Step 1 — Review Intelligence Layer
==================================
Turns a raw reviews CSV into structured insights:

  * clusters reviews into max 5 themes (lexicon + scoring engine, no external deps)
  * ranks the top 3 themes
  * extracts 3 representative verbatim user quotes (one per top theme)
  * detects the most frequently *misunderstood* fee/charge, with weekly trend

The clustering engine is deterministic so the demo is reproducible. It scores
every review against 5 theme lexicons and assigns it to the best-scoring theme
("Other" when no lexicon clears the threshold). Swap `classify_theme` for an
embedding/LLM call if you want semantic clustering — the rest of the pipeline
only consumes the resulting `Insights` structure.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from pathlib import Path

# --------------------------------------------------------------------------------------
# Theme definitions (max 5 themes, as required)
# --------------------------------------------------------------------------------------

THEMES: dict[str, list[str]] = {
    "Charges & fee transparency": [
        r"exit[ -]?load", r"\bcharge[sd]?\b", r"\bfees?\b", r"deduct", r"brokerage",
        r"\bdp charges?\b", r"depository", r"\bstt\b", r"\bgst\b", r"stamp duty",
        r"platform fee", r"pricing", r"hidden", r"misleading", r"clarity", r"unclear",
        r"transparen", r"breakup", r"costs?",
    ],
    "App stability & performance": [
        r"crash", r"freeze[sd]?\b", r"hangs?\b", r"slow", r"lag", r"bug", r"glitch",
        r"force clos", r"logged me out", r"error", r"something went wrong", r"overlap",
        r"restart the app", r"fails? to", r"unresponsiv", r"market hours",
        r"missed the trade", r"price moved", r"latest update", r"generic error",
        r"status unknown", r"notification",
    ],
    "Mutual fund & SIP experience": [
        r"\bsip\b", r"mutual fund", r"\bnav\b", r"folio", r"mandate", r"\bunits?\b",
        r"redeem", r"redemption", r"switched", r"installment", r"arbitrage fund",
        r"smallcap fund", r"debt fund", r"liquid fund", r"xirr",
    ],
    "Customer support & resolution": [
        r"support", r"ticket", r"chatbot", r"no response", r"respond", r"escalat",
        r"agent", r"template reply", r"call support", r"resolved", r"human",
    ],
    "Portfolio & reporting": [
        r"\bp and l\b", r"p&l", r"profit.{0,3}loss", r"capital gains", r"report",
        r"statement", r"contract note", r"portfolio", r"buy price", r"sector breakdown",
        r"match my", r"calculation", r"ca flagged",
    ],
}

THEME_MIN_SCORE = 2          # a review needs >=2 keyword hits to join a theme
MAX_THEMES = 5
TOP_N_THEMES = 3
NUM_QUOTES = 3

# --------------------------------------------------------------------------------------
# Fee/charge definitions + "confusion" signal detection
# --------------------------------------------------------------------------------------

FEE_PATTERNS: dict[str, list[str]] = {
    "Exit load on mutual fund redemption": [r"exit[ -]?load"],
    "DP (Depository Participant) charge": [r"\bdp charges?\b", r"depository participant"],
    "Intraday brokerage & statutory charges": [
        r"brokerage", r"intraday charges", r"\bstt\b", r"\bgst\b",
        r"exchange (txn|transaction) charge", r"platform fee", r"stamp duty",
        r"auto square off charges", r"f and o trades?", r"charges on f",
    ],
}

# Signals that a user is *confused* by the fee (not merely mentioning it)
CONFUSION_SIGNALS: list[str] = [
    r"never told", r"nobody told", r"no information", r"no intimation", r"not shown",
    r"wasn'?t shown", r"why was i not warned", r"without any warning", r"no warning",
    r"zero warning", r"hidden", r"surprise", r"unexpected", r"feels? like a hidden",
    r"not explained", r"never explains?", r"where do i", r"where do users learn",
    r"what is (this|exit load|dp)", r"can you explain", r"unclear", r"clarity",
    r"no clarity", r"confus", r"misleading", r"buried", r"should be shown",
    r"should say", r"please warn", r"should be disclosed", r"explain this",
    r"not disclosed", r"appears? to be", r"apparently", r"turned out to be",
    r"no idea", r"supposed to know", r"found out by googling", r"had to (explain|tell) me",
    r"not (clear|mentioned|listed|visible|informed)", r"first time i (found|came to know)",
    r"no mention", r"silent(ly)? deduct", r"wasn'?t informed",
]

# --------------------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------------------


@dataclass
class Review:
    review_id: str
    date: str
    source: str
    rating: int
    review_text: str
    app_version: str = ""
    user_segment: str = ""
    theme: str = "Other"
    fee_mentions: list[str] = field(default_factory=list)
    fee_confusion: list[str] = field(default_factory=list)


def load_reviews(csv_path: str | Path) -> list[Review]:
    """Load the reviews CSV. Date range of the file is reported in the insights."""
    reviews: list[Review] = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            reviews.append(
                Review(
                    review_id=row["review_id"].strip(),
                    date=row["date"].strip(),
                    source=row["source"].strip(),
                    rating=int(row["rating"]),
                    review_text=row["review_text"].strip(),
                    app_version=row.get("app_version", "").strip(),
                    user_segment=row.get("user_segment", "").strip(),
                )
            )
    return reviews


# --------------------------------------------------------------------------------------
# Theme clustering
# --------------------------------------------------------------------------------------


def _score_theme(text: str, patterns: list[str]) -> int:
    return sum(1 for p in patterns if re.search(p, text, flags=re.IGNORECASE))


def classify_theme(text: str) -> str:
    """Assign the review to its best-scoring theme, or 'Other'."""
    scores = {name: _score_theme(text, pats) for name, pats in THEMES.items()}
    best, best_score = max(scores.items(), key=lambda kv: kv[1])
    return best if best_score >= THEME_MIN_SCORE else "Other"


def cluster_reviews(reviews: list[Review]) -> dict[str, list[Review]]:
    clusters: dict[str, list[Review]] = defaultdict(list)
    for r in reviews:
        r.theme = classify_theme(r.review_text)
        clusters[r.theme].append(r)
    # keep insertion order stable: themes by descending size
    return dict(sorted(clusters.items(), key=lambda kv: len(kv[1]), reverse=True))


# --------------------------------------------------------------------------------------
# Quote extraction — pick the most representative verbatim quote per top theme
# --------------------------------------------------------------------------------------

_REPRESENTATIVE_SIGNALS = [
    r"exit[ -]?load", r"\bfee", r"charge", r"deduct", r"hidden", r"surprise",
    r"never", r"no (response|clarity|information)", r"crash", r"lost", r"support",
    r"took \d+ days", r"why", r"what is",
]


def pick_quote(cluster: list[Review]) -> Review | None:
    """Highest-signal review: complaint-leaning rating, informative length,
    and the most signal-word hits per character."""

    def score(rv: Review) -> float:
        text = rv.review_text.lower()
        hits = sum(1 for p in _REPRESENTATIVE_SIGNALS if re.search(p, text))
        length_bonus = min(len(text), 220) / 220          # prefer informative length
        rating_bias = 1.0 if rv.rating <= 2 else 0.45     # pain points over praise
        return (hits + 1.2) * rating_bias * (0.55 + 0.45 * length_bonus)

    candidates = [rv for rv in cluster if len(rv.review_text) >= 55] or cluster
    return max(candidates, key=score) if candidates else None


# --------------------------------------------------------------------------------------
# Fee-confusion detection
# --------------------------------------------------------------------------------------


def _iso_week(date_str: str) -> str:
    d = date.fromisoformat(date_str)
    start = d - timedelta(days=d.weekday())
    return start.isoformat()


def detect_fee_confusion(reviews: list[Review]) -> dict:
    """Rank fee types by *confusion* signal (mentions + confusing-context mentions)."""
    mention_count: Counter[str] = Counter()
    confusion_count: Counter[str] = Counter()
    examples: dict[str, list[Review]] = defaultdict(list)

    for r in reviews:
        text = r.review_text
        has_confusion = any(re.search(p, text, flags=re.IGNORECASE) for p in CONFUSION_SIGNALS)
        for fee, patterns in FEE_PATTERNS.items():
            if any(re.search(p, text, flags=re.IGNORECASE) for p in patterns):
                mention_count[fee] += 1
                r.fee_mentions.append(fee)
                examples[fee].append(r)
                if has_confusion:
                    confusion_count[fee] += 1
                    r.fee_confusion.append(fee)

    if not mention_count:
        return {"detected": False, "fee": None}

    # Score = volume x confusion-rate. Raw volume alone always picks the
    # best-known charge; raw confusion-count alone picks niche charges two
    # people mentioned. The product balances "how much is it discussed" with
    # "how often is it misread".
    def _score(f: str) -> float:
        rate = confusion_count[f] / mention_count[f] if mention_count[f] else 0.0
        return round(mention_count[f] * rate, 3)

    ranked = sorted(mention_count, key=lambda f: (_score(f), mention_count[f]), reverse=True)
    top_fee = ranked[0]

    weeks = Counter(_iso_week(r.date) for r in examples[top_fee])
    weekly_trend = [{"week_starting": w, "mentions": c} for w, c in sorted(weeks.items())]
    mid = len(weekly_trend) // 2 or 1
    first_half = sum(w["mentions"] for w in weekly_trend[:mid])
    second_half = sum(w["mentions"] for w in weekly_trend[mid:])

    return {
        "detected": True,
        "fee": top_fee,
        "total_fee_mentions_all_types": sum(mention_count.values()),
        "mentions": mention_count[top_fee],
        "confusion_mentions": confusion_count[top_fee],
        "share_of_fee_confusion": round(confusion_count[top_fee] / max(sum(confusion_count.values()), 1), 2),
        "mention_ranking": [
            {
                "fee": f,
                "mentions": mention_count[f],
                "confusion_mentions": confusion_count[f],
                "confusion_rate": round(confusion_count[f] / mention_count[f], 2) if mention_count[f] else 0.0,
                "score": _score(f),
            }
            for f in ranked
        ],
        "first_seen": min(r.date for r in examples[top_fee]),
        "last_seen": max(r.date for r in examples[top_fee]),
        "first_half_mentions": first_half,
        "second_half_mentions": second_half,
        "weekly_trend": weekly_trend,
        "sample_confusion_quotes": [
            {
                "review_id": r.review_id,
                "date": r.date,
                "source": r.source,
                "rating": r.rating,
                "quote": r.review_text,
            }
            for r in sorted(examples[top_fee], key=lambda x: x.date)[-3:]
        ],
    }


# --------------------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------------------


def analyze(csv_path: str | Path) -> dict:
    """Run the full Step-1 pipeline and return the insights structure."""
    reviews = load_reviews(csv_path)
    clusters = cluster_reviews(reviews)

    theme_rows = []
    for theme, members in clusters.items():
        if theme == "Other":
            continue
        theme_rows.append(
            {
                "theme": theme,
                "review_count": len(members),
                "share": round(len(members) / len(reviews), 2),
                "avg_rating": round(sum(m.rating for m in members) / len(members), 1),
                "trend_first_half": sum(1 for m in members if m.date < "2026-09-20"),
                "trend_second_half": sum(1 for m in members if m.date >= "2026-09-20"),
            }
        )

    top_themes = theme_rows[:TOP_N_THEMES]

    quotes = []
    for theme_row in top_themes:
        q = pick_quote(clusters[theme_row["theme"]])
        if q:
            quotes.append(
                {
                    "theme": theme_row["theme"],
                    "review_id": q.review_id,
                    "date": q.date,
                    "source": q.source,
                    "rating": q.rating,
                    "quote": q.review_text,
                }
            )
    # top up to NUM_QUOTES from next-largest clusters if needed
    if len(quotes) < NUM_QUOTES:
        for theme, members in clusters.items():
            if theme == "Other" or any(q["theme"] == theme for q in quotes):
                continue
            q = pick_quote(members)
            if q:
                quotes.append(
                    {
                        "theme": theme,
                        "review_id": q.review_id,
                        "date": q.date,
                        "source": q.source,
                        "rating": q.rating,
                        "quote": q.review_text,
                    }
                )
            if len(quotes) >= NUM_QUOTES:
                break

    fee_issue = detect_fee_confusion(reviews)

    dates = sorted(r.date for r in reviews)
    return {
        "source_csv": str(csv_path),
        "review_window": {"start": dates[0], "end": dates[-1], "weeks": round((date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days / 7, 1)},
        "total_reviews": len(reviews),
        "themes_clustered": min(len(theme_rows), MAX_THEMES),
        "other_count": len(clusters.get("Other", [])),
        "theme_cap": MAX_THEMES,
        "themes": theme_rows[:MAX_THEMES],
        "top_themes": top_themes,
        "quotes": quotes[:NUM_QUOTES],
        "fee_issue": fee_issue,
    }


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "data/groww_reviews.csv"
    print(json.dumps(analyze(path), indent=2, ensure_ascii=False))
