# Contributing to Harness of Serenity

Thanks for looking. This is a personal research harness that happens to be public, so the process
here is deliberately light — no CLA, no issue templates, no required sign-off. What follows is
what you need to make a change that will actually get merged.

## The one rule

Everything else in this document is negotiable. This is not:

> **Deterministic code may load, normalize, and verify facts. It may never emit a verdict, score,
> archetype tag, regime label, rating, price target, or option-vehicle recommendation.**

That boundary is the entire point of the project, and it is enforced mechanically. If you add a
field named `risk_score`, a value of `"BUY"`, or a key containing `regime` anywhere in the
evidence payload, `serenity_harness.py validate` will fail and so will the contract tests.

The reasoning: a judgment encoded in code drifts silently between runs, and one stale threshold
among a hundred can invert a conclusion with nothing to catch it. Code answers "is this number
right." It never answers "is this thesis right."

**In practice this means:**

- New data module? Return the raw measurement. `vix_spot: 18.9` is evidence; `vix_regime:
  "panic"` is judgment, and the pipeline will strip it.
- New derived figure? Fine, if it is pure arithmetic over disclosed inputs (`ev_to_revenue`,
  `net_debt`). Not fine if it embeds a threshold that decides something (`is_cheap`,
  `quality_grade`).
- Need a label anyway for your own use? Put it in a skill or in `CLAUDE.md`, which are the
  judgment layers. See [Architecture](docs/wiki/Architecture.md).

The concrete enforcement lists live in `scripts/pipeline/_evidence.py`
(`FORBIDDEN_EVIDENCE_KEYS`, `FORBIDDEN_KEY_SUBSTRINGS`, `FORBIDDEN_VALUE_PATTERN`).

## What contributions are wanted

Genuinely useful:

- **Bug fixes**, especially the ones listed in
  [Known Limitations](docs/wiki/Known-Limitations.md) — they are documented precisely so someone
  can pick one up.
- **New data modules** under `scripts/modules/`, following the existing subprocess-CLI shape.
- **Robustness** in the fetch layer: better degradation, clearer structured errors.
- **Documentation** corrections. If a doc page contradicts the code, the code is right and the
  page is a bug.
- **Test coverage** where a behavior boundary needs protecting.

Please open an issue first for:

- **New dependencies.** The install is already heavy; each addition needs a reason.
- **Doctrine changes** to `CLAUDE.md` or the skills. These are the judgment layer, and the
  project's stated design rule is to *generalize an existing principle* rather than append a new
  case-specific one. A patch per missed case is the failure mode the harness is built against.
- **Anything that moves a judgment into code**, even a convenient one. Especially then.

## Development setup

Python **3.12+** is required — `scripts/pipeline/_evidence.py` uses PEP 695 `type` aliases, which
older interpreters will not parse.

```bash
git clone https://github.com/tjdwls101010/Harness-of-Serenity.git
cd Harness-of-Serenity

python3 -m venv scripts/.venv
scripts/.venv/bin/pip install -r scripts/requirements.txt
cp .env.example .env
```

The virtualenv lives at `scripts/.venv` by convention — the hooks in `.claude/settings.json`
reference that exact interpreter path, so a venv elsewhere will silently disable them.

Optional keys in `.env`:

| Variable | Needed for |
| --- | --- |
| `FRED_API_KEY` | Macro gauges: rates, inflation, net liquidity, ERP. Free from [FRED](https://fred.stlouisfed.org/docs/api/api_key.html). |
| `EDGAR_IDENTITY` | SEC compliance. Format `"Your Name you@example.com"`. Falls back to a default if unset. |

Neither is needed to run the validator or the offline tests.

## Tests and checks

Run these before opening a PR. There is no CI, so they are the only gate.

```bash
PY=scripts/.venv/bin/python

# 1. Structural self-check — 15 checks, no network, no keys required.
#    This is the important one: it replays all 16 golden fixtures
#    through the evidence builder and enforces the boundary rule.
$PY scripts/serenity_harness.py validate
$PY scripts/serenity_harness.py validate --verbose   # detail for passing checks too

# 2. Hook behavior fixtures — must print "22/22 fixtures passed".
$PY .claude/hooks/tests/run_fixtures.py

# 3. Evidence contract tests.
#    See Known Limitations — these currently fail on a path bug in the
#    test file itself, not in the code under test.
python3 -m pytest scripts/tests/ -q
```

A healthy `validate` prints `"ok": true` with `pass: 15, warn: 0, fail: 0`. Warnings never fail
the run; only hard failures exit non-zero.

### Offline replay

The fastest way to check an evidence-layer change without touching the network:

```bash
scripts/.venv/bin/python scripts/serenity_pipeline.py evidence \
  --fixture scripts/tests/golden/AAOI.inputs.json
```

`build_evidence()` is a pure function of its payload, so this is byte-stable and reproducible.

### Regenerating a golden fixture

Only when a change legitimately moves a captured fact. Fixtures are **blessed from a live
capture, never hand-written** — hand-typing them would bake in exactly the error they exist to
catch.

```bash
cd scripts
../scripts/.venv/bin/python -m pipeline.legacy legacy-regress AAOI --update
```

Explain in the PR why the old fixture was wrong.

## Making a change

- **Branch** off `main`. Name it for the change: `fix/next-report-null`,
  `feat/module-put-call-ratio`, `docs/pipeline-reference`.
- **Commits** follow Conventional Commits, matching the existing history:
  `fix(pipeline): …`, `feat(modules): …`, `docs(wiki): …`, `chore: …`.
- **A good PR** states what changed and why, notes which of the three checks above you ran, and
  — if it touches `scripts/pipeline/` or `scripts/modules/` — confirms the boundary rule still
  holds. Keep it focused; one concern per PR.
- **Review** is by the maintainer, best-effort. This is a side project; a slow response is not
  disinterest.

## Code style

There is no linter or formatter config in the repo, so the standard is consistency with the file
you are editing. Observable conventions:

- Every module in `scripts/modules/` is a standalone argparse CLI with `cmd_<name>(args)`
  handlers that print JSON via `utils.output_json` and wrap errors with the `@safe_run`
  decorator. Follow that shape exactly — the pipeline invokes them as subprocesses and depends
  on it.
- Private helpers are `_`-prefixed. Public entry points are not.
- Docstrings explain *why* a piece of code exists and what failure it prevents, not what the next
  line does. Several modules carry a paragraph of rationale at the top; that is intentional and
  worth continuing.
- Type hints where they clarify. `from __future__ import annotations` at the top of new pipeline
  modules.

## Reporting bugs and requesting features

Open a [GitHub issue](https://github.com/tjdwls101010/Harness-of-Serenity/issues). There are no
templates; a useful report includes:

- the exact command you ran and its full output (JSON errors are structured — paste them whole),
- your Python version (`scripts/.venv/bin/python --version`),
- whether `serenity_harness.py validate` passes,
- for data problems, the ticker and roughly when you ran it, since upstream sources change.

**Security issues do not go in the issue tracker.** Follow [SECURITY.md](SECURITY.md).

## Code of Conduct

Participation is governed by the [Code of Conduct](CODE_OF_CONDUCT.md).

---

**Next:** [Architecture](docs/wiki/Architecture.md) · [Testing and Validation](docs/wiki/Testing-and-Validation.md) · [Known Limitations](docs/wiki/Known-Limitations.md)
