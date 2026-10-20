# GrowPulse

[![Streamlit App](https://img.shields.io/badge/Streamlit-Live%20Demo-FF4B4B?logo=streamlit&logoColor=white)](https://growpulse-hxa8i5rqh5gfbnapppppahwi.streamlit.app/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-server--side%20approval%20gate-2E7D6E)](https://modelcontextprotocol.io)

**Raw customer reviews in — a weekly product pulse and a source-linked fee
explainer out, with nothing written until a human approves it.**

GrowPulse turns public Groww app reviews into two deliverables a product and
support team can use the same day:

1. an **internal weekly pulse** (≤ 250 words: top themes, three verbatim quotes,
   one key observation, three action ideas), and
2. a **customer-facing fee explainer** (≤ 6 bullets, facts only, two official
   source links, a *Last checked* date) for the charge users keep misreading.

Both are delivered through **MCP tools whose approval is enforced inside the
server**: a tool call without a valid single-use token returns a preview and
writes nothing. Email is drafted (`.eml` with `X-Unsent: 1`) — never sent.

**Live demo:** https://growpulse-hxa8i5rqh5gfbnapppppahwi.streamlit.app/

---

## Highlights

- **Deterministic core.** The same CSV always produces the same themes, counts,
  quotes and fee ranking. AI drafting is opt-in, validated against the data, and
  falls back silently if it fails any check.
- **Quality gate first.** Every CSV passes a validation gate before analysis —
  blanks, duplicate ids, duplicate content, bad dates, invalid ratings, unknown
  sources, too-short text, encoding artifacts. Drops are counted and reported,
  never silently kept.
- **Server-side approval gate.** Each tool call is bound to a single-use
  `HMAC-SHA256` token computed over the exact arguments. Tampered payloads and
  replayed tokens are refused by the server, and every request lands in an
  append-only audit log.
- **Pain ranking with trends.** Themes are ranked by 1–2★ review volume (not
  theme size), with a last-4-weeks vs previous-4-weeks trend per theme.
- **Checked, not trusted.** The app verifies its own output in the UI: word
  limits, verbatim quotes, bullet counts, links and the last-checked date are
  re-counted from the rendered text and shown as pass/fail checks.
- **Your own data.** Upload any CSV with the schema
  `review_id, date, source, rating, review_text` — bad rows are dropped and
  itemised in the Data Quality tab.

---

## Deliverables

| Deliverable | Location |
| --- | --- |
| Web app (7 pages, approval gate as buttons) | `streamlit run app.py` → http://localhost:8501 |
| Live deployment | [Streamlit Community Cloud](https://growpulse-hxa8i5rqh5gfbnapppppahwi.streamlit.app/) |
| Reviews dataset (1,200 rows, quality-gated) | [data/groww_reviews.csv](data/groww_reviews.csv) |
| Quality-gate fixture (100 rows, 8 injected problems) | [data/alt_reviews_test.csv](data/alt_reviews_test.csv) |
| Weekly product pulse (≤ 250 words) | `output/weekly_pulse_<date>.md` |
| Fee explainer (≤ 6 bullets, 2 official links) | `output/fee_explainer_<date>.md` |
| Notes-doc entry (appended via MCP) | [product_pulse/product_notes.md](product_pulse/product_notes.md) |
| Email draft (`.md` + `.eml`, `X-Unsent: 1`) | `output/drafts/` |
| Data quality report | `output/data_quality_report.json` |
| Approval log (human decisions) | `output/approval_log.json` |
| MCP audit log (requested / executed / refused) | `output/mcp_audit_log.jsonl` |
| Official source list | [docs/SOURCES.md](docs/SOURCES.md) |

---

## Quick start

Requires **Python 3.10+**. The pipeline and MCP server use only the standard
library; `requirements.txt` provides Streamlit for the web app.

```bash
git clone https://github.com/punitpandey7/GrowPulse.git
cd GrowPulse
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Configuration (optional).** Copy `.env.example` to `.env` and add a Groq API
key if you want AI drafting. Without a key everything still runs — the
deterministic writers are the default.

```bash
cp .env.example .env
```

**Run the web app:**

```bash
streamlit run app.py               # http://localhost:8501
```

**Run the pipeline headless (writes every deliverable into `output/`):**

```bash
python src/workflow.py             # interactive y/N approval at the terminal
python src/workflow.py --approve   # auto-approve (demos)
python src/workflow.py --reject    # prove the gate blocks every write
python src/workflow.py --llm       # optional Groq drafting (needs GROQ_API_KEY)
```

**Tests and tooling:**

```bash
python scripts/selftest_ai_drafts.py   # AI-draft validation suite (must pass)
python scripts/make_test_csv.py        # regenerate the 100-row quality fixture
python scripts/generate_reviews.py     # regenerate/expand the demo corpus (seeded)
python src/data_quality.py             # Step 0 gate on its own
```

---

## Pipeline

The CLI and the web app call the **same** `run_steps()` function, so the UI can
never drift from the code the checks run against.

| Step | Module | What it does |
| --- | --- | --- |
| 0 — Quality gate | `src/data_quality.py` | Validates and cleans every row; writes `data_quality_report.json`; analysis stops if the gate fails |
| 1 — Review intelligence | `src/review_intelligence.py` | Five-theme clustering, pain ranking (1–2★ volume + 4v4 trend), verbatim quote selection, fee-confusion scoring |
| 2 — Weekly pulse | `src/generators.py` | ≤ 250 words: themes, quotes, key observation, three actions |
| 3 — Fee explainer | `src/generators.py` | ≤ 6 bullets, facts only, two official links, *Last checked* date |
| 4 — Approval-gated MCP | `src/mcp_server.py`, `src/mcp_client.py` | Two-step approval: preview + single-use token, then exactly-once execution |

### Fee detection

Every review is scanned for fee terms crossed with explicit confusion signals
("never told", "hidden", "surprise", "no warning"…), and charges are scored
**mentions × confusion-rate** — raw volume alone always selects the
best-known charge; raw confusion counts select charges two people mentioned.

On the shipped 1,200-review corpus (2026-08-02 → 2026-10-18, all quality checks
green):

| Fee | Mentions | Confused | Rate | Score |
| --- | --- | --- | --- | --- |
| **Exit load on mutual fund redemption** | **119** | **84** | 71% | **84.0** |
| DP (Depository Participant) charge | 50 | 30 | 60% | 30.0 |
| Intraday brokerage & statutory charges | 184 | 21 | 11% | 21.0 |

Users redeem short-holding funds unaware the **scheme** (not Groww) deducts an
exit load, discover it when the credited amount is below `NAV × units`, then
open tickets. The explainer answers exactly that — what it is, when it applies,
how it is calculated, that an approximate amount is shown on the redeem screen —
citing two official Groww help-centre links.

---

## The approval gate

**Two layers — and the one that matters is the server.**

1. **Client layer** (`src/mcp_client.py`, or the *Approve & Log* tab): shows the
   previews the server returned and asks a human to decide.
2. **Server layer** (`src/mcp_server.py`): a `tools/call` **without** an
   `approval_token` does not execute. It returns
   `{status: "approval_required", approval_token, preview}` and writes nothing.
   The token is `HMAC-SHA256(per-process-secret, tool-name | canonical-arguments)`:

   - **Payload-bound** — approve one payload, then edit a single field → refused
     (*"token does not match these exact arguments"*).
   - **Single-use** — replay an executed token → refused (*"token already used"*).
   - **Per-process secret** — tokens cannot survive a server restart.

After approval each tool executes exactly once. Every call — requested,
executed, refused — is appended to `output/mcp_audit_log.jsonl`, and the app
shows the live transcript, including the replay and tamper proofs it runs after
each approval.

Tools exposed:

- `append_to_product_notes` — appends the structured entry (`date`, `top_themes`,
  `weekly_pulse`, `identified_fee_issue`, `explanation_bullets`, `source_links`)
  to `product_pulse/product_notes.md`.
- `create_email_draft` — writes a `.md` and an `.eml` with `X-Unsent: 1`, so a
  mail client opens it as an editable draft. **There is no send path anywhere in
  the codebase.**

### Using the server from any MCP client

```json
{
  "mcpServers": {
    "growpulse": {
      "command": "python",
      "args": ["C:/path/to/GrowPulse/src/mcp_server.py"]
    }
  }
}
```

The two-step flow works from any MCP client: the first call returns the preview
and token, a human approves, the second call with the token executes exactly once.

---

## Web app

Seven pages built with `st.navigation`, one shared frame, download buttons for
every artefact. The entrypoint (`app.py`) owns the sidebar controls and the
pipeline run; each page lives in `views/`:

| Page | Contents |
| --- | --- |
| **🏠 Home** | Hero, KPI cards (reviews, window, themes, fee confusion, pulse length), quick links, overview chips |
| **📊 Insights** | Reviews-per-theme chart, *Where the pain is* ranking with 4v4 trend arrows, three verbatim quote cards with id/source/date |
| **📝 Pulse** | Word-count meter, live pass/fail checks (limit, quotes, actions, observation, fee named), rendered pulse, `.md` download |
| **💰 Fee Explainer** | Detected-fee banner with signal strength, format checks (bullets/links/date/no-advice), rendered snippet, `.md` download |
| **🔐 Approve & Log** | MCP connection check (handshake only, zero side effects), payload previews, approve/reject buttons, live transcript with gate proofs, run history |
| **📜 History** | Every recorded decision (approve/reject) and the append-only server audit log |
| **🧪 Checks** | Per-check pass/fail table, drop counts, window/rating/source distributions, AI drafting log, server audit log |

Navigation uses `st.navigation`, so `st.session_state["artifacts"]` survives
page switches. (Switching pages by raw URL starts a *new* session and drops the
run — which is why the nav widget, not plain links, is the way to move around.)

The sidebar switches between the bundled 1,200-row corpus and your own CSV
upload, sets the report week (IST-aware so it reads correctly on Cloud, which
runs in UTC), and hides AI drafting behind *Advanced* — the default run is
fully deterministic.

---

## Testing

- `scripts/selftest_ai_drafts.py` — exercises the AI-draft validator (limits,
  verbatim quotes, computed figures, advice words) and must pass.
- `data/alt_reviews_test.csv` — a 100-row fixture with 8 injected problems
  (2 blanks, 3 duplicate-content rows, 1 bad date, 1 unknown source, 1 too-short).
  Upload it in the app: the gate reports **100 → 92** with each drop counted.
- The approval gate is proven on every approved run: the client replays the used
  token and sends a tampered payload; the server refuses both (visible in the
  transcript).

---

## Deployment

**Streamlit Community Cloud (free):**

1. Push this repository to GitHub.
2. [share.streamlit.io](https://share.streamlit.io) → *Create app* → select the
   repository, `app.py` as the main file.
3. *App settings → Secrets* → add `GROQ_API_KEY` (and optionally `GROQ_MODEL`)
   if you want AI drafting in the cloud; without them the app runs deterministically.
4. Deploy. The MCP server runs as a subprocess of the app, so the approval gate
   behaves exactly as it does locally. Writes inside the container are
   ephemeral — the local repository remains the durable record.

---

## Project structure

```
GrowPulse/
├── app.py                      # Streamlit entrypoint: frame, sidebar controls, pipeline run
├── views/                      # one file per page (st.navigation)
│   ├── 01_home.py              #   🏠 hero, KPIs, quick links
│   ├── 02_insights.py          #   📊 themes, pain ranking, quotes
│   ├── 03_pulse.py             #   📝 weekly pulse + live checks
│   ├── 04_fee_explainer.py     #   💰 fee explainer + checks
│   ├── 05_approve.py           #   🔐 approval gate + MCP transcript
│   ├── 06_history.py           #   📜 decisions + server audit log
│   └── 07_checks.py            #   🧪 data-quality gate + distributions
├── data/
│   ├── groww_reviews.csv       # 1,200-row demo corpus (Step 0 verified)
│   └── alt_reviews_test.csv    # 100-row fixture with injected quality problems
├── docs/SOURCES.md             # official source URLs cited by the explainer
├── output/                     # generated artefacts (selected ones committed)
│   ├── weekly_pulse_*.md
│   ├── fee_explainer_*.md
│   ├── insights.json           # themes, trends, quotes, fee ranking
│   ├── mcp_payload.json        # exact payloads sent for approval
│   ├── approval_log.json       # human decisions
│   ├── mcp_audit_log.jsonl     # append-only server-side audit trail
│   └── drafts/                 # .md + .eml drafts (X-Unsent: 1)
├── product_pulse/
│   └── product_notes.md        # internal doc — entries appended via MCP only
├── scripts/
│   ├── generate_reviews.py     # seeded corpus generator
│   ├── make_test_csv.py        # quality-gate fixture generator
│   └── selftest_ai_drafts.py   # AI-draft validation suite
├── src/
│   ├── data_quality.py         # Step 0 gate
│   ├── review_intelligence.py  # Step 1: themes, pain ranking, quotes, fee scoring
│   ├── generators.py           # Steps 2–3: pulse ≤ 250 words, explainer ≤ 6 bullets
│   ├── llm.py                  # Groq client (optional)
│   ├── ai_drafts.py            # validate → retry once → fall back
│   ├── mcp_server.py           # MCP server + server-side HMAC approval gate
│   ├── mcp_client.py           # two-step approval client, transcript, connection check
│   └── workflow.py             # orchestrator: CLI + run_steps()
├── .env.example                # copy to .env (gitignored) — never commit keys
└── requirements.txt
```

### Design principles

- **Deterministic by default** — same CSV in, same pulse out; the LLM only
  words the parts a person would write and cannot break any limit.
- **Traceable** — quotes are verbatim CSV text with id/source/date; every
  explainer bullet cites an official source; the approver sees the exact payload.
- **Safe by construction** — server-side single-use token gate, draft-only
  email, append-only notes doc, rejections leave zero side effects.

---

## Security notes

- `.env` and `.streamlit/secrets.toml` are gitignored; only placeholders live in
  `.env.example`. If a key is ever exposed, **revoke and rotate it** immediately.
- On Streamlit Community Cloud, keys belong in *App settings → Secrets*, never
  in the repository.
- The only network call in the codebase is the optional Groq API request; the
  MCP server itself performs no network I/O.

---



---

Not affiliated with, endorsed by, or connected to Groww. The bundled corpus is
synthetic (generated by `scripts/generate_reviews.py`, seeded) and modelled on
public app-review patterns for study — upload your own CSV for real data.
Nothing here is investment advice.
