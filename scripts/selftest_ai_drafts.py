"""Self-test for the AI drafting checks — mocks llm.chat, no network.

Run: python scripts\\selftest_ai_drafts.py
Exits 0 if every expectation holds.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import llm                      # noqa: E402
import ai_drafts                # noqa: E402

INSIGHTS_FAKE = {
    "review_window": {"start": "2026-08-02", "end": "2026-10-18", "weeks": 11.0},
    "total_reviews": 500,
    "themes": [{"theme": "Charges & fee transparency", "review_count": 120, "share": 0.24, "avg_rating": 2.2}],
    "quotes": [
        {"quote": "Never told about exit load.", "theme": "Charges"},
        {"quote": "App crashed during market hours.", "theme": "Stability"},
        {"quote": "Support took days to reply.", "theme": "Support"},
    ],
    "fee_issue": {"fee": "Exit load on mutual fund redemption", "mentions": 52,
                  "confusion_mentions": 38, "first_half_mentions": 20, "second_half_mentions": 32,
                  "mention_ranking": []},
}

GOOD_PULSE = (
    "**Top themes:** Charges (120, 2.2★), Stability, Support.\n\n"
    "**What users are saying**\n"
    "> “Never told about exit load.”\n"
    "> “App crashed during market hours.”\n"
    "> “Support took days to reply.”\n\n"
    "**Key observation:** Exit load on mutual fund redemption confusion rose 20 to 32 per half-window.\n\n"
    "**Actions for the product team:**\n1. Show exit load on redeem sheet.\n2. Add fund-page disclosure.\n3. Ship a support macro.\n"
)

GOOD_EXPLAINER = '{"bullets": ["Exit load is a fee payable to the fund house for early redemption.", "Schemes commonly charge around 1% within a year.", "It is deducted from the redemption proceeds.", "An approximate value is shown on the redeem order screen."]}'

failures: list[str] = []

# --- pulse: good draft accepted -----------------------------------------------------
llm.chat = lambda *a, **k: GOOD_PULSE
pulse, log = ai_drafts.draft_pulse(INSIGHTS_FAKE, "2026-10-20")
if pulse is None:
    failures.append(f"good pulse rejected: {log}")

# --- pulse: over-long draft fails then fallback --------------------------------------
llm.chat = lambda *a, **k: GOOD_PULSE + " filler" * 300
pulse2, log2 = ai_drafts.draft_pulse(INSIGHTS_FAKE, "2026-10-20")
if pulse2 is not None:
    failures.append("over-long pulse was accepted")
if not any("too long" in l for l in log2):
    failures.append(f"word-limit failure not reported: {log2}")

# --- pulse: altered quote fails -------------------------------------------------------
llm.chat = lambda *a, **k: GOOD_PULSE.replace("Never told about exit load.", "Paraphrased quote.")
_, log3 = ai_drafts.draft_pulse(INSIGHTS_FAKE, "2026-10-20")
if not any("verbatim quote" in l for l in log3):
    failures.append(f"altered quote not caught: {log3}")

# --- explainer: good draft accepted ---------------------------------------------------
SOURCE_FACTS = [{"title": "Groww Blog", "fact": "Fund houses commonly charge around 1% exit load within a year."}]
llm.chat = lambda *a, **k: GOOD_EXPLAINER
bul, log4 = ai_drafts.draft_explainer(INSIGHTS_FAKE["fee_issue"], SOURCE_FACTS, "2026-10-20")
if not bul or len(bul) != 4:
    failures.append(f"good explainer rejected: {log4}")

# --- explainer: invented figure + 7th bullet + exclamation caught -----------------------
BAD = ('{"bullets": ["Fee is 47.5% of redemption.", "Second bullet!", "Third.", "Fourth.", '
       '"Fifth.", "Sixth.", "Seventh."]}')
llm.chat = lambda *a, **k: BAD
bul2, log5 = ai_drafts.draft_explainer(INSIGHTS_FAKE["fee_issue"], SOURCE_FACTS, "2026-10-20")
if bul2 is not None:
    failures.append("bad explainer was accepted")
joined = " ".join(log5)
for expected in ("bullet count", "exclamation", "not found in source facts"):
    if expected not in joined:
        failures.append(f"'{expected}' not caught: {log5}")

# --- API error -> clean fallback ---------------------------------------------------------
def _boom(*a, **k):
    raise RuntimeError("Groq API unreachable (mock)")
llm.chat = _boom
pulse6, log6 = ai_drafts.draft_pulse(INSIGHTS_FAKE, "2026-10-20")
if pulse6 is not None or not any("LLM call failed" in l for l in log6):
    failures.append(f"API error not handled: {log6}")

if failures:
    print("SELFTEST FAIL:")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("SELFTEST PASS — pulse/explainer checks accept good drafts, reject over-length, "
      "altered quotes, invented figures, extra bullets, tone violations; API errors fall back cleanly.")
