# Hook fixtures

Committed stdin payloads that pin the branch behavior of the two prose-gating hooks — `verdict_gate.py`
(Stop) and `evidence_discipline.py` (UserPromptSubmit). Each `.json` file is one scenario: the exact
stdin a hook would receive at its lifecycle event. Before this directory existed the scenarios lived
only as names in `harness-spec.md`, so "re-run the regressions" was not executable — these files fix that.

## Re-run the whole suite

```bash
scripts/.venv/bin/python .claude/hooks/tests/run_fixtures.py    # dependency-free, from the repo root
```

`run_fixtures.py` pipes each payload to the hook on stdin and asserts the expected branch — the durable,
in-repo check. It must exit 0; the pass count it prints is derived, never asserted anywhere else.

## Re-run one fixture through the harness-creator tool (the canonical per-file check)

```bash
test_hook.py --command .claude/hooks/verdict_gate.py       --event Stop            --input .claude/hooks/tests/verdict_gate/silent_full.json
test_hook.py --command .claude/hooks/evidence_discipline.py --event UserPromptSubmit --input .claude/hooks/tests/evidence_discipline/equity_cashtag.json
```

(`test_hook.py` ships with the harness-creator skill: `~/.claude/skills/harness-creator/scripts/test_hook.py`.)
`verdict_gate.py`'s `Saved:`-mark branch resolves the archive folder against `$CLAUDE_PROJECT_DIR`
(set by Claude Code in production), falling back to the current directory. The scaffolding it resolves
against — `990101.hook-fixture/` (holds a `.md`) and `990102.hook-empty/` (holds none) — lives in this
suite's own sandbox at `fixtures/sessions/`, so for the `--command` form above, point
`CLAUDE_PROJECT_DIR` at `.claude/hooks/tests/fixtures`. `run_fixtures.py` does that for you.
Both hook scripts must be
executable (`chmod +x`) for the `--command` form, since it execs them via their shebang; in production
`settings.json` invokes them through the venv python explicitly, so the bit is irrelevant there.

## Scenarios and expected outcomes

### verdict_gate/ (Stop) — SILENT = exit 0 no output · SOFT = `additionalContext` nudge · HARD = `decision: block`

| Fixture | Expected |
|---|---|
| `silent_full` | SILENT — complete verdict: NFI + `Lens:`(×/÷,=) + Downsides + falsifier + valid `Saved:` mark |
| `soft_lens` | SOFT — valuation verdict, no `Lens:` line → the machine-checkable-lens nudge |
| `hard_nfi` | HARD — complete market verdict, no NFI/NFA sign-off |
| `coding_silent` | SILENT — coding answer that says "TL;DR" but carries no finance signal |
| `macro_hard` | HARD — macro overweight/underweight call with no sign-off (also appends soft lens+Saved) |
| `meta_silent` | SILENT — harness-dev answer literally mentioning "Saved:" but with no verdict; `Saved:` branch must not fire |
| `bear_leg_soft` | SOFT — floor/discount leg run, no bull leg → the half-run-fork nudge |
| `saved_missing` | SOFT — finance verdict, no `Saved:` line → the "isn't archived" nudge |
| `saved_folder_missing` | SOFT — valid-shaped mark but the folder is absent → false-claim nudge |
| `saved_wrong_shape` | SOFT — mark = `sessions/INDEX.md` (no `yymmdd.slug`) → invalid-path nudge |
| `saved_empty_folder` | SOFT — valid mark, folder exists but holds no `.md` → claimed-but-empty nudge |
| `saved_backtick_silent` | SILENT — backtick-wrapped valid mark; regex tolerance strips the backticks |
| `false_fire_guard` | SILENT — coding/harness answer with near-miss words ("bottleneck", "pass"), no finance signal |

### evidence_discipline/ (UserPromptSubmit) — FIRE = reminder printed · SILENT = no output

| Fixture | Expected |
|---|---|
| `equity_cashtag` | FIRE — cashtag + "should i buy" |
| `equity_korean` | FIRE — Korean market phrasing (뭐 사 / 사도) |
| `macro_regime` | FIRE — macro/regime intent (장 어때) |
| `equity_english_phrase` | FIRE — "priced in" / "worth owning" |
| `meta_hook_no_anchor` | SILENT — "bottleneck" trips intent but reads as hook dev, no market anchor |
| `meta_dev_refactor` | SILENT — "archetype" trips intent but this is refactor/skill dev, no anchor |
| `meta_with_anchor` | FIRE — dev words present, but the `$NVDA` anchor overrides the meta guard |
| `non_market` | SILENT — neither market intent nor meta |
| `ranking_retrieval` | FIRE — ranking intent; the reminder must contain the new sessions/INDEX retrieval line |
