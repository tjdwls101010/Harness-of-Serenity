# Harness of Serenity — Documentation

This is the full documentation for Harness of Serenity, a research harness that separates
**deterministic evidence collection** from **analytical judgment** and enforces the separation
mechanically.

If you have not read the [project README](../../README.md) yet, start there for the one-minute
version. If you have, **[Getting Started](Getting-Started.md)** takes you from a fresh clone to
your first evidence dossier.

## Table of contents

### Start here

| Page | What it covers |
| --- | --- |
| [Overview](Overview.md) | The problem this solves, the approach, who it is for, and the explicit non-goals |
| [Getting Started](Getting-Started.md) | Prerequisites, install, configuration, and a verified first run |
| [Concepts](Concepts.md) | The vocabulary — evidence contract, archetype, valuation lens, winner gates, the session archive |

### The deterministic layer

| Page | What it covers |
| --- | --- |
| [Architecture](Architecture.md) | How the layers fit, how an `analyze` run flows through them, and why the boundary sits where it does |
| [Pipeline Reference](Pipeline-Reference.md) | Every subcommand and flag, plus the complete output schema field by field |
| [Data Modules](Data-Modules.md) | All 27 modules behind the pipeline, what each fetches and from which external source |
| [Filings and SEC](Filings-and-SEC.md) | The `serenity_filings.py` CLI, edgartools usage, and the EDGAR identity rules |

### The judgment layer

| Page | What it covers |
| --- | --- |
| [Agent Harness](Agent-Harness.md) | The reasoning spine, three skills, two subagents, and the rank-N protocol |
| [Hooks Reference](Hooks-Reference.md) | All four lifecycle hooks and their block/warn/silent contracts |
| [Session Archive](Session-Archive.md) | How analyses are persisted, the scorecard schema, and the two reuse rules |

### Verification and operations

| Page | What it covers |
| --- | --- |
| [Testing and Validation](Testing-and-Validation.md) | The 15 validator checks, 16 golden fixtures, and 22 hook fixtures |
| [Eval Harness](Eval-Harness.md) | Measuring whether the harness reproduces the method, not just the format |
| [Troubleshooting](Troubleshooting.md) | Common failures mapped to fixes |
| [Known Limitations](Known-Limitations.md) | Verified defects and rough edges, stated plainly |
| [Release Process](Release-Process.md) | Versioning, the release checklist, and the change-history convention |

## The one-paragraph version

Most equity analysis blurs three jobs into one stream of output: gathering numbers, interpreting
structure, and deciding what price already reflects. Blur them and a wrong number in step one
propagates invisibly into a confident verdict in step three. Harness of Serenity splits them.
Python loads facts — market data, macro gauges, SEC disclosures — into JSON whose identity is
pinned and whose shape is contract-tested. Everything interpretive stays in the analyst's hands,
supported by a documented method but never automated. A validator fails the build if judgment
leaks into the data layer.

## Repository map

| Path | What lives there |
| --- | --- |
| `CLAUDE.md` | The always-on reasoning spine — doctrine, routing, answer contract, non-negotiables |
| `.claude/skills/` | Three focused skills: `serenity-macro`, `serenity-discovery`, `serenity-analysis` |
| `.claude/agents/` | Two subagents: `serenity-filings` (reads filings), `serenity-scorecard` (fills one ranking scorecard) |
| `.claude/hooks/` | Four lifecycle hooks that enforce evidence discipline at runtime, plus their fixtures |
| `scripts/serenity_pipeline.py` | The main evidence CLI: `macro`, `analyze`, `discover`, `evidence` |
| `scripts/pipeline/` | The evidence builder, fetch orchestration, and the quarantined `legacy/` pipeline |
| `scripts/modules/` | 27 standalone data-fetching CLIs invoked as subprocesses |
| `scripts/serenity_filings.py` | Deterministic edgartools wrapper for SEC numbers and text |
| `scripts/serenity_harness.py` | The structural validator (`validate`) and ranking differ (`rankdiff`) |
| `scripts/serenity_eval.py`, `scripts/eval/` | Reproducibility measurement |
| `scripts/tests/golden/` | 16 frozen input payloads and their blessed expectations |
| `sessions/` | The analysis archive — one folder per saved session |
| `docs/wiki/` | These pages |

## Conventions in these docs

- Commands assume the repository root as the working directory and the project virtualenv at
  `scripts/.venv`. Many examples abbreviate it as `PY=scripts/.venv/bin/python`.
- Code references use `path/to/file.py:LINE` so you can jump straight to the source.
- Where a documented behavior differs from what the code currently does, the difference is
  recorded in [Known Limitations](Known-Limitations.md) rather than papered over.

---

**Next:** [Overview](Overview.md) — the problem, the approach, and the non-goals.
