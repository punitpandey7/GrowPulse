"""
Step 2 — Weekly Product Pulse (internal, <= 250 words)
Step 3 — Fee Explainer (customer-facing support snippet, <= 6 bullets)

Both generators consume the Step-1 `insights` structure only — the outputs are
directly traceable to what users said in the reviews (quotes are verbatim, the
fee explainer is written for the fee that Step 1 detected as most confused).
"""

from __future__ import annotations

from datetime import date

# --------------------------------------------------------------------------------------
# Official sources (verified working URLs)
# --------------------------------------------------------------------------------------

SOURCES = {
    "groww_exit_load_help": {
        "title": "Groww Help — What is exit load?",
        "url": "https://groww.in/help/mutual-funds/order/what-is-exit-load--71",
    },
    "groww_redeem_charges_help": {
        "title": "Groww Help — What are the charges applicable for redeeming?",
        "url": "https://groww.in/help/mutual-funds/order/what-are-the-charges-applicable-for-redeeming--53",
    },
    "groww_mf_fees_blog": {
        "title": "Groww Blog — Mutual Fund Fees and Charges in India",
        "url": "https://groww.in/blog/mutual-fund-fees-and-charges",
    },
    "groww_exit_load_glossary": {
        "title": "Groww Glossary — Exit Load in Mutual Funds",
        "url": "https://groww.in/p/exit-load-in-mutual-funds",
    },
    "groww_no_exit_load_funds": {
        "title": "Groww Blog — List of Mutual Funds with Zero Exit Load",
        "url": "https://groww.in/blog/10-debt-funds-with-no-exit-load",
    },
    "amfi": {
        "title": "AMFI — Association of Mutual Funds in India (industry body)",
        "url": "https://www.amfiindia.com/",
    },
}

PULSE_WORD_LIMIT = 250
EXPLAINER_BULLET_LIMIT = 6


def word_count(text: str) -> int:
    return len(text.split())


# --------------------------------------------------------------------------------------
# Step 2 — Weekly Product Pulse
# --------------------------------------------------------------------------------------

_ACTION_BANK = {
    "Exit load on mutual fund redemption": [
        "Show the scheme's exit load (amount + applicable %) on the redeem confirmation sheet before the user taps Confirm.",
        "Surface the exit-load window and % on the fund detail page next to NAV, not only inside the scheme document.",
        "Add a redemptions FAQ entry point in-app and route exit-load tickets to a macro with the new support snippet.",
    ],
    "DP (Depository Participant) charge": [
        "Add a one-line DP-charge note on the sell confirmation sheet for delivery trades.",
        "List DP charge with amount on the pricing page with an example.",
        "Route DP-charge tickets to a support macro with the new snippet.",
    ],
    "Intraday brokerage & statutory charges": [
        "Show an estimated all-in charge breakup before order placement for intraday and F&O.",
        "Add a charges calculator link on the order pad.",
        "Review zero-charges marketing copy for statutory-charge footnotes.",
    ],
}
_DEFAULT_ACTIONS = [
    "Add a pre-confirmation charge disclosure for the flagged fee on the relevant order screen.",
    "Publish an in-app explainer page for the flagged fee and link it from the fund/stock detail page.",
    "Ship a support macro with the new snippet so tickets resolve in one reply.",
]


def _actions_for(fee: str | None) -> list[str]:
    return list(_ACTION_BANK.get(fee, _DEFAULT_ACTIONS))


def build_weekly_pulse(insights: dict, week_ending: str | None = None) -> tuple[str, int]:
    week_ending = week_ending or date.today().isoformat()
    themes = insights["top_themes"]
    quotes = insights["quotes"]
    fee = insights["fee_issue"]
    total = insights["total_reviews"]
    window = insights["review_window"]

    theme_summary = ", ".join(
        f"{t['theme']} ({t['review_count']}, avg {t['avg_rating']}★)" for t in themes
    )

    quote_lines = "\n".join(
        f"> \u201c{q['quote']}\u201d \u2014 {q['source']}, {q['rating']}\u2605, {q['date']}"
        for q in quotes
    )

    if fee.get("detected"):
        first_half = fee.get("first_half_mentions", 0)
        second_half = fee.get("second_half_mentions", 0)
        if second_half > first_half:
            trend_words = f"trend up ({first_half}\u2192{second_half} mentions per half-window)"
        elif second_half < first_half:
            trend_words = f"trend down ({first_half}\u2192{second_half} per half-window), but still #1"
        else:
            trend_words = f"trend flat ({first_half}\u2192{second_half} per half-window)"
        observation = (
            f"{fee['fee']} is the clearest recurring confusion: {fee['mentions']} of "
            f"{fee['total_fee_mentions_all_types']} fee mentions, {fee['confusion_mentions']} with explicit "
            f"confusion signals ({round(fee['share_of_fee_confusion'] * 100)}% of all fee confusion), "
            f"{trend_words}. Users discover the charge only after redemption, then open tickets "
            f"\u2014 it is a fund-house rule our flow never surfaces pre-confirmation."
        )
        actions = _actions_for(fee["fee"])
    else:
        observation = "No dominant fee-confusion signal this week; themes are spread across stability and support."
        actions = _DEFAULT_ACTIONS

    pulse = (
        f"# Weekly Product Pulse \u2014 week ending {week_ending}\n"
        f"*(Internal \u2014 Product & Support; source: {total} public reviews, "
        f"{window['start']} \u2192 {window['end']})*\n\n"
        f"**Top themes:** {theme_summary}.\n\n"
        f"**What users are saying**\n{quote_lines}\n\n"
        f"**Key observation:** {observation}\n\n"
        f"**Actions for the product team:**\n"
        f"1. {actions[0]}\n"
        f"2. {actions[1]}\n"
        f"3. {actions[2]}\n"
    )

    wc = word_count(pulse)
    if wc > PULSE_WORD_LIMIT:
        # auto-trim guard: progressively strip detail from the observation
        import re as _re
        trimmed = _re.sub(r", trend (up|down|flat) \([^)]*\)(, but still #1)?", "", observation)
        trimmed = _re.sub(r" \(\d+% of all fee confusion\)", "", trimmed)
        pulse = pulse.replace(observation, trimmed)
        wc = word_count(pulse)
        if wc > PULSE_WORD_LIMIT and fee.get("detected"):
            minimal = (
                f"{fee['fee']} dominates fee confusion: {fee['mentions']} mentions, "
                f"{fee['confusion_mentions']} with confusion signals. Users hit it after "
                f"redemption, then open tickets."
            )
            pulse = pulse.replace(trimmed, minimal)
            wc = word_count(pulse)
    return pulse, wc  # type: ignore[return-value]


# --------------------------------------------------------------------------------------
# Step 3 — Fee Explainer (facts-only support snippet)
# --------------------------------------------------------------------------------------

_EXPLAINER_TEMPLATES = {
    "Exit load on mutual fund redemption": {
        "headline": "Support snippet: why my mutual fund redemption amount was less than expected (exit load)",
        "audience": "Users asking: \u201cI redeemed my mutual fund and got less money than the NAV x units. Where did the amount go?\u201d",
        "bullets": [
            "Exit load is a fee payable to the mutual fund house for redeeming units before a specified period from the date of investment; it is set by the scheme, not by Groww. [{groww_exit_load_help}]",
            "Every scheme defines its own exit-load percentage and holding period in its scheme document \u2014 for example 1% if redeemed within 30 days, or 0.25% if redeemed within 7 days; many funds charge nothing after the period ends. [{groww_mf_fees_blog}]",
            "The deduction is calculated as: exit-load % x redemption value, and the amount credited is the redemption value minus this load; STT may also apply for equity-oriented schemes. [{groww_redeem_charges_help}]",
            "It applies per redemption transaction, including partial redemptions, and only to units still within that scheme's exit-load window; units held beyond the window are not charged.",
            "Groww shows an approximate exit-load amount on the redeem order screen before the order is placed, and the exact deduction appears in the redemption order details. [{groww_exit_load_help}]",
            "If a redemption amount looks lower than expected, users can check the scheme's exit-load terms on its Groww fund page or the help article, and contact support with the order ID for a breakup. Last checked: {last_checked}. [{groww_exit_load_glossary}]",
        ],
    },
}

_EXPLAINER_FALLBACK = {
    "headline": "Support snippet: clarification on {fee}",
    "audience": "Users asking about this charge in recent reviews.",
    "bullets": [
        "This charge is defined by the product or scheme terms, not applied arbitrarily by Groww.",
        "Exact rates and conditions are listed on the official charges page.",
        "The amount is shown in the order breakdown after execution.",
        "Users can request a breakup of any deduction from support with their order ID.",
        "Official references: see source links below. Last checked: {last_checked}.",
    ],
}


def build_fee_explainer(insights: dict, last_checked: str | None = None,
                        bullets_override: list[str] | None = None) -> dict:
    """Return {markdown, bullets, source_links, fee}. <= 6 bullets, neutral tone,
    2+ official source links, 'Last checked' date.

    bullets_override: validated LLM bullets (from ai_drafts) replace the default
    text; sources and the Last checked line are ALWAYS engine-controlled."""
    last_checked = last_checked or date.today().isoformat()
    fee = insights["fee_issue"]
    fee_name = fee.get("fee") if fee.get("detected") else None

    tpl = _EXPLAINER_TEMPLATES.get(fee_name, _EXPLAINER_FALLBACK)
    raw = bullets_override[:EXPLAINER_BULLET_LIMIT] if bullets_override else tpl["bullets"][:EXPLAINER_BULLET_LIMIT]

    # which source keys are referenced? (LLM bullets reference none -> pick defaults)
    used_keys: list[str] = []
    for b in raw:
        for key in SOURCES:
            if f"{{{key}}}" in b:
                used_keys.append(key)
    used_keys = list(dict.fromkeys(used_keys))[:2]
    if len(used_keys) < 2:  # guarantee 2 official links
        for key in ("groww_exit_load_help", "groww_mf_fees_blog", "amfi"):
            if key not in used_keys:
                used_keys.append(key)
            if len(used_keys) == 2:
                break

    bullets = []
    for b in raw:
        line = b
        for key, meta in SOURCES.items():
            line = line.replace(f"{{{key}}}", meta["title"])
        line = line.format(last_checked=last_checked) if "{last_checked}" in line else line
        bullets.append(line)

    source_links = [SOURCES[k]["url"] for k in used_keys]

    lines = [
        f"# {tpl['headline'].format(fee=fee_name or 'flagged charge')}",
        f"*Audience: {tpl['audience']}*",
        "",
    ]
    for i, b in enumerate(bullets, 1):
        lines.append(f"{i}. {b}")
    lines.append("")
    lines.append("**Official sources**")
    for k in used_keys:
        lines.append(f"- [{SOURCES[k]['title']}]({SOURCES[k]['url']})")
    lines += ["", f"Last checked: {last_checked}", ""]

    return {
        "markdown": "\n".join(lines),
        "bullets": bullets,
        "source_links": source_links,
        "fee": fee_name,
    }
