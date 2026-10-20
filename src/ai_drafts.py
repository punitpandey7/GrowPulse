"""
GrowPulse — AI drafting with checks (the "checks, not trust" layer)
===================================================================
Optionally uses Groq (see llm.py) to draft the two human-sounding parts of the
workflow — the key observation + action ideas in the weekly pulse, and the fee
explainer bullets. Everything COUNTED (themes, counts, quotes, the detected fee)
stays computed by the engine and is fed to the model as evidence, never guessed.

Every draft must pass validation before use:

  * weekly pulse   : <=250 words, contains all 3 verbatim quotes unchanged,
                     contains the computed numbers, ends with 3 numbered actions
  * fee explainer  : 3..6 bullets, no exclamation marks (neutral tone),
                     no ₹ figures other than those in the evidence pack
                     (the model cannot invent rates), source links and
                     "Last checked" are appended by the engine, not the model

A failing draft is retried ONCE with the failure list included in the prompt.
If the retry fails too — or the key is missing, or the API errors — the
deterministic generator output is used unchanged, with a warning. Nothing the
model says can break the deliverable constraints.
"""

from __future__ import annotations

import json
import re

import llm

ADVICE_WORDS = ["you should invest", "best fund", "avoid this", "i recommend", "guaranteed"]


# --------------------------------------------------------------------------------------
# Weekly pulse
# --------------------------------------------------------------------------------------

_PULSE_SYSTEM = (
    "You are a product analyst at a fintech company. You write a weekly internal "
    "product pulse from a structured evidence pack of customer-review statistics. "
    "You never invent numbers, ids or quotes. Neutral, specific, no hype."
)


def _pulse_prompt(insights: dict, week_ending: str) -> str:
    fee = insights["fee_issue"]
    evidence = {
        "window": insights["review_window"],
        "total_reviews": insights["total_reviews"],
        "themes": insights["themes"],
        "detected_fee_issue": {k: fee[k] for k in
                               ("fee", "mentions", "confusion_mentions", "first_half_mentions",
                                "second_half_mentions", "mention_ranking") if k in fee},
        "verbatim_quotes_to_include_exactly": [q["quote"] for q in insights["quotes"]],
    }
    return f"""Evidence pack (JSON):
{json.dumps(evidence, ensure_ascii=False, indent=1)}

Write ONLY the body of the weekly pulse for week ending {week_ending}, in Markdown:
- one line: **Top themes:** (name them with counts and average ratings from the pack)
- **What users are saying** with the three verbatim quotes as blockquotes (copy them EXACTLY, do not paraphrase)
- **Key observation:** 2-3 sentences on the detected fee confusion and its trend
  (first-half vs second-half mentions are in the pack), and why it happens
- **Actions for the product team:** exactly 3 numbered, concrete, UI/product-level ideas

Total must stay under 220 words. No header, no sign-off, no emoji."""


def _validate_pulse(text: str, insights: dict) -> list[str]:
    failures = []
    words = len(text.split())
    if words > 250:
        failures.append(f"too long: {words} words (limit 250)")
    for q in insights["quotes"]:
        if q["quote"] not in text:
            failures.append(f"verbatim quote missing or altered: {q['quote'][:60]}...")
    if not re.search(r"1\.\s", text) or not re.search(r"3\.\s", text):
        failures.append("actions must be exactly 3 numbered items")
    fee = insights["fee_issue"]
    if fee.get("detected") and str(fee["mentions"]) not in text:
        failures.append(f"the computed mention count {fee['mentions']} does not appear")
    low = text.lower()
    for w in ADVICE_WORDS:
        if w in low:
            failures.append(f"advice-style wording: '{w}'")
    return failures


def draft_pulse(insights: dict, week_ending: str, model: str | None = None) -> tuple[str | None, list[str]]:
    """Return (pulse_markdown_or_None, log). None means: use the deterministic one."""
    log: list[str] = []
    prompt = _pulse_prompt(insights, week_ending)
    for attempt in (1, 2):
        try:
            text = llm.chat(prompt, system=_PULSE_SYSTEM, model=model)
        except RuntimeError as exc:
            log.append(f"LLM call failed: {exc}")
            return None, log
        failures = _validate_pulse(text, insights)
        if not failures:
            log.append(f"draft accepted on attempt {attempt} ({len(text.split())} words)")
            return text, log
        log.append(f"attempt {attempt} failed checks: {'; '.join(failures)}")
        prompt += "\n\nYour previous draft FAILED these checks:\n- " + "\n- ".join(failures) \
            + "\nFix every one. Output the full corrected pulse only."
    return None, log


# --------------------------------------------------------------------------------------
# Fee explainer
# --------------------------------------------------------------------------------------

_EXPLAINER_SYSTEM = (
    "You are a support enablement writer at a fintech company. You explain one fee "
    "that customers misunderstand, in a neutral, facts-only tone. You state only "
    "figures that appear in the evidence you are given. No advice, no marketing, "
    "no exclamation marks."
)


def _explainer_prompt(fee_issue: dict, source_facts: list[dict], last_checked: str) -> str:
    return f"""Fee users are confused about: {fee_issue.get('fee')}
Review evidence: {fee_issue.get('mentions')} mentions, {fee_issue.get('confusion_mentions')} with
explicit confusion signals. Users typically discover it AFTER the deduction.

Official source facts you may use (do NOT invent any other figure):
{json.dumps(source_facts, ensure_ascii=False, indent=1)}

Write 4 to 6 numbered bullets explaining this fee to an upset user, in this order:
what it is -> when it applies -> how it is calculated -> what the user sees in the app
-> where to verify. Use only figures from the source facts. No exclamation marks,
no advice words (should/best/avoid/recommend). Output JSON only:
{{"bullets": ["...", "..."]}}"""


def _validate_explainer(text: str, allowed_figures: list[str]) -> tuple[list[str], list[str]]:
    """Return (bullets, failures)."""
    failures: list[str] = []
    try:
        raw = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        bullets = json.loads(raw).get("bullets", [])
    except (json.JSONDecodeError, AttributeError):
        return [], ["reply is not valid JSON {\"bullets\": [...]}"]

    if not 3 <= len(bullets) <= 6:
        failures.append(f"bullet count {len(bullets)} outside 3..6")
    for b in bullets:
        if "!" in b:
            failures.append(f"exclamation mark (tone): {b[:60]}...")
        low = b.lower()
        for w in ADVICE_WORDS:
            if w in low:
                failures.append(f"advice-style wording '{w}' in: {b[:60]}...")
        # strip list numbering ("1. ", "2) ", "- ") so ordinals are not scanned as figures
        body = re.sub(r"^\s*(?:\d+[\.\)]|[-*])\s*", "", b)
        for fig in re.findall(r"\d[\d,.]*%?", body):
            if fig.replace(",", "") not in [a.replace(",", "") for a in allowed_figures]:
                # every digit-run must be a figure present in the evidence pack
                failures.append(f"figure '{fig}' not found in source facts: {b[:60]}...")
    return bullets, failures


def draft_explainer(fee_issue: dict, source_facts: list[dict], last_checked: str,
                    model: str | None = None) -> tuple[list[str] | None, list[str]]:
    """Return (bullets_or_None, log). None means: use the deterministic explainer."""
    log: list[str] = []
    allowed_figures: list[str] = []
    for fact in source_facts:
        allowed_figures += re.findall(r"\d[\d,.]*%?", json.dumps(fact))
    # figures the review data itself legitimately contains are also allowed
    allowed_figures += [str(fee_issue.get("mentions", "")), str(fee_issue.get("confusion_mentions", ""))]

    prompt = _explainer_prompt(fee_issue, source_facts, last_checked)
    for attempt in (1, 2):
        try:
            text = llm.chat(prompt, system=_EXPLAINER_SYSTEM, model=model)
        except RuntimeError as exc:
            log.append(f"LLM call failed: {exc}")
            return None, log
        bullets, failures = _validate_explainer(text, allowed_figures)
        if not failures:
            log.append(f"draft accepted on attempt {attempt} ({len(bullets)} bullets)")
            return bullets, log
        log.append(f"attempt {attempt} failed checks: {'; '.join(failures[:4])}")
        prompt += "\n\nYour previous draft FAILED these checks:\n- " + "\n- ".join(failures) \
            + "\nFix every one. Output the corrected JSON only."
    return None, log
