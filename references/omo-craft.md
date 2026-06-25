# omo Harness — Transferable Authoring Craft

Distilled from `.tmp/omo` (an expert-built Codex harness) + the `skill-creator` doctrine. This is the craft WF2 authoring agents must apply when writing CLAUDE.md and the skills. It is about *how to write*, not what.

## The one law: conviction over compliance
A rule tells the model *what*; a principle convinces it *why* — and a convinced model handles the case the rule never named. A rule is a rail bolted outside the model's judgment: on an unanticipated case, obeying the rail overrides intelligence, breaking it loses the rule. A principle the model is *persuaded* of has no such collision — it re-derives the right move. So principle-embodiment is not a gentler order; it is the only way to instruct without clipping the capability you're instructing.

**The test for every line:** *given only the why I supplied, could the model re-derive this instruction and handle an unmentioned case?* Yes → principle. Only-works-for-listed-cases → rail (rewrite or cut).

## The mechanism: what + a why that convinces + a picture
Every instruction answers three things, weight on the why — and not every why convinces:
- Flat: "Use ISO 8601 dates — they're unambiguous."
- Convincing: "Use ISO 8601 (`2025-03-15`). When input mixes US/EU conventions, `03/04/2025` is March 4th to the author and April 3rd to a parser elsewhere — nothing errors, the data silently corrupts. An unambiguous format kills the failure at its source."
Make the failure *visible*; then the model reaches for the principle in places you never listed. Convince once, generalize everywhere.

## Target: persuade only what isn't already believed
The model already owns general finance/analysis/coding sense. Spending a paragraph on what it knows does worse than waste space — it signals "I don't trust you," and a model told it isn't trusted works smaller. Over-explaining the obvious clips intelligence from the other side. **Keep only:** domain knowledge it hasn't seen (serenity's specific edge), preferences it can't guess, decisions already made (exact commands/schemas), and — highest signal of all — **gotchas**: traps the model walks into precisely because it can't know the domain. One gotcha prevents more wasted runs than a page of advice. The strongest skills *accumulate* gotchas.

Per-line verdict:
| Line is… | Verdict |
|---|---|
| Direction (a decision the system made: "evidence loads via scripts/serenity_pipeline.py") | KEEP |
| Principle (claim + convincing reason + instance) | KEEP |
| Knowledge counter to the model's default ("here, the scarcer node out-multiples the assembler") | KEEP |
| Gotcha (loss-hardened trap) | KEEP (never cut) |
| Bare rule (steps, no reason) | CUT — supply the reason, or trust the model |
| Denial of something never raised ("this has no quick mode") | CUT — describe what *is*; let absence stay absent |

## Leanness follows, it isn't imposed
You're not trimming to be terse; you're cutting lines that don't pull weight, because each dead line dilutes the live ones and buries the key instruction where attention thins. A 200-line skill of filler is worse than a 700-line skill where every line earns its place — *non-contributing* length is the enemy, not length. Audit: read each paragraph, ask "what changes if this vanishes?" If "nothing" → it's gone. When an edge case is stubborn, delete it and strengthen the principle; don't add a 16th rule that snaps on the 17th case.

## Progressive disclosure has an optimum, not a direction
Three load stages: (1) name+description — always in context; (2) SKILL.md body — on trigger; (3) references/ — only when reached.
- **SKILL.md body** = needed on *every* invocation: triggers, the decision backbone, the top procedure, the governing philosophy. The model must orient on this each time.
- **references/** = conditional depth only some runs need (a deep catalogue, a variant, a long table).
- Under-split → key lines drown. Over-split → the model can't route to its own knowledge (loads the wrong file, misses connective tissue, fails silently). Split when the saving (skipped on most runs) beats the routing cost. Don't split by *volume* ("feels long") — split by *invocation pattern*. Never push the core decision tree into a reference.

## Frontmatter & triggering
- `name`: kebab-case.
- `description`: the PRIMARY trigger — carries ALL the "when to use." Claude currently *under*-triggers, so lean slightly toward triggering ("Use whenever the user mentions X, Y, or Z — even if they never say 'X'"). A skill loading when marginally unneeded costs little; staying dark when needed costs the whole skill.
- Body: When/Why → gotchas → references → invariants. (omo's skills follow this; e.g. ast-grep front-loads its 3 hard gotchas, ends with invariants.)

## Scripts: parameterized, never frozen
Bundled code pays off only when it *composes*: a CLI taking args (`serenity_pipeline.py evidence --ticker MU`), or importable helpers the model assembles. The trap is the frozen no-arg script with one hardcoded purpose — the moment the task shifts an inch the model rewrites it and the bundle bought nothing. Write the parameterized version.

## Hooks: three modes, deterministic JSON I/O (omo)
- **Guards** block bad actions (Pre-tool, Stop). **Injectors** add context at the right moment (SessionStart/UserPromptSubmit/PostToolUse `additionalContext`). **Verifiers** check work and optionally block. A hook trying to be all three is brittle.
- Command-based, read JSON stdin → write JSON stdout, exit 0, silent = no-op. Language-neutral, testable with fixtures, every output loggable. Use matchers to fire only on the relevant tool.
- Named by *event+action* (`user-prompt-submit-loading-rules`), so the registry is self-documenting.

## Orchestrator discipline (for our workflows)
A skill/agent that spawns subagents must forbid itself from implementing directly — it coordinates, delegates, aggregates verdicts, records evidence. Keeps the orchestrator's context for conclusions, not raw material.
