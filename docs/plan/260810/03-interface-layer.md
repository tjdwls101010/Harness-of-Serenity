# Phase 03 — the interface layer: move what is *valid* into signatures

**Prerequisite:** Phase 01.

**Scope note:** everything in this phase is **code only**. Each item ships a working tool; the doctrine sentence that tells the model to *reach for* it is deferred to Phase 06, because "when to use this" is a judgment-prose change and therefore gated on Phase 04's working eval. Shipping the tool early is free; shipping the instruction to use it before it can be measured defeats the sequencing.

Findings covered: F07, F08, F09, F10/F27 (rediscovered independently by two lenses), F11, F22.

---

## The two-CLI principle, resolved

The owner's design instinct — *one execution gathers everything needed for judgment; the arg is just the ticker* — is correct, and this plan preserves it. It applies to **fact loaders**, whose input is an identity (which company, which period) and whose job is to fetch. `analyze TICKER` should never grow an `--archetype` flag: beyond being unnecessary, it would leak judgment into the fact layer and break C1.

It does not apply to **arithmetic over judgment outputs**, because those inputs do not exist to be fetched. The content-sizing lens needs content-per-unit (the doctrine itself says this is "load-bearing and almost always confidential — triangulate from a CEO value-capture quote") and a projected unit volume (an estimate). Two of its three inputs come into existence only after the model has judged. "One call gathers everything" is not undesirable here, it is impossible.

The harness already runs this pattern in three places, which is the strongest argument that it fits: `discover TKR1 TKR2 …` takes a **model-generated cohort** (which names are comparable is a judgment no fetch can make), and `serenity_filings.py xbrl-facts TICKER --concept … --dimension …` and `section TICKER --named …` take **model-chosen selectors**. The lens CLI is the same pattern applied to arithmetic, not a new philosophy.

Net tool count stays flat: `pipeline` / `filings` / `harness` / `tweets` becomes `pipeline` / `filings` / `harness` / `lens`, with generators and linters folded into `harness` as subcommands rather than new files.

---

## 3.1 — The lens CLI

**What it is.** One subcommand per doctrine-named valuation driver, each taking only that driver's model-supplied inputs, whose sole output is the verified `Lens:` line the contract already requires.

**What it buys, honestly.** Not arithmetic correctness on its own — the model multiplies fine at this scale, and if that were the whole case this would be ceremony. Three things justify it:

- The doctrine's most-repeated numeric warning is not about multiplication, it is about **dividing by the wrong market cap** ("cite MC from `key_facts` verbatim… never one you remember"). A tool that pulls MC from the same source `analyze` did makes that failure structurally impossible instead of rule-enforced.
- **The closed driver list in non-negotiable #10 becomes an open space.** A subcommand set plus a `custom` escape hatch is the same information in a form that teaches the shape and admits a sixth driver — converting an RC4 rail into a principle, and relocating it to a surface re-read for free inside subagents that never load CLAUDE.md (C3).
- **The forked-lens fight becomes structural.** Running only the bear leg is named in the doctrine as the single biggest direction-miss; a `--fork floor|upside` tag makes "both legs ran" a checkable fact rather than a hope.

**The argument space** (names indicative; the shape is the point). Each subcommand takes only deduced or estimated inputs, never facts the pipeline already loads — PEG and the no-growth floor are already `valuation_inputs.forward_pe` / `valuation_inputs.no_growth` and need correct citation, not a subcommand:

```
lens content-volume     --content --volume --mc
lens mw-irr             --rev-per-gpu-hr --mw --cogs-per-mw --financing-rate
lens replacement-cost   --capacity-units --cost-per-unit --comp-ev-per-unit
lens pro-forma-fcf      --cogs-addressable --opex-saved --new-recurring-rev --multiple
lens net-cash-after-atm --raised --shares-cost --sbc-funded
lens sum-of-parts       --stake-value --operating-value --parent-mc
lens custom             --expr 'a×b÷c' --inputs k=v,...
```

`--fork floor|upside` on any of them. `sum-of-parts` is included deliberately: it is doctrine, it is additive, and it is the case that keeps breaking the hook's operator regex (Phase 02.3) — a tool that emits the line ends that whole class of problem.

**The seam constraints (C1), enforced by fixture, not by discipline.** This is the item in the plan most likely to drift into judgment-in-code, so the guards are mechanical:

- the argument surface **never accepts a ticker or an archetype** — the mirror image of the fact loaders' ticker-only rule;
- the output **never contains valuation vocabulary** (`cheap`, `priced`, `rich`, `buy`, `pass`, `sell`, `overvalued`, `undervalued`);
- the tool never ranks drivers, never selects which lens applies, and never refuses a driver as inapplicable.

Write these as fixtures alongside the code, the same way the harness already fixture-enforces its other seam invariants. If someone later adds a convenience feature that infers the lens from a sector code, the fixture fails and says why.

**The 16th case:** a driver nobody has named yet. `custom --expr` must be genuinely usable — not a degraded fallback — because the doctrine explicitly authorizes re-anchoring on a new driver when the framework breaks (strategic monopoly, float-yield, policy-mandated TAM). If `custom` is awkward enough that the model avoids it, the escape hatch is decorative and the list is still closed.

**Deferred to Phase 06:** the doctrine line telling the model when to call this, and whether `verdict_gate` should eventually verify the emitted line's arithmetic against captured `key_facts`.

## 3.2 — A session-folder generator

The `{yymmdd}.{topic-slug}` convention broke on its first real use: the only session folder this repo has ever produced is `sessions/260726. 반도체 인더스트리 딥리서치/` — a space and a Korean phrase, against an `INDEX.md` header that says "English only." Worse, this actively corrupts the hook: feeding `verdict_gate.py` a `Saved:` line naming that **real, correctly-archived** folder produces the soft nudge "not a valid session path," because the regex cannot match a space or Hangul after the dot. Finished work gets nagged to re-archive.

Add `harness new-session --slug <kebab> [--type ranking|analysis|macro|postmortem] [--tickers T1,T2,…]`. It computes `{yymmdd}` from wall-clock (never model memory — a date recalled under output pressure is exactly the class of error the harness bans elsewhere), validates the slug at the argument boundary so a bad name is rejected *before* `mkdir` rather than discovered after, auto-suffixes `-2` on collision per the doctrine, creates the folder, and prints both the exact `Saved:` line and the exact `INDEX.md` append line ready to paste.

The mechanism is the point: the model transcribes generated text instead of composing four rules from memory at the end of a long answer. Convention plus a soft nudge has now been tried, and its one real trial produced a folder that fails its own check.

**The 16th case:** a Korean topic. The generator should either transliterate or require an English slug and say so at the boundary — the failure must be impossible to commit, not merely detected afterward.

## 3.3 — Schema enforcement for scorecards and rankings

**The evidence.** All seven real scorecards violate the pinned schema: every one carries the explicitly-forbidden `tier:` field, writes `archetype: Bottleneck` where the schema pins lowercase `chokepoint`, uses free text where `stage` is an int 1–5, and omits `type` / `session` / `date` / `data_as_of` / `mc` / `gate_strength`. `validate` reported green throughout, because its scorecard check greps `serenity-scorecard.md` for the strings `gate_strength:` and `conviction:` — it verifies the spec file contains its own sentinels, never that any produced file conforms.

Three layers, in order of leverage:

1. **`harness scorecard-lint FILE`** — required keys present, `archetype`/`gates`/`conviction` as enums, `stage` as int 1–5, forbidden `tier:` absent. Mirror the pattern `serenity_sectormap.py`'s `validate_map` already uses; do not invent a new idiom.
2. **A `PostToolUse` hook on `Write` to `sessions/**/[A-Z0-9.]*.md`** — same shape as the existing `data_integrity_guard.py`, soft-flagging a non-conforming frontmatter at the moment it is written, when the context to fix it is still live.
3. **Change `validate`'s check** to lint the most recent real scorecard under `sessions/` in addition to the spec file's self-consistency.

**Also:** `rankdiff`'s `_parse_ranking` does plain string equality on tier cells, so `Tier 1` in one run and `1 (core)` in another read as a changed tier and deflate the agreement percentage the spec calls a free reproducibility measurement. Add a canonicalization pass and reject any tier string outside the doctrine's fixed vocabulary with a named error.

**Scope it to format, hard.** `rankdiff` must keep reporting only *that* a tier changed, never labelling *why* — evidence delta versus judgment revision versus cohort delta needs both rankings' reasoning text and is the model's call (C1). A linter that starts explaining changes has crossed the seam.

**The 16th case worth pausing on:** it is not established that the scorecard *agent* produced these seven files — the session also contains `_codex_*` artifacts, so a different path may have written them. That does not change the fix (a schema honored only on one path is not honored), but it does change the diagnosis, and it is worth resolving during implementation because it tells you whether the agent's instructions or the inline-fill path is the leak. Either way, the Rank-N protocol's Step 1 should inline the field list rather than pointing at the agent file, since the inline path is precisely the one that never loads it.

## 3.4 — Make `harness` fail like the rest of the repo

`rankdiff` with a bad path raises a bare `FileNotFoundError` traceback, against a repo where every other command returns `{"error": …}` JSON. Given real session paths here already contain spaces and non-ASCII, an unquoted path is exactly the input this command will see, and a traceback teaches nothing about the fix. Adopt `serenity_sectormap.py`'s `JsonArgumentParser` pattern — it already exists in this repo.

Treat the error text as an interface (C3): it is read at exactly the moment it matters and costs nothing otherwise, so it should say what valid input looks like.

## 3.5 — Resolve `serenity_sectormap.py`'s status

It is a fully built, tested, working CLI with `validate`/`show`/`layers`/`tickers`/`cohort`/`diff`/`index` subcommands, used by the one real session — and it is untracked in git, absent from `harness-spec.md`, and mentioned in no doctrine file. A fresh session asking a type-D supply-chain question has zero signal that a schema-validated `_sectormap.json` format exists, so it will free-form an unstructured chain map exactly as the D-template describes.

Decide deliberately, and record the decision: either **adopt** it (git add, spec row, a pointer from CLAUDE.md's D bullet or `serenity-discovery`'s chain-tracing section — the pointer being Phase-06 work) or **remove** it along with the dangling `INDEX.md` cross-reference. Leaving a capability that exists but is invisible is the worst of the three.

If adopted, fix the flaw its own session review already named and deferred: `cohort --layer` emits a ready-to-run `discover` argv including tickers the map's own notes disclaim as "theme exposure, not bottleneck ownership," feeding two $50B+ conglomerates into a comparator the routing reflex calls "the verdict." Add a `relationship: owner | tool | consumer | adjacent_proxy` field, enum-validated like the existing `listing` field, and default `cohort` to owners with an explicit `--include-adjacent` opt-in.

**The 16th case:** any future tool built in a side session. The generalizable lesson — a tool that is not in the spec and not pointed to by doctrine does not exist from the model's perspective — belongs in `harness-spec.md` as a completion criterion for adding a component.

---

## Exit criteria

1. `lens` runs, every subcommand emits a correctly-formatted `Lens:` line, and the seam fixtures (no ticker/archetype argument, no valuation vocabulary in output) pass.
2. `harness new-session` creates a conforming folder and prints both paste-ready lines; a non-kebab slug is rejected at the boundary.
3. `harness scorecard-lint` flags all seven existing scorecards, `validate` picks that up, and the `PostToolUse` write-guard fires on a synthetic bad write.
4. `rankdiff` returns JSON on a bad path and canonicalizes tier strings.
5. `serenity_sectormap.py` is either committed and specced, or removed with its references.
6. **No doctrine file changed in this phase.** Wiring is Phase 06.
