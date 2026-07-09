# Pipeline Reference

The pipeline is the deterministic evidence surface. It loads data and emits JSON. It does not decide.

## Command Overview

```bash
scripts/.venv/bin/python scripts/serenity_pipeline.py macro
scripts/.venv/bin/python scripts/serenity_pipeline.py analyze TICKER
scripts/.venv/bin/python scripts/serenity_pipeline.py analyze TICKER --skip-macro
scripts/.venv/bin/python scripts/serenity_pipeline.py discover TKR1 TKR2 ...
scripts/.venv/bin/python scripts/serenity_pipeline.py evidence --fixture FILE --ticker TICKER
```

## `macro`

Returns raw macro gauges and related context. It intentionally does not label the regime.

```bash
scripts/.venv/bin/python scripts/serenity_pipeline.py macro
```

Use it before single-name work when the market environment or a catalyst matters.

## `analyze`

Returns a full single-name evidence dossier.

```bash
scripts/.venv/bin/python scripts/serenity_pipeline.py analyze TICKER
```

Use `--skip-macro` for batch work after a macro read:

```bash
scripts/.venv/bin/python scripts/serenity_pipeline.py analyze TICKER --skip-macro
```

The output is the source for objective facts such as market cap, price, valuation multiples, margins, debt, cash, total assets, inventory, and related evidence fields.

## `discover`

Runs a side-by-side comparator across tickers.

```bash
scripts/.venv/bin/python scripts/serenity_pipeline.py discover TKR1 TKR2 TKR3
```

This command helps route attention. It is not a ranking verdict.

## `evidence`

Replays a frozen fixture for testing and validation.

```bash
scripts/.venv/bin/python scripts/serenity_pipeline.py evidence --fixture scripts/tests/golden/AXTI.inputs.json --ticker AXTI
```

Use this when changing evidence code or validating fixture behavior.

## Filing CLI

`scripts/serenity_filings.py` is the deterministic EDGAR surface.

Examples:

```bash
scripts/.venv/bin/python scripts/serenity_filings.py company TICKER
scripts/.venv/bin/python scripts/serenity_filings.py financials TICKER
scripts/.venv/bin/python scripts/serenity_filings.py filings TICKER --form 10-K --limit 3
scripts/.venv/bin/python scripts/serenity_filings.py section TICKER --form 10-K --named business
scripts/.venv/bin/python scripts/serenity_filings.py segments TICKER --axis StatementGeographicalAxis
scripts/.venv/bin/python scripts/serenity_filings.py xbrl-facts TICKER --concept "Concentration" --limit 20
```

Use this surface when a thesis depends on filing-native facts:

- named customers
- suppliers
- partners
- country or segment revenue
- customer concentration
- inventory composition
- purchase obligations
- ATM, convertible, debt, prepayment, or offtake terms

## Output Discipline

- Treat null as silence, not zero.
- Do not fill missing filing relationships from memory.
- Do not use web snippets for numbers the pipeline can load.
- Preserve the full JSON when using it as evidence.

## Validation

```bash
scripts/.venv/bin/python scripts/serenity_harness.py validate
```

This is the fastest confidence check after changing the evidence layer or documentation that references pipeline behavior.
