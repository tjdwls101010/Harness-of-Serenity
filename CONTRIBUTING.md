# Contributing to Harness of Serenity

Thanks for helping improve this research tool. Useful contributions make facts easier to identify, provenance easier to audit, or research decisions harder to overclaim; they do not move investment judgment into a provider, score, hook, or static pipeline.

## Scope

Good candidates include typed provider adapters, schema/lifecycle fixes, corpus audit improvements, cleanroom/evaluation cases, harness wiring, and documentation corrections. Discuss a new external dependency, a new provider source, or a method/doctrine change before implementing it, because those choices alter the evidence boundary for every user.

The runtime must not emit a winner label, ranking verdict, conviction score, trade instruction, or portfolio allocation. It may resolve identity, collect and normalize facts, preserve source/time/provenance, execute declared arithmetic, and block invalid artifacts. The analyst/model retains hypothesis formation, materiality, valuation-lens selection, and the research action.

## Development setup

Python 3.12 or newer is required. Create the repository-local virtual environment expected by the documented commands.

```bash
git clone https://github.com/tjdwls101010/Harness-of-Serenity.git
cd Harness-of-Serenity
python3 -m venv scripts/.venv
scripts/.venv/bin/python -m pip install -r scripts/requirements.txt
cp .env.example .env
```

`FRED_API_KEY` enables live FRED/ALFRED evidence. `SERENITY_SEC_USER_AGENT` is the preferred contactable SEC user agent; `EDGAR_IDENTITY` remains a supported legacy setting. Do not put real credentials in a fixture, command transcript, issue, PR, or commit.

## Tests and checks

All tests belong under `tests/260817/`. Start a behavior change with a failing test at a public seam, implement the smallest vertical slice, run the focused test, then run the whole v2 suite.

```bash
PY=scripts/.venv/bin/python

# Focused TDD slice
$PY -m pytest tests/260817/cli -q

# Full v2 test suite
$PY -m pytest tests/260817 -q

# Static harness inventory; provider/network research is intentionally excluded.
$PY scripts/serenity_harness.py validate

# Inspect the public interfaces without writing or contacting providers.
$PY scripts/serenity.py --help
$PY scripts/serenity_corpus.py --help
$PY scripts/serenity_eval.py --help
```

Use a real CLI subprocess, a schema document, or an artifact boundary as the seam. External provider/network, filesystem-clock, and process boundaries may be injected or mocked; do not mock private runtime helpers simply to make a test pass. Provider tests must preserve explicit availability, time axes, source identity, raw hashes where a response exists, and degraded outcomes. A provider failure should become a typed result or documented command error, never a fabricated value.

## Making a change

Branch from `main` using `feat/`, `fix/`, `docs/`, `chore/`, or `refactor/` followed by an English kebab-case slug. Keep each change focused: do not reformat or refactor adjacent code unless the requested change made it necessary.

Commits and pull-request titles use `<type>: <Korean title>` and stay within 50 characters; permitted types are `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `build`, and `ci`. Use Korean for commit messages, PR titles, PR bodies, and issues; keep code, paths, commands, and identifiers unchanged.

Open a PR for a feature, bug fix, refactor, documentation overhaul, or behavior-changing configuration. Follow [`.github/pull_request_template.md`](.github/pull_request_template.md) exactly: `## 무엇을 바꿨나`, `## 왜`, `## 영향`, then `## 검증`. The verification section records the commands actually run and their real result counts. A test not run is reported as not run, not implied by a related command.

## Code and documentation style

Follow the local style of the file you touch. New Markdown uses one soft-wrapped paragraph per line: do not hard-wrap by column, and do not put every sentence on its own line. Every changed line should directly support the requested behavior. If you discover unrelated dead code, report it but do not remove it.

## Reporting bugs and security issues

For a normal bug or feature request, open a GitHub issue with the exact command, one JSON stdout result, Python version, and source/provider context needed to reproduce it. For a vulnerability or accidental credential exposure, do not open a public issue; follow [SECURITY.md](SECURITY.md).

## Code of Conduct

Participation is governed by the [Code of Conduct](CODE_OF_CONDUCT.md).
