# GrowPulse 💹 — where Groww reviews go critical

**Raw public customer reviews in → weekly product pulse + fee clarification out.**
Nothing reaches an internal tool until a human approves it — and the approval is
enforced **inside the MCP server** with a single-use HMAC token, not by client
courtesy. Email is drafted, never sent.

Built as a Product + Support monitoring loop for **Groww**: product teams track
user sentiment weekly; support teams get a ready-to-paste, facts-only
explanation for the charge users keep misreading.

| Deliverable | Where |
| --- | --- |
| Working prototype (web) | `streamlit run app.py` → http://localhost:8501 |
| Reviews CSV (500 rows, quality-gated) | [data/groww_reviews.csv](data/groww_reviews.csv) |
| Weekly product pulse (≤250 words) | `output/weekly_pulse_<date>.md` |
| Fee explainer (≤6 bullets, 2 official links) | `output/fee_explainer_<date>.md` |
| Notes doc snippet (appended via MCP) | [product_pulse/product_notes.md](product_pulse/product_notes.md) |
| Email draft (`.md` + `.eml`, X-Unsent:1) | `output/drafts/` |
| Source list (6 URLs) | [docs/SOURCES.md](docs/SOURCES.md) |
| Data quality report | `output/data_quality_report.json` |
| MCP audit log (requested/executed/refused) | `output/mcp_audit_log.jsonl` |
| Approval log | `output/approval_log.json` |

---

## 1. How to run

Python 3.10+. The core pipeline and MCP server use **only the standard library**;
Streamlit is needed for the web app.

```bat
:: Web app (colorful UI, approval gate as buttons)
pip install -r requirements.txt
streamlit run app.py                    ::  http://localhost:8501

:: Same pipeline, headless (writes every deliverable into output\)
python src\workflow.py --approve        ::  auto-approve for demos
python src\workflow.py                  ::  interactive y/N at the terminal
python src\workflow.py --reject         ::  prove the gate blocks everything
python src\workflow.py --llm            ::  AI drafting via Groq (needs GROQ_API_KEY)

:: Pieces on their own
python src\data_quality.py              ::  Step 0 gate on the CSV, writes report
python scripts\generate_reviews.py      ::  regenerate/expand the corpus (seeded)
python src\mcp_client.py --payload output\mcp_payload.json --approve
```

**Environment.** Copy `.env.example` → `.env` and fill in your Groq key.
`.env` is gitignored — only the example is committed, so pushing this repo never
ships a key. On Streamlit Community Cloud, paste the same lines into
*App settings → Secrets* (`.streamlit/secrets.toml.example`). Without a key
everything still runs; the deterministic writers are the default and the LLM
path validates its drafts and falls back automatically.

## 2. Where the MCP approval happens

**Two layers, and the one that matters is the server.**

1. **Client layer** (`src/mcp_client.py`, and the 🔐 Approve & Log tab in the
   app): shows the exact previews the server returned and asks a human `y/N`
   (or button click).
2. **Server layer** (`src/mcp_server.py`): a `tools/call` **without** an
   `approval_token` does not execute. It returns
   `{status: "approval_required", approval_token, preview}` and writes nothing.
   The token is `HMAC-SHA256(per-process-secret, tool-name | canonical-arguments)`:

   - **payload-bound** — approve one payload, then edit a single field → refused
     ("token does not match these exact arguments")
   - **single-use** — replaying an executed token → refused ("token already used")
   - **per-process secret** — tokens cannot survive a server restart

After approval each tool executes exactly once; every call (requested /
executed / refused) lands in `output/mcp_audit_log.jsonl`, and the app shows the
live transcript including the two gate proofs it runs in front of you.

Tools exposed: `append_to_product_notes` (appends the structured entry — date,
top themes, weekly pulse, identified fee issue, explanation bullets, source
links — to `product_pulse/product_notes.md`) and `create_email_draft` (writes
`.md` + `.eml` with `X-Unsent: 1`, so a mail client opens it as an editable
draft; there is no send path in the codebase).

## 3. What fee issue the reviews identified

**Exit load on mutual fund redemption** — detected from the data, not hard-coded.
Every review is scanned for fee terms × explicit confusion signals ("never told",
"hidden", "surprise", "no warning", "found out by googling"…), and charges are
scored **mentions × confusion-rate** (raw volume alone always picks the
best-known charge; raw confusion-count picks charges two people mentioned).

On the shipped 500-review corpus (2026-08-02 → 2026-10-18, all quality checks
green):

| Fee | Mentions | Confused | Rate | Score |
| --- | --- | --- | --- | --- |
| **Exit load on mutual fund redemption** | **52** | **38** | 73% | **38.0** |
| DP (Depository Participant) charge | 21 | 15 | 71% | 15.0 |
| Intraday brokerage & statutory charges | 48 | 8 | 17% | 8.0 |

Users redeem short-holding funds unaware the **scheme** (not Groww) deducts an
exit load, discover it when the credited amount is below `NAV × units`, then
open tickets. The generated explainer answers exactly that — what it is, when it
applies, how it is calculated, that an approximate amount is shown on the redeem
screen — with two official Groww help-center links and a **Last checked** date.

## 4. Data quality (Step 0)

Before any analysis, the CSV passes a gate (`src/data_quality.py`): required
fields present, no duplicate ids, **no duplicate content** (normalized-text
match, so "Great app!!" and "great app" cannot both survive), parseable
in-window dates, integer ratings 1–5, source whitelist, minimum text length,
encoding artifacts. The report lands in `output/data_quality_report.json` and is
shown in the app's 🧪 tab. The corpus itself is generated deterministically by
`scripts/generate_reviews.py` (seeded, uniqueness enforced) and re-checked by
the same gate before it is written.

## 5. Optional AI drafting (Groq)

`--llm` (CLI) or the sidebar checkbox (app) lets Groq draft the human-sounding
parts — the key observation, the three action ideas, and the explainer bullets.
Everything *counted* (themes, counts, verbatim quotes, the detected fee) stays
computed and is fed to the model as an evidence pack. Drafts must pass
validation (≤250 words, quotes unchanged and verbatim, computed numbers present,
3–6 bullets, no advice words, no invented ₹ figures) — one retry with the failed
checks listed, then silent fallback to the deterministic writers. The key lives
in memory for the tab / `.env` locally; it is never committed and never sent to
anywhere but the provider you chose.

## 6. Deploying the web app

**Locally:** `streamlit run app.py` (steps above).

**Streamlit Community Cloud (free):**
1. Push this repo to GitHub (see the remote already configured, or yours).
2. Go to [share.streamlit.io](https://share.streamlit.io) → *Create app* → pick
   the repo, `app.py` as the main file, Python 3.13.
3. *App settings → Secrets* → paste the contents of `.env.example` with your
   real values.
4. Deploy. The MCP server runs as a subprocess of the app process on the
   container, so the approval gate works there exactly as it does locally.

## 7. Wiring a real email tool (optional, your call)

Default: local `.eml` drafts, zero credentials, nothing can send. If you want
real Gmail drafts via MCP, send me any ONE of these and I'll add it as another
approval-gated tool in `src/mcp_server.py` (it would go through the same token
gate):

- **Gmail MCP server** — the command + OAuth client credentials (or run it
  yourself and give me the launch command for `GMAIL_MCP_COMMAND`)
- **Zapier MCP** — a connector token (Zapier's MCP endpoint supports Gmail
  draft actions)
- **Make.com** — a scenario webhook URL that creates a Gmail draft

The env hooks already exist in `.env.example`; nothing sends without passing the
same human approval.

## 8. Design notes & layout

```
D:\Milestone5
├── app.py                        # Streamlit UI (colorful; approval gate as buttons)
├── data/groww_reviews.csv        # 500 clean reviews (Step 0 verified)
├── docs/SOURCES.md               # 6 official source URLs
├── product_pulse/product_notes.md# internal doc — entries appended via MCP only
├── scripts/generate_reviews.py   # seeded corpus generator (uniqueness enforced)
├── src/
│   ├── data_quality.py           # Step 0 gate: dedupe, blanks, dates, ratings, sources
│   ├── review_intelligence.py    # Step 1: 5-theme clustering, quotes, fee-confusion score
│   ├── generators.py             # Steps 2+3: pulse ≤250w, explainer ≤6 bullets
│   ├── llm.py                    # Groq client (stdlib urllib, .env loader)
│   ├── ai_drafts.py              # checks-not-trust AI writer (validate → retry → fallback)
│   ├── mcp_server.py             # MCP server: JSON-RPC stdio + server-side HMAC gate
│   ├── mcp_client.py             # MCP client: previews, human decision, transcript
│   └── workflow.py               # orchestrator (CLI + run_steps() used by the app)
├── .env.example                  # copy to .env (gitignored) — never commit keys
└── output/                       # all generated artifacts (gitignored)
```

- **Deterministic by default** — same CSV in, same pulse, same fee out; the LLM
  only adds wording where a person would write, and cannot break limits.
- **Traceable** — quotes are verbatim CSV text with id/source/date; every
  explainer bullet cites an official source; the approver sees the exact payload.
- **Safe by construction** — server-side token gate, single-use, tamper-proof;
  email draft-only; notes append-only; rejections leave zero side effects.

---

Not affiliated with, endorsed by, or connected to Groww. Reviews are synthetic
but modeled on public app-review patterns, for study. Nothing here is investment
advice.
