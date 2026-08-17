# Appendix 02 — corpus and method

## Corpus purpose

The tweet database is evidence of a method, not a cache of conclusions to repeat. v2 must learn reusable reasoning moves, evidence preferences, phrasing constraints, and failure modes from it while preventing old name-specific calls from anchoring new work. A routine analysis must not query it. An explicit user request to compare against historical tweets may use it only after the independent v2 analysis is complete, and the comparison must be labelled as such.

The approved interview recorded an earlier snapshot of 1,844 rows, 1,443 media rows, and 2,027 unique images (1,984 JPEG and 43 PNG). Immediately before implementation, the current `main` DB was recounted as 1,874 rows and 2,062 unique media URLs. Treat the latter as the current rebase observation, not as an invariant: the audit command must compute its input denominators from the DB on every run, record the query/version/hash used, and reconcile every discovered row/media relation against its manifest. A change in source counts is a reportable corpus delta, never a reason to silently reduce the denominator or claim the old snapshot is current.

## Full media and text audit

Create a corpus inventory operation in `scripts/serenity_corpus.py` that reads `data/analysis_Serenity.db`, assigns stable source-row/media identifiers, and emits a tracked manifest describing source row, media reference, MIME/size, content SHA-256, extraction status, OCR/vision status, and audit disposition. Raw images go to an ignored content-addressed cache (for example `.serenity/cache/corpus-media/sha256/...`); git tracks the manifest and derived annotations, never the copied media payload unless the repository explicitly chooses to version it.

The audit is complete only when its dynamically counted DB rows and unique media references exactly reconcile to the manifest, with row-to-media relations preserved and the source DB hash/query included in the report. For the implementation rebase, the report must explicitly show the observed 1,874 rows and 2,062 unique media URLs or explain any later source delta. A duplicate URL or byte-identical image referenced by multiple rows remains one physical cache object and multiple manifest relations; therefore cache object/hash count is reported separately from unique URL count. Missing local media, failed OCR, and unsupported content are explicit audit dispositions with retry/provenance fields; none may be represented as a blank note.

Use text extraction first, OCR for text-bearing images, and vision review for charts, diagrams, screenshots, or images where OCR cannot establish the claim. Store the extractor/model name, version, prompt/template version for vision, extraction timestamp, source hash, confidence/caveat, and reviewer/audit status. Derived assertions must link to both a source row and the relevant media/hash. Do not infer a claim from a chart image without a reviewable explanation of what the image actually supports.

## Method reconstruction: open coding before doctrine

Run open coding in a cleanroom that excludes the old generated doctrine, old scores, saved verdicts, and v1 natural-language hooks. Coders receive corpus text/media derivatives and a compact coding protocol, not `CLAUDE.md`, prior skill text, old sessions, or previous candidate rankings. The purpose is to discover recurring moves and counterexamples rather than confirm a known taxonomy.

The codebook must separately label: observation type; causal-chain hop; claimed value-capture mechanism; identity/provenance discipline; valuation lens or missing lens; catalyst/mechanism distinction; funding/capital-structure reasoning; bear case/falsifier; timing/entry condition; recommendation scope; confidence/hedge language; contradiction; and outcome/post-mortem signal. A code requires source links and a short rationale. If evidence is thin or inconsistent, code it `unverified` rather than rewriting it into a principle.

Build a claim ledger from the codes. Every resulting doctrine item is tagged exactly one of `sourced`, `augmented`, or `unverified`. `sourced` has direct corpus support and representative/counterexample references. `augmented` is a deliberate v2 safety or engineering addition with a stated rationale, not attributed to the corpus. `unverified` is retained as a hypothesis/research question or excluded from operating rules; it must never become an invisible hard gate. The final harness loads sourced and explicitly adopted augmented rules, while a traceability appendix preserves every rule-to-evidence relation.

## Implemented reconstruction evidence

The cutover audit reconciles 1,874 tweets and all 2,062 media relations against a source record that includes DB SHA-256 `6c7cafab481ee721c001746d5a5008e77de5f2cbf989d705929f58fa8403c713`, query `SELECT id, type, media FROM tweets ORDER BY id`, and SQLite `user_version` 0. Of those relations, 1,911 have hash-verified cached bytes and 151 are explicit terminal HTTP 404 `unavailable` records; the available relations deduplicate to 1,892 physical SHA-256 objects. The strict extraction reconciliation has zero blockers.

Blind reconstruction produced 1,874 text chunks plus 1,892 SHA-deduplicated media chunks, 3,766 total, in 76 hash-bound packets. The private source index retains DB rows, media relations, and provenance; blind packets omit ticker, date, URL, DB identity, old doctrine, sessions, rankings, and answer keys. Exactly one selected completed result covers every packet and every chunk: 1,953 chunks were coded and 1,813 were explicit no-move dispositions.

The deterministic aggregate preserves exact labels rather than semantically merging them. Its bounded candidate digest selects frequent labels first and uses deterministic manifest-span quantiles only within a tied cutoff tier, with omitted counts and hashes for every truncated section. The final candidate digest has content hash `3056087bca1f24c5ee660bfce20a47bfdc93961f7b8e1f090efdd8949632d6f3` and raw SHA-256 `a2dd0883ae5aa804d7346ee2695b5be58da463a74ce5a1851e8f71ac0f495cb7`.

One `gpt-5.6-sol` final synthesis was run over that digest, with broad fan-out forbidden. Its historical execution record retains a conservative false-positive transcript classification caused by jq's `//` operator; the same immutable transcript and output were subsequently revalidated read-only after the auditor was corrected, without rerunning the model. The final ledger has content hash `dba5fe018b2061048cb97d0207b363f6ac0ecddef6735bef7f1f2fdbc369aaab` and contains exactly 12 corpus-`sourced`, 8 explicitly engineered `augmented`, and 0 `unverified` operating claims. [The synthesis evidence](../../../method/synthesis-evidence.v1.json), [candidate digest](../../../method/candidate-digest.v1.json), and [claim ledger](../../../method/claim-ledger.v1.json) preserve the bindings.

## Method principles adopted for v2

The following are v2 operating principles, expressed as interfaces rather than rigid analysis order:

- Start from a specific question and a small, identity-pinned fact snapshot; form multiple plausible mechanisms before selecting a conclusion.
- Distinguish structural claims from price claims. A company can own a real chokepoint yet be fully priced, a weak vehicle, or an inaccessible expression.
- Map economic power across physical, financial, regulatory, and strategic dependencies when the question calls for it. Do not force non-chain businesses into a physical bottleneck story.
- Treat the relationship between a catalyst and forward revenue as a falsifiable mechanical proposition, especially after cancellation, displacement, loss, cost-shock, or selloff headlines.
- Keep business thesis, valuation, timing, vehicle, bear case, and falsifier separate. A positive narrative cannot substitute for arithmetic; a weak trailing metric cannot automatically settle a buildout/restructuring thesis.
- Prefer source-pinned facts to memory or ambiguous web snippets. Deterministic source code protects identity; narrative research fills only evidence gaps that deterministic sources cannot answer.
- Track uncertainty as part of the result. Missing disclosure, stale data, and conflicting evidence reduce what can be claimed rather than inviting fill-in from memory.

These are not a mandatory archetype taxonomy or a fixed time horizon. The model may explore alternative structures and scenarios as long as it records what would distinguish them. It must never pretend that a provider’s composite, relative-strength field, or historical tweet call resolved the judgment.

## Data-provider policy

The baseline is free, modular, and provenance-preserving. The provider interface should make it possible to replace a source without changing decisions or schemas. Implement the high-value deterministic providers first:

| Provider/source | v2 use | Priority |
| --- | --- | --- |
| SEC ticker/CIK/exchange data and submissions | US issuer/listing identity, filing metadata, filing facts/narrative handoff | Mandatory |
| OpenFIGI | Cross-check instrument/issuer identity | Mandatory |
| FRED with ALFRED-aware vintage handling | Macro series with release/vintage and cutoff-safe availability | Mandatory |
| `ibd-rs-rating==0.3.0` | Owned adapter for raw relative-strength evidence and record dates | Mandatory adapter |
| USASpending, USITC, EIA | Contracts, trade/physical-flow, and energy evidence for adaptive requests | High |
| BLS, BEA, CFTC | Labour, macro/industry, and positioning evidence | Medium |
| SAM.gov, USPTO | Only when an evidence request demonstrates an E2E need | Conditional |
| Federal Register/BIS and primary issuer/agency documents | Narrative policy/regulatory evidence, never substituted market numbers | Adaptive |

Explicitly exclude Nasdaq Data Link, paid FINRA/exchange feeds, automated WIPO PATENTSCOPE scraping, and transcript aggregators from baseline v2. A later addition requires a documented user value, lawful/source-policy review, a provider envelope implementation, and a representative E2E case.

`ibd-rs-rating` is a user-owned library and is pinned in `scripts/requirements.txt` as `ibd-rs-rating==0.3.0`. Its adapter preserves raw values, upstream record dates, adapter version, query arguments, and availability/provenance. It must not implement an `RS >= 70` gate, map its score to leadership, or convert it into a recommendation. The model may judge its relevance alongside other evidence and must state that judgment in the hypothesis/decision layer.

## Evidence request policy

Evidence is gathered adaptively from competing hypotheses. Each request states the question it would answer, linked hypothesis IDs, required source class, desired temporal coverage, acceptance criteria, and what result would disconfirm or weaken the hypothesis. This prevents “collect every parameter” behavior while keeping the model free to explore scenarios the original pipeline did not predict.

An evidence result captures both positive and negative outcomes. `not_disclosed` is a valid filing finding; `conflict` retains all competing source claims and identity bindings; `stale` records the freshness policy/age rather than becoming silently current. Providers may retry under a documented bounded policy, then produce a typed unavailable result or return exit `4` if no typed result can be created.

## Corpus tests and completion gate

Tests go only in `tests/260817/`, with fixed miniature SQLite/media fixtures under `fixtures/` and public CLI tests under `cli/`/`adapters/`. Unit-like tests should assert manifest accounting, content-addressed deduplication, source-hash preservation, explicit failed-extraction status, claim provenance, codebook tag validity, and cleanroom allowlist enforcement. One representative live-safe corpus audit runs separately and writes a dated evidence report, but it must not make test success depend on a model provider being available.

The corpus/method stage completes when the full audit report gives exact raw counts and a failure taxonomy, every generated doctrine claim has a source/augmentation/unverified tag, a cleanroom attempt demonstrably lacks forbidden v1 inputs, and the implementation can show that a historical ticker verdict is unavailable to a routine analysis path.
