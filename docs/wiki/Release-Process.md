# Release Process

How a version gets cut, what a release must satisfy, and the change-history conventions this
repository uses.

Scaled to what this project is: a personal research harness with no CI and no release cadence.
The process is a checklist, not a pipeline.

## Versioning

Semantic versioning, interpreted for a project whose "API" is a set of CLIs and a JSON schema:

| Bump | Triggered by |
| --- | --- |
| **Major** | A change to the evidence-contract shape, or a removed or renamed top-level output key |
| **Minor** | A new subcommand, a new output field, a new data module, a new hook or skill |
| **Patch** | Bug fixes, documentation, dependency bumps, fixture re-blessing |

Version tags are `vX.Y.Z`. The current release is `v0.1.0` (2026-07-09).

**A caution stated plainly:** while the project is pre-1.0, interfaces change without a
deprecation period. Pin a commit if you depend on one.

### What counts as a breaking change here

The user-visible surface is JSON, so the compatibility question is about payload shape:

**Breaking** — removing or renaming a top-level key, changing a field's type, changing
`evidence_contract.kind`, or removing a subcommand or a flag.

**Not breaking** — adding a field (consumers should tolerate unknown keys), a value changing
because upstream data changed, or a field becoming absent because its source returned nothing.
That last one is normal operation: `_pick` omits null-valued keys by design, so **every consumer
must treat any field as potentially absent.**

## The release checklist

### 1. All three suites green

```bash
PY=scripts/.venv/bin/python

$PY scripts/serenity_harness.py validate        # → "ok": true, pass: 15, fail: 0
$PY .claude/hooks/tests/run_fixtures.py         # → 22/22 fixtures passed
python3 -m pytest scripts/tests/ -q             # see Known Limitations
```

`validate` must be green. It is the only check that verifies the boundary rule across all 16
fixtures, and a release that ships a judgment leak defeats the project's purpose.

### 2. A live smoke test

Fixtures are frozen, so they cannot catch an upstream break. Run at least one real ticker:

```bash
$PY scripts/serenity_pipeline.py analyze AAPL | jq '.key_facts | keys | length'
$PY scripts/serenity_pipeline.py macro | jq '.macro_inputs | keys'
$PY scripts/serenity_filings.py company AAPL | jq '.cik'
```

Check that `key_facts` is populated, that macro gauges are present (with `FRED_API_KEY`
exported — see [Known Limitations](Known-Limitations.md#env-is-not-loaded-for-macro-modules)),
and that EDGAR responds.

### 3. Documentation matches the code

If the release changes a command, a flag, or an output field, the corresponding wiki page changes
in the same commit. Specifically:

- New or changed CLI surface → [Pipeline Reference](Pipeline-Reference.md) or
  [Filings and SEC](Filings-and-SEC.md)
- New module → [Data Modules](Data-Modules.md)
- New hook, skill, or agent → [Agent Harness](Agent-Harness.md) or
  [Hooks Reference](Hooks-Reference.md)
- A fixed defect → remove its entry from [Known Limitations](Known-Limitations.md)
- Any structural change → `.claude/harness-spec.md`

### 4. No placeholders or broken links

```bash
grep -rnE 'TODO|FIXME|XXX|\{\{|<your ' README.md CONTRIBUTING.md SECURITY.md docs/
```

### 5. Update the changelog

Add a dated entry to `CHANGELOG.md` under a new version heading. Format follows Keep a Changelog:
`Added`, `Changed`, `Fixed`, `Removed`, plus a `Verification` note recording what was actually run.

### 6. Tag and publish

```bash
git tag -a v0.2.0 -m "v0.2.0"
git push origin v0.2.0
```

Then add release notes at `docs/releases/vX.Y.Z.md` and, if publishing on GitHub, a release
pointing at the tag.

## Release notes

One file per version at `docs/releases/vX.Y.Z.md`, covering:

- **What changed**, grouped by area, written for someone deciding whether to upgrade.
- **Breaking changes** with migration steps — never omitted, never softened.
- **Known issues** shipping with the release, linked to
  [Known Limitations](Known-Limitations.md).
- **Verification**: which suites were run and what they returned.

The changelog is the index; release notes are the detail. Do not duplicate one into the other.

## The design record

`.claude/harness-spec.md` is the audit anchor for the harness layer — what each component is and
**why it lives in the layer it lives in** — plus a dated change history.

Its conventions are worth preserving because they are unusually honest:

- Each entry lists per-file changes **and what was deliberately not done, with the reason.**
- Where a change was measured, the measurement is recorded even when unflattering. One entry notes
  an eval moving from 72% to 70% and states that this is inside the noise floor at n = 6 — neither
  claimed as an improvement nor hidden as a regression.

Update it whenever a component changes, so the next audit has something to compare against.

## Planning documents

Substantial changes get a plan at `docs/plans/YYYY-MM-DD-{topic}-plan.md` **before**
implementation. The convention, visible in the one shipped example, is a plan written to be
executed by a different session than the one that wrote it:

| Section | Purpose |
| --- | --- |
| Status | Provenance — who approved it, when, and what review it survived |
| Goal | What success means, plus explicitly rejected targets |
| Decisions log | A table of settled decisions, frozen — not to be re-litigated |
| Deliverables | Numbered, in implementation order, mapped to files touched |
| Per-deliverable sections | One each, with verbatim anchors for text being replaced |
| Risks and honest limits | What could go wrong and what the plan does not solve |
| Deferred | Explicitly out of scope |
| Acceptance checklist | Checkboxes the implementing session works through |
| Adversarial review log | Findings from reviewing the plan before finalizing |
| Implementation log | Appended during implementation — deviations and what was skipped |

Two features carry most of the value. **Decisions are frozen** — but the plan explicitly instructs
the implementing session to surface anything that turns out to be technically impossible rather
than silently improvising around it. And **pre-verification items run first**: assumptions the
design leans on get checked before any code is written.

After implementation, the implementation log is compressed into `harness-spec.md`'s change
history.

## What a release is not

- **Not a promise of stability.** Pre-1.0, and there is no support commitment.
- **Not automated.** No CI, no release workflow. Every step above is manual.
- **Not a performance claim.** Nothing in a release asserts that the method produces returns. The
  [eval](Eval-Harness.md) measures method reproduction only, and no backtest exists anywhere in
  this repository.

---

**Next:** [Testing and Validation](Testing-and-Validation.md) ·
[Contributing](../../CONTRIBUTING.md) · [Back to index](README.md)
