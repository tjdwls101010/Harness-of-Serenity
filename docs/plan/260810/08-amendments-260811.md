# Amendments from implementation — 2026-08-11

The code layer (phases 00–03, 07) was implemented on 2026-08-11. This file records where the plan was **wrong or unimplementable as written**, so the next session works from the corrected version rather than re-deriving the same dead ends. The original phase files are left intact: they are the analysis as it stood, and overwriting them would hide that these were discoveries rather than the plan's own foresight.

Everything here was confirmed by direct execution, never by reading.

## Phase 00 — a phase the plan does not have

Three separate things were dead for the same reason: **the repository moved out of `~/Documents/` and hardcoded absolute paths never followed it.**

- `.codex/hooks.json` bound all four hooks to `/Users/seongjin/Documents/Coding/Invest/…`, so the Codex hook layer was inert. Already documented in the wiki as a known limitation, never fixed.
- `sec-analyzer` was installed as an editable pointing at the same dead root. Its only importer is `scripts/pipeline/legacy/_commands.py`, which `validate` asserts never loads, so the `requirements.txt` pin was both unsatisfiable from PyPI and pointless.
- **`scripts/.venv/bin/pip`'s own shebang** points at a *third* dead path (`~/Documents/⭐성진이의 옵시디언/…`), so the venv has been relocated twice. `bin/python` works; every console script in that venv does not. Route through `python -m pip`, `python -m pytest`.

**`pytest` was never installed in `scripts/.venv` and was not in `requirements.txt`.** Phase 01's exit criterion #4 (`scripts/.venv/bin/python -m pytest scripts/tests/test_evidence_contract.py`) was therefore unachievable as written, and so was the whole verification story for the untracked 55-test sector-map suite. **Nothing in phases 01–07 could be verified until this was fixed**, which is why it became a phase-0 rather than an item inside 01.

Consequence: **01.5 was pulled forward into phase 00.** `test_evidence_contract.py`'s `ROOT = SCRIPTS_DIR.parents[3]` bug meant the two tests guarding the fact/judgment seam — C1, the invariant the whole harness rests on — had never once executed. Fixing it first is what made every later "it passes" mean something.

## 02.6 — the premise is false. Deferred.

The plan says `serenity_eval.py:59-66` and `:79-83` "reimplement the `Lens:` and Downsides/falsifier checks." **They do not.** Those lines are the `lens_run` and `bear_and_falsifier` entries of `RUBRIC` — natural-language questions handed to an LLM judge. The only `re.compile` in the file are `_EVENT_RE:105` and `_FEAR_RE:111`.

So there is no duplicated regex to extract, and exit criterion #3 ("no duplicated regex remaining in `serenity_eval.py`") is **vacuously true and unfalsifiable**. The appendix is more honest than the phase file here: `99-appendix-findings.md:399` says the fix is to run a deterministic pre-pass in `report`, which is *building a new consumer* — phase 04.5 work.

Extracting a shared module now would produce a module with exactly one consumer, at the cost of breaking the hooks' deliberate zero-local-import property (`run_fixtures.py` advertises "dependency-free… runnable from any checkout"), and would force an unresolved placement decision: `.claude` is not a valid Python identifier, so a module there is not importable from `scripts/` by normal syntax; a module under `scripts/` makes every hook fail wherever `scripts/` is absent.

**Move 02.6 to the phase-04 session, where its second consumer is actually built.** It is not a prerequisite for anything in the code layer.

## 02.2 — the numeric bar is line-level, not per-operand

The plan proposes rejecting a `Lens:` line "whose operands are placeholders rather than numbers," calling the per-operand form "the sharper of the two."

Per-operand **inverts the suite's only positive assertion.** `verdict_gate/silent_full.json` — the one fixture asserting that a *correct* answer produces *silence* — carries:

```
Lens: floor — EV/Rev 18 ÷ MC $3.2T = defensible base; upside — content×volume ÷ MC = the re-rate leg.
```

The upside leg's operands are words. `hard_nfi.json` carries the same construction. The bar is therefore **at least one numeric-or-currency operand per `Lens:` line**, recorded as an accepted limit: the check verifies "an arithmetic expression with real numbers is present," not "every leg is numeric."

## 03.3 layer 3 — must WARN, never FAIL

The plan says to "change `validate`'s check to lint the most recent real scorecard under `sessions/`." That directly inverts the validator's own stated contract at `serenity_harness.py:200`: *"Structure only — never sessions/ CONTENT, which is runtime data, not harness wiring."*

And it has no in-scope fix. All seven archived scorecards violate the schema, and `date` / `data_as_of` / `mc` are unrecoverable without re-running the pipeline — back-filling them would produce a file that *looks* current while carrying expired numbers, which the spine's "numbers expire, structure doesn't" rule exists to prevent. So a hard failure would make `validate` **permanently red over history nobody can repair**, and a red banner that cannot be cleared is one people learn to dismiss. That would undo the entire point of phase 01.

Implemented as: a **separate** `scorecard_conformance` check (kept out of `_check_reproducibility`, whose contract is wiring alone), emitting **`warn`** — `hard_fail` counts only `"fail"`, so a warn costs nothing — under a **boundary date** (`_SCORECARD_LINT_FROM`), dated off the session folder's own `{yymmdd}`.

## 03.5 — adopt WITHOUT the `relationship:` field

The plan's `relationship: owner | tool | consumer | adjacent_proxy` field cannot be added alone. `_validate_object` (`serenity_sectormap.py:118-124`) treats `_CANDIDATE_FIELDS` as **both required and closed**, and `load_map` *raises*, so `show` / `layers` / `tickers` / `cohort` / `diff` all die — not just `validate`. The one real map has **100 candidates, none carrying it**, so the field would take a fully working tool to fully dead. It also needs 100 tickers classified by judgment against a real archive, which this session explicitly scoped out.

`--include-adjacent` goes with it: without `relationship:` there is nothing for it to filter on.

**What was done instead, addressing the same underlying defect:** `cohort` now carries each candidate's `role`/`note` beside the argv. The map already disclaims some names as "theme exposure, not bottleneck ownership" — the command was simply discarding that field before the comparator saw it. Surfacing it is fact-loading, needs no schema change, and puts the analyst's own caveat where it matters.

To finish the original item later: add optional-field support to the validator **first**, or do the field and the 100-candidate migration in one pass.

## 01.3 — a timeout must EMIT, not be swallowed

The plan says to narrow `session_status.py`'s except to the modes that mean "nothing to report (missing file, **timeout**, empty stdout)."

That was right *before* 01.2 and wrong *after*. Once the fixture suite runs inside `validate`, a timeout means **the fixtures did not finish** — a signal, not a non-event. Swallowing it restores exactly the blind spot 01.2 exists to remove. Implemented with three distinguished outcomes: red, crashed, timed out.

Related: **phase 07.1's tests must not enter the hook fixture suite**, since `validate` runs it behind `session_status.py`'s 30s timeout. They live in `scripts/tests/` as pytest, which `validate` never invokes.

## 01.1 — the scaffolding move needs an explicit env override

Relocating the fixture scaffolding cannot be done by rewriting the fixture payloads. `verdict_gate.py:153` anchors its capture on the literal `sessions/` immediately after `Saved:`, so a rewritten path stops matching **entirely** and lands in the "not a valid session path" branch, inverting `silent_full` and `saved_backtick_silent`. Loosening the regex would let a test dictate the production contract.

The sound mechanism was already in the hook: `verdict_gate.py:168`, `base = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()`. `run_fixtures.py` now passes `CLAUDE_PROJECT_DIR` **explicitly**, pointing at its own sandbox.

**The explicitness is the whole point.** `run_fixtures.py` previously passed `cwd=ROOT` and no `env=`, so relying on the `or os.getcwd()` fallback would pass in a terminal (variable unset) and fail at every real SessionStart (variable set by Claude Code to the repo root) — a trap that is invisible exactly where you test it. Verify any change to this with the variable both unset and set.

## New work not in the plan

**Fixture autodiscovery (01.1b).** `run_fixtures.py` discovers fixtures by directory and reads each expectation from an `_expect` key inside the fixture. Two consequences: adding a fixture touches only the new file, which is what made a four-agent fan-out safe; and the pass count is printed rather than asserted, so it cannot rot. `22/22` had appeared in nine documents while the suite was at 19/22, and `15/15` in six more. A fixture with no `_expect` is a hard FAIL, never a skip — a skipped fixture is indistinguishable from a passing one.

**`hooks` check restructured to event → list.** It was event → *one* script, which could not represent a second `PostToolUse` hook at all; adding one left it entirely unvalidated. It now also flags a script present on disk but not referenced in `settings.json` — and caught exactly that during implementation.

**`run_fixtures.py` assertions match decoded text.** Hooks emit `json.dumps` at default `ensure_ascii=True`, so an em-dash on the wire is `—`. Matching raw stdout would force fixtures to assert the escaped form — invisible until it bites, and it bites hardest on the prose most worth asserting, since these hooks use dashes and Korean freely.

**`rankdiff` tier canonicalization found real drift on its first run.** The archive's `_ranking.md` carries `EXIT/TRIM`, outside the doctrine's fixed vocabulary. Contrary to the plan's "reject with a named error," unknown tiers are **reported and excluded from the agreement math**, not rejected: refusing the whole diff over a few rows destroys the agreement percentage for every other row — including comparisons where the bad row is not even in the intersection — and the archive legitimately contains rankings written before the vocabulary existed. A measurement that refuses to run is not safer than one that names what it skipped.

## Two defects found by USE, not by review

Both surfaced from subagents doing the work reporting back, and neither would have been found by reading the diff. Worth recording because the mechanism generalizes better than either fix.

**A dev report about `verdict_gate` was hard-blocked by `verdict_gate`.** The agent's own summary quoted its fixtures' example vocabulary — a price target, a rating, "overweight", "priced-in" — which sets `other_finance_signal` without any cashtag. The 2.4a suppression is scoped to the cashtag-only path by design, so it never applied. This is the plan's own stated 16th case for the 2.4 group ("the harness's own development… this repo talks about tickers, valuation, and dilution constantly *as subject matter*") arriving in production rather than in a fixture.

Fixed with a marker deliberately narrower than `dev_context`: a **literal repository filename or path**, not a topic word. "harness" or "refactor" can appear in a real market answer; `verdict_gate.py` or `.claude/hooks/` cannot. That tightness is what makes it safe to apply against the layer's only hard block.

And the first attempt at it was itself over-broad — `fixtures?/` matched `sessions/990101.hook-fixture/` inside a genuine `Saved:` mark, so a real archived verdict stopped blocking. **The fixture suite caught it on the first run.** The transferable lesson is in the code where the pattern was removed: a path fragment general enough to feel safe is general enough to match the archive, and this guard suppresses a hard block, so over-matching is the expensive direction.

**A shared definition handed to two agents carried an error, and the agent flagged it rather than following it silently.** The agreed market-anchor keeper-list included `목표가`. Every other entry is an ACTION (매수/매도/살까/팔까/물타/존버) or a scope-setter (종목, 장 어때); `목표가` is simply "price target" in Korean — the same token being dropped in English on the very same pass. Keeping it left the identical bug open for a Korean dev prompt. The agent applied the rule it was given, noticed the list contradicted the rule, and asked instead of resolving it alone. **A shared definition duplicated across two files is worth more when its holders are told the rule behind it, not just the list** — the list is what drifted; the rule is what caught it.

## Still open, deliberately

- **02.6** — moves to the phase-04 session.
- **`relationship:` + the 100-candidate migration** — needs optional-field support in the validator, or a one-pass migration.
- **The seven archived scorecards** — grandfathered. Resolve on the next cohort re-run, not by patching frontmatter onto expired numbers.
- **The filings *subagent's* judgment promises** — "silence is null," "quote and cite." The CLI beneath them is now contract-tested, which removes the raw material for the worst failure; whether the agent honors a clean `data_unavailable` instead of answering from memory needs a live agent loop and remains unverified. Stated in the test module so the file's existence does not imply coverage it lacks.
- **Phases 04, 05, 06** — untouched. 04's baseline run and 05's corpus extraction are the token-heavy halves, and 06 is gated on both.
