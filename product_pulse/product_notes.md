# Product Notes â€” Weekly Pulse Log

Internal document. Each entry is appended by the review-insight workflow via MCP
(`append_to_product_notes`) after explicit human approval.

---

## Week ending 2026-10-13

### Top themes
- App stability & performance â€” 4 reviews (avg 1.5â˜…)
- Charges & fee transparency â€” 3 reviews (avg 2.0â˜…)
- Customer support & resolution â€” 2 reviews (avg 2.0â˜…)

### Identified fee issue
**DP (Depository Participant) charge** â€” 1 mention, 0 with explicit confusion signals.
(Seeded example entry from the previous week's run â€” kept short for the demo.)

### Weekly product pulse
Small sample week due to the Diwali market holiday; app stability dominated with
order-screen overlap reports on v8.0.5. DP-charge questions appeared once.

### Fee explanation (support snippet)
- DP charge is a flat depository participant fee applied on delivery sell transactions.
- It is disclosed on the Groww pricing page.

### Sources
- https://groww.in/charges/brokerage

*Logged via MCP by groww-feedback-mcp on 2026-10-13T18:05:00*

---

---

## Week ending 2026-10-20

### Top themes
- Charges & fee transparency â€” 116 reviews (avg 2.3â˜…)
- Mutual fund & SIP experience â€” 92 reviews (avg 2.1â˜…)
- App stability & performance â€” 15 reviews (avg 1.7â˜…)

### Identified fee issue
**Exit load on mutual fund redemption** â€” 52 mentions, 38 with explicit confusion signals. Exit load on mutual fund redemption is the most misunderstood charge: 52 mentions, 38 with explicit confusion signals (users discover it post-redemption).

### Weekly product pulse
# Weekly Product Pulse â€” week ending 2026-10-20
*(Internal â€” Product & Support; source: 500 public reviews, 2026-08-02 â†’ 2026-10-18)*

**Top themes:** Charges & fee transparency (116, avg 2.3â˜…), Mutual fund & SIP experience (92, avg 2.1â˜…), App stability & performance (15, avg 1.7â˜…).

**What users are saying**
> â€œWhy does Groww not show exit load before I hit redeem? Charged 150 rupees on a 6 day holding. Hidden fees vibes.â€ â€” Twitter, 1â˜…, 2026-09-21
> â€œRedeemed my mutual fund for an emergency expense at 11 days and somewhere â‚¹487 vanished between shown and received. Support took days to even tell me it was exit load. Rest of the experience is genuinely smooth.â€ â€” Google Play, 2â˜…, 2026-08-28
> â€œApp crashed twice during market hours today. Lost a good entry on a limit order.â€ â€” Google Play, 1â˜…, 2026-08-03

**Key observation:** Exit load on mutual fund redemption is the clearest recurring confusion: 52 of 121 fee mentions, 38 with explicit confusion signals. Users discover the charge only after redemption, then open tickets â€” it is a fund-house rule our flow never surfaces pre-confirmation.

**Actions for the product team:**
1. Show the scheme's exit load (amount + applicable %) on the redeem confirmation sheet before the user taps Confirm.
2. Surface the exit-load window and % on the fund detail page next to NAV, not only inside the scheme document.
3. Add a redemptions FAQ entry point in-app and route exit-load tickets to a macro with the new support snippet.

### Fee explanation (support snippet)
- Exit load is a fee payable to the mutual fund house for redeeming units before a specified period from the date of investment; it is set by the scheme, not by Groww. [Groww Help â€” What is exit load?]
- Every scheme defines its own exit-load percentage and holding period in its scheme document â€” for example 1% if redeemed within 30 days, or 0.25% if redeemed within 7 days; many funds charge nothing after the period ends. [Groww Blog â€” Mutual Fund Fees and Charges in India]
- The deduction is calculated as: exit-load % x redemption value, and the amount credited is the redemption value minus this load; STT may also apply for equity-oriented schemes. [Groww Help â€” What are the charges applicable for redeeming?]
- It applies per redemption transaction, including partial redemptions, and only to units still within that scheme's exit-load window; units held beyond the window are not charged.
- Groww shows an approximate exit-load amount on the redeem order screen before the order is placed, and the exact deduction appears in the redemption order details. [Groww Help â€” What is exit load?]
- If a redemption amount looks lower than expected, users can check the scheme's exit-load terms on its Groww fund page or the help article, and contact support with the order ID for a breakup. Last checked: 2026-10-20. [Groww Glossary â€” Exit Load in Mutual Funds]

### Sources
- https://groww.in/help/mutual-funds/order/what-is-exit-load--71
- https://groww.in/blog/mutual-fund-fees-and-charges

*Logged via MCP by growpulse-mcp on 2026-10-20T23:26:02*
