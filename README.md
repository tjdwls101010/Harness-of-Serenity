# Harness of Serenity

![Harness of Serenity brand image](https://raw.githubusercontent.com/tjdwls101010/tjdwls101010/refs/heads/main/Images/ChatGPT%20Image%202026%E1%84%82%E1%85%A7%E1%86%AB%207%E1%84%8B%E1%85%AF%E1%86%AF%209%E1%84%8B%E1%85%B5%E1%86%AF%20%E1%84%8B%E1%85%A9%E1%84%92%E1%85%AE%2001_33_21.png)

Harness of Serenity is an open-source evidence harness for supply-chain-first equity analysis. It separates the work into two clean layers:

- **Code loads facts**: deterministic scripts pull market data, macro gauges, filings data, and regression evidence as JSON.
- **The analyst judges**: `CLAUDE.md`, the Serenity skills, hooks, and filing subagent enforce the reasoning method without baking verdicts into code.

The project is built for people who want a repeatable way to ask: where does economic power structurally concentrate, who depends on whom, and what has the market not priced yet?

> This project is research tooling. It is not financial advice. Use it to structure analysis, not to outsource judgment.

## What It Does

Harness of Serenity helps an agent or analyst reconstruct decision-grade evidence before making a market call:

- Runs a deterministic evidence pipeline with `scripts/serenity_pipeline.py`.
- Keeps judgment out of the data layer with `scripts/serenity_harness.py validate`.
- Routes the analyst into focused skills for macro, discovery, and single-name analysis.
- Uses a `serenity-filings` subagent to read SEC filings for objective relationship facts.
- Preserves an explicit discipline: pipeline numbers first, web/search for narrative gaps only, thesis DB only on explicit cross-validation.

## Repository Map

| Path | Purpose |
| --- | --- |
| `CLAUDE.md` | Always-on reasoning spine, answer contract, routing rules, and non-negotiables. |
| `.claude/skills/serenity-analysis/` | Single-name analysis: archetype, winner gates, valuation lens, cycle stage, rating. |
| `.claude/skills/serenity-discovery/` | Discovery: find the under-priced US-listed node before a ticker is obvious. |
| `.claude/skills/serenity-macro/` | Macro/catalyst regime read and aggression dial. |
| `.claude/agents/serenity-filings.md` | Filing reader that extracts facts from SEC filings without rendering judgment. |
| `scripts/serenity_pipeline.py` | Main JSON evidence CLI: `macro`, `analyze`, `discover`, `evidence`. |
| `scripts/serenity_filings.py` | Deterministic edgartools wrapper for SEC company, filing, XBRL, and text reads. |
| `scripts/serenity_harness.py` | Structural validator for the harness and evidence/judgment boundary. |
| `scripts/tests/golden/` | Frozen inputs and expected evidence fixtures. |
| `docs/wiki/` | User-facing wiki pages for setup, architecture, and operating workflows. |

## Quick Start

```bash
git clone https://github.com/tjdwls101010/Harness-of-Serenity.git
cd Harness-of-Serenity

python3 -m venv scripts/.venv
scripts/.venv/bin/pip install -r scripts/requirements.txt
cp .env.example .env
```

Fill in any API keys you need in `.env`. Live macro evidence uses `FRED_API_KEY`; SEC commands use `EDGAR_IDENTITY` when present and otherwise fall back to the neutral identity configured in `scripts/serenity_filings.py`.

Validate the harness:

```bash
scripts/.venv/bin/python scripts/serenity_harness.py validate
```

Run evidence commands:

```bash
scripts/.venv/bin/python scripts/serenity_pipeline.py macro
scripts/.venv/bin/python scripts/serenity_pipeline.py analyze TSM
scripts/.venv/bin/python scripts/serenity_pipeline.py analyze TSM --skip-macro
scripts/.venv/bin/python scripts/serenity_pipeline.py discover TSM ASML ARM
scripts/.venv/bin/python scripts/serenity_pipeline.py evidence --fixture scripts/tests/golden/AXTI.inputs.json --ticker AXTI
```

All pipeline output is JSON. Do not truncate it when using it as evidence for a thesis.

## Core Workflow

1. **Start with the shape of value capture.** Is this a physical chokepoint, a profit pool being drained, or an emerging standard?
2. **Run the pipeline first.** Use `macro`, `analyze`, or `discover` before reasoning from numbers.
3. **Pull filings when relationships matter.** Use the `serenity-filings` subagent or `scripts/serenity_filings.py` when the thesis depends on named customers, suppliers, financing, country exposure, or critical inputs.
4. **Run the valuation lens, not just the label.** Show the arithmetic and tie each input back to evidence.
5. **Separate thesis, timing, vehicle, and kill condition.** A good business thesis is not automatically a good entry.

## Common Commands

```bash
# Validate harness structure and evidence invariants
scripts/.venv/bin/python scripts/serenity_harness.py validate

# Raw macro gauges only, no regime label
scripts/.venv/bin/python scripts/serenity_pipeline.py macro

# Full single-name evidence dossier
scripts/.venv/bin/python scripts/serenity_pipeline.py analyze TICKER

# Side-by-side comparator across tickers
scripts/.venv/bin/python scripts/serenity_pipeline.py discover TKR1 TKR2 TKR3

# Filing numbers and text through edgartools
scripts/.venv/bin/python scripts/serenity_filings.py company TICKER
scripts/.venv/bin/python scripts/serenity_filings.py filings TICKER --form 10-K --limit 3
scripts/.venv/bin/python scripts/serenity_filings.py section TICKER --form 10-K --named business
```

## Documentation

- [Wiki home](docs/wiki/README.md)
- [Getting started](docs/wiki/Getting-Started.md)
- [Architecture](docs/wiki/Architecture.md)
- [Pipeline reference](docs/wiki/Pipeline-Reference.md)
- [Release process](docs/wiki/Release-Process.md)

## Contributing

Contributions should preserve the central boundary: deterministic code may load facts, normalize evidence, and verify contracts, but it must not emit investment verdicts, archetypes, scores, or ratings.

Before opening a pull request:

```bash
scripts/.venv/bin/python scripts/serenity_harness.py validate
```

For code changes, add or update focused tests only where the behavior boundary needs protection. For doctrine or docs changes, make the operating rule more general rather than adding one-off case patches.

## License

Released under the MIT License. See [LICENSE](LICENSE).

## Disclaimer

Harness of Serenity is educational and research infrastructure. It does not provide investment, legal, tax, or financial advice, and it does not guarantee data availability, data accuracy, or investment outcomes.
