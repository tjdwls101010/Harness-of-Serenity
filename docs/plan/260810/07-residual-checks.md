# Phase 07 — the two residual checks

**Prerequisite:** Phase 01.

The audit's synthesis closed by naming five things its six lenses never looked at. The owner selected two for this plan. The other three are recorded at the end so a future session knows they were considered and deferred rather than missed.

---

## 7.1 — Does the filings subagent keep its own promises?

**Why this one.** The scorecard subagent's promises have already **provably** drifted in the wild — seven of seven real scorecards violate the schema its own body pins, including the one field that body explicitly forbids. Nobody has run the equivalent check on `serenity-filings`, and it is the more consequential of the two: it is the sole source of the filing's structured disclosure numbers (customer concentration %, geographic revenue %, inventory composition, purchase obligations), and the doctrine routes around web search specifically because a web figure can silently be the wrong ticker's or a stale period's. If this agent degrades toward a paraphrase or a remembered number, every downstream guard is intact and the input is wrong — the exact failure mode the harness's own "data-error mispricing" gotcha describes, turned on itself.

**What to test.** Three behaviors the agent's body promises, none of which anything currently verifies:

- **Hard-stop on a blocked read.** Non-negotiable 9a says a line nulled by a blocked EDGAR read hard-blocks the archetype tag until reconciled — never "proceed structurally." Run with EDGAR genuinely blocked and observe: does it return `data_unavailable` and say what is missing, or does it fill from prose, from memory, or from a web result? A live example already exists in the archive — `NBIS.md` records `gates: "blocked: financing structure — EDGAR 403 all session"`, which is the *correct* behavior and is worth studying as the reference case before testing the failure paths.
- **Silence is null.** Give it a filing that genuinely does not disclose a customer name. The body says the field is empty and the absence is itself a fact. Confirm it does not infer one from the ticker or from what "everyone knows."
- **Citation is real.** Every number it returns should carry the XBRL concept or the form-and-item it came from. Spot-check that the citations resolve and that the figure matches — a citation that is present but wrong is worse than none, because it converts a guess into evidence.

**Shape of the test.** Prefer fixtures over a live loop where possible: a few captured filing payloads plus the blocked-EDGAR case, run through the agent, with expected-behavior assertions. That makes it re-runnable after any edit to the agent body, which is what turns this from a one-time check into a guard. Where a behavior genuinely needs a live SEC call, isolate it and mark it as such.

**The 16th case:** any future subagent. The generalizable finding is that **a subagent's body is a promise nothing verifies** — the harness has two, and the one that was checked had drifted completely. Whatever form this check takes should be cheap enough to apply to the third.

## 7.2 — A prose-growth tripwire

**Why this one.** Every fix in this plan adds a hook clause, a schema field, or a doctrine sentence. The audit's own synthesis flagged that its bloat warning is qualitative — there is no number, so nothing distinguishes "the harness grew because it needed to" from "the harness is accreting." The harness's spec names per-miss patching as the root cause of bloat and the commit history shows four rounds of it, so this project has already demonstrated it is susceptible.

**What it is.** A `validate` check that measures the always-loaded budget and total doctrine prose, prints both, and warns on a delta larger than a set threshold since the last recorded measurement. Store the baseline in `harness-spec.md` beside the change history, so growth is attributable to a named change rather than appearing as an unexplained trend.

**What it explicitly is not.** Not a cap, and not grounds for deleting anything — C5 is binding and this check must never be read as authorizing a diet. Its job is to convert a hunch into a signal: growth is fine, *unexamined* growth is not. A warning that fires and is dismissed with a one-line reason in the change history is the check working exactly as intended.

Measure at least the always-loaded budget (CLAUDE.md, plus any rule without a `paths:` glob, plus expanded imports) separately from on-demand skill bodies, since those two costs are paid on completely different schedules and merging them hides which one moved.

**The 16th case:** growth that happens across many small commits, none individually notable. A per-commit delta would be noise; a cumulative figure against a recorded baseline is what catches the trend. The threshold matters less than the fact that the number is printed every session and lands in the spec.

---

## Deferred, with reasons

Recorded so a future session knows these were seen.

**Investing-judgment quality was never audited.** All six lenses asked whether the doctrine is internally consistent, non-rail, undrifted, correctly routed and correctly measured. **None asked whether the six winner gates, the R1–R6 precedence, or a given archetype playbook is good investing judgment** rather than merely well-wired judgment. Even a fully repaired eval only measures conformance to a rubric, and that rubric's own validity as a proxy for "reproduces the real method" has never itself been questioned. This is the largest open question in the project and it is genuinely hard — it needs a domain expert or a deliberate red-team, not another structural pass. Phase 05's provenance layer is the closest available proxy, since it at least separates what came from him from what the harness invented.

**The input-trust boundary.** The filings subagent reads real SEC filings and can run WebSearch; nothing has tested whether hostile or malformed content inside ingested text could manipulate a number that is then reported as verified and byte-cited. The quieter failure matters more in practice: a degraded-but-not-wrong-ticker source — yfinance rate-limited or returning partial data — where "retry, then say unavailable" is enforced by nothing except the model remembering to comply. Deferred as lower frequency, but 7.1's fixtures are the natural place to add it later.

**Long, compacted and concurrent sessions.** Every test in the audit was a synthetic single-shot message or a freshly sampled case. Nobody has checked whether a `Saved:` or `Lens:` obligation established forty turns before a compaction is still honored in the final message the Stop hook actually sees — and compaction is the normal condition for a long analysis session, not an edge case. Nor has anyone tested the production equivalent of the eval's concurrent-write risk: two real sessions racing on `sessions/INDEX.md`. Phase 04.6 isolates the *eval's* instance of this; the production instance remains open.
