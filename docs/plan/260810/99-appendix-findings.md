# Appendix — the 37 verified audit findings

Raw material for implementation, produced by a 13-agent audit (6 independent lenses, each finding put through an adversarial refutation pass) on 2026-08-11 against commit `89392df`. Every finding below SURVIVED refutation; the verifier's note records what it checked and any severity correction. Reproducing this cost ~2.1M tokens, so treat it as the source of record rather than re-deriving it.

Severity is the verifier's corrected value where it differs from the finder's. Line numbers are as of `89392df` — re-confirm before editing, they drift.

## F01 · [HIGH] Hook fixture suite is 19/22 right now, not the 22/22 harness-spec.md (and CHANGELOG/wiki) claim — the fixture scaffolding was deleted from disk

**Where** — .claude/harness-spec.md:45

**Failure** — Run `scripts/.venv/bin/python .claude/hooks/tests/run_fixtures.py` today: it prints '19/22 fixtures passed' with 3 explicit FAILs — verdict_gate/silent_full, verdict_gate/saved_empty_folder, verdict_gate/saved_backtick_silent. Cause: `git status` shows `sessions/990101.hook-fixture/FIXT.md` and `sessions/990102.hook-empty/.gitkeep` as unstaged deletions of tracked files, and both are actually gone (`ls sessions/990101.hook-fixture` → 'No such file or directory'). These two folders are the filesystem scaffolding `verdict_gate.py`'s `Saved:`-mark branch resolves against — docs/wiki/Session-Archive.md:34 and :196/273 label them 'test scaffolding — do not delete' / 'committed' — so their absence isn't a doc gap, it's the harness's own documented invariant being violated on disk. The same false '22/22' claim is repeated verbatim in CHANGELOG.md:36 and six docs/wiki pages (Hooks-Reference, Getting-Started, Troubleshooting, Release-Process, Testing-and-Validation, Session-Archive), so the drift isn't confined to one file.

**Why it matters** — harness-spec.md's own preamble says 'the next audit compares against this; keep it in sync' — trusting the 22/22 line would make an auditor certify the verdict_gate `Saved:` contract as fully regression-tested when 3 of 13 scenarios are currently unverifiable. Worse, this regression is structurally invisible: `session_status.py`'s SessionStart hook exists specifically to 'fail loud if the harness wiring regressed,' but it only shells out to `serenity_harness.py validate` (which reports 15/15 green and never calls run_fixtures.py), so a deleted test-fixture folder can sit broken indefinitely with the harness's own self-check reporting all-clear every session.

**Proposed fix** — `git checkout -- "sessions/990101.hook-fixture/FIXT.md" "sessions/990102.hook-empty/.gitkeep"` to restore the tracked scaffolding from the index, confirm run_fixtures.py returns 22/22, and add a 16th `validate` check that shells out to run_fixtures.py so a future deletion fails loud at SessionStart instead of only surfacing when someone manually inspects .claude/hooks/tests/.

---

## F02 · [HIGH] No generator for session folders — the `{yymmdd}.{topic-slug}` convention broke on its first real use, and the break actively corrupts the Stop-hook's own compliance check

**Where** — CLAUDE.md:126-128 (session-archive convention); sessions/INDEX.md:3-4 (format + "English only"); .claude/hooks/verdict_gate.py:153 (Saved: regex)

**Failure** — The only session folder this repo has ever produced is `sessions/260726. 반도체 인더스트리 딥리서치/` — a space then a Korean phrase, not the `{yymmdd}.{topic-slug}` kebab format the doctrine names (INDEX.md's own header says 'English only'). I fed verdict_gate.py a synthetic message ending `Saved: sessions/260726. 반도체 인더스트리 딥리서치/` (the real, existing path, run directly via `python3 .claude/hooks/verdict_gate.py`) and it printed the soft nudge: "a `Saved:` line is present but not a valid session path" — a confirmed false positive on a session that is fully archived and correct, because the hook's regex `sessions/\d{6}\.[a-z0-9-]+` cannot match a space or Hangul right after the dot. Any future turn citing this session by its Saved: line gets nagged to re-archive finished work, and nothing stops a second session from repeating the exact mistake, since the date+slug are composed from memory under output pressure with zero validation at write time.

**Why it matters** — This is the harness's only enforcement point for its archival convention, and it is confirmed broken by real data, not a hypothetical. The rule bundles four separate prose facts the model must recall correctly (date math, slug charset, collision-suffix handling, verdict-free index-line shape) on nearly every substantive turn — exactly the output-pressure condition verdict_gate.py's own docstring says causes 'prose read as a label and skipped.'

**Proposed fix** — Add `serenity_harness.py new-session --slug <kebab-only> [--type ranking|analysis|macro|postmortem] [--tickers T1,T2,...]`: compute `{yymmdd}` from wall-clock (never model memory), validate `--slug` against `^[a-z0-9-]+$` at the argument boundary (reject before mkdir, not after), auto-suffix `-2`/`-3` on collision, create the folder, and print both the exact `Saved: sessions/{yymmdd}.{slug}/` line and the exact INDEX.md append line ready to paste — so the model transcribes generated text instead of composing four rules from memory. Reuse `serenity_sectormap.py`'s `JsonArgumentParser` pattern (already in this repo) for always-JSON errors instead of raw argparse.

---

## F03 · [HIGH] The `Lens:` line is shape-checked but never arithmetic-checked — spec the already-approved lens CLI's argument space

**Where** — CLAUDE.md:124,150 (Lens: contract, non-negotiable #10); .claude/hooks/verdict_gate.py:96-108 (lens_marker — presence-only regex); .claude/skills/serenity-analysis/SKILL.md:111-129 (driver catalog), :260-261 (§6 GATE + machine-checkable-line requirement)

**Failure** — Nothing today stops the model from printing `Lens: content×volume÷MC — 1200×50000÷2,500,000,000 = 240` when the correct value is 24 (a plausible $B/$M unit slip). verdict_gate.py's `lens_marker` check (lines 105-108: `_has(r"Lens:[^\n]*[×÷*][^\n]*=", msg) or _has(r"Lens:[^\n]*=[^\n]*[×÷*]", msg)`) only asserts a `×/÷/*` operator and an `=` sit on the same line — it never recomputes the result. Per non-negotiable #10 this exact number 'authors the priced/cheap verdict,' so a 10x mental-math slip sails through the one gate built to catch an unrun lens, and the hook reports success.

**Why it matters** — This is the single highest-stakes number in every B-type answer, and it is presently produced the one way every other number in this harness is explicitly forbidden to be produced: from the model's own unverified arithmetic. CLAUDE.md line 26's whole design thesis — 'code loads facts because a wrong number silently inverts a call' — doesn't yet cover the Lens: line.

**Proposed fix** — Give the already-approved lens-arithmetic CLI one subcommand per doctrine-named driver, each taking ONLY that driver's model-supplied (deduced/estimated) inputs — never re-fetching facts the pipeline already loads (PEG and the no-growth floor are already `valuation_inputs.forward_pe` / `valuation_inputs.no_growth`, so they need correct citation, not a new subcommand): `content-volume --content --volume --mc`, `mw-irr --rev-per-gpu-hr --mw --cogs-per-mw --financing-rate`, `replacement-cost --capacity-units --cost-per-unit --comp-ev-per-unit`, `pro-forma-fcf --cogs-addressable --opex-saved --new-recurring-rev --multiple`, `net-cash-after-atm --raised --shares-cost --sbc-funded`, `sum-of-parts --stake-value --operating-value --parent-mc`, plus a `custom --expr 'a×b÷c' --inputs k=v,...` escape hatch for the re-anchor cases doctrine explicitly allows (Strategic monopoly, float-yield, etc.) so the catalog stays open, not a closed rail. Every subcommand's ONLY output is the exact, arithmetically-verified `Lens: <name> — ... = <result>` string (`--fork floor|upside` tags the leg) — it must never rank drivers, choose which lens applies, or print a priced/cheap word; that judgment stays the model's.

---

## F04 · [HIGH] Evolution gate-3's funded-vs-dilution enforcement checklist is scoped to "the neocloud," not to capital-intensive buildouts generally

**Where** — .claude/skills/serenity-analysis/SKILL.md:53-62 (header at 53, "This is R4 at the neocloud" at 54, "Two follow-on traps" at 60-62)

**Failure** — A user asks about an SMR nuclear developer, a green-hydrogen electrolyzer builder, or a battery-gigafactory name — all Evolution-archetype, all funding construction off a live at-market ATM sized near market cap while touting a "strategic MOU" with a utility/hyperscaler for future offtake. This is structurally identical to the neocloud GPU-ATM pattern the section was written to catch (per the round-1/round-2 commit messages, this exact block was built to rescue NBIS/SNAP-adjacent misses). The general gate-3 principle stated earlier ("a buildout funded by its own at-market ATM/serial dilution does NOT [clear]") is present and would fire. But the operationalized checks that catch the specific evasions — "a purchase/brand/strategic agreement is not funding," the tranche-carve-out-doesn't-launder-dilution trap, "a silent filing is not a funded confirmation" — sit entirely under a header reading "This is R4 at the neocloud," in GPU/hyperscaler/Mag7 vocabulary throughout. A model triaging which doctrine block applies to an SMR or hydrogen name can read "neocloud" and judge the block inapplicable, actively skipping the granular traps rather than merely lacking them.

**Why it matters** — This is worse than a missing worked example: the section header functions as a relevance filter, and it filters OUT the exact class of question it should generalize to. R4 ("who put capital at risk, on what terms") is domain-general and this harness explicitly disclaims being semis/AI-only ("never fall back to semis/AI when asked about a new domain"), yet the one place this gate's teeth actually live is dressed entirely in one sector's clothing. The topic sentence generalized after WF4's misses; the enforcement layer underneath it did not.

**Proposed fix** — Reframe the header and opening line to name the general case first ("Evolution gate-3 — verify which side of funded you're on, on any capital-intensive buildout; the neocloud is the worked instance") and de-sector the two follow-on traps' language (e.g. "the GPU leg" -> "the funded leg") so neocloud becomes one bracketed example rather than the frame a model matches against.

---

## F05 · [HIGH] "The 6 winner gates" is closed ("clears ALL six") with no extension principle, unlike the kill-signal list in the same file

**Where** — .claude/skills/serenity-analysis/SKILL.md:66-77 (list at 70-77; "Survival to the ramp" at 74); contrast with :213-214 ("The 9 kill signals (+ the principle that spots a 10th)")

**Failure** — A domestic HALEU/uranium-enrichment name, or a rare-earth-separation name, clears all 6 named gates cleanly: it monetizes, has pricing power, a strong balance sheet, TAM-expansion room, allocation control, and broad demand. Its NRC license (or an EPA permit) then stalls for years and the plant never ramps. Gate 3, "Survival to the ramp," is explicitly defined as balance-sheet survival ("can the balance sheet last to monetization?") — a well-capitalized name can lose entirely to a permitting delay despite passing every gate as literally written, because none of the 6 asks about regulatory/permitting risk at all.

**Why it matters** — A permitting/regulatory block is a structurally independent way a real chokepoint "returns nothing" (the section's own organizing test), yet the list is presented as closed ("clears ALL six") with no license to add a 7th — contrast the kill-signal list 150 lines later in the SAME file, which explicitly states "Define the kill by this PRINCIPLE, not the list, so you catch the #10 that isn't enumerated." The asymmetry between two structurally identical checklists in one document is itself evidence this one wasn't written with extension in mind, and Bottleneck is the harness's default archetype ("Hardware/materials defaults to Bottleneck") — this list runs on the largest share of single-name questions.

**Proposed fix** — Fold regulatory/permitting survival explicitly into gate 3 ("can the balance sheet AND the regulatory pathway last to monetization?"), or add the same generative disclaimer the kill-signal list already carries.

---

## F06 · [HIGH] Check 6 ("RUN, not tagged") is the only pre-answer check with no downstream verification, no skill pointer, and its worked technique sits in a skill the funnel doesn't route bare-ticker questions to

**Where** — CLAUDE.md:101 (check 6, no closing pointer) vs CLAUDE.md:149-150 (NN9/NN10, each closes with an explicit "mechanics live in serenity-analysis §X" pointer); .claude/hooks/verdict_gate.py:96-146 (structural checks exist for Lens:/NFI-NFA/Downsides/falsifier/bear-bull-legs/Saved: — none for recursive-hop/second-order/sibling); .claude/skills/serenity-discovery/SKILL.md:47-55 (the only "recursive hop" worked procedure in the whole harness) vs zero hits for "recursive" in serenity-analysis/serenity-macro and zero hits for "second-order" or "sibling" in any of the three skill bodies

**Failure** — User asks "is $AXTI a buy" — a bare ticker. Per CLAUDE.md:92/109 the model loads `analyze` + serenity-analysis only; serenity-discovery is explicitly framed (CLAUDE.md:108) as the *finding* skill for when you don't have a ticker yet, so nothing routes a B-type question to it. Archetype comes back chokepoint, so check 6 applies. The model has CLAUDE.md's one summary sentence in context but never loaded discovery's three-test stopping rule (does concentration rise / does the end-use demand a higher grade / is the dependency captive) that actually operationalizes "recursive bottom hop" — because nothing routed it there and check 6 names no pointer. It writes a plausible paragraph naming "the substrate" as the bottleneck, satisfies check 6 nominally, and the Stop hook — which structurally re-checks four other contract items — has no equivalent check for this one and lets the answer stand.

**Why it matters** — Every other bold, "load-bearing" directive in CLAUDE.md gets a hook (Lens:, NFI/NFA, Saved:) or at minimum an explicit "mechanics live in serenity-X §Y" pointer (NN9, NN10) — usually both. Check 6 gets neither, despite being the densest of the six checks (three full elaborated sentences vs. one clause each for checks 1-5) and despite its scope trigger ("chokepoint only") being a label the model itself assigns earlier in the same turn, with a standing documented incentive to mislabel toward a softer archetype (CLAUDE.md:89: "relabel... never to unlock a softer valuation"). That's two independent escape hatches — mistag out of scope, or nominally gesture inside scope — on exactly the moves the task brief's own eval data flags as weakest-reproduced.

**Proposed fix** — Reorganize, don't delete: (a) end check 6 with the same pointer form NN9/NN10 already use — "mechanics: the 3-test recursive-hop stopping rule live in serenity-discovery's 'The recursive hop' section; load it even on a bare-ticker B-type question when check 6 applies"; (b) add one cross-reference sentence in serenity-analysis §1 near gate 5 ("Allocation control = synthetic bottleneck", which is check 6's second-order content in substance but currently uncredited as such) pointing back to check 6 by name, so the skill a B-type question actually loads carries the depth; (c) extend verdict_gate.py's existing soft-nudge pattern (it already does this for the bear/bull-leg fork) with one more structural, non-semantic check: on a chokepoint-scoped answer, flag when no token naming a sub-layer beneath the headline node (feedstock/purity/substep/etc.) appears — same presence-only philosophy as the existing `lens_marker` check.

---

## F07 · [HIGH] The countable-end-unit `discover` comparator is placed BEFORE the valuation verdict in CLAUDE.md's routing reflex but AFTER the rating in serenity-analysis §6

**Where** — CLAUDE.md:99 (reflex b: "...shows the MC-vs-forward-revenue ranking before quoting the subject's own multiple") vs .claude/skills/serenity-analysis/SKILL.md:268 ("Close comparatively" — the identical `discover` call, positioned as the LAST paragraph of §6's required content, after Rating)

**Failure** — "Is $AAOI still worth owning here?" AAOI is a countable-end-unit supplier, so reflex (b) fires: CLAUDE.md:99 requires the comparator table to appear, with its cross-peer ratio (not the standalone PEG) as the verdict, before the subject's own multiple gets quoted. But the B-template (CLAUDE.md:119) sequences "valuation with the lens named" as step 3 of 6, well before "rating" (step 6) — and §6, which is what actually spells out what "valuation" and "close" mean in the rendered answer, ties the identical `discover` call to the closing paragraph, after Rating. Following §6 literally: the valuation section quotes the subject's own EV/Rev or PEG (since nothing there says to hold off), the rating gets printed, and only in the closing paragraph does `discover` run and the comparator appear — by which point the "verdict" the reflex said must rest on the cross-peer ratio has already been rendered off the standalone multiple.

**Why it matters** — This reproduces the exact anti-pattern N10/R5 exist to prevent ("A verdict resting on the subject's OWN top-down multiple IS the consensus read the gap is built against... unfinished, not conservative"). Reflex (b) is one of only three mechanics CLAUDE.md explicitly flags as firing "on their own, before you settle into a B-type read" — i.e., marked high-precedence — yet the skill section that operationalizes paragraph order relegates the identical tool call to the closing flourish. Neither document acknowledges the other's placement requirement, so nothing signals these are ONE action rather than two; the likely outcome is whichever text was read most recently (probably §6, being the more detailed, more recently-loaded skill content) wins, silently dropping CLAUDE.md's earlier, higher-salience placement.

**Proposed fix** — Make one document own the placement and have the other point to it. Keep the substantive "before quoting the subject's own multiple" instruction at CLAUDE.md:99 (it's the always-loaded surface, and the routing-reflex framing already marks it as pre-empting the normal template order). Rewrite serenity-analysis:268 to stop re-issuing the `discover SUBJECT PEER1 PEER2…` instruction and instead read: "on a countable-end-unit/inherently-comparative name this ranking already ran per the CLAUDE.md routing reflex and sits before the Valuation section above — the close is the one-line callback to it, not a new tool call."

---

## F08 · [HIGH] The scorecard frontmatter schema is pure prose with no enforcement path, has already drifted 100% in the one real archived session, and the validator that's supposed to catch this only checks the SPEC file's self-consistency, not real output

**Where** — .claude/agents/serenity-scorecard.md:41-64 (pinned schema + explicit "No tier field" rule at line 64) vs all 7 real files in "sessions/260726. 반도체 인더스트리 딥리서치/" (AAOI.md, LITE.md, ONTO.md, KLIC.md, TSEM.md, NBIS.md, 000660.KS.md); validator blind spot at scripts/serenity_harness.py:213 (`sentinels = "gate_strength:" in text and "conviction:" in text` checked against serenity-scorecard.md's OWN text, never against a written sessions/ file)

**Failure** — A future session asks "which of my saved names are chokepoint-archetype, and is AAOI's tier still 3?" `grep "archetype: chokepoint" sessions/` returns zero of the six real Bottleneck-archetype scorecards — all seven files write `archetype: Bottleneck` (matching serenity-analysis's own proper-noun section headers, not the schema's lowercase `chokepoint` enum), and all seven also carry a `tier:` field the schema explicitly forbids ("a scorecard that carries a tier is inviting itself to rank, and it can't see the cohort") while omitting `type`/`session`/`date`/`data_as_of`/`mc`/`gate_strength` entirely. Meanwhile `serenity_harness.py validate` reports this layer green every session, because its "schema sentinel" check only greps for the strings `gate_strength:` and `conviction:` inside serenity-scorecard.md itself — the spec file — never against any file actually written under sessions/.

**Why it matters** — This is the interface-over-document failure named in the audit brief, caught with direct evidence: the schema is reachable only via a two-hop pointer (CLAUDE.md never mentions it; serenity-analysis's Rank-N protocol says "read serenity-scorecard's body for the schema when filling scorecards inline"), so it is re-derived from memory on every inline fill rather than re-read from a signature — and the one real session that exists (which explicitly attests "same schema, same precedence" after its agent fan-out failed and it fell back to inline scoring) still drifted on every file. Because grep-based retrieval is the harness's own documented way to check `sessions/INDEX.md` for priors ("a ticker grep is safe" — evidence_discipline.py), a silently-renamed enum value or a silently-added forbidden field defeats exactly the retrieval path the archive exists to support, and the self-check that's supposed to catch drift (session_status.py → serenity_harness.py validate, which "fails loud" when red) structurally cannot see it.

**Proposed fix** — Reorganize, don't delete: (a) add a PostToolUse hook, same shape as the existing data_integrity_guard.py (which already fires on Bash/`analyze` output), that fires on `Write` to `sessions/**/[A-Z0-9.]*.md` and soft-flags a frontmatter missing any required key or carrying the forbidden `tier:` key; (b) change serenity_harness.py's check at line 213 to also sample the most recent file under `sessions/` (if any exist) and check ITS keys against the schema, not just grep the spec file for its own sentinel strings; (c) have serenity-analysis's Rank-N protocol Step 1 inline the exact field list rather than pointing at the agent file, since the inline-fill path is precisely the one that skips loading that file at all.

---

## F09 · [HIGH] The literal "TLDR"/"TL;DR" token is a single point of failure for the entire Stop-hook contract

**Where** — .claude/hooks/verdict_gate.py:52-54

**Failure** — Verified by piping directly to the hook. last_assistant_message = "Bottom line: Nvidia is still the cleanest chokepoint long here, priced rich but not priced-in imo... PT $250, 12 months, LEAPS as the vehicle. Rating: overweight, high conviction. $NVDA is the name." (a cashtag, a PT, a vehicle, a rating, priced-in language, and ZERO NFI/NFA) produces empty stdout — no hard block, no soft nudge, nothing. Any opener that isn't the literal substring "TLDR"/"TL;DR" ("Bottom line:", "Quick take:", "Short version:") skips line 53's `if not _has(r"\bTL;?DR\b", msg): return` and every downstream check (NFI, Lens, Downsides, falsifier, Saved:) never runs.

**Why it matters** — CLAUDE.md mandates the TLDR opener but nothing enforces THAT requirement itself, so one stylistic habit gates everything else, including the one HARD block doctrine calls near-universal. This is worse than any single missed sub-check because it takes the whole deterministic layer down at once on a turn that is otherwise a complete, undisclaimed market verdict.

**Proposed fix** — Enter the gate on finance_signal (cashtag/PT/rating/vehicle — already computed further down) OR the TLDR token, not on TLDR alone. Check TLDR-presence as its own independent soft requirement instead of the gatekeeper for everything else.

---

## F10 · [HIGH] Company-name-only market talk (no cashtag, no listed vocabulary) is invisible on both the input nudge and the output gate

**Where** — .claude/hooks/verdict_gate.py:67-89 (finance_signal); .claude/hooks/evidence_discipline.py:19-29 (_INTENT)

**Failure** — Verified on both hooks. Prompt "should I load up on Nvidia here, or is it too risky at these levels?" -> evidence_discipline.py: silent, no pipeline-first reminder. Reply "TLDR: Nvidia is a screaming buy right now, the AI buildout isn't slowing down lol. -> hyperscaler capex still ripping -> the packaging step is the real constraint and it's not going away. I'd load up here, feels like the market's sleeping on this one honestly." -> verdict_gate.py: silent, zero NFI/Downside/falsifier/Saved nudge, despite an unambiguous, undisclaimed buy call with a TLDR present.

**Why it matters** — Both hooks key market-detection off a closed cashtag/vocabulary list — a rail, not a principle. The 'sharp friend over DMs' voice CLAUDE.md prescribes naturally reaches for a company's name over its cashtag and for casual verbs ('load up', 'screaming buy') that aren't in either list, so the harness misses the same turn on both ends: nothing tells the model to run the pipeline first, and nothing catches it for answering from memory with no disclaimer.

**Proposed fix** — Fire on the grammatical pattern (a capitalized proper noun + a buy/sell/hold/rating verb) rather than only a closed word list, or seed both regexes with a maintained company-name alias list (e.g. derived from sessions/INDEX.md tickers) alongside the cashtags.

---

## F11 · [HIGH] Downside/Falsifier soft-checks are satisfied by the section LABEL, not its content — a verdict that explicitly negates having a bear case or a falsifier passes clean

**Where** — .claude/hooks/verdict_gate.py:125-126 (Downside check), :127-128 (falsifier check)

**Failure** — Verified end-to-end (with a real, minimal archive folder+md so the Saved: branch also clears). Message: "TLDR: $NVDA is a screaming buy, priced-in doesn't matter here. NFI/NFA.\n\nStructural position: chokepoint.\nLens: EV/Rev N/A × N/A ÷ N/A = still good.\nDownsides: none that matter.\nFalsifier: can't think of one, pretty confident honestly.\nRating: overweight, shares.\n\nSaved: sessions/260811.token-test/" -> completely silent, zero hard or soft output. 'Falsifier' itself contains the substring 'falsif' that line 127's regex matches, so the bare label satisfies the check regardless of content; 'Downsides:' trips `\bDownside` on line 125 even though the very next words say there are none; the Lens line's inputs are the literal placeholder 'N/A' yet satisfy the operator+'=' structural check.

**Why it matters** — This is the deepest risk the brief names: under output pressure (the exact condition the hook's own docstring says it exists to counter), the cheapest way to silence the gate is to write the labels and negate their content — which reads as MORE compliant than omitting them while actually inverting V7/R6 (explicit bear case, an honest falsifier).

**Proposed fix** — Reject a Downside/Falsifier line whose remainder after the label is under some minimum length or matches 'none/n/a/can't think of' — this doesn't verify semantics, but it closes the label-as-content loophole in the same structural spirit as the rest of the file.

---

## F12 · [HIGH] session_status.py's fail-loud self-check fails SILENTLY exactly when serenity_harness.py itself crashes

**Where** — .claude/hooks/session_status.py:23-30

**Failure** — Verified via a controlled stand-in root (CLAUDE_PROJECT_DIR pointed at a scratch copy whose serenity_harness.py raises NameError inside cmd_validate, simulating a bad edit / broken import). Direct invocation: traceback on stderr, exit 1. session_status.py run against that same root: zero stdout, exit 0 — completely silent, identical to the green-and-quiet path.

**Why it matters** — The broad `except Exception: return` treats 'validate ran and is green' and 'validate could not even run' identically. The second case is the more dangerous regression (a real Python-level break somewhere the harness depends on) and is exactly the case the hook's own docstring says it exists to surface ('fail loud if the harness wiring regressed'). The fail-loud mechanism inverts to fail-quiet on its own worst-case input.

**Proposed fix** — Narrow the except to the expected failure modes (missing file, timeout, JSONDecodeError on truly empty stdout) and surface a distinct 'validate itself crashed' warning when the subprocess exits non-zero with stderr content, separate from the already-handled 'ran and is red' path.

---

## F13 · [HIGH] The committed hook-fixture suite is currently red (19/22, not the documented 22/22), and validate's "hooks" check never runs it — the regression is invisible to the harness's own self-check

**Where** — .claude/hooks/tests/verdict_gate/silent_full.json and saved_backtick_silent.json (depend on sessions/990101.hook-fixture/, currently deleted per `git status`); scripts/serenity_harness.py:293-324, decisive logic at :314-322 (only checks the four hook scripts exist as files)

**Failure** — Verified live, twice, in the current working tree. `scripts/.venv/bin/python .claude/hooks/tests/run_fixtures.py` right now prints `FAIL verdict_gate/silent_full`, `FAIL verdict_gate/saved_empty_folder`, `FAIL verdict_gate/saved_backtick_silent`, ending '19/22 fixtures passed' — because sessions/990101.hook-fixture/ and sessions/990102.hook-empty/ are deleted from the working tree (shown as `D` in `git status`, not yet committed). In the same tree, `scripts/.venv/bin/python scripts/serenity_harness.py validate` reports `"ok": true`, `"hooks": "pass"`, all 15 checks green — because that check (lines 293-324) only asserts the four hook scripts exist on disk, it never executes run_fixtures.py. session_status.py, gated on `report.get("ok")`, is therefore silent at every session start right now.

**Why it matters** — harness-spec.md records this suite as 22/22; it is not, right now, and nothing in the automated self-check would tell anyone. Likely mechanism: sessions/990101.hook-fixture/ and sessions/990102.hook-empty/ read, by the archive's own {yymmdd}.{slug} convention, as garbage placeholder dates (1999-01-01) to any future session doing 'clean up stale sessions' — the fixtures live inside the exact directory a hygiene pass is licensed to sweep, and one already did.

**Proposed fix** — Restore the two scaffolding folders (or regenerate FIXT.md / .gitkeep). Move test scaffolding outside sessions/ entirely (e.g. .claude/hooks/tests/fixtures/sessions/) so it is structurally distinguishable from real archived analysis and immune to future sessions-hygiene sweeps. Wire run_fixtures.py's exit code into serenity_harness.py validate so a fixture regression actually turns session_status.py loud.

---

## F14 · [HIGH] Sampler has no ticker-resolution check — verified 4/25 (16%) of the seed=7 draw return completely empty pipeline data

**Where** — scripts/serenity_eval.py:128-138 (_primary_ticker), :170-257 (cmd_sample — no pipeline/data-validity check anywhere in the candidate loop)

**Failure** — Ran the owner's exact planned command live: `serenity_eval.py sample --n 25 --seed 7`. It selects SIVE, ASHM, APPL, and XFAB as primary tickers. Running the real `serenity_pipeline.py analyze <TICKER>` on all four returns `"key_facts": {}` — verified by direct execution, not inferred. ASHM and XFAB 404 outright on yfinance. SIVE resolves with quoteType=NONE, no marketCap. APPL is a typo for AAPL in the source tweet (tickers=["APPL","GOOGL"], content compares Apple/Google to Samsung/SK Hynix) and yfinance resolves the literal string "APPL" to an unrelated MUTUALFUND with no longName/marketCap — not Apple. A claude -p blind-run on any of these four has no data to build a Lens: line, an archetype read, or any scorable move from; it will score near-zero on doctrine grounds that have nothing to do with doctrine quality. At n=6 (the CURRENT recorded baseline, same seed=7), SIVE alone is already 1 of 6 cases (16.7%).

**Why it matters** — This corrupts the exact metric the owner is trying to make trustworthy. Because sampling is seeded, this isn't washed out by re-running — the same seed deterministically and permanently burns ~1 in 6 cases in every future comparison at this seed, and expanding n (the owner's chosen fix) scales the absolute count of dead cases proportionally rather than diluting them.

**Proposed fix** — Inside cmd_sample's candidate loop, before accepting a candidate into `pool`, resolve its primary ticker (reuse the pipeline's own fact-loading path, e.g. import the function `cmd_analyze` in scripts/pipeline/_evidence_commands.py calls into, or a cheap direct yfinance lookup) and require at least `marketCap` or `sector` to be non-null; on failure, drop the candidate and keep scanning, exactly like the existing regex-based ticker filter. This only needs to run once per case actually chosen (~25-40 pipeline calls, ~5-8 minutes one-time), and it's a pure fact-check, not a judgment call, so it belongs in the deterministic sampler.

---

## F15 · [HIGH] _primary_ticker can select a ticker the thesis explicitly disclaims as NOT the subject

**Where** — scripts/serenity_eval.py:128-138 (_primary_ticker), :141-152 (_blind_prompt)

**Failure** — Case id 2059532571839729902 (drawn at n=25/seed=7; tickers=["DPZ"], the ONLY ticker tag present) has thesis_text: 'This was the company i personally liked + have positions in. Definitely not $DPZ. But kinda me of Soitec in a way. Power semi / SiPH exposure... ~$1.28B MC, EU chips act grantee.' The author uses DPZ (Domino's Pizza) purely as a negative rhetorical anchor for an unnamed ~$1.3B European power-semi name that was never given a resolvable cashtag in the DB. _primary_ticker still returns 'DPZ' (the only regex-valid ticker present), so _blind_prompt asks 'What's your read on DPZ? Is it structurally mispriced right now?' — and the harness will correctly analyze Domino's Pizza, a conventional consumer-discretionary name, which has nothing to do with the chokepoint economics the answer-key thesis is actually about. cmd_report (lines 285-299) tallies this case's 0/1 scores into the aggregate from `scores` alone; a judge noting the mismatch in free-text `notes` does not stop the six binary items from being counted as misses.

**Why it matters** — An uninterpretable case is worse than a hard one: it doesn't test method reproduction, it tests whether the harness can guess an unstated company from a 'definitely not X' hint, and it will reliably score near-zero regardless of doctrine quality, silently dragging down every per-move rate it touches.

**Proposed fix** — Add a cheap negation guard in candidate selection: skip a candidate whose selected primary-ticker cashtag is immediately preceded (within ~3 words) by a negation ('not', "isn't", "n't", '아니') in the thesis text. This is an imperfect proxy, so pair it with a one-time human eyeball pass over whichever seed's case set gets locked in as the standing regression sample — a fixed cost since that set is reused across every future audit.

---

## F16 · [HIGH] cmd_sample never uses the 12 hand-curated, archetype-labeled gold theses — archetype coverage is left entirely to chance

**Where** — scripts/serenity_eval.py cmd_sample (lines 170-257 — no reference anywhere in the file to db-mining-report.md or a fixed ID list); references/db-mining-report.md:48-65 (the 12-thesis set, each with an archetype label and a case-specific 'Tests:' annotation)

**Failure** — Verified directly: of the 12 curated IDs in section D, only 1 (2016921538780680402, CPSH) appears in the actual `sample --n 25 --seed 7` draw — and even that one gets entry_type='event' from the sampler's keyword heuristic despite its curated label being 'BOTTLENECK/enabler-material (early-cycle)'; the two classification axes don't correspond. The other 11 — including #1 AXTI, purpose-built with 'Tests: chain-trace to feedstock, demand>supply gate' for exactly the recursive_bottom_hop move — are absent. cmd_sample instead draws from the full ~951-row eligible pool using an entry-type (fear_dip/event/discovery) heuristic that is orthogonal to archetype, so nothing guarantees any given draw contains a chokepoint case at all. Same (n, seed) does guarantee identical case IDs every run (verified: `sample --n 6 --seed 7` reproduces {HOOD, SIVE, AAOI, LITE, SNDK, GM} identically on repeat) — but that only pins WHICH questions get asked, never that the mix is archetype-balanced, that the tickers resolve (finding 1), or that the model/temperature answering them is fixed (finding 8).

**Why it matters** — recursive_bottom_hop and second_order_and_sibling (scope: chokepoint) are the two rubric rows harness-spec.md's own 2026-07-09 retrospective flags as 'the weakest-reproduced moves' — exactly what the owner most needs a reliable read on. Their in-scope N is whatever fraction of a random draw happens to read as chokepoint, which could be zero. Discarding the curated set's per-case 'Tests:' annotations also weakens judge accuracy on the two hardest, most domain-specific items for EVERY case, not just the 11 missing ones — the judge has to reverse-engineer 'what should the bottom hop have been here' from raw prose each run instead of scoring against a validated hint.

**Proposed fix** — Give cmd_sample a forced-include path (a small companion JSON with the 12 IDs + their §D archetype label) that always enters the sample before the remainder of --n is filled from the existing random draw. This guarantees a stable, archetype-diverse floor (4 chokepoint / 2 disruption / 2 evolution / 2 falling-knife / 1 macro / 1 meta) regardless of seed.

---

## F17 · [HIGH] The 'discovery' blind_prompt has no date anchor, so a present-tense question is scored against a thesis whose mispricing may already have resolved

**Where** — scripts/serenity_eval.py:151-152 (_blind_prompt, discovery branch — 'right now' with zero date reference, unlike the fear_dip/event branches at :146-150 which say 'around {day}'); scripts/eval/README.md:49-51 ('Scoring METHOD, not numbers' claim, covers number drift only)

**Failure** — Gold-set case 1969151544320016527 (NBIS, dated 2025-09-20, '$1M+ position, $225 PT') would generate the blind_prompt 'What's your read on NBIS? Is it structurally mispriced right now?' as asked TODAY — roughly 11 months later. The pipeline loads current, not September-2025, data. If NBIS has already re-rated toward $225 in the interim, the objectively CORRECT present-tense answer is 'already re-rated, look elsewhere' or a different residual thesis — not a restatement of the original call. None of the six fixed 0/1 rubric items (archetype_named, lens_run, priced_in_decomposed, etc.) carry an instruction to treat a genuinely-different-because-time-passed verdict as anything but a miss; only the free-text `notes` field has a 'different (and defensible?)' escape hatch, and cmd_report's aggregation (lines 285-299) never reads `notes` — it only tallies the six binary scores.

**Why it matters** — This breaks the eval's own stated claim ('scores method not numbers') for any thesis old enough that its setup has plausibly played out — which is most of the pool, since the DB spans mid-2025 through the eval's run date. It isn't just a number differing; the entire premise of the question (a live mispricing exists to find) can be false today, and nothing currently shields the binary items from that.

**Proposed fix** — Anchor the discovery prompt to the thesis date too ('As of {day}, is TICKER structurally mispriced...'), matching the pattern already used for fear_dip/event. Additionally bias the sampler toward theses recent enough (e.g. within ~60-90 days of eval-run time) that the setup is unlikely to have fully resolved, or explicitly instruct the judge to score priced_in_decomposed/lens_run on decomposition METHOD quality rather than directional agreement once a case exceeds an age threshold.

---

## F18 · [HIGH] Statistical power at n=25 falls far short of realistic doctrine-edit effect sizes; a uniform mode-B run also spends the expensive tier on items hooks don't touch

**Where** — scripts/eval/README.md (before/after design, mode A vs B split at lines 29-43); .claude/harness-spec.md:61 (the one recorded data point: baseline 72%→70% at n=6, 'inside the n=6 noise floor... every per-move Δ is a single stochastic judge flip... the eval detects only GROSS regressions')

**Failure** — Standard two-proportion sample-size formula, n_per_arm ≈ (z_{α/2}+z_β)²·[p1(1−p1)+p2(1−p2)]/(p1−p2)², at α=0.05 two-sided / 80% power ((1.96+0.84)²=7.84): detecting p1=0.5→p2=0.7 (a 20-point true shift) needs ≈90 in-scope cases; p1=0.6→0.9 (30 points) needs ≈29; only a ≈40-point swing (0.4→0.8) drops to ≈20. The one recorded measurement moved by an amount its own authors called 'a single stochastic judge flip' — at n=6 that's ~17 points, far below what even n=25 can distinguish from noise for the four scope:all items (which need a ~35-40-point true swing to be reliably visible at n=25). The two scope:chokepoint items (recursive_bottom_hop, second_order_and_sibling) get a strictly smaller in-scope N, bounded by however many of the 25 read as chokepoint (uncontrolled — see the gold-set finding), so they're further still from adequate power. Separately: none of the four hooks (verdict_gate.py, evidence_discipline.py, data_integrity_guard.py, session_status.py — all read in full or by description this session) check archetype naming, chain depth, second-order actors, or priced-in decomposition text at all; verdict_gate.py only touches the Lens: token, the Downside/falsifier phrasing, and the Saved: mark. Routing archetype_named/recursive_bottom_hop/second_order_and_sibling/priced_in_decomposed through the expensive, hook-firing mode B therefore buys zero extra measurement fidelity over the cheap mode A for those four items.

**Why it matters** — The owner's chosen fix (n=25, hooks included) does not by itself produce a per-move claim trustworthy at effect sizes a real doctrine edit plausibly produces, and a uniform mode-B run for every item spends the full hooks-included cost on items hooks can't influence, while under-resourcing exactly the two items that most need a larger n.

**Proposed fix** — Split the run rather than run everything through mode B: (1) a cheap, HIGH-n (60-100+) mode-A pass scoring the four doctrine-content items, affordable because mode A is the harness's own documented 'fast, parallel' path; (2) a small mode-B pass (n≈15-20) focused purely on confirming the hook-triggered structural items (lens_run, bear_and_falsifier, the Saved: mark) still fire correctly — the only piece that genuinely requires hooks — scored mechanically per the rubric-mechanization finding so it needs no judge call at all, which also means it doesn't need judge-level n to get a stable read. In the report output itself, state plainly what n=25-in-mode-B alone can legitimately claim: (a) gross regressions/breaks, visible well below the 80%-power threshold; (b) a pooled cross-move aggregate (~100 checks) with a tighter ~10pp half-width, usable as a coarse dashboard number though it conflates distinct moves; (c) a running trend across every future doctrine edit rather than a single-shot test. Concretely, have cmd_report suppress a per-move percentage when in-scope `tot` is below ~10-15 and print 'insufficient n for a per-move claim' instead, so a reader can't mistake a 100%-on-1-case row for a real result.

---

## F19 · [MEDIUM] scripts/serenity_sectormap.py is a fully-built, in-use CLI that no doctrine file mentions — and it isn't even committed to git

**Where** — scripts/serenity_sectormap.py (whole file); .claude/harness-spec.md:28-40

**Failure** — Ask a 'D — Supply-chain / what-if' question (CLAUDE.md's own type D: 'map the chain (WebSearch) before discovery'). CLAUDE.md and serenity-discovery's SKILL.md tell the model to free-form the chain map in prose; neither ever mentions that an authored, schema-validated `sessions/{folder}/_sectormap.json` format already exists with a CLI (`validate`/`show`/`layers`/`tickers`/`cohort`/`diff`/`index`) whose `cohort --layer ID` subcommand builds the exact `serenity_pipeline.py discover …` argv for one layer's candidates. A fresh session — including one asking about the repo's own only worked example (sessions/260726.../_sectormap.json, cited only in passing at sessions/INDEX.md:7) — has zero doctrinal signal to reuse this tool; it will produce an unstructured, non-diffable chain map exactly as CLAUDE.md's D-template describes, because the tool is invisible except via `ls scripts/`.

**Why it matters** — This is the audit brief's own INTERFACE-OVER-DOCUMENT failure mode in reverse: a real, tested capability (scripts/tests/test_serenity_sectormap.py exists for it) sits in a script signature that no doctrine file re-surfaces, so it's lost on every fresh session and after every compaction. It's also currently untracked (`git status`: `?? scripts/serenity_sectormap.py`, `?? scripts/tests/test_serenity_sectormap.py`), so unlike every other pipeline script it has no git history to recover it from if an accidental `git clean -fd` runs.

**Proposed fix** — Either wire it in — add a Components-table row in harness-spec.md, a pointer from CLAUDE.md's 'D' bullet and/or serenity-discovery's chain-tracing section telling the model when to author/read `_sectormap.json`, and `git add` the script plus its test — or, if this was a one-off Codex side-experiment never meant to become doctrine, delete it and the dangling sessions/INDEX.md:7 cross-reference so the repo doesn't carry a capability documented nowhere.

---

## F20 · [MEDIUM] harness-spec.md cites test_evidence_contract.py as a working validation with no caveat; it currently cannot execute at all

**Where** — .claude/harness-spec.md:46

**Failure** — scripts/tests/test_evidence_contract.py:8-9 computes `SCRIPTS_DIR = Path(__file__).resolve().parents[1]` (correctly `.../scripts/`) then `ROOT = SCRIPTS_DIR.parents[3]` — three levels too many. Verified directly: `ROOT` evaluates to `/Users/seongjin` (the user's home directory), a real directory so no early error masks it. Both test functions then run `subprocess.run([sys.executable, str(ROOT / "scripts" / "serenity_pipeline.py"), "evidence", "--fixture", ...], check=True)` against `/Users/seongjin/scripts/serenity_pipeline.py`, which does not exist — `check=True` turns that into an immediate `FileNotFoundError`/`CalledProcessError` before any contract assertion runs, so both tests fail on every invocation. This exact defect is already independently documented in docs/wiki/Known-Limitations.md ('both contract tests fail') and CHANGELOG.md, but harness-spec.md:46 — the file whose own preamble claims 'the next audit compares against this' — still lists the file as a plain, uncaveated validation bullet.

**Why it matters** — Two of the harness's own documents now disagree about whether 'the fact/judge seam is judgment-free' is actually being verified by a running test right now (it is not) — harness-spec.md is stale relative to a newer, more accurate doc in the same repository, on the exact question it exists to answer.

**Proposed fix** — Fix the path bug (`ROOT = SCRIPTS_DIR.parent`, one level up from scripts/, not `.parents[3]`), or at minimum add the same 'known-broken' caveat harness-spec.md already gives other soft gaps, so the Validation section stops overstating coverage.

---

## F21 · [MEDIUM] Sector-map candidates have no owner-vs-proxy field — `cohort`'s auto-generated `discover` call mechanically includes tickers the map's own notes disclaim

**Where** — scripts/serenity_sectormap.py:66 (`_CANDIDATE_FIELDS`), :545-566 (`cmd_cohort`); real evidence: sessions/260726.../_codex_review_sectormap.md:146, _sectormap.md:146

**Failure** — `serenity_sectormap.py cohort --layer process-materials` on the repo's real sector map returns a ready-to-run `discover` argv containing LIN and APD — both tagged in the map's own free-text `note` as 'theme exposure, not bottleneck ownership' / 'the semiconductor slice is small relative to the whole.' Running that argv (exactly what `cmd_cohort` exists to make effortless) feeds two $50B+ industrial conglomerates' MC and multiples into the same comparator table CLAUDE.md's routing reflex (b) calls 'the verdict' for a comparative archetype. This was independently confirmed by an adversarial review of this exact session ('Proxy contamination in the candidate column... a machine consumer reading `candidates` still gets the ticker') and the fix was named and explicitly deferred, not disputed.

**Why it matters** — This is the one interface in the harness whose entire job is turning a structured map into a mechanically-correct pipeline call — so it's the clearest live proof that a free-text `note` disclaimer is not load-bearing against a mechanical consumer, even inside code written to be mechanical. Every future `cohort` call on any sector map inherits this hole, and the map format is the doctrine's designated interface for the D-type ('map the chain before discovery') entry point.

**Proposed fix** — Add `relationship: owner | tool | consumer | adjacent_proxy` (required, enum-validated in `_validate_candidate`, matching the existing pattern for `listing`/`link`) to `_CANDIDATE_FIELDS`; default `cmd_cohort` to `relationship == owner` only, with an explicit `--include-adjacent` opt-in for when the wider comparator is deliberately wanted. This is the exact fix already named in `_sectormap.md:146` — apply it rather than re-deriving it.

---

## F22 · [MEDIUM] The Rank-N protocol's two machine-read artifacts (scorecard frontmatter, `_ranking.md` tier column) have no field-level schema check — unlike the newer, less-used sector-map format that already has one in this repo

**Where** — scripts/serenity_harness.py:197-239 (`_check_reproducibility` — checks the AGENT instructions file's substrings, never a produced scorecard), :348-370 (`_parse_ranking` — no header or tier-vocabulary check); .claude/agents/serenity-scorecard.md:41-62 (schema as an unvalidated markdown code block)

**Failure** — (a) A scorecard instance writes `gates: Pass` or `stage: "3-4"` — nothing in `serenity_harness.py validate` catches it, because its only scorecard-related check (`_check_reproducibility`, lines 201-217) tests whether `.claude/agents/serenity-scorecard.md` itself contains the substrings `gate_strength:` and `conviction:`, never that a real `sessions/*/TICKER.md` conforms. The synthesizer's Step 2 ('Gate = membership', 'Stage rung = the spine') silently mis-sorts that one name. (b) Two `_ranking.md` files use `Tier 1` in one run and `1 (core)` in another for the identical judgment — `rankdiff`'s `_parse_ranking` does plain string equality (`a_tiers[t] == b_tiers[t]`), reports a spurious 'changed' tier, and deflates `agreement_pct`, the number harness-spec.md calls a free reproducibility measurement.

**Why it matters** — This is the exact class of gap `serenity_sectormap.py`'s `validate_map()` (required fields + `_validate_enum` for `listing`/`link`/`limitation_class`) already closes for a much newer, so-far-once-used file format. The more heavily-used, more central Rank-N outputs (produced on every N≥5 ranking) have no equivalent, so the harness's most-repeated structured output is its least-checked one.

**Proposed fix** — Extend `serenity_harness.py` with a `scorecard-lint FILE` subcommand mirroring `validate_map`'s pattern (required frontmatter keys, `gates`/`archetype`/`conviction` as enums, `stage` as int 1-5) that the scorecard agent's own Step 5 can self-invoke before returning; give `_parse_ranking` a canonicalization pass (strip parentheticals, reject any tier string outside the doctrine's fixed 6-value vocabulary with a named error) before diffing. Scope narrowly to FORMAT: `rankdiff` must keep reporting only THAT a tier changed, never auto-labeling WHY — evidence delta / judgment revision / cohort delta stays the model's call (CLAUDE.md Step 4), since that classification needs the two rankings' reasoning text, not just the tier cell, and must never be inferred by code.

---

## F23 · [MEDIUM] `_MAG7_NAMES` is a set of 6 companies masquerading as "Mag7"

**Where** — scripts/pipeline/_bottleneck.py:80-81 (definition), :198 (use)

**Failure** — `_MAG7_NAMES = {"microsoft","msft","google","alphabet","googl","meta","amazon","amzn","apple","aapl","nvidia","nvda"}` — that's 6 companies (MSFT/GOOGL/META/AMZN/AAPL/NVDA); Tesla is absent. Run `analyze` on a name whose filing discloses "a multi-year supply agreement with Tesla" (a battery-materials, custom-silicon, or sensor supplier — exactly this harness's hardware/supply-chain focus). The `mag7_named_counterparty` flag never fires for it, no matter how large or explicit the Tesla relationship, because `"tesla"`/`"tsla"` is not in the set. The flag's own comment says it exists to surface "a direct Mag7 contract [that] insulates the filer from intermediary/neocloud credit contagion (V3)" — that signal silently never appears for the one Mag7 name most likely to show up as a named hardware counterparty.

**Why it matters** — This is the closed-enumeration-presented-as-exhaustive failure living in the fact-loading code layer the harness trains the analyst to trust MOST ("code loads facts... never a web snippet for a number a script can load"). "Mag7" is a fixed, well-known 7-member term; a variable literally named `_MAG7_NAMES` silently encoding 6 is not a judgment call with room for interpretation — it's a miscount, and because it's code (not prose the model reasons over), nothing signals the analyst that the flag's coverage is incomplete. The doctrine gives the model no instinct to double-check pipeline flag coverage, since the entire design point of the code/judgment split is that code doesn't need re-verifying.

**Proposed fix** — Add "tesla"/"tsla" to the set. Longer-term, derive Mag7 membership from one canonical, dated comment or source-of-truth constant instead of a hand-typed literal, so a future membership question doesn't drift silently again.

---

## F24 · [MEDIUM] `_HIGH_RISK_REGIONS` hardcodes 4 China/Taiwan strings for "export-control/tariff exposure," missing every actually-sanctioned jurisdiction and conflating two different risk mechanisms

**Where** — scripts/pipeline/_bottleneck.py:76 (definition), :185-196 (threshold logic, `hr_pct >= 15`)

**Failure** — `_HIGH_RISK_REGIONS = {"taiwan","china","hong kong","mainland china"}`. A US-listed industrial name with 40% of disclosed revenue in Russia (comprehensively OFAC-sanctioned since 2022), or material exposure to Iran/Myanmar/Venezuela, runs through `analyze` — `high_risk_region_revenue` never fires, at any exposure level, because none of those strings are in the set. Meanwhile a name with 16% Taiwan revenue DOES trip the identical flag with the identical message "export-control / tariff exposure" — but Taiwan is a US-ally invasion/supply-disruption risk, not an export-control target the way China is; the two are mechanically different risks folded into one undifferentiated signal.

**Why it matters** — The flag is meant as an objective proxy for a real, sourceable category (US sanctions/export-control destination lists), but is implemented as 4 literal strings with no stated derivation — a closed enumeration standing in for a re-derivable rule ("any OFAC-comprehensively-sanctioned or BIS-controlled destination"). Because it lives in the trusted fact layer, its silence reads as "no material country-concentration risk" precisely where the harness's own architecture says the analyst should rely on it most. It also sits in tension with CLAUDE.md's own explicit disclaimer that "semis are a recent convenience, not the doctrine" — this hardcoded list is scoped exactly to the semis-China corridor and silently fails outside it.

**Proposed fix** — Either broaden the set to track an actual sourced list (OFAC comprehensive-sanctions countries + BIS/Commerce controlled destinations), or split into two separately-labeled flags — export-control-target-exposure vs. sanctions/geopolitical-tail-risk-exposure — so the signal's meaning travels with the flag instead of being silently merged.

---

## F25 · [MEDIUM] verdict_gate's `Lens:` detector regex excludes "/", which is the doctrine's own notation for a named driver

**Where** — .claude/hooks/verdict_gate.py:96-108 (esp. the `lens_marker` regex at 105-108, char class `[×÷*]`)

**Failure** — The analyst runs the asset-value-turnaround lens correctly: "Lens: replacement-cost-per-unit — $4.2B rebuild cost / 12 reactors = $350M per reactor vs $280M peer comp" — genuinely computed, input traced to key_facts, exactly what N10/§6's GATE demands. The line contains only "/" for the division — no ×, ÷, or literal `*` — so `lens_marker` evaluates False, and the Stop hook fires its soft nudge ("you rendered a valuation verdict but no machine-checkable Lens: line appears") on an answer that already satisfied the contract.

**Why it matters** — The regex's own comment explains the exclusion is deliberate — to stop a bare top-down multiple like "EV/Rev = 12x" from satisfying the gate via an incidental "/" and "x" — a legitimate anti-goal, but a character-class whitelist can't tell "/" used as a ratio's NAME apart from "/" used as a real division operator, so it bans both. This isn't a rare edge: CLAUDE.md's own non-negotiable #10 names this exact driver "replacement-cost/unit" and R5 writes it as "replacement cost / a pure-play comp per unit of physical capacity" — the doctrine's own canonical notation for one of the five named valuation drivers uses the character the gate excludes. Every other financial ratio in the doctrine (EV/Rev, EV/FCF, P/E, P/S) is also written with "/", so a model naturally extending that convention to a real division produces a false miss.

**Proposed fix** — Accept a bare "/" between two numeric/dollar tokens as satisfying `lens_marker` (reserve the exclusion for the narrower "EV/Rev"-style ratio-name pattern specifically), or simply add "/" to the operator class — a soft nudge over-firing once on a genuine top-down-only answer is far cheaper than misfiring on real, correctly-notated arithmetic.

---

## F26 · [MEDIUM] "Four drains" liquidity-count ladder has no test for a 5th independent channel

**Where** — .claude/skills/serenity-macro/SKILL.md:140

**Failure** — "Four independent channels pull risk capital out: crypto precursor shock · Fed/policy hawkish surprise · AI credit stress · carry-trade unwind... One = noise; two = tighten stops; three+ = cut leverage." A regional-bank-run/banking-crisis event (an SVB-2023-style failure) fires alongside one already-named channel (say AI credit stress). The bank failure doesn't map cleanly onto any of the four labels, so a literal count sees "one channel firing" and returns "normal posture" — when a genuinely independent second door is open and the graded response should already be "tighten stops," or "cut leverage" if a third fires too.

**Why it matters** — The ladder's entire mechanism depends on an accurate count of independent channels, and the four are named as if the enumeration is complete, with a rationale given for why independence matters (a systemic-withdrawal signature) but no test for recognizing a channel outside the named four. This directly gates a portfolio-wide leverage decision — the highest-stakes single output the macro lens produces — on a closed list with no generative membership test.

**Proposed fix** — State the generative test explicitly: "any channel pulling risk capital out through a mechanism distinct from the others already firing counts toward the ladder — the four named are the recurring instances, not the ceiling," mirroring the kill-signal list's extensibility framing.

---

## F27 · [MEDIUM] The three routing reflexes (price-extreme fade / auto-discover / event-first) have no stated firing order when more than one triggers on the same prompt

**Where** — CLAUDE.md:99 — three reflexes (a)/(b)/(c) joined by semicolons in one sentence, each independently prescribing a "run X first"/"BEFORE the single-name read" action, with no tie-break among them — unlike the two OTHER precedence chains the harness states explicitly two lines apart (V-priority at CLAUDE.md:81; A>D>B>C>E at CLAUDE.md:97)

**Failure** — "AAOI's ripping to new highs, but with the Taiwan situation heating up is this too extended to add?" AAOI is a countable-end-unit supplier sitting above the 90th percentile of its 52-week range, asked about alongside an active-conflict headline — a single prompt that trips all three reflexes: (a) says default toward bearish and run the prove-the-math fade FIRST; (b) says auto-run `discover` and show the peer-comparator BEFORE quoting the subject's own multiple; (c) says treat the whole thing as a macro/event question and run serenity-macro's catalyst test + cost-shock margin math BEFORE the single-name read. Each clause claims priority relative to the normal B-type read, but none states its position relative to the OTHER two — whether the event-frame in (c) should resolve first (since it may determine whether a bearish read in (a) is even warranted), or (a) runs standalone, is left to per-turn improvisation.

**Why it matters** — The harness explicitly prides itself on resolving exactly this kind of collision elsewhere — the V-priority chain and the A>D>B>C>E chain both exist because "when two [things] pull opposite ways, this order settles it." The three routing reflexes are a third, adjacent collision surface introduced two lines later in the same document, and it's the one place left without a stated order. A multi-trigger prompt can therefore produce a different reflex sequence — and potentially a different verdict — depending on which reflex the model happens to reason about first, undercutting the reproducibility goal the rest of the harness (Rank-N protocol, scorecard schema, `rankdiff`) is explicitly built around.

**Proposed fix** — State the order explicitly, in the same terse form as the other two chains — e.g. append to CLAUDE.md:99: "(order when several fire: c → a → b — resolve whether this is fundamentally an event first, since that changes whether a bearish frame is even warranted; then the bearish fade; then let the comparator feed the valuation step it already governs)."

---

## F28 · [MEDIUM] A harness-dev answer that cites a real ticker as an example (e.g. "$NVDA" in a regex-fix description) hard-blocks for a missing financial disclaimer

**Where** — .claude/hooks/verdict_gate.py:88 (cashtag branch of finance_signal), :110-112 (hard block)

**Failure** — Verified. Message: "TL;DR: fixed the verdict_gate cashtag regex so a $NVDA-style example now round-trips through the new fixture; reran the suite and it's green again.\nChanged the regex in verdict_gate.py and added a test case." produces `{"decision": "block", "reason": "Your answer is a serenity market verdict (TLDR + a finance signal) but is missing the NFI/NFA sign-off..."}` on a pure coding/harness-dev summary.

**Why it matters** — $NVDA/$AVGO/$XYZ are the standard placeholder tickers used throughout this hook's own committed fixtures (silent_full.json, hard_nfi.json, bear_leg_soft.json, ...) and this audit's own brief — so a routine conversation about fixing or discussing verdict_gate.py is at real, recurring risk of self-triggering a hard block over a regex-fix summary. This directly falsifies the hook's own docstring claim (lines 16-19) that a coding answer 'is never hard-blocked'.

**Proposed fix** — Port evidence_discipline's _META/_MARKET_ANCHOR dev-prompt exemption into verdict_gate.py — suppress the cashtag-only path of finance_signal when the message also carries an obvious dev-context signal (.py, 'regex', 'fixture', 'hook') and no other finance signal (single_name/strong_verdict) is present.

---

## F29 · [MEDIUM] evidence_discipline's dev-prompt suppression is defeated by "earnings"/"valuation"/"PT"/"dividend" — words that are simultaneously the trigger and its own override

**Where** — .claude/hooks/evidence_discipline.py:19-29 (_INTENT), :43-48 (_MARKET_ANCHOR), :66 (suppression logic)

**Failure** — Verified, twice. Prompt "the pipeline's forward P/E field looks wrong for tickers with negative earnings -- can you check the yfinance mapping in serenity_pipeline.py?" and prompt "refactor how serenity_pipeline.py computes the valuation multiples so PEG doesn't divide by zero when growth is flat" both fire the full `[evidence-discipline]` 'run the pipeline first' reminder, despite each asking to EDIT serenity_pipeline.py, not analyze a ticker.

**Why it matters** — The pipeline's whole job is fetching P/E, valuation multiples, and earnings-adjacent fields, so a bug report or refactor request about the pipeline's own financial-field handling is a highly likely, on-topic prompt in this exact repo — precisely the case the _META guard's own docstring names as its target ('verdict_gate', 'exec-form', 'refactor'). Recurring false fires on the harness's own maintenance work train a user to skim past the reminder even when it applies to a real market question.

**Proposed fix** — Drop pure financial-statement-field names (earnings/valuation/dividend/PT/price target) from _MARKET_ANCHOR's override list, or require a cashtag/Korean-market-phrase specifically to override _META — the override should mean 'there's also a concrete market ask here', not 'this prompt happens to name a field the pipeline fetches'.

---

## F30 · [MEDIUM] The soft Lens: nudge fires on macro-only overweight/underweight calls that never name a single company

**Where** — .claude/hooks/verdict_gate.py:92-94 (valuation_verdict folds in strong_verdict), :117-123 (soft nudge)

**Failure** — Verified. Message "TLDR: regime reads risk-on, liquidity ample -> overweight semis, underweight defensives. NFI.\nThe biggest signal of whether the AI trade continues is hyperscaler spending, still climbing." (no single name, no PT, no vehicle, NFI present so no hard block) produces the soft nudge: "...you rendered a valuation verdict but no machine-checkable `Lens:` line appears — emit it: `Lens: <name> — <input>×<input>÷<input> = <result>`..." — asking for a single-company driver computation on an answer that never names a company.

**Why it matters** — CLAUDE.md defines the Lens: line as an exclusively single-name construct ('every single-name answer carries...'). Nudging it onto a sector-level overweight/underweight call either trains the model to treat the nudge as noise, or — feeding directly into the compliance-token risk above — invites a fabricated per-name Lens: line bolted on just to silence the hook on a turn that was never about one name.

**Proposed fix** — Gate the Lens nudge on single_name (or an explicit cashtag), not the broader valuation_verdict, leaving macro-only overweight/underweight calls to the Saved: nudge alone.

---

## F31 · [MEDIUM] data_integrity_guard's revenue-divergence check never escalates severity by magnitude, and its EV/balance checks silently mix two unreconciled cash fields

**Where** — .claude/hooks/data_integrity_guard.py:109-118 (check #6, unconditional "note"); compare :58-68 (check #1's HARD/soft escalation); :49 vs :125 (two different cash sources feeding checks #5 and #7)

**Failure** — Ran the live pipeline (`scripts/.venv/bin/python scripts/serenity_pipeline.py analyze MU`) and fed the real JSON through `_checks()`. Result: key_facts.totalRevenue = $90.27B vs fundamental_inputs.debt_and_cash.total_revenue = $37.38B — a 142% gap — logged only as `[note] ... choose the denominator deliberately`, the identical severity as AAPL's benign 12% gap in the same session. Micron's real scale (matching the $37.38B figure and the $82.8B total_assets line in the very same payload) makes a genuine $90B TTM figure implausible on its face. Separately, the same live run shows checks #5 and #7 draw 'cash' from two different pipeline fields (key_facts.totalCash vs debt_and_cash.cash_and_equivalents) that diverged by $26.5B on AAPL and $16.4B on MU in this run — both stayed under their respective 15%/HARD thresholds, but only by coincidence of scale, not by any reconciliation in the code.

**Why it matters** — N9 exists precisely to catch 'a ticker-collision / stale / mis-tagged number... itself the mispricing'. A ~$53B, 142% gap on a name in current coverage (MU is in the golden fixture set) is a strong candidate for exactly that, yet the check is coded to always render as low-priority commentary — the hook's own closing line ('a soft/note just means choose the denominator deliberately') actively tells the agent not to chase it.

**Proposed fix** — Give check #6 the same magnitude tiering as check #1 (e.g. note under ~30%, soft above, HARD above ~75-100% — a gap that large between two TTM-ish figures for the same company is no longer a denominator-choice question). Pick one cash field consistently for checks #5 and #7, or diff the two cash fields against each other the way check #6 already diffs the two revenue fields.

---

## F32 · [MEDIUM] n/a-vs-0 stochasticity: the chokepoint-scope decision has no persisted ground truth and is re-inferred by the judge every run

**Where** — scripts/eval/serenity_eval_workflow.js:25-40 (CASES_SCHEMA — no `archetype` field on a case, only `entry_type`), :81-93 (RUBRIC_TEXT instructs 'n/a = out of scope for this case's archetype' with nothing to read that archetype from); .claude/harness-spec.md:61 (names the symptom: 'every per-move Δ is a single stochastic judge flip... judge n/a-vs-0 stochasticity')

**Failure** — For recursive_bottom_hop/second_order_and_sibling, the judge must decide in-scope (chokepoint, score 0/1) vs out-of-scope (n/a) by freely re-reading unstructured thesis_text + the harness answer on every scoring pass — no `archetype` field exists anywhere in the case JSON to anchor this. A borderline case (e.g. gold case #4, labeled 'EVOLUTION/asset-financed + levered-IRR' but built on a cross-cloud GPU-margin comparison that could easily read as chokepoint-adjacent) can flip n/a↔0 between two scoring passes of the IDENTICAL answer, purely from judge sampling variance — a false 'regression' or 'improvement' with zero underlying change.

**Why it matters** — This is the exact confound harness-spec.md already names but doesn't fix. It directly inflates apparent noise on the two rubric rows the owner most needs to trust (see the gold-set finding above), and no increase in n alone removes it — it's a per-case labeling instability, not a sample-size problem.

**Proposed fix** — Persist `archetype` as a fixed field on each case at sample time (from the gold set's §D hand labels for forced-included cases; for other cases, either leave the two chokepoint-scoped items unscored by default or run a one-time, cached archetype-labeling pass whose output is written into cases.json and never re-derived at judge time). Have cmd_report — not the per-run judge — apply the n/a/in-scope split mechanically from that fixed field.

---

## F33 · [MEDIUM] lens_run / bear_and_falsifier duplicate verdict_gate.py's own structural regex instead of reusing it deterministically

**Where** — .claude/hooks/verdict_gate.py:96-108 (lens_marker — the exact `Lens:[...][×÷*][...]=` structural check) and :124-146 (Downside/falsifier/bear-leg/bull-leg regex) vs scripts/serenity_eval.py:59-66 (lens_run) and :79-83 (bear_and_falsifier)

**Failure** — In mode B, a harness answer missing the `Lens:` token already gets a soft additionalContext nudge mid-turn from verdict_gate.py; whether the FINAL answer satisfies that exact bar is checkable by the identical regex with zero LLM calls. Instead serenity_eval.py asks a judge to eyeball 'was the lens run, arithmetic shown' freeform — a judge can score lens_run=1 on an answer with driver arithmetic but no literal `Lens:` prefix (passing the rubric's looser bar while failing the hook's actual contract), or the reverse. The reported reproduction rate can diverge from what the live hook actually guarantees a real user.

**Why it matters** — Wastes judge tokens re-deriving a check code can already do for free, worsening the cost problem at the n the owner wants; and a lenient-judge/strict-hook mismatch means the 'reproduction rate' doesn't certify what mode B was specifically chosen to measure (hook effects).

**Proposed fix** — Extract lens_marker, the Downside/falsifier regex, and the bear-leg/bull-leg regex from verdict_gate.py into a small shared module imported by both the hook and serenity_eval.py. Run it as a deterministic pre-pass in `report`; escalate to a judge only for cases where the mechanical check is ambiguous or for genuinely unmechanizable judgment (archetype correctness, decomposition quality, chain-hop correctness). Strengthen further by extracting the numbers on the Lens: line and confirming each appears (≈1% tolerance) in that case's own captured key_facts JSON — a fully mechanical version of 'each input traced to key_facts.' archetype_named and priced_in_decomposed can get a cheaper partial version of this: a fast-reject to 0 when the answer contains none of the expected keywords at all, judge only when a keyword is present (presence doesn't imply correctness, so the judge is still needed there). recursive_bottom_hop and second_order_and_sibling get no such shortcut — correctly identifying the true bottom hop requires company-specific domain knowledge no regex can supply; the only lever there is feeding the judge the gold set's 'Tests:' annotation (see the gold-set finding) rather than trying to mechanize the check itself.

---

## F34 · [MEDIUM] Mode B (claude -p in the project dir) will write synthetic artifacts into the live sessions/ archive, with a concurrent-write risk if parallelized

**Where** — scripts/eval/README.md:41-43 (mode B instructs 'blind-run each case as a fresh top-level session in the project dir', no isolation); CLAUDE.md 'The session archive' section (unconditional save-every-substantive-analysis rule); .claude/hooks/verdict_gate.py:148-184 (the Saved: mark check, which actively nudges the session to go create these files)

**Failure** — Running --n 25 through mode B exactly as documented means 25 real top-level Claude Code sessions in the actual project directory, each producing a finance verdict that CLAUDE.md's archive rule plus verdict_gate's Saved: nudge push toward writing `sessions/{yymmdd}.{slug}/TICKER.md` and appending a line to the real `sessions/INDEX.md`. If any two of the 25 run concurrently — the natural way to keep a 25-case run's wall-clock reasonable — two processes appending to the same INDEX.md at once can interleave or drop a line.

**Why it matters** — This is a data-integrity risk to the project itself, not just the eval: synthetic scorecards for blind hypothetical questions would pollute the real decision archive that future genuine sessions read from to reconcile deltas (CLAUDE.md's own retrieval rule), and a corrupted/interleaved INDEX.md is exactly the kind of silent structural damage the harness's reproducibility layer exists to prevent.

**Proposed fix** — Run each of the 25 blind-run sessions in its own isolated git worktree (or a throwaway directory copy) rather than the live project directory, so CLAUDE_PROJECT_DIR/cwd resolves to a private, disposable sessions/ tree per case; discard the worktrees after scoring. This preserves the realism of the Saved:-mark hook firing (still worth measuring) without touching the real archive and removes the concurrent-write hazard entirely.

---

## F35 · [MEDIUM] Cost estimate for n=25 mode B: roughly 1-4M tokens and 1-2.75 hours wall-clock if serial, with the model/temperature left unpinned

**Where** — scripts/eval/README.md:41-43 (mode B); measured directly this session: CLAUDE.md=27,451 chars, serenity-analysis SKILL.md=58,013 chars, serenity-filings.md=9,890 chars, `serenity_pipeline.py analyze AAPL` output=17,005 chars taking 12.555s wall-clock, `macro` output=3,138 chars

**Failure** — Per case, a mode-B blind-run agentic session loads CLAUDE.md (~7K tokens) + one skill (serenity-analysis ≈15K tokens, the heaviest) + the pipeline's analyze JSON (≈4.5K tokens, measured) + possibly macro (≈0.8K) + possibly a nested serenity-filings subagent call (its own ≈2.5K-token agent definition plus whatever SEC filing text it reads, easily another 10K-30K+ tokens in a separate context) + a ~1,500-2,500 word final answer (≈2,000-3,300 tokens output) — and because it's a genuine multi-turn agentic loop, each tool round-trip resends the accumulated transcript, pushing a realistic per-case total to roughly 40,000-150,000 tokens. The judge pass is far cheaper (thesis_text measured 400-4,031 chars across the real sample pulled this session, + the answer + the ≈500-600-token rubric text, no tools) at roughly 3,000-5,500 tokens. At n=25: blind-run ≈1.0M-3.75M tokens, judge ≈75K-140K tokens, combined roughly 1-4M tokens. Wall-clock: the pipeline call alone measured 12.5s; a full blind-run session (reasoning + tool calls + possible subagent dispatch + long-form writing) plausibly runs 2-6 minutes, judge 15-45s; sequential n=25 ≈ 65-165 minutes (roughly 1-2.75 hours). Separately, neither README mode B nor serenity_eval_workflow.js's agent() calls pin a --model or temperature for the blind-run or judge — a delta between a 'before' and 'after' run separated by weeks could partly reflect a default-model change (a real occurrence across calendar time) rather than the doctrine edit, and nothing in the scored-cases JSON records which model produced a given answer, so this confound is unrecoverable after the fact.

**Why it matters** — This is a large, currently-unbudgeted spend for a single before/after comparison, and — per the statistical-power finding — it still doesn't buy a reliable per-move claim at realistic effect sizes, so the spend-to-trustworthiness ratio is poor as currently designed.

**Proposed fix** — See the paired finding on the cheapest split design. Independently: pin and record an explicit --model (and temperature, if exposed) for both the blind-run and judge calls, and stamp the resolved model identity into the scored-cases JSON's `meta` block alongside `seed` so every report shows exactly which model pairing produced a given delta.

---

## F36 · [LOW] serenity_harness.py's sec_consolidation check partially asserts a hardcoded constant, not a behavior

**Where** — scripts/serenity_harness.py:178-194

**Failure** — `_check_sec_consolidation` sets `ok = not leaked and xbrl_empty and classification_empty`, where `xbrl_empty`/`classification_empty` come from calling `_extract_sec_supply_chain("AAPL")` (scripts/pipeline/_fetch.py:198-212). That function is a single unconditional `return {"data": {"filing": {}, "classification": {}, "xbrl": {}}, ...}` — no branch, no I/O, and it ignores its own `ticker` argument — so `xbrl_empty` and `classification_empty` are `True` for every possible call today, by construction. Neither sub-condition can ever be the reason this check reports `fail`; the check's entire discriminating power reduces to the `leaked` sys.modules scan, even though a failure's `detail` string prints all three as if independently informative.

**Why it matters** — This is precisely the 'check that passes vacuously' pattern the harness's own design thesis (code loads facts, never judgment, and must never drift silently) warns against applied to its own self-check: `validate` reports this as 1 of 15 green checks, but it is really testing 1 real condition dressed as 3, so a reviewer reading '15/15 green' cannot tell how much of that green is load-bearing without reading the stub's source.

**Proposed fix** — Either drop `xbrl_empty`/`classification_empty` from the `ok` computation and rename the check to reflect that it only guards the module-leak boundary, or replace the hardcoded-stub call with a check that would actually exercise a non-empty branch if one were ever reintroduced, so the assertion tests behavior rather than a source-code literal.

---

## F37 · [LOW] rankdiff crashes with a raw non-JSON traceback on a malformed call — inconsistent with the pattern the repo's own newest script already uses correctly

**Where** — scripts/serenity_harness.py:353 (`_parse_ranking`, uncaught `FileNotFoundError`), :373-399 (`cmd_rankdiff`, no try/except); vs. scripts/serenity_sectormap.py:79-86 (`JsonArgumentParser`, always-JSON contract)

**Failure** — Running `serenity_harness.py rankdiff sessions/nope_a.md sessions/nope_b.md` directly crashes with a bare Python traceback (`FileNotFoundError: [Errno 2] No such file or directory: 'sessions/nope_a.md'`), confirmed by execution, not the `{"error": ...}` JSON shape every other command in this repo (including rankdiff's own sibling `validate`) returns. Given real session paths in this repo already contain spaces and non-ASCII text (see Finding 1), a mistyped or unquoted path is exactly the input this command will see, and the traceback teaches nothing about the fix.

**Why it matters** — rankdiff is the harness's only reproducibility-measurement tool, so it's the one most likely to be re-run repeatedly across sessions months apart — the lowest-context, highest-typo-risk situation a clean error matters most in. The inconsistency also means the codebase carries two different error-handling idioms for the same JSON-CLI contract.

**Proposed fix** — Wrap `serenity_harness.py`'s subcommands with the `safe_run`-style guard `scripts/modules/utils.py` already provides, or adopt `serenity_sectormap.py`'s `JsonArgumentParser`+`SectorMapError` pattern directly — it already exists in this repo, not a new idiom to invent.

---

## F38 · [LOW] Guard: never let `analyze` suggest an archetype from sector/industry code — naming the exact tempting mistake this audit's own lens could cause

**Where** — CLAUDE.md:89 ("Hardware/materials is a chokepoint by default; relabel... never to unlock a softer valuation"); .claude/skills/serenity-analysis/SKILL.md:39 (same rule, worked); scripts/pipeline/_evidence.py:14-32 (`FORBIDDEN_EVIDENCE_KEYS`, already excludes `verdict`/`assessment`/etc. but not a hypothetical `suggested_archetype`)

**Failure** — `key_facts` already carries `sector`/`industry` (yfinance fields) for every ticker. A future 'interface improvement' could add a `suggested_archetype` field to `analyze`'s output, defaulting hardware/materials sector codes to `bottleneck` — silently reintroducing the deleted `objective_screen` judgment-in-code pattern this harness's central invariant exists to prevent. It would be wrong on exactly the names the doctrine cites as the reason the rule exists: a hardware name that's actually a Disruption/Evolution play (the doctrine's own worked exception) would default-tag Bottleneck and never get relabeled, because relabeling requires reading FOR a drained profit pool or a datable step-change — evidence no sector code carries.

**Why it matters** — This is the harness's single most-guarded boundary (restated independently at CLAUDE.md and serenity-analysis §0) precisely because it's the most tempting one to cross while doing legitimate interface work — sector/industry are already loaded facts sitting right next to where the temptation would strike. Naming it is the cheapest possible insurance against the one mistake that would undo the whole design.

**Proposed fix** — No code change — a do-not-build note for future interface work on this harness. Consider one comment line near `_evidence.py:25-31`'s `FORBIDDEN_EVIDENCE_KEYS` pointing future editors at this exact failure mode, the same way that block already documents why `regime`/`risk_level` are forbidden.

---

