# Getting Started

This page gets a fresh clone to the point where the harness can validate itself and emit JSON evidence.

## Requirements

- Python 3.
- Git.
- Network access for live market, macro, and filing data.
- Optional API keys in `.env`.

The repository keeps its Python environment under `scripts/.venv` by convention.

## Install

```bash
git clone https://github.com/tjdwls101010/Harness-of-Serenity.git
cd Harness-of-Serenity

python3 -m venv scripts/.venv
scripts/.venv/bin/pip install -r scripts/requirements.txt
cp .env.example .env
```

Then edit `.env` as needed:

```bash
FRED_API_KEY=...
EDGAR_IDENTITY="Your Name your.email@example.com"
```

`FRED_API_KEY` is required for live macro evidence. SEC identity improves EDGAR compliance and can also be supplied through `EDGAR_IDENTITY`.

## Validate The Harness

```bash
scripts/.venv/bin/python scripts/serenity_harness.py validate
```

A healthy run returns JSON with `"ok": true` and checks for:

- `CLAUDE.md`
- Serenity skill frontmatter
- pipeline imports
- evidence invariants
- macro sanitizer
- SEC layer
- hook wiring

## Run Your First Evidence Dossier

```bash
scripts/.venv/bin/python scripts/serenity_pipeline.py analyze TSM
```

The command returns JSON. Keep the full output when using it as thesis evidence. Seemingly minor fields, such as financing facts or country exposure, can be thesis-critical.

For repeated single-name work after one macro read:

```bash
scripts/.venv/bin/python scripts/serenity_pipeline.py macro
scripts/.venv/bin/python scripts/serenity_pipeline.py analyze TSM --skip-macro
scripts/.venv/bin/python scripts/serenity_pipeline.py analyze ASML --skip-macro
```

## Compare A Basket

```bash
scripts/.venv/bin/python scripts/serenity_pipeline.py discover TSM ASML ARM
```

`discover` is a comparator, not a verdict. It helps route attention; the analyst still decides which name actually clears the structural gate.

## Filing Reads

When a thesis depends on named customers, suppliers, country revenue, purchase obligations, inventory composition, or financing terms, use the filings surface:

```bash
scripts/.venv/bin/python scripts/serenity_filings.py company TSM
scripts/.venv/bin/python scripts/serenity_filings.py filings TSM --form 10-K --limit 3
scripts/.venv/bin/python scripts/serenity_filings.py section TSM --form 10-K --named business
scripts/.venv/bin/python scripts/serenity_filings.py xbrl-facts TSM --concept "Concentration" --limit 20
```

The CLI emits JSON and preserves nulls. If EDGAR is unavailable, it returns a structured `data_unavailable` error instead of a traceback.

## Common Troubleshooting

| Symptom | Check |
| --- | --- |
| Macro data missing | Confirm `FRED_API_KEY` is set in `.env`. |
| SEC reads unavailable | Confirm `EDGAR_IDENTITY`, retry later, and inspect the JSON error. |
| Validation fails | Run with `--verbose` and inspect the failing check. |
| Import errors | Reinstall `scripts/requirements.txt` inside `scripts/.venv`. |

## Next

Read [Architecture](Architecture.md) to understand why the repository is organized around an evidence/judgment boundary.
