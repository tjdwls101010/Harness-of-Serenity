# Harness of Serenity Wiki

Harness of Serenity is a research harness for supply-chain-first equity analysis. Its practical goal is simple: make an analyst or coding agent start from decision-grade evidence, then reason about where value structurally concentrates before consensus prices it.

## Why It Exists

Most market writeups collapse three different jobs into one stream of prose:

1. Gather numbers.
2. Interpret structure.
3. Decide what the price already reflects.

This project splits those jobs. The code gathers and validates evidence. The analyst owns the judgment.

That split matters because a verdict encoded in code can drift silently. A deterministic pipeline should say what the filing, market data, and macro sources show. It should not say whether a stock is a buy, whether a name is a chokepoint, or what conviction should be.

## What You Can Use It For

- Build repeatable evidence dossiers for US-listed equities.
- Compare tickers with a side-by-side evidence view.
- Keep SEC filing facts separate from promotional narrative.
- Validate that the harness still keeps judgment out of code.
- Use the methodology files as a structured operating system for an analyst agent.

## Key Pages

- [Getting Started](Getting-Started.md)
- [Architecture](Architecture.md)
- [Pipeline Reference](Pipeline-Reference.md)
- [Release Process](Release-Process.md)

## Main Surfaces

| Surface | Use |
| --- | --- |
| `scripts/serenity_pipeline.py macro` | Raw macro gauges. |
| `scripts/serenity_pipeline.py analyze TICKER` | Single-name evidence dossier. |
| `scripts/serenity_pipeline.py discover TKR1 TKR2 ...` | Comparator for multiple names. |
| `scripts/serenity_filings.py ...` | Deterministic filing and XBRL reads. |
| `scripts/serenity_harness.py validate` | Structural self-check. |

## Operating Principle

Code loads facts. The analyst judges.

Everything else in the repository is organized around that boundary.
