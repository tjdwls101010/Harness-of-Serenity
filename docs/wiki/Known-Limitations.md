# Known Limitations

Verified defects and rough edges, stated plainly. Every entry below was reproduced against the
current `main` before being written here.

This page exists because a documentation set that describes intended behavior while the code does
something else is worse than no documentation — it makes a reader confident about something
false. Where the code and the design disagree, the code is documented and the disagreement is
recorded here.

**Severity key**

| | Meaning |
| --- | --- |
| 🔴 | Silently produces wrong or missing data an analysis might rely on |
| 🟡 | A feature does not work; the failure is visible |
| ⚪ | Cosmetic, stale, or an accepted trade-off |

---

## `.env` is not loaded for macro modules

**Severity:** 🔴 Data-affecting

**What happens.** `FRED_API_KEY` in `.env` is invisible to `serenity_pipeline.py macro`. The four
FRED-backed gauges are dropped from the payload, which is indistinguishable from a genuinely
unavailable reading.

**Why it matters.** The drop is silent by design — `_fetch.py` filters `None` gauges out entirely,
with the comment that zeros and `false` are real readings worth keeping. That is correct behavior
for a failed fetch and wrong here, because the fetch never had a chance. An analyst reading
`macro` output sees no equity risk premium and no net liquidity direction, with nothing indicating
that a configured key was simply never read.

**Verified.** Only three files call `load_dotenv`, and none of them is on the live macro path:

```
scripts/serenity_filings.py:58
scripts/pipeline/legacy/_sec_xbrl.py:55      (quarantined)
scripts/pipeline/legacy/_commands.py:108     (quarantined)
```

`modules/erp.py`, `rates.py`, `inflation.py`, and `net_liquidity.py` read `os.environ` directly.

**Affected:** `erp_pct`, `net_liq_direction`, `real_rate`, and the rates/inflation gauges.

**Workaround.**

```bash
export $(grep -v '^#' .env | grep FRED_API_KEY | xargs)
scripts/.venv/bin/python scripts/serenity_pipeline.py macro
```

Or put `export FRED_API_KEY=...` in your shell profile.

**Fix.** Call `load_dotenv` once in `scripts/pipeline/_fetch.py` before the fan-out, or in
`modules/utils.py` so every module inherits it. The second is tidier but loads dotenv into 27
processes.

---

## `next_report` is always `null`

**Severity:** 🔴 Data-affecting

**What happens.** `catalyst_inputs.next_report` is `null` for every ticker, on both live runs and
fixture replays.

**Why it matters.** Its own docstring says this is "the days-to-earnings the CSP / earnings-gap
timing rule turns on" — so a documented timing input never reaches the analyst, and its absence
reads as "no scheduled earnings" rather than "not extracted."

**Root cause.** `_next_report` (`scripts/pipeline/_evidence.py:148`) reads
`ed.get("Earnings Date")`, but `utils.normalize` converts DataFrames **column-oriented** and
"Earnings Date" is the yfinance DataFrame's *index*, not a column. The live columns are
`['EPS Estimate', 'Reported EPS', 'Surprise(%)', 'days_to_next']`, so the lookup returns `None`
and the function short-circuits.

The same bug exists in `pipeline/legacy/_commands.py:42`.

**Verified.** Replaying `scripts/tests/golden/AAOI.inputs.json` yields `next_report = None`.

**Workaround.**

```bash
scripts/.venv/bin/python scripts/modules/actions.py get-earnings-dates TICKER --limit 4
```

**Fix.** Either have `actions.py` reset the index into a column before normalizing, or have
`_next_report` read `days_to_next`, which is already present.

---

## `recent_events` is always empty

**Severity:** 🔴 Data-affecting

**What happens.** `filing_evidence.recent_events` is `[]` even when the underlying fetch returned
events.

**Why it matters.** `modules/events.py` runs on **every** `analyze` call and is the single slowest
job in the fan-out — a 120-second timeout, the only non-default one on the live path. Its results
are fetched and then discarded. You pay the latency and get nothing.

**Root cause.** `scripts/pipeline/_evidence.py:356`:

```python
"recent_events": _without(_dict(_dict(l3.get("data")).get("sec_events")), ("confidence",)),
```

`l3["data"]["sec_events"]` is a **list**. The outer `_dict(...)` coerces a non-dict to `{}`, so the
list is destroyed before `_without` ever sees it.

**Verified.** On the AAOI fixture, `_build_l3_bottleneck` returns `sec_events` as a `list` of
length 3; the emitted `recent_events` is `[]`.

**Workaround.**

```bash
scripts/.venv/bin/python scripts/modules/events.py events TICKER --limit 5 --days 180
```

**Fix.** Drop the outer `_dict(...)` so the list reaches `_without`.

---

## `filing_evidence` is empty on the live path

**Severity:** 🟡 Feature broken

**What happens.** `filing_evidence.dossier` and `absence_evidence_flags` are `null` for every live
`analyze` run. Frozen fixtures show populated data, which makes this easy to misread as working.

**Why.** Partly intentional, partly not.

The **intentional** part: `_extract_sec_supply_chain` (`scripts/pipeline/_fetch.py:196`) is now a
pure stub that makes no network call. Its docstring explains the consolidation — filing extraction
moved to the `serenity-filings` subagent because the in-pipeline XBRL parser "duplicated the
subagent's capability and degraded silently on tag drift / SEC blocks." The stub deliberately
preserves the payload shape so `build_evidence` reads a silent filing as `null` rather than
fabricating a fact.

The **unintentional** part: the documentation and the field name still suggest the pipeline
supplies filing evidence. It does not, and has not since the consolidation.

**Verified.** The AAOI fixture — captured *before* the consolidation — still produces a populated
`dossier` with all six keys. A live run produces `null`. So the fixtures document historical
behavior, not current behavior.

**Use instead.** [`serenity_filings.py`](Filings-and-SEC.md), or the `serenity-filings` subagent.

**Possible fix.** Rename the field, or have it carry an explicit marker such as
`{"source": "serenity-filings subagent", "in_pipeline": false}` so the null is self-explanatory.

---

## The session archive has no committed worked example

**Severity:** ⚪ Cosmetic / accepted

**What happens.** The archive convention is fully specified, and a fresh clone contains no
example of it. `git ls-files sessions/` returns exactly three paths: `INDEX.md` (zero entries) and
the two `9901xx` hook-fixture folders. Real session folders are generated locally and are not
published with the repository.

**Why it matters.** Only for expectations, which is why this is ⚪ rather than 🟡 — nothing is
broken, there is simply nothing to copy from:

- No reference `_ranking.md` exists, so the tier table, the `Tier cut:` line, and the deltas
  section have no example. The column contract in
  [Agent Harness](Agent-Harness.md#the-rank-n-protocol) is the specification, and it is exact
  because `rankdiff` parses it.
- `serenity_harness.py rankdiff` has nothing in a fresh clone to run against. Point it at two of
  your own session folders once you have them.

**Not a defect to fix in code.** Whether a maintainer's own analysis belongs in a public
repository is a judgment call, and keeping it out is defensible. Noted here so the specification
in [Session Archive](Session-Archive.md) is not mistaken for something demonstrated.

---

## Stale entries in `requirements.txt`

**Severity:** ⚪ Cosmetic / accepted

Three listed dependencies have **zero imports** anywhere under `scripts/`:

| Listed | Reality |
| --- | --- |
| `finvizfinance>=0.14.6` | No import |
| `finviz>=2.0.0` | No import |
| `sec-edgar-downloader>=5.0.0` | No import |

A comment also mentions a "CFTC direct API" that no module contacts.

**Impact:** a slower, larger install and a misleading source map. Do not read `requirements.txt`
as a list of what the project actually talks to — the real external surfaces are yfinance (14
modules), FRED (4), CBOE (2), SEC EDGAR (2), plus three wrapper libraries and one scraped page.

**Resolved 2026-08-11.** `sec-analyzer>=0.2.0` is no longer listed: its only importer is
quarantined legacy code, and the pin was never satisfiable from PyPI — the installed build was an
editable checkout under `~/Documents/`, a path that died when this repository moved. `pytest` is
now listed, and must be installed into `scripts/.venv` rather than system-wide, because the tests
shell out to the pipeline with `sys.executable`.

---

## Legacy is not actually runnable

**Severity:** ⚪ Cosmetic / accepted

`scripts/pipeline/legacy/` is documented as reference-only, and it is also largely inoperable:

- `legacy/_commands.py:112` imports `sec_analyzer`, whose editable install points at a directory
  that no longer exists. The failure is caught and returns a structured error, so
  `legacy-analyze` still completes with an empty supply-chain layer.
- `legacy/_regression.py:51` sets `GOLDEN_DIR` to `scripts/pipeline/tests/golden` — a path that
  does not exist. The real fixtures are at `scripts/tests/golden/`. As written,
  `legacy-regress` would report every name as skipped.

**This matters more than it looks.** The fixture-regeneration procedure documented in
[Testing and Validation](Testing-and-Validation.md#the-blessing-rule) routes through
`legacy-regress`, so regenerating a golden fixture requires fixing `GOLDEN_DIR` first. Since
fixture capture is the one remaining reason `legacy/` is kept rather than deleted, that path being
broken means the quarantine currently has no working purpose.

---

## Dead flags and stale comments

**Severity:** ⚪ Cosmetic / accepted

| Item | Reality |
| --- | --- |
| `evidence --json` | Defaults to `True` and is never read. Cannot be turned off. |
| `legacy-macro --extended` | Accepted and never read. |
| `legacy/_health.py` docstring | Says "4 health gates" and "severity_score (0-4.0)"; it is 5 gates and 0–5.0. |
| `legacy/_commands.py:752` comment | Says "9 top-level keys" for an 8-key dict. |

---

## Accepted trade-offs

**Severity:** ⚪ Cosmetic / accepted

Not bugs. Deliberate choices with consequences worth knowing.

**No caching.** Every run re-fetches everything — no memoization, no disk cache, no HTTP cache.
Analyzing the same ticker twice in a row costs the same both times. `--skip-macro` is the only
reuse mechanism and it is manual. Justified by the identity-pinning goal (a cached number is a
stale number waiting to be quoted), but it makes iteration slow.

**Fixed timeouts and concurrency.** 60 s per module (120 s for SEC events), 10 workers per group,
3 at the top level. None configurable by flag. On a slow connection, modules time out and their
fields silently vanish.

**The integrity hook misses piped runs.** `data_integrity_guard.py` parses the tool's stdout, so
`analyze NVDA > out.json` skips the arithmetic audit entirely. Deliberate — a pipe is not a
failure — but redirected runs are unaudited.

**A 15× multiple is hardcoded.** `modules/no_growth_valuation.py:79` assumes 15× for its
zero-growth valuation. It is a stated modeling assumption rather than a threshold that decides
anything, but it is the closest thing to a judgment on the code side. Read the output as "value at
15× no-growth," not as fair value.

**No network tests, no CI, no coverage measurement.** Degradation behavior is designed for but not
verified automatically. See
[Testing and Validation](Testing-and-Validation.md#what-is-not-tested).

**Upstream fragility.** `modules/erp.py` scrapes YCharts with `curl` and regex — the most brittle
fetch in the tree. yfinance tracks an undocumented endpoint and breaks periodically. Neither is
under this project's control.

---

## Reporting

Found something not listed here? Open an issue with the exact command, the full output, and your
Python version — see
[Contributing](../../CONTRIBUTING.md#reporting-bugs-and-requesting-features). Security issues go
through [SECURITY.md](../../SECURITY.md) instead.

Fixes for anything on this page are welcome. The 🔴 and 🟡 entries are written with enough
precision — file, line, root cause, suggested fix — to be picked up directly.

---

**Next:** [Troubleshooting](Troubleshooting.md) for workarounds · [Back to index](README.md)
