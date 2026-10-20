"""
GrowPulse — review corpus generator
===================================
Expands data/groww_reviews.csv from the 75 handcrafted seed reviews to a few
hundred realistic, UNIQUE reviews spanning 2026-08-02 .. 2026-10-18 (~11 weeks).

  * deterministic (seeded) — regenerate with a different --seed for a new corpus
  * uniqueness enforced on normalized text (no duplicate reviews)
  * exit-load confusion is deliberately the dominant fee signal, because the
    whole workflow (Step 1 detection -> Step 2 pulse -> Step 3 explainer)
    must connect to what users are actually confused about
  * runs the shared data-quality checks before writing, so the shipped CSV
    is clean by construction

Usage:  python scripts\\generate_reviews.py [--seed 42] [--extra 271]
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from data_quality import clean_and_validate, normalize_text  # noqa: E402

CSV_PATH = REPO_ROOT / "data" / "groww_reviews.csv"
WINDOW_START = date(2026, 8, 2)
WINDOW_END = date(2026, 10, 18)

FUNDS = ["debt fund", "liquid fund", "smallcap fund", "index fund", "flexi cap fund",
         "arbitrage fund", "overnight fund", "mid cap fund", "ELSS fund", "gold fund",
         "large cap fund", "conservative hybrid fund"]
STOCKS = ["Tata Motors", "Reliance", "HDFC Bank", "Infosys", "ITC", "Zomato",
          "SBI", "Tata Steel", "Adani Power", "IRCTC", "Yes Bank", "Vedanta"]

# --------------------------------------------------------------------------------------
# Fragment pools per category: openers + details + closers, composed at random
# --------------------------------------------------------------------------------------

POOLS: dict[str, dict[str, list[str]]] = {
    "exit_load": {
        "open": [
            "Redeemed my {fund} after {days} days",
            "Cashed out of my mutual fund {days} days in",
            "Sold my {fund} units early",
            "Withdrew from my {fund} on day {days}",
            "Exited my mutual fund position after {days} days",
            "Redeemed at day {days} and the credit was short",
            "My mutual fund redemption paid out lesser than shown",
            "Partial redemption of my {fund} came up short",
            "Booked out of my {fund} in {days} days",
            "Full redemption of my SIP folio after {days} days",
            "Withdrew my money from a {fund} within {days} days",
            "Redeemed units bought {days} days ago",
            "Sold off my {fund} holdings way too early it seems",
            "Redeemed my mutual fund for an emergency expense at {days} days",
            "Triggered a full redemption of my {fund} yesterday",
            "Redeemed half my {fund} units at the {days} day mark",
            "My first mutual fund redemption did not add up",
            "Cashed out my {fund} to rebalance into stocks",
        ],
        "mid": [
            "and got ₹{amount} less than what the app showed",
            "and ₹{amount} was silently deducted before the credit",
            "and the amount that hit my bank was ₹{amount} lesser",
            "and somewhere ₹{amount} vanished between shown and received",
            "the shortfall was ₹{amount} for me",
            "₹{amount} less arrived than the redemption estimate",
            "my bank credit was ₹{amount} below the shown value",
            "the difference worked out to ₹{amount}",
        ],
        "detail": [
            "Nobody told me an early exit fee applies to mutual funds",
            "Nowhere in the redemption flow is this charge mentioned",
            "I had no idea funds charge you for leaving early",
            "This was a complete surprise deduction with zero warning",
            "Feels like a hidden fee, how is a new investor supposed to know",
            "Why is this not shown before I confirm the redemption",
            "There should be a big warning before this happens",
            "Support took days to even tell me it was exit load",
            "The app says zero charges and then deducts anyway",
            "For first time investors this is really confusing",
            "I only found out by googling what exit load means",
            "No information about this anywhere inside the app",
            "My CA had to explain this to me, the app never does",
            "The order screen shows an estimate but no clear label",
            "I was not informed about the exit load window before investing",
            "It should at least be spelled out in plain language on the redeem screen",
        ],
        "close": [
            "Please show the exit load on the redeem screen itself",
            "Add a confirmation dialog that explains this deduction",
            "Groww should warn users before they redeem",
            "Transparency needs work here",
            "Otherwise the app is fine",
            "Fix this and it is a five star app from me",
            "Better disclosure would prevent so many tickets",
            "New investors will all hit this same wall",
            "Not a dealbreaker but communication is weak",
            "Rest of the experience is genuinely smooth",
        ],
    },
    "dp_charge": {
        "open": [
            "Sold one share of {stock} and something was cut",
            "My first delivery sell had an extra deduction of ₹{dp}",
            "Sold {stock} after a year and ₹{dp} disappeared",
            "Noticed ₹{dp} gone after my equity sell order",
            "Executed a delivery sell and the credit was ₹{dp} short",
            "Why does every sell order cost ₹{dp} extra",
            "Sold a single share for testing and got ₹{dp} less",
            "My equity sell credit never matches the order value, always ₹{dp} off",
            "Cleared my {stock} position and found a small cut of ₹{dp}",
            "Sold 3 shares and ₹{dp} was deducted on top",
        ],
        "detail": [
            "What exactly is this DP charge, it is not explained anywhere",
            "No intimation about this fee before placing the order",
            "For small trades this is a big percentage, unclear policy",
            "Support said it is standard, but where is it written",
            "The pricing page should list this with an example",
            "First time I came to know such a charge exists",
            "It is not a huge amount but the surprise is annoying",
            "Nobody mentions DP charges in the zero brokerage ads",
            "This needs a line on the sell confirmation screen",
            "How is a retail investor supposed to know about this",
        ],
        "close": [
            "Please disclose it upfront",
            "Add it to the pricing page",
            "Otherwise no complaints",
            "Small thing but it matters for trust",
            "Clarity would help beginners a lot",
        ],
    },
    "intraday_charges": {
        "open": [
            "Made ₹{profit} profit intraday on {stock} and lost a chunk to charges",
            "Intraday trade on {stock} netted me much less than expected",
            "My ₹{profit} intraday gain shrunk after all deductions",
            "Did two intraday trades on {stock} and fees ate the gains",
            "Small intraday win on {stock}, still ended up with less",
            "Charged on a flat intraday trade on {stock}, made almost nothing",
            "F and O trade on {symbol} ended up costing me ₹{profit} in charges",
            "Scalped {stock} intraday and the deductions shocked me",
        ],
        "detail": [
            "Brokerage plus STT plus GST is never shown before the order",
            "Zero brokerage sounds nice until the statutory charges pile up",
            "The all in one breakup should appear on the order pad",
            "Exchange charges and STT are not part of the marketing, understandably, but warn us",
            "Auto square off charges are a whole separate topic nobody explains",
            "Platform fee of ₹{fee} monthly was also a surprise",
            "Stamp duty exists too, none of this is listed upfront",
            "GST on brokerage further eats the margin",
        ],
        "close": [
            "Show estimated charges before placing the order",
            "A charges calculator in the app would fix this",
            "Education and disclosure, that is all we ask",
            "Still like the app overall",
        ],
    },
    "app_stability": [
        "App crashed while I was placing a {kind} order on {stock}",
        "The app froze during market hours and I missed my entry on {stock}",
        "Watchlist took forever to load, then the app crashed outright",
        "Got logged out in the middle of a trade on {stock}",
        "Order screen hung on the spinning loader for minutes",
        "Repeated something went wrong error every time I opened orders",
        "Push notification for my alert on {stock} came {late} minutes late",
        "Charts freeze when I switch timeframes on my phone",
        "The latest update made everything laggy, takes {late} seconds to open the app",
        "App closed by itself twice today during live market",
        "Order placement kept failing with a network error even with full bars",
        "Dark mode buttons overlap on the order screen after the update",
        "Portfolio screen shows stale values during market hours",
        "The app is unusable between 9:15 and 9:30, everything hangs",
        "IPO application page crashed after my UPI mandate",
        "SIP page throws a generic error since the last update",
        "Live prices stopped updating until I restarted the app",
        "App crashed while loading the {stock} option chain",
        "Fingerprint login stopped working after the update, keeps asking for PIN",
        "Two orders in a row failed to register, had to retype everything",
        "The heat map widget freezes the whole app on my older phone",
        "Market depth stops refreshing randomly on {stock}",
        "App took {late} seconds to launch and then showed a blank screen",
        "Placed a SL order and the app hung, order status stayed pending",
        "Chart drawings disappeared after the app force closed itself",
        "The order pad keyboard covers the buy button on small screens",
        "App crashed during the {symbol} expiry, worst possible time",
        "Price alerts stop working after I swipe the app away",
        "Loading the funds page throws me back to the dashboard repeatedly",
        "App is heating my phone and then crashing on longer chart views",
        "SIP edit screen shows a blank white page for me",
        "App hung at the UPI step of my deposit and debited me anyway",
        "Switching between stocks and funds tabs lags {late} seconds every time",
        "The basket order screen crashed and deleted my unsaved basket",
    ],
    "mf_sip": [
        "My SIP mandate failed again, the bank debit never retried",
        "SIP installment has been pending for three days with no status",
        "NAV updated so late that my portfolio value looked wrong all evening",
        "Cancelled my SIP but the next installment got debited anyway",
        "Switch from regular to direct fund took days to reflect",
        "Mutual fund order stays in placed status the whole day, why so slow",
        "Nominee update for my folio keeps failing with a generic error",
        "SIP step up option is buried in menus, hard to find",
        "Redemption proceeds took longer than promised to reach my bank",
        "My SIP of ₹{amount} was debited but units are still not allotted",
        "STP from liquid to equity fund did not execute on the scheduled date",
        "XIRR shown for my SIPs is way off from the fund website numbers",
        "The folio number shown does not match my AMC statement",
        "SIP pause feature is confusing, resumed accidentally",
        "Added a new fund to my SIP and it skipped the next cycle",
        "Lumpsum order in {fund} stayed unconfirmed for two days",
        "SIP reminder notifications stopped coming after I changed my number",
        "Portfolio shows wrong average cost for my {fund} units",
        "The MF order status screen gives no clue what happens next",
        "My SIP was shown active but never debited for two months",
        "Redeemed units but the bank credit shows a different final value",
        "SIP date change did not apply to the next installment",
        "The fund factsheet link inside the app is broken",
        "Bought {fund} via lumpsum, units allotted a day later than peers show",
        "My consolidated MF statement misses one folio entirely",
        "SIP cancellation took a full week to reflect in the AMC records",
        "The new fund alert notifications are irrelevant to my holdings",
        "Portfolio import from other apps failed midway with no rollback",
        "The MF switch order created a new folio instead of switching",
        "My debt fund holdings do not show the dividend credit anywhere",
        "SIP success email comes before units are actually allotted, confusing",
        "The app shows gains for the day even when NAV is not yet updated",
    ],
    "support": [
        "Ticket open for days and still no response from support",
        "Chatbot loops endlessly and never connects me to a human",
        "Support resolved my query only after I escalated on social media",
        "Template reply, my actual issue was never addressed",
        "No call support option for urgent trade issues",
        "It takes days to get a response on charge disputes",
        "Support closed my ticket without solving anything",
        "The help section does not answer basic charge questions",
        "Raised a withdrawal issue, support took a week to acknowledge",
        "Chat support does not understand simple questions",
        "I have replied to the same email thread three times, no update",
        "The callback request never happened, waited the whole day",
        "Support agent had no clue about the charges I was asking about",
        "Every response feels copy pasted, no actual investigation",
        "The in app chat disconnects mid conversation and loses history",
        "Ticket status says open for days with zero movement",
        "Support asked for documents I already uploaded twice",
        "No way to talk to a human unless you complain publicly first",
        "Response time has gotten worse over the last few months",
        "The escalation matrix on the website is outdated",
        "Support could not explain the deduction in my statement",
        "First response always comes at midnight, useless for market hours",
        "The grievance redressal link leads to a dead page",
        "Two tickets merged into one and both got closed unresolved",
        "Support suggested steps I already tried before contacting them",
        "The SLA promised on the website is not honored at all",
        "Language barrier made my issue worse, agent misunderstood twice",
        "I miss the old email support that actually solved things",
    ],
    "portfolio": [
        "P and L screen does not match my own calculation at all",
        "Capital gains report shows the wrong buy price for one lot",
        "XIRR for my SIPs seems inflated compared to the AMC site",
        "Contract note PDF is missing the charges breakup for one trade",
        "Portfolio needs a sector breakdown view for better analysis",
        "Downloaded statement has a different total than the app shows",
        "The gains percentage on my holdings screen is misleading",
        "Realized gains tab includes trades I actually cancelled",
        "The tax report lags a day behind my executed orders",
        "Portfolio download in Excel format has broken columns",
        "The P and L of my intraday trades is not separated clearly",
        "My transferred shares show a wrong acquisition date",
        "The holdings screen value differs between app and website",
        "Dividend credits are missing from my portfolio summary",
        "The realized vs unrealized split in the report is wrong",
        "Order history filters miss trades older than three months",
        "The portfolio chart total does not match the listed holdings",
        "Benchmark comparison in my portfolio report is outdated",
    ],
    "praise": [
        "Cleanest investing app in India, deposits via UPI are instant",
        "Started my first SIP here, onboarding was genuinely smooth",
        "Charts are excellent, would love more drawing tools though",
        "Stocks and mutual funds in one place, perfect for beginners",
        "Withdrawals arrive by the next working day, no fuss",
        "Gold SIP and mutual funds both work beautifully here",
        "The interface is simple and fast, my whole family uses it now",
        "Customer friendly design, the order flow feels effortless",
        "Best app for someone starting with small amounts",
        "The monthly investment statement is clear and neat",
        "I love the alerts and the clean portfolio view",
        "Transfers are instant and the UI is the tidiest around",
        "Switched from another broker, the体验 is night and day",
        "SIP setup took two minutes, impressive onboarding",
        "The learning section actually helped me understand investing",
        "Price alerts work reliably, never missed a trade since",
        "The app is light, fast and does exactly what I need",
        "Zero complaints on delivery trades so far",
        "The IPO section is well designed and simple",
        "Basket orders saved me so much time this month",
        "The dashboard loads instantly even on my old phone",
        "Great product, small improvements keep coming every update",
        "My CA liked how clean the reports are",
        "Deposits and withdrawals have never failed me in two years",
    ],
    "misc": [
        "How do I download my contract note from the app",
        "Please add a dark mode scheduling option",
        "Can someone explain the difference between delivery and MTF here",
        "Feature request, let us set alerts on portfolio value not just price",
        "Where can I see my funded amount before it reflects in stocks",
        "Please add widgets for the home screen",
        "The app language should support more regional languages",
        "Can we get a web terminal that mirrors the app exactly",
        "Please add an option to hide my portfolio value in screenshots",
        "Why is the app size so large after the last few updates",
        "Add a recycle bin for deleted watchlists please",
        "The weekly digest email stopped arriving for me",
        "Please support multiple portfolios for different goals",
        "Can we get an iPad optimized layout",
    ],
}


def compose(rng: random.Random, category: str) -> str:
    """Compose one unique review string for a category."""
    p = POOLS[category]
    if category == "exit_load":
        t = f"{rng.choice(p['open'])} {rng.choice(p['mid'])}."
        if rng.random() < 0.85:  # strong majority carries a confusion signal
            t += f" {rng.choice(p['detail'])}."
        if rng.random() < 0.55:
            t += f" {rng.choice(p['close'])}."
    elif category in ("dp_charge", "intraday_charges"):
        t = f"{rng.choice(p['open'])}. {rng.choice(p['detail'])}."
        if rng.random() < 0.6:
            t += f" {rng.choice(p['close'])}."
    else:  # list-style categories
        t = f"{rng.choice(p)}."
        if rng.random() < 0.35 and category == "app_stability":
            t += " Please fix this before someone loses real money."
        if rng.random() < 0.25 and category == "mf_sip":
            t += " A little more clarity would help a lot."
    return t.format(
        fund=rng.choice(FUNDS), stock=rng.choice(STOCKS),
        symbol=rng.choice(["NIFTY", "BANKNIFTY", "FINNIFTY"]),
        days=rng.randint(2, 33), amount=rng.randint(45, 1450),
        dp=rng.choice(["15.34", "15", "15.34", "15.34"]),
        profit=rng.randint(150, 3800), fee=rng.choice([20, 20, 25, 50]),
        late=rng.choice([10, 15, 20, 25, 30, 45, 60]),
        kind=rng.choice(["delivery", "intraday", "limit", "SL"]),
    )


CATEGORY_META = {
    #            count, rating pool,                     date bias (0=early 1=late), segments
    "exit_load":         (65, [1, 1, 2, 2, 2, 3],          0.72, ["SIP investor", "new investor", "retail"]),
    "dp_charge":         (28, [2, 2, 3, 3, 3, 4],          0.50, ["retail", "trader", "new investor"]),
    "intraday_charges":  (24, [1, 2, 2, 2, 3, 3],          0.50, ["trader", "retail"]),
    "app_stability":     (38, [1, 1, 1, 2, 2, 3],          0.55, ["trader", "retail"]),
    "mf_sip":            (32, [2, 2, 3, 3, 3, 4],          0.50, ["SIP investor", "new investor", "retail"]),
    "support":           (28, [1, 1, 2, 2, 2, 3],          0.50, ["retail", "trader", "new investor"]),
    "portfolio":         (18, [2, 2, 3, 3, 4],             0.50, ["retail", "trader"]),
    "praise":            (24, [4, 4, 5, 5, 5],             0.50, ["new investor", "retail", "SIP investor"]),
    "misc":              (14, [3, 3, 4, 4, 5],             0.50, ["retail", "new investor"]),
}

SOURCE_CHOICES = [("Google Play", 0.68), ("Trustpilot", 0.14), ("Twitter", 0.10), ("App Store", 0.08)]


def weighted_source(rng: random.Random) -> str:
    r, acc = rng.random(), 0.0
    for src, w in SOURCE_CHOICES:
        acc += w
        if r <= acc:
            return src
    return "Google Play"


def date_for(rng: random.Random, bias: float) -> date:
    """Random date in the window; bias 1.0 pushes toward October (later weeks)."""
    span = (WINDOW_END - WINDOW_START).days
    u = rng.random() ** (1.0 / max(bias, 0.05))  # bias>0.5 skews late, <0.5 skews early
    return WINDOW_START + timedelta(days=int(u * span))


def version_for(d: date) -> str:
    if d < date(2026, 8, 14):
        return "8.0.3"
    if d < date(2026, 9, 12):
        return "8.0.4"
    return "8.0.5"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--extra", type=int, default=271, help="number of new reviews to generate")
    ns = ap.parse_args()
    rng = random.Random(ns.seed)

    # keep the handcrafted seeds
    existing: list[dict] = []
    if CSV_PATH.exists():
        with open(CSV_PATH, newline="", encoding="utf-8") as fh:
            existing = list(csv.DictReader(fh))

    seen = {normalize_text(r["review_text"]) for r in existing}
    next_id = len(existing) + 1
    new_rows: list[dict] = []

    categories = list(CATEGORY_META)
    weights = [CATEGORY_META[c][0] for c in categories]
    made = 0
    while made < ns.extra:
        cat = rng.choices(categories, weights=weights, k=1)[0]
        text = compose(rng, cat)
        norm = normalize_text(text)
        if norm in seen or len(text) < 40:  # uniqueness + quality floor
            continue
        seen.add(norm)
        _, ratings, bias, segments = CATEGORY_META[cat]
        d = date_for(rng, bias)
        new_rows.append({
            "review_id": f"G{next_id + made:03d}",
            "date": d.isoformat(),
            "source": weighted_source(rng),
            "rating": str(rng.choice(ratings)),
            "review_text": text,
            "app_version": version_for(d),
            "user_segment": rng.choice(segments),
        })
        made += 1

    combined = existing + new_rows
    combined.sort(key=lambda r: (r["date"], r["review_id"]))

    # run the shared data-quality gate before writing anything
    clean_rows, report = clean_and_validate(combined)
    if report["hard_failures"]:
        print("REFUSING TO WRITE — quality gate failed:", report["hard_failures"])
        return 1

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["review_id", "date", "source", "rating",
                                                "review_text", "app_version", "user_segment"],
                                quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(clean_rows)

    print(f"Wrote {len(clean_rows)} clean reviews to {CSV_PATH}")
    print(f"  dropped during generation-quality gate: "
          f"{report['duplicate_text_dropped'] + report['duplicate_id_dropped']} dupes, "
          f"{report['blank_dropped']} blanks, {report['short_text_dropped']} too short")
    dist = report["rating_distribution"]
    print("  rating distribution:", {k: dist[k] for k in sorted(dist)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
