# Getting Started

From a fresh clone to a verified first evidence dossier. Follow only this page and you will reach
a working state.

## Prerequisites

| Requirement | Why |
| --- | --- |
| **Python 3.12+** | `scripts/pipeline/_evidence.py` uses PEP 695 `type` aliases. Older interpreters fail at import with a `SyntaxError`. |
| **Git** | To clone. |
| **Network access** | Every live command reaches yfinance, FRED, CBOE, or SEC EDGAR. The validator and fixture replay work fully offline. |
| **A C toolchain** | Only if a wheel is unavailable for your platform — `lxml` and `numpy` occasionally build from source. |

Optional but recommended:

| Credential | Unlocks | Cost |
| --- | --- | --- |
| [FRED API key](https://fred.stlouisfed.org/docs/api/api_key.html) | Rates, inflation, net liquidity, and ERP gauges | Free, instant |
| SEC EDGAR identity | Compliant EDGAR access — SEC policy requires a contact string | Free, it is just your name and email |

## Install

```bash
git clone https://github.com/tjdwls101010/Harness-of-Serenity.git
cd Harness-of-Serenity

python3 -m venv scripts/.venv
scripts/.venv/bin/pip install -r scripts/requirements.txt
```

> **Keep the virtualenv at `scripts/.venv`.** It is not merely a convention — `.claude/settings.json`
> references that exact interpreter path when wiring the lifecycle hooks. A venv anywhere else
> silently disables them, with no error.

Verify the interpreter version:

```bash
scripts/.venv/bin/python --version    # must be 3.12 or newer
```

## Configure

```bash
cp .env.example .env
```

Then edit `.env`:

```bash
# Macro gauges: rates, inflation, net liquidity, ERP
FRED_API_KEY=your_key_here

# SEC EDGAR compliance — "Name email@example.com"
EDGAR_IDENTITY="Jane Doe jane@example.com"
```

### Every environment variable

| Variable | Read by | Effect if unset |
| --- | --- | --- |
| `FRED_API_KEY` | `modules/rates.py`, `inflation.py`, `net_liquidity.py`, `erp.py` | Those gauges are **dropped from the output silently** — the key simply does not appear. See the warning below. |
| `EDGAR_IDENTITY` | `scripts/serenity_filings.py` | Falls back to a built-in default identity. EDGAR still works, but requests are attributed to the maintainer's contact rather than yours. |
| `GOOGLE_API_KEY`, `GOOGLE_MODEL`, `GOOGLE_THINKING_LEVEL` | Nothing in the current tree | No effect. Reserved for optional narrative enrichment. |
| `X_AUTH_TOKEN`, `X_CT0`, `X_TWID` | Nothing in this repository | No effect. Listed for an out-of-tree scraper that produced the thesis DB. Treat as account credentials if you ever populate them. |
| `SERENITY_CAPTURE_DIR` | `pipeline/legacy/_commands.py` | Only used when regenerating golden fixtures. |
| `CLAUDE_PROJECT_DIR` | All four hooks | Set by Claude Code automatically. Hooks fall back to the current working directory. |

> ⚠️ **Known issue — `.env` is not auto-loaded for macro modules.** The macro data modules read
> `os.environ` directly and never call `load_dotenv`, so a `FRED_API_KEY` sitting in `.env` is
> **not** picked up by `serenity_pipeline.py macro`. The affected gauges are then dropped from the
> payload, which is indistinguishable from a genuinely unavailable reading.
>
> **Workaround** — export it into the shell environment:
>
> ```bash
> export $(grep -v '^#' .env | grep FRED_API_KEY | xargs)
> scripts/.venv/bin/python scripts/serenity_pipeline.py macro
> ```
>
> Or put `export FRED_API_KEY=...` in your shell profile. `serenity_filings.py` is unaffected — it
> does load `.env`. Tracked in [Known Limitations](Known-Limitations.md#env-is-not-loaded-for-macro-modules).

`.env` is gitignored. Never commit it. `.env.example` is the template and holds no live values.

## Step 1 — Validate the harness

Do this first. It needs no network and no keys, so it isolates installation problems from data
problems.

```bash
scripts/.venv/bin/python scripts/serenity_harness.py validate
```

Expected:

```json
{
  "harness": "serenity",
  "ok": true,
  "summary": { "pass": 15, "warn": 0, "fail": 0 },
  "checks": [ { "check": "claude_md", "status": "pass" }, ... ]
}
```

`"ok": true` with 15 passes means the spine is present, the skills parse, the pipeline imports,
and — the substantive part — all 16 golden fixtures replay through the evidence builder without a
single judgment-shaped key or value leaking through.

Add `--verbose` to see detail for passing checks too. Warnings never fail the run; only hard
failures exit non-zero. If it does not come back green, jump to
[Troubleshooting](Troubleshooting.md).

## Step 2 — Replay a fixture (still offline)

Before spending a network round trip, confirm the evidence layer produces what you expect:

```bash
scripts/.venv/bin/python scripts/serenity_pipeline.py evidence \
  --fixture scripts/tests/golden/AAOI.inputs.json
```

This replays a frozen payload captured from a live run. `build_evidence()` is a pure function of
its input, so the output is byte-stable — the same JSON every time, on any machine. You should see
nine top-level keys beginning with:

```json
{
  "evidence_contract": {
    "kind": "serenity_evidence",
    "judgment_owner": "agent",
    "code_role": "load_and_normalize_evidence",
    "boundary": "No verdicts, portfolio actions, numeric conviction scores, ..."
  },
  "ticker": "AAOI",
  ...
}
```

That `evidence_contract` block travels with every payload. It is the data layer stating in-band
that it has not decided anything.

## Step 3 — Your first live dossier

```bash
scripts/.venv/bin/python scripts/serenity_pipeline.py analyze TSM
```

This takes roughly 30–90 seconds. It fans out about two dozen subprocesses across yfinance, FRED,
CBOE, and SEC EDGAR, then normalizes everything into one JSON object.

### How to read what comes back

| Key | Holds |
| --- | --- |
| `evidence_contract` | The in-band boundary declaration |
| `ticker` | The resolved symbol, upper-cased |
| `macro_inputs` | Raw macro gauges — `null` with `--skip-macro` |
| `key_facts` | Market cap, price, 52-week range, shares, float, short interest, margins, ownership |
| `fundamental_inputs` | Revenue trajectory, margins, dilution, debt and cash, capex |
| `valuation_inputs` | Forward P/E, PEG, no-growth valuation, analyst targets, EV multiples |
| `market_structure_inputs` | Institutional holders, relative strength, short-interest depth, insider flow, volatility |
| `catalyst_inputs` | Next report, earnings surprise history, estimate revisions |
| `filing_evidence` | SEC dossier and absence flags — see the note in [Pipeline Reference](Pipeline-Reference.md#filing_evidence) |

Every field is documented in the [Pipeline Reference](Pipeline-Reference.md#the-analyze-output-schema).

> **Do not truncate the output.** The fields most tempting to cut — financing terms, country
> revenue share, inventory composition — are usually exactly the ones a thesis turns on.

### Verify it worked

Pipe through `jq` and check that the anchor numbers are present and sane:

```bash
scripts/.venv/bin/python scripts/serenity_pipeline.py analyze TSM \
  | jq '{ticker, mc: .key_facts.marketCap, price: .key_facts.currentPrice,
          gm: .key_facts.grossMargins, ev_rev: .valuation_inputs.ev_multiples.ev_to_revenue}'
```

A healthy result has a non-null market cap and price. If `key_facts` comes back nearly empty, the
upstream data source failed for that ticker — the pipeline degrades to missing fields rather than
crashing, which is deliberate but does mean an empty result is a real signal. See
[Troubleshooting](Troubleshooting.md#key_facts-is-empty-or-nearly-empty).

## Step 4 — Batch work

Macro data is the slowest part of a run and identical across names, so fetch it once:

```bash
PY=scripts/.venv/bin/python

$PY scripts/serenity_pipeline.py macro > macro.json
$PY scripts/serenity_pipeline.py analyze TSM  --skip-macro > tsm.json
$PY scripts/serenity_pipeline.py analyze ASML --skip-macro > asml.json
$PY scripts/serenity_pipeline.py analyze ARM  --skip-macro > arm.json
```

With `--skip-macro`, `macro_inputs` is `null` and the run is meaningfully faster.

To put several names side by side on normalized metrics:

```bash
$PY scripts/serenity_pipeline.py discover TSM ASML ARM
```

`discover` returns each candidate on the same 18 fields plus a `missing_data` map naming exactly
which fields were unavailable per ticker. Candidates come back in **input order** — there is no
sort, because sorting would be ranking, and ranking is a judgment. It is a routing aid.

## Step 5 — Read a filing

When a thesis depends on who the customers are, where revenue is earned, or how something is
financed, the income statement will not tell you. The filing will:

```bash
PY=scripts/.venv/bin/python

# Identity and basic facts
$PY scripts/serenity_filings.py company TSM

# Geographic revenue split, straight from XBRL
$PY scripts/serenity_filings.py segments TSM --axis StatementGeographicalAxis

# Customer concentration disclosures
$PY scripts/serenity_filings.py xbrl-facts TSM --concept "Concentration" --dimension MajorCustomersAxis

# The narrative sections
$PY scripts/serenity_filings.py section TSM --form 10-K --named business
$PY scripts/serenity_filings.py filings TSM --form 8-K --limit 5
```

Every command emits JSON, preserves nulls, and **always exits 0** — an EDGAR failure returns
`{"error": "data_unavailable", "detail": "..."}` rather than a traceback, so a caller always gets
parseable output. Full surface in [Filings and SEC](Filings-and-SEC.md).

## Optional — the agent harness

Everything above is a plain Python CLI and works standalone. If you open the repository in
[Claude Code](https://claude.com/claude-code), an additional layer activates automatically:

- `CLAUDE.md` loads as the always-on reasoning spine.
- Three skills load on demand for macro, discovery, and single-name analysis.
- Four lifecycle hooks fire — a session-start health check, a prompt-time evidence reminder, a
  post-`analyze` arithmetic audit, and a pre-answer structural gate.

Confirm the hooks behave correctly:

```bash
scripts/.venv/bin/python .claude/hooks/tests/run_fixtures.py
# → 22/22 fixtures passed
```

See [Agent Harness](Agent-Harness.md) and [Hooks Reference](Hooks-Reference.md). None of it is
required to use the pipeline.

## Where to go next

| If you want to | Read |
| --- | --- |
| Understand the vocabulary these docs use | [Concepts](Concepts.md) |
| Know every flag and output field | [Pipeline Reference](Pipeline-Reference.md) |
| See which module fetches what, from where | [Data Modules](Data-Modules.md) |
| Understand why the code is split this way | [Architecture](Architecture.md) |
| Fix something that went wrong | [Troubleshooting](Troubleshooting.md) |
| Know what is currently broken | [Known Limitations](Known-Limitations.md) |

---

**Next:** [Concepts](Concepts.md) · [Back to index](README.md)
