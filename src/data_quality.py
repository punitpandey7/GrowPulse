"""
GrowPulse — data quality layer (pipeline Step 0)
=================================================
Every analysis run starts here. The gate:

  * required-field / blank checks (review_id, date, source, rating, review_text)
  * duplicate review_id detection
  * duplicate *content* detection via normalized text (case/punctuation/whitespace
    insensitive, so "Great app!!" and "great app" cannot both survive)
  * date parsing + window-range validation
  * rating bounds (1..5, integer)
  * source whitelist
  * minimum text length (too-short reviews carry no signal)
  * encoding artifact detection (U+FFFD replacement chars)

Hard failures (blanks, bad dates, bad ratings, unknown sources, short text) cause
the offending rows to be DROPPED and the run to be flagged. Duplicates are
dropped silently-but-counted. The full report is returned as a dict and can be
written to output/data_quality_report.json.

Importable (clean_and_validate) and runnable standalone:

    python src\\data_quality.py [path/to/reviews.csv]
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

REQUIRED_FIELDS = ["review_id", "date", "source", "rating", "review_text"]
ALLOWED_SOURCES = {"Google Play", "Trustpilot", "Twitter", "App Store"}
MIN_TEXT_LENGTH = 25
WINDOW_START = "2026-08-01"
WINDOW_END = "2026-10-20"


def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — for duplicate detection."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\u0900-\u097F ]+", " ", text)  # keep devanagari too
    return re.sub(r"\s+", " ", text).strip()


def clean_and_validate(rows: list[dict]) -> tuple[list[dict], dict]:
    """Validate + clean raw review rows. Returns (clean_rows, report)."""
    report: dict = {
        "total_input": len(rows),
        "blank_dropped": 0,
        "duplicate_id_dropped": 0,
        "duplicate_text_dropped": 0,
        "bad_date_dropped": 0,
        "bad_rating_dropped": 0,
        "unknown_source_dropped": 0,
        "short_text_dropped": 0,
        "encoding_flagged": 0,
        "whitespace_normalized": 0,
        "hard_failures": [],
    }

    clean: list[dict] = []
    seen_ids: set[str] = set()
    seen_text: set[str] = set()

    for raw in rows:
        row = dict(raw)
        # --- blanks / required fields ------------------------------------------
        if any(not str(row.get(f, "")).strip() for f in REQUIRED_FIELDS):
            report["blank_dropped"] += 1
            continue

        # --- normalize whitespace ---------------------------------------------
        for f in REQUIRED_FIELDS:
            orig = str(row[f])
            normed = re.sub(r"\s+", " ", orig).strip()
            if normed != orig:
                report["whitespace_normalized"] += 1
            row[f] = normed

        # --- encoding artifacts -------------------------------------------------
        if "\ufffd" in row["review_text"]:
            report["encoding_flagged"] += 1
            report["hard_failures"].append(f"U+FFFD replacement char in {row['review_id']}")

        # --- duplicate ids ------------------------------------------------------
        if row["review_id"] in seen_ids:
            report["duplicate_id_dropped"] += 1
            continue

        # --- duplicate content --------------------------------------------------
        norm = normalize_text(row["review_text"])
        if not norm or norm in seen_text:
            report["duplicate_text_dropped"] += 1
            continue

        # --- date ---------------------------------------------------------------
        try:
            d = date.fromisoformat(row["date"])
            if not (date.fromisoformat(WINDOW_START) <= d <= date.fromisoformat(WINDOW_END)):
                report["bad_date_dropped"] += 1
                continue
        except ValueError:
            report["bad_date_dropped"] += 1
            continue

        # --- rating ---------------------------------------------------------------
        try:
            rating = int(row["rating"])
            if not 1 <= rating <= 5:
                report["bad_rating_dropped"] += 1
                continue
            row["rating"] = rating
        except (TypeError, ValueError):
            report["bad_rating_dropped"] += 1
            continue

        # --- source -----------------------------------------------------------------
        if row["source"] not in ALLOWED_SOURCES:
            report["unknown_source_dropped"] += 1
            continue

        # --- text length ---------------------------------------------------------------
        if len(row["review_text"]) < MIN_TEXT_LENGTH:
            report["short_text_dropped"] += 1
            continue

        seen_ids.add(row["review_id"])
        seen_text.add(norm)
        clean.append(row)

    # --- summary statistics ------------------------------------------------------
    report["total_output"] = len(clean)
    report["rating_distribution"] = dict(Counter(str(r["rating"]) for r in clean))
    report["source_distribution"] = dict(Counter(r["source"] for r in clean))
    report["date_min"] = min((r["date"] for r in clean), default=None)
    report["date_max"] = max((r["date"] for r in clean), default=None)
    report["weeks_spanned"] = (
        round((date.fromisoformat(report["date_max"]) - date.fromisoformat(report["date_min"])).days / 7, 1)
        if clean else 0
    )
    report["clean"] = not report["hard_failures"]
    return clean, report


def print_report(report: dict) -> None:
    icon = "PASS" if report["clean"] else "FAIL"
    print(f"[data-quality] {icon} — {report['total_input']} in, {report['total_output']} clean rows out")
    checks = [
        ("blank required fields", report["blank_dropped"]),
        ("duplicate review_id", report["duplicate_id_dropped"]),
        ("duplicate content", report["duplicate_text_dropped"]),
        ("bad/unparseable dates", report["bad_date_dropped"]),
        ("invalid ratings", report["bad_rating_dropped"]),
        ("unknown sources", report["unknown_source_dropped"]),
        ("too-short text", report["short_text_dropped"]),
        ("whitespace normalized", report["whitespace_normalized"]),
        ("encoding artifacts", report["encoding_flagged"]),
    ]
    for name, count in checks:
        mark = "  " if count == 0 else ">>"
        print(f"   {mark} {name:<28} {count}")
    if report["hard_failures"]:
        for f in report["hard_failures"][:5]:
            print(f"   !! {f}")


if __name__ == "__main__":
    import csv

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "data" / "groww_reviews.csv"
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    clean, report = clean_and_validate(rows)
    print_report(report)
    out = Path(__file__).resolve().parent.parent / "output" / "data_quality_report.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[data-quality] report written to {out}")
    sys.exit(0 if report["clean"] else 1)
