<p align="center">
  <img src="https://raw.githubusercontent.com/tjdwls101010/tjdwls101010/main/Images/Harness%20of%20Serenity.png" alt="Harness of Serenity" width="640">
</p>

<h1 align="center">Harness of Serenity</h1>

<p align="center">
  <em>A research harness that makes deterministic code load the facts and leaves every judgment to the analyst.</em>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue.svg" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/status-personal%20research%20tool-orange.svg" alt="Status: personal research tool">
</p>

---

## What this is

Ask a language model "is $NVDA a buy?" and it will happily quote you a market cap. The number
might be last quarter's. It might belong to a different company that shares the ticker prefix.
Nothing downstream will catch it, because a wrong number that *looks* right reads exactly like a
right one — and it inverts the conclusion silently.

Harness of Serenity fixes that by drawing one hard line through the middle of equity research:

- **Code loads facts.** A deterministic Python pipeline pulls market data, macro gauges, and SEC
  filing disclosures and emits them as JSON. Same inputs, same bytes, every run. Identity pinned:
  the right ticker, the right period.
- **The analyst judges.** Whether a company owns a real chokepoint, which valuation lens its
  capital structure demands, what the price already reflects — none of that lives in code, ever.

The split is enforced mechanically, not by convention. A validator replays sixteen frozen
fixtures and fails if a single verdict-shaped key (`rating`, `risk_score`, `regime`,
`objective_screen`) leaks into the evidence layer. That is the whole idea: a judgment baked into
code drifts silently run to run, and one stale criterion among a hundred can invert a call
without anyone noticing.

> **This is research tooling, not financial advice.** It structures analysis; it does not
> outsource it. See [Disclaimer](#disclaimer).

## Why the boundary is the point

Most analysis tools blur three separate jobs into one stream of output: gathering numbers,
interpreting structure, and deciding what the price already reflects. Blur them and you cannot
tell which step was wrong when the call misses.

This repository splits them and keeps them split:

| The code may emit | The code must never emit |
| --- | --- |
| market cap, price, multiples, margins | a buy/sell rating |
| cash, debt, total assets, inventory | an archetype tag ("this is a chokepoint") |
| raw macro gauges (VIX, net liquidity, ERP) | a regime label ("risk-on") |
| SEC filing facts, quoted and cited | a conviction score or price target |
| side-by-side comparison metrics | a ranking verdict |

## Highlights

- **One JSON evidence surface** — `macro`, `analyze TICKER`, `discover A B C`, and an offline
  `evidence --fixture` replay, all from a single CLI.
- **27 data modules** behind it, each a standalone subprocess that fails into structured JSON
  rather than a traceback, so one dead upstream never takes down a whole dossier.
- **A separate SEC layer** (`serenity_filings.py`) that reproduces filing numbers byte-stably via
  edgartools XBRL with the concept cited — no LLM anywhere in the extraction path.
- **A self-check that actually runs** — `serenity_harness.py validate` performs 15 structural
  checks including a full replay of every golden fixture against the judgment-free contract.
- **An agent harness on top** — an always-on reasoning spine, three focused skills, two
  subagents, and four lifecycle hooks that enforce evidence discipline at runtime.
- **Reproducibility measurement** — a seeded, stratified eval that scores whether the harness
  reproduces the *method* on real past cases, deliberately grading moves rather than numbers.

## Quick start

**Prerequisites:** Python 3.12 or newer (the evidence layer uses PEP 695 type aliases), Git, and
network access. A free [FRED API key](https://fred.stlouisfed.org/docs/api/api_key.html) unlocks
the macro gauges; everything else works without a key.

```bash
git clone https://github.com/tjdwls101010/Harness-of-Serenity.git
cd Harness-of-Serenity

python3 -m venv scripts/.venv
scripts/.venv/bin/pip install -r scripts/requirements.txt
cp .env.example .env          # then add FRED_API_KEY and EDGAR_IDENTITY
```

Confirm the harness is wired correctly — this needs no network and no keys:

```bash
scripts/.venv/bin/python scripts/serenity_harness.py validate
```

A healthy run reports `"ok": true` with 15 passing checks. Now pull a real evidence dossier:

```bash
scripts/.venv/bin/python scripts/serenity_pipeline.py analyze TSM
```

You get one JSON object: `key_facts` (market cap, price, margins, float, short interest),
`fundamental_inputs`, `valuation_inputs`, `market_structure_inputs`, `catalyst_inputs`, and
`filing_evidence` — plus an `evidence_contract` block declaring in-band that judgment belongs to
you, not to the code that produced the payload.

**Do not truncate that output.** The fields most tempting to cut — financing terms, country
revenue share, inventory composition — are usually the ones a thesis turns on.

## Usage overview

```bash
PY=scripts/.venv/bin/python

# Raw macro gauges — no regime label, deliberately
$PY scripts/serenity_pipeline.py macro

# Full single-name dossier
$PY scripts/serenity_pipeline.py analyze NVDA

# Batch: run macro once, then reuse it across names
$PY scripts/serenity_pipeline.py analyze AVGO --skip-macro

# Side-by-side comparator (routing, not a ranking verdict)
$PY scripts/serenity_pipeline.py discover TSM ASML ARM

# SEC filings: numbers and text, deterministically
$PY scripts/serenity_filings.py segments TSM --axis StatementGeographicalAxis
$PY scripts/serenity_filings.py section TSM --form 10-K --named business
```

Flag-by-flag detail lives in the [Pipeline Reference](docs/wiki/Pipeline-Reference.md) and
[Filings and SEC](docs/wiki/Filings-and-SEC.md) pages.

## Documentation

The full documentation lives in **[docs/wiki](docs/wiki/README.md)**. Start here:

| Page | For |
| --- | --- |
| [Overview](docs/wiki/Overview.md) | The problem, the approach, and the non-goals |
| [Getting Started](docs/wiki/Getting-Started.md) | Install → configure → first dossier, end to end |
| [Concepts](docs/wiki/Concepts.md) | The vocabulary: evidence contract, archetype, lens, gates |
| [Architecture](docs/wiki/Architecture.md) | How the layers fit and how a run flows through them |
| [Pipeline Reference](docs/wiki/Pipeline-Reference.md) | Every subcommand, flag, and output field |
| [Known Limitations](docs/wiki/Known-Limitations.md) | Verified defects and rough edges, stated plainly |

## Project status

A working personal research harness, published because the pattern it demonstrates — a
mechanically enforced boundary between deterministic evidence and model judgment — generalizes
well beyond equities.

**What that means for you:** it works and it is used, but there is no CI, no stability guarantee,
no release cadence, and no support commitment. Interfaces may change without a deprecation
period. Fork it freely; pin a commit if you depend on it.

Pull requests are welcome. There is exactly one rule a contribution must not break: deterministic
code may load, normalize, and verify facts, but it may never emit a verdict, score, archetype
tag, regime label, or rating.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) for setup, the test commands, and the boundary rule every
PR is checked against. By participating you agree to the
[Code of Conduct](CODE_OF_CONDUCT.md). To report a security issue, follow
[SECURITY.md](SECURITY.md) rather than opening a public issue.

## License

Released under the MIT License. See [LICENSE](LICENSE).

## Disclaimer

Harness of Serenity is educational and research infrastructure. It does not provide investment,
legal, tax, or financial advice, and it makes no guarantee of data availability, data accuracy,
or investment outcomes. Market data comes from third-party sources that can be delayed,
incomplete, or wrong. Every output is an input to your own judgment — verify anything you would
act on.
