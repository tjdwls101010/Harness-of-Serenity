# references/ — build-time scaffolding (NOT a runtime dependency)

These files are consulted while **building** the harness. The **runtime** harness —
when it discovers/analyzes a sector or ticker — never reads them.

**Runtime harness uses only:** `CLAUDE.md` (always loaded) + the triggered skill(s)
under `.claude/skills/` + the `scripts/` CLIs + `data/analysis_Serenity.db`
(the DB only on an explicit cross-validation request — see the DB discipline).

**Authoring invariant:** skills must *embody* the tacit knowledge in themselves; they
must never point to `references/` at runtime. Content here is distilled *into*
CLAUDE.md and the skills — not referenced as a pointer.

Contents:
- `legacy-monolith-skill.md` — the original embodied doctrine; **source of truth** the skills are extracted from (never loaded at runtime).
- `db-mining-report.md` — real-corpus fidelity corrections + the 12-thesis validation gold-set (used in build-time validation only).
- `omo-craft.md` — transferable authoring craft applied when writing the skills.
- `pipeline-audit.md` — evidence-only code refactor checklist.
- `legacy-router-skill-draft.md`, `Scrap_Serenity.ipynb`, `Seongjin-validations/` — archive.
