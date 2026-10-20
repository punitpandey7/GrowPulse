"""
GrowPulse — alternate CSV fixture for upload-path testing
=========================================================
Builds data/alt_reviews_test.csv: a DIFFERENT corpus from groww_reviews.csv
(fresh seed, same schema) with deliberately injected quality problems:

  * 3 duplicate review texts (different ids)
  * 1 blank review_text, 1 blank rating
  * 1 unparseable date, 1 unknown source, 1 too-short text

Expected behaviour when analysed: the Step 0 gate DROPS exactly those 8 rows,
reports them in the data-quality tab/report, and the run proceeds on the
clean remainder — proving the pipeline accepts any conforming CSV and
enforces quality on it.

Run: python scripts\\make_test_csv.py   (writes data/alt_reviews_test.csv)
"""

from __future__ import annotations

import csv
import random
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_reviews import compose, CATEGORY_META, weighted_source, date_for, version_for  # noqa: E402
from data_quality import normalize_text  # noqa: E402

OUT = REPO_ROOT / "data" / "alt_reviews_test.csv"
FIELDS = ["review_id", "date", "source", "rating", "review_text", "app_version", "user_segment"]


def main() -> int:
    rng = random.Random(7)  # different seed than the main corpus
    categories = list(CATEGORY_META)
    weights = [CATEGORY_META[c][0] for c in categories]

    rows: list[dict] = []
    seen: set[str] = set()
    n = 0
    while n < 92:  # clean rows
        cat = rng.choices(categories, weights=weights, k=1)[0]
        text = compose(rng, cat)
        norm = normalize_text(text)
        if norm in seen or len(text) < 40:
            continue
        seen.add(norm)
        _, ratings, bias, segments = CATEGORY_META[cat]
        d = date_for(rng, bias)
        n += 1
        rows.append({
            "review_id": f"A{n:03d}",
            "date": d.isoformat(),
            "source": weighted_source(rng),
            "rating": str(rng.choice(ratings)),
            "review_text": text,
            "app_version": version_for(d),
            "user_segment": rng.choice(segments),
        })

    # ---- injected quality problems (8 rows; the gate must drop all of them) ----
    # Bad rows are kept text-unique so each one reaches its OWN check instead of
    # being shadowed by the earlier duplicate-content rule.
    def clone(base: dict, rid: str, suffix: str = "") -> dict:
        r = dict(base)
        r["review_id"] = rid
        if suffix:
            r["review_text"] = base["review_text"].rstrip() + " " + suffix
        return r

    rows.append(clone(rows[0], "A901"))                       # duplicate text
    rows.append(clone(rows[5], "A902"))                       # duplicate text
    rows.append(clone(rows[11], "A903"))                      # duplicate text
    bad = dict(rows[2]); bad["review_text"] = ""              # blank text
    rows.append(clone(bad, "A904"))
    bad = dict(rows[3]); bad["rating"] = ""                   # blank rating
    rows.append(clone(bad, "A905", "Rating field was left empty on this submission."))
    bad = dict(rows[4]); bad["date"] = "31/09/2026"           # unparseable date
    rows.append(clone(bad, "A906", "Logging this with a malformed date attached."))
    bad = dict(rows[6]); bad["source"] = "Reddit"             # unknown source
    rows.append(clone(bad, "A907", "Cross-posting this from another forum."))
    bad = dict(rows[7]); bad["review_text"] = "ok app"        # too short
    rows.append(clone(bad, "A908"))

    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUT} (92 clean + 8 injected problems)")
    print("Expected gate report: 3 duplicate texts, 1 blank text, 1 blank rating, "
          "1 bad date, 1 unknown source, 1 short text -> 92 rows analysed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
