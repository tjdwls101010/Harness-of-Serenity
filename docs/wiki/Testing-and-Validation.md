# Testing and Validation

Every check in the repository, what it protects, and how to run it. This is the machinery that
makes the code/judgment boundary an enforced invariant rather than a stated intention.

## The three suites

| Suite | Command | Count | Network |
| --- | --- | --- | --- |
| Structural validator | `serenity_harness.py validate` | Wiring + the fact/judge seam | No |
| Hook fixtures | `.claude/hooks/tests/run_fixtures.py` | Every committed hook scenario | No |
| Contract tests | `scripts/.venv/bin/python -m pytest scripts/tests/ -q` | The fact/judge seam + the sector-map schema | No |

Run all three before opening a pull request. There is no CI, so they are the only gate.

```bash
PY=scripts/.venv/bin/python

$PY scripts/serenity_harness.py validate        # → "ok": true
$PY .claude/hooks/tests/run_fixtures.py         # → all fixtures passed (exit 0)
$PY -m pytest scripts/tests/ -q                 # → all pass
```

---

## The structural validator

`scripts/serenity_harness.py validate` answers one question: *is the harness still structurally
sound — the spine present, the skills loadable, and above all the code/judgment boundary intact?*

```bash
scripts/.venv/bin/python scripts/serenity_harness.py validate
scripts/.venv/bin/python scripts/serenity_harness.py validate --verbose
```

Output:

```json
{
  "harness": "serenity",
  "ok": true,
  "summary": { "pass": 16, "warn": 0, "fail": 0 },
  "checks": [ { "check": "claude_md", "status": "pass" }, ... ]
}
```

`detail` appears only for non-passing checks unless `--verbose` is set. **Warnings never fail the
run** — only hard failures exit non-zero.

### The checks

| # | Check | Asserts |
| --- | --- | --- |
| 1 | `claude_md` | `CLAUDE.md` exists at the repository root |
| 2–4 | `skill:serenity-{discovery,analysis,macro}` | Each `SKILL.md` exists and its frontmatter yields both `name` and `description` |
| 5 | `pipeline_entry` | `serenity_pipeline` imports and the three command functions are importable |
| 6 | `evidence_invariants` | **The real regression** — see below |
| 7 | `macro_sanitizer` | A synthetic poisoned macro payload comes out clean |
| 8 | `xbrl_module_boundary` | No `_sec_xbrl` module outside `legacy` has been imported into the active path |
| 9 | `judgment_boundary` | No module matching `pipeline.legacy` appears in `sys.modules` |
| 10–11 | `sec_layer:*` | `serenity_filings.py` and the filings agent exist (**soft** — warns, never fails) |
| 12 | `hooks` | `.claude/settings.json` maps the exact four events to the exact four scripts, and each script file exists |
| 13 | `agent:serenity-scorecard` | The agent file exists, declares all four required tools, and its body contains the schema sentinels |
| 14 | `session_archive_doctrine` | `CLAUDE.md` contains the archive section and the `Saved:` token |
| 15 | `sessions_index` | `sessions/INDEX.md` exists and declares itself verdict-free |
| 16 | `hook_fixtures` | **The hooks behave** — runs `run_fixtures.py` and adopts its exit code. Check 12 asserts the wiring exists; this asserts it works |

Frontmatter is parsed with a regex rather than a YAML library — a deliberate choice to keep the
validator dependency-free so it can run before anything is installed.

### Check 6 in detail

The substantive one. It replays **every** `scripts/tests/golden/*.inputs.json` through
`build_evidence()` and asserts seven invariants per fixture:

| # | Invariant |
| --- | --- |
| a | `evidence_contract.judgment_owner == "agent"` |
| b | No key in the tree intersects `FORBIDDEN_EVIDENCE_KEYS` literally |
| c | No key is forbidden after normalization — `Risk_Score`, `risk-score`, `RiskScore` all collapse to the same form, and `regime` / `risklevel` are caught as substrings so `vix_regime` cannot slip through namespaced |
| d | No value equals a forbidden literal (`BUY`, `SELL`, `STRONG_BUY`, `MOONSHOT`, `ACCUMULATE`, `AVOID`) |
| e | No value matches the verdict-shaped pattern |
| f | Load-bearing fields exist — conditionally |
| g | If the payload carried filing classification data, `filing_evidence.dossier` surfaced it |

Three refinements make it precise rather than merely strict:

**The `filing_evidence` value exemption.** Invariant (e) scans everything *except* `filing_evidence`,
because reproduced filing text legitimately contains "buy" and "sell" as ordinary verbs
("agreed to issue and sell"). The scan targets a *code-emitted verdict label*, never the filing's
own words — and the forbidden-**key** scan (b, c) still covers the entire tree including
`filing_evidence`.

**Exact matching for `rating` and `recommendation`.** Both are matched exactly, never as
substrings, so the legitimate `rs_rating` (IBD relative strength) and `recommendation_distribution`
(the raw analyst tally) survive. A substring rule would have banned real data.

**Conditional field requirements.** `key_facts` must be non-empty *only if* the source payload
carried a market cap or price. Some captures are legitimately degenerate — a delisted ticker
returning nothing. A thin fixture is not a code bug; an empty `key_facts` *despite* a real market
cap is.

### Check 7 in detail

The golden fixtures all have a `null` macro layer, so they never exercise the sanitizer. Check 7
feeds a synthetic payload that does:

```python
{"l1": {"vix_spot": 18.9, "real_rate": 1.2,
        "vix_regime": "panic", "regime": "risk_off", "macro_risk_level": "high"},
 "l4": {}, "l5": {}, "sec_sc": {}}
```

and asserts the output retains `vix_spot` and `real_rate` while stripping every judgment label.
Raw gauges kept, interpretations removed.

### `rankdiff`

A second subcommand, deterministic and judgment-free:

```bash
scripts/.venv/bin/python scripts/serenity_harness.py rankdiff \
  sessions/260701.ai-chain/_ranking.md \
  sessions/260718.ai-chain/_ranking.md
```

Parses the fixed tier table from both files and returns the intersection, agreement percentage,
per-ticker changes, names in only one, and whether the tier cut moved. It diffs two files a human
already wrote, so it sits on the code side of the boundary.

---

## Golden fixtures

Sixteen frozen payloads at `scripts/tests/golden/`: AAOI, AEHR, AXTI, CRCL, HIMS, HOOD, IONQ,
LITE, MU, NBIS, POET, QBTS, RGTI, RKLB, SIVE, SSYS.

Each ticker has two files:

**`{TICKER}.inputs.json`** — a frozen four-layer pipeline payload (`l1` macro, `l4` fundamentals,
`l5` catalysts, `sec_sc` filings), roughly 17–21 KB, captured live from a real run.

**`{TICKER}.expected.json`** — the blessed projection, roughly 400–900 bytes:

```json
{
  "ticker": "AAOI", "role": "winner",
  "note": "optical transceiver maker — physical bottleneck",
  "captured_at": "2026-06-21",
  "hard": { "revenue_status": "has_revenue", "data_insufficient": false,
            "screen_component_keys": ["catalyst","health","momentum","valuation"],
            "pre_commercial": false },
  "baseline": { "screen_score": 47.0 }
}
```

The basket is chosen deliberately: **winners** (12 names), **losers** (RGTI, QBTS, IONQ), and a
**divergence** case (SSYS). Losers carry an additional ceiling assertion — a known poor outcome
must never surface as investable. How *badly* a loser scores is allowed to drift; a loser becoming
a buy is not.

The divergence case is deliberately *not* ceilinged, because asserting the pipeline must reach a
particular grade would force the code to do the analyst's job — the exact thing the architecture
forbids.

### The blessing rule

> Golden values are **blessed from a live capture, never hand-typed.**

Hand-writing an expected value bakes in exactly the transcription error the fixture exists to
catch. When a legitimate change moves a fact, you review the failure and re-bless — the failure is
the harness working.

Regenerate:

```bash
cd scripts

# Capture fresh inputs from a live run
../scripts/.venv/bin/python -m pipeline.legacy legacy-regress AAOI --capture

# Re-bless expectations from a replay of the frozen inputs
../scripts/.venv/bin/python -m pipeline.legacy legacy-regress AAOI --bless

# Both
../scripts/.venv/bin/python -m pipeline.legacy legacy-regress AAOI --update
```

Note this routes through the quarantined legacy entry point, which is the one remaining reason
`legacy/` is kept rather than deleted. (Its golden-directory constant currently points at a path
that does not exist — see [Known Limitations](Known-Limitations.md).)

### Offline replay

The fastest check of an evidence-layer change:

```bash
scripts/.venv/bin/python scripts/serenity_pipeline.py evidence \
  --fixture scripts/tests/golden/AAOI.inputs.json
```

`build_evidence()` is a pure function of its input, so output is byte-stable across machines.

---

## Contract tests

`scripts/tests/test_evidence_contract.py` — two tests, both shelling out to the `evidence`
subcommand and parsing its stdout.

**`test_pipeline_evidence_command_is_judgment_free`** replays the AAOI fixture and asserts the
contract fields, the required top-level keys, and the full forbidden-key and forbidden-value scans
with the same `filing_evidence` value exemption as the validator.

**`test_pipeline_evidence_sanitizes_non_null_macro_payload`** is the more interesting one. It
writes a synthetic fixture whose macro layer is **deliberately poisoned**:

```python
"l1": {
    "verdict": "Buy", "Verdict": "strong buy",
    "risk_score": 88, "Risk_Score": 91,
    "Recommendation": "please sell", "signals": {...},
    "raw_inputs": {"vix_spot": 20, "dxy": 105},
}
```

Forbidden keys in several casings, verdict-shaped values in four spellings, and one legitimate
block. The payoff assertion:

```python
assert payload["macro_inputs"] == {"raw_inputs": {"vix_spot": 20, "dxy": 105}}
```

Everything judgment-shaped stripped; the raw gauges preserved exactly.

> ⚠️ **Both tests currently fail** on a path bug in the test file itself — the repository root is
> computed by walking three directory levels too far. The code under test is fine; the harness
> around it is not. See
> [Known Limitations](Known-Limitations.md#contract-tests-fail-on-a-path-bug).

---

## Hook fixtures

One fixture per scenario, covering the two hooks with branch logic. `run_fixtures.py` discovers them
by directory, so the count is whatever is committed — it is printed, never asserted.

```bash
scripts/.venv/bin/python .claude/hooks/tests/run_fixtures.py
# → all fixtures passed (exit 0)
```

A fixture is the exact stdin payload the hook receives; the runner asserts on stdout using
`silent`, `contains`, and `excludes` combinators. It must run with the repository root as the
working directory, since `verdict_gate` resolves session paths relative to it.

Thirteen fixtures cover `verdict_gate` (the hard block, each soft nudge in isolation, all four
`Saved:` branches, and two false-fire guards); nine cover `evidence_discipline` (firing cases in
English and Korean, meta suppression, the anchor override, a non-market control). The full table
is in [Hooks Reference](Hooks-Reference.md#testing-the-hooks).

These exist because the scenarios previously lived only as names in the design spec — "re-run the
regressions" was not an executable instruction until the fixtures made it one.

---

## What is *not* tested

Stated plainly so you know where the edges are:

- **No test hits the network.** Live fetch behavior — a rate-limited yfinance call, an EDGAR 403 —
  is not covered. Degradation is designed for but not verified automatically.
- **No coverage measurement.** There is no coverage tool configured, and module-level unit tests
  do not exist for the 27 data modules.
- **No CI.** Nothing runs on push. The three suites are manual.
- **The eval is not a test.** [Eval Harness](Eval-Harness.md) measures method reproduction, spends
  tokens, and is user-triggered only.
- **No performance or load testing.**

The coverage that does exist is aimed narrowly at the one property most worth protecting: that
judgment does not leak into the data layer. That is deliberate prioritization, not thoroughness.

---

**Next:** [Eval Harness](Eval-Harness.md) · [Known Limitations](Known-Limitations.md) ·
[Back to index](README.md)
