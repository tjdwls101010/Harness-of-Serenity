# Troubleshooting

Symptoms mapped to causes and fixes. For defects that are in the code rather than your setup, see
[Known Limitations](Known-Limitations.md) — several entries below cross-reference it.

## First: which layer is broken?

Run these three in order. The first failure localizes the problem.

```bash
PY=scripts/.venv/bin/python

$PY scripts/serenity_harness.py validate --verbose   # installation + structure, offline
$PY scripts/serenity_pipeline.py evidence \
    --fixture scripts/tests/golden/AAOI.inputs.json  # evidence layer, offline
$PY scripts/serenity_pipeline.py analyze AAPL        # network + upstream sources
```

| First failure | Problem is in |
| --- | --- |
| `validate` | Installation, Python version, or file structure |
| `evidence` | The evidence builder — a code bug, not a data problem |
| `analyze` | Network, credentials, or an upstream source |
| None | Whatever you saw is ticker-specific or transient |

---

## Installation

### `SyntaxError` mentioning `type Json = ...`

Python is older than 3.12. `scripts/pipeline/_evidence.py` uses PEP 695 type aliases.

```bash
scripts/.venv/bin/python --version    # must be 3.12+
```

Rebuild against a newer interpreter:

```bash
rm -rf scripts/.venv
python3.12 -m venv scripts/.venv      # or 3.13
scripts/.venv/bin/pip install -r scripts/requirements.txt
```

### `ModuleNotFoundError` for yfinance, fredapi, edgar, …

The venv is missing packages, or you are running the wrong interpreter. Always invoke
`scripts/.venv/bin/python` explicitly rather than a bare `python`.

```bash
scripts/.venv/bin/pip install -r scripts/requirements.txt
```

### `pip install` fails building lxml or numpy

No wheel for your platform, so it is compiling from source. On macOS:

```bash
xcode-select --install
```

On Debian or Ubuntu:

```bash
sudo apt-get install python3-dev libxml2-dev libxslt1-dev
```

### Hooks never fire

The venv is not at `scripts/.venv`. `.claude/settings.json` references that exact interpreter path,
and a venv elsewhere disables the hooks silently with no error. Recreate it at the expected
location.

Verify the hooks themselves are healthy:

```bash
scripts/.venv/bin/python .claude/hooks/tests/run_fixtures.py    # → all fixtures passed (exit 0)
```

### `pytest: command not found` / `No module named pytest`

pytest is in `requirements.txt` but not installed in this venv:

```bash
scripts/.venv/bin/python -m pip install pytest
scripts/.venv/bin/python -m pytest scripts/tests/ -q
```

Note `-m pip` rather than `scripts/.venv/bin/pip`: this venv has been relocated, so its console
scripts (`bin/pip`, `bin/pytest`) carry a shebang pointing at an interpreter path that no longer
exists. `bin/python` itself is fine, so route everything through `-m`.

Install into the venv, never system-wide. The tests shell out to `serenity_pipeline.py` with
`sys.executable`, so a runner outside the venv resolves an interpreter with no yfinance and the
failure looks like a missing dependency rather than a wrong runner.

---

## Validation

### `validate` returns `"ok": false`

Re-run with `--verbose` and read the failing check's `detail`.

| Failing check | Usual cause |
| --- | --- |
| `claude_md` | Not running from the repository root, or `CLAUDE.md` was moved |
| `skill:serenity-*` | A `SKILL.md` lost its frontmatter `name` or `description` |
| `pipeline_entry` | An import error — run the import directly to see the traceback |
| `evidence_invariants` | A judgment-shaped key or value reached the evidence output. **This is the boundary rule firing.** The detail names the offending key. |
| `judgment_boundary` | Something on the live path imported from `pipeline.legacy` |
| `hooks` | `.claude/settings.json` and the files in `.claude/hooks/` disagree |
| `sessions_index` | `sessions/INDEX.md` is missing or lost its verdict-free declaration |

For `evidence_invariants`, the fix is nearly always to stop emitting the field rather than to
rename it. See [Contributing](../../CONTRIBUTING.md#the-one-rule).

### `validate` warns on `sec_layer:*`

Soft checks. They warn when `scripts/serenity_filings.py` or `.claude/agents/serenity-filings.md`
is missing. Warnings never fail the run.

---

## Data and network

### `key_facts` is empty or nearly empty

`_pick` omits keys whose value is `None`, so an empty `key_facts` means the upstream `info` call
returned nothing usable. Causes, in rough order of likelihood:

1. **Ticker does not exist or is delisted.** Check it directly:
   ```bash
   scripts/.venv/bin/python scripts/modules/info.py get-info-fields TICKER
   ```
2. **yfinance rate limiting.** Wait a few minutes and retry. A burst of `analyze` calls will
   trigger it.
3. **A yfinance breaking change.** It tracks an undocumented endpoint and breaks periodically.
   `scripts/.venv/bin/pip install -U yfinance` often fixes it.
4. **Non-US listing.** The pipeline targets US-listed symbols. Use the ADR.

An empty result is real information — the pipeline degrades to missing fields rather than
crashing, so it will not tell you loudly.

### Macro gauges are missing — `erp_pct`, `net_liq_direction`, `real_rate`

Almost always `FRED_API_KEY` not reaching the process. **The macro modules do not read `.env`** —
a key sitting in that file is invisible to them.

```bash
export $(grep -v '^#' .env | grep FRED_API_KEY | xargs)
scripts/.venv/bin/python scripts/serenity_pipeline.py macro
```

Confirm it is set:

```bash
echo $FRED_API_KEY
scripts/.venv/bin/python scripts/modules/erp.py erp
```

Full detail: [Known Limitations](Known-Limitations.md#env-is-not-loaded-for-macro-modules).

### `erp_pct` missing even with a valid key

`modules/erp.py` scrapes YCharts with `curl` for the CAPE ratio. It is the most fragile fetch in
the tree. Test in isolation:

```bash
scripts/.venv/bin/python scripts/modules/erp.py erp
```

It falls back to a cached Shiller CSV at `scripts/.cache/shiller_cape.csv` if present. If YCharts
changed its page structure, the parse fails and the gauge drops.

### SEC commands return `data_unavailable`

```json
{ "error": "data_unavailable", "detail": "HTTPError: 403 Client Error: Forbidden" }
```

| Detail contains | Cause | Fix |
| --- | --- | --- |
| `403 Forbidden` | Missing or malformed identity | Set `EDGAR_IDENTITY="Name email@example.com"` |
| `429` or a rate message | Throttled | Wait, then reduce parallelism |
| `not found` / empty | The form does not exist for that filer | Try a different `--form` |
| Timeout | Large filing or slow response | Use `context` before `text` |

These commands always exit 0 by design, so check the JSON rather than the exit code.

> A null caused by an EDGAR block is indistinguishable from genuine non-disclosure. The method
> treats an unreconciled null as a hard stop rather than proceeding on the assumption that silence
> means absence.

### `analyze` is slow

30–90 seconds is normal — roughly 34 subprocesses, most of them network-bound. To speed up:

```bash
# Fetch macro once, reuse across a cohort
$PY scripts/serenity_pipeline.py macro > macro.json
$PY scripts/serenity_pipeline.py analyze NVDA --skip-macro
$PY scripts/serenity_pipeline.py analyze AVGO --skip-macro
```

`--skip-macro` removes 14 of those subprocesses, which is most of the wall clock. There is no
caching layer, so every run re-fetches everything.

### `analyze` hangs

Individual module timeouts are 60 seconds (120 for SEC events), so a full run should not exceed a
few minutes. If it does, a module is blocked on a network call that is neither returning nor
timing out. Isolate it by running the modules directly — see the field-to-module map in
[Data Modules](Data-Modules.md#which-module-feeds-which-field).

### A top-level `{"error": "..."}` instead of a dossier

The pipeline itself failed, not an upstream source. Partial failures become missing fields; a
top-level error means an uncaught exception in the pipeline code. Reproduce it offline:

```bash
$PY scripts/serenity_pipeline.py evidence --fixture scripts/tests/golden/AAOI.inputs.json
```

If that works, the problem is in fetch or normalization for that specific ticker's data shape.
That is a bug worth reporting — include the ticker.

---

## Output fields

### `filing_evidence` is empty on every ticker

Expected. The in-pipeline SEC extraction is a stub since the capability moved to the
`serenity-filings` subagent. Use [`serenity_filings.py`](Filings-and-SEC.md) instead:

```bash
$PY scripts/serenity_filings.py segments TSM --axis StatementGeographicalAxis
$PY scripts/serenity_filings.py section TSM --form 10-K --named business
```

[Known Limitations](Known-Limitations.md#filing_evidence-is-empty-on-the-live-path).

### `catalyst_inputs.next_report` is always `null`

A known bug — yfinance returns earnings dates in the DataFrame index and the normalizer emits
columns only. Get the date directly:

```bash
$PY scripts/modules/actions.py get-earnings-dates TICKER --limit 4
```

[Known Limitations](Known-Limitations.md#next_report-is-always-null).

### `recent_events` is always `[]`

A known bug — a list is passed through a dict-coercing helper. The underlying fetch works:

```bash
$PY scripts/modules/events.py events TICKER --limit 5 --days 180
```

[Known Limitations](Known-Limitations.md#recent_events-is-always-empty).

### `ev_to_fcf` is missing but `ev_to_revenue` is present

Intentional. `ev_to_fcf` is emitted only when free cash flow is positive — a negative multiple is a
division artifact, not a valuation signal. Check `valuation_inputs.ev_multiples.real_fcf`.

### Margins look wrong by a factor of 100

They are decimal fractions, not percentages. `grossMargins: 0.296` means 29.6%.
`shortPercentOfFloat`, `heldPercentInsiders`, and `heldPercentInstitutions` are the same.

### A `discover` candidate has nulls everywhere

Check `missing_data` in the response — it names exactly which fields failed per ticker, which
distinguishes "this ticker has no analyst coverage" from "the fetch broke."

---

## Agent harness

### The evidence-discipline reminder does not fire

The prompt was classified as harness development. Adding a cashtag or an explicit market phrase
overrides the suppression. Test your exact prompt:

```bash
echo '{"prompt":"your prompt here"}' | \
  scripts/.venv/bin/python .claude/hooks/evidence_discipline.py
```

Output means it fired; silence means it did not.

### An answer is blocked for a missing sign-off

The only hard block in the harness. An answer carrying a market verdict must include `NFI` / `NFA`
or an equivalent "not financial advice" statement. Add it.

### The `Saved:` nudge fires despite a `Saved:` line

The check resolves against the real filesystem. It fires when the folder does not exist, or exists
but contains no `.md` file. Both are deliberate — an empty `mkdir` would otherwise falsely certify
that archiving happened. See
[Hooks Reference](Hooks-Reference.md#verdict_gatepy--stop).

### The `Lens:` nudge fires despite naming a lens

Naming is not running. The check requires a literal `Lens:` line containing a real `×`, `÷`, or `*`
operator **and** `=` on the same line:

```
Lens: content×volume÷MC — $180/unit × 4.2M units ÷ $12.4B = 6.1% of MC
```

`EV/Rev = 12x` does not satisfy it, deliberately — that bare top-down multiple is the exact miss
the check was built to catch.

---

## Still stuck?

Open an issue with the exact command, the full JSON output, your Python version, and whether
`validate` passes. See [Contributing](../../CONTRIBUTING.md#reporting-bugs-and-requesting-features).
Security issues go through [SECURITY.md](../../SECURITY.md) instead.

---

**Next:** [Known Limitations](Known-Limitations.md) · [Back to index](README.md)
