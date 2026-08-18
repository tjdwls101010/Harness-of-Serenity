# Harness specification

## Status

This is the active harness for typed US-listed equity research. Historical recovery points live on GitHub rather than in the runtime tree. The authoritative structural check is `"$SERENITY_PYTHON" "$SERENITY_HARNESS" validate`; this document records why that narrow inventory exists and how to recover it.

## Design rationale

The root instruction stays small because every request pays for it. Its generic multi-user identity names Harness of Serenity, the independent-method objective, the always-on structural capabilities, adversarial temperament, and user outcomes before carrying the project boundary, lifecycle, evidence identity/time rules, Fact/Inference/Action distinction, action vocabulary, answer style, and runtime variables. Typed fact, evidence, lens, graph, and outcome interfaces are capability enablers, not a substitute for judgment. Detailed procedures live at the task interface, where they can be loaded only when their trigger applies. The root does not dictate an archetype-first pipeline or preserve a threshold encyclopedia: hypotheses and evidence decide what lens is appropriate.

The research boundary is US-listed common stock, ADRs, and ETFs. The harness never produces portfolio allocations or position sizing. It can state a research action only from the fixed vocabulary `RECOMMEND_NOW`, `ENTER_ON_TRIGGER`, `MONITOR`, `PASS`, and `BLOCKED`; an actionable response remains non-personalized and ends with `NFA`.

`AGENTS.md -> CLAUDE.md` remains the shared entry point, and the bundled tracked `.codex -> .claude` symlink gives Codex the same harness without a duplicate tree. They are checked as symlinks rather than duplicated instructions. A user must trust the workspace for project hooks to run; on an untrusted clone, the written lifecycle rules still describe the contract but hook enforcement is unavailable.

## Source-tagged method contract

The active method contract is source-tagged, not a retrospective style guide. `method/claim-ledger.v1.json` is the canonical ledger (`content_hash` `dba5fe018b2061048cb97d0207b363f6ac0ecddef6735bef7f1f2fdbc369aaab`): 12 `sourced` claims reconstruct reusable moves from the bounded evidence, while 8 `augmented` claims are explicit product, safety, and interface choices. There are zero `unverified` claims; if one appears in a future ledger it is a lead, not a rule, until the ledger is regenerated and verified.

The ledger is bound to `method/candidate-digest.v1.json` (`content_hash` `3056087bca1f24c5ee660bfce20a47bfdc93961f7b8e1f090efdd8949632d6f3`; 76 packets, 3,766 chunks, 1,953 coded and 1,813 no-reusable-move chunks) and `method/synthesis-evidence.v1.json`. The latter records one gpt-5.6-sol invocation as the single Sol final synthesis, attests to the ledger's 12/8/0 counts and raw SHA-256, and preserves the original jq // false-positive record (`forbidden_read_observed`) unchanged. Its read-only revalidation is valid: the repair exempts only jq's exact `//` alternative operator, with zero forbidden reads, no relaunch, and no record rewrite.

The claim IDs are interfaces, not a second rail encyclopedia. The root applies `aug-structural-concentration-and-priced-in`, `aug-identity-time-provenance-boundary`, `aug-adaptive-evidence-not-decision-code`, `aug-fact-referenced-lens-validity`, `aug-immutable-action-lifecycle`, and `aug-product-and-history-boundary` as compact cross-cutting principles. Macro/event routes `claim-01-screen-price-and-positioning-before-inference`, `claim-06-test-catalyst-conversion-capacity`, and `claim-10-treat-thin-reports-as-leads`; discovery routes `claim-02-validate-every-causal-hop`, `claim-03-verify-identity-and-revenue-linkage`, and `aug-physical-chain-and-vehicle-contract`; single-name routes `claim-04-separate-asset-value-from-realizability`, `claim-05-match-derivative-hurdle-to-thesis-window`, `claim-07-evaluate-capital-by-per-share-conversion`, `claim-08-resolve-dilution-growth-contradiction`, `claim-09-use-milestone-falsifiers-not-price-alone`, `claim-12-separate-timing-error-from-thesis-failure`, `aug-fact-referenced-lens-validity`, and `aug-immutable-action-lifecycle`; cohort routes `claim-03-verify-identity-and-revenue-linkage`, `claim-09-use-milestone-falsifiers-not-price-alone`, `claim-11-evaluate-process-with-complete-attribution`, `aug-adaptive-evidence-not-decision-code`, and `aug-blind-method-and-evaluation-boundary`. The focused skills carry exact IDs so a changed rule has one source of truth.

## Active inventory

There are exactly four task workflows:

| Directory | Trigger and boundary |
| --- | --- |
| `.claude/skills/serenity-macro-event/` | Regime, policy, headline, drawdown, mechanical catalyst, and forward-economics questions. |
| `.claude/skills/serenity-discovery/` | Sector/theme discovery, supply-chain mapping, US-listed vehicle resolution, and no-clean-vehicle cases. |
| `.claude/skills/serenity-single-name/` | One ticker’s identity, evidence, lens, trigger, bear case, falsifier, and conditional action. |
| `.claude/skills/serenity-cohort/` | Blind candidate challenge and transparent cohort comparison without a provider-driven score. |

Each workflow calls the `SERENITY_CLI` variable defined in `CLAUDE.md`; it does not assume that a copied skill has a relative `scripts/` directory. The runtime mode is one of `macro-event`, `discovery`, `single-name`, or `cohort`.

Each focused skill is a self-contained method interface for a candidate cleanroom that receives only the root and that skill, not the ledger or another workflow body. It directly distills its relevant sourced/augmented claims into question framing, competing hypotheses, adaptive evidence sought, falsifiable inference, action boundary, and deliverable/hand-off. Claim IDs remain provenance, not the only executable method body; the skills do not restore a score, threshold list, or archetype rail.

There are exactly two agents:

| Agent | Contract |
| --- | --- |
| `.claude/agents/serenity-filings.md` | Returns SEC and official issuer evidence only: accession or official URL, concept/location, source/provenance, time, raw hash, identity binding, management claim versus operating observation, and explicit absence/conflict. It cannot recommend, rank, value, or select an action. |
| `.claude/agents/peer-blind-candidate.md` | Proposes or challenges candidates from the question and evidence rules without receiving prior decisions, rankings, or verdicts. It returns reasons, exclusions, and evidence requests; the main analyst synthesizes later. |

Both agents use the sonnet/terra exploration tier. The issuer-evidence agent has read-only WebSearch/WebFetch to locate official issuer documents, but search is source discovery only: the already-resolved URL must pass the identity-, domain-, time-, and raw-byte-bound `issuer-ir.document` provider before its contents become evidence. It separates prepared remarks from Q&A, management claims from hard operating observations, and disclosed/corroborated relationships from inferred or contradicted ones; cross-company read-through remains a candidate for the main analyst. The peer-blind candidate agent uses the same read-only tools because current narrative sources can resolve or challenge a discovery/Physical AI relationship that supplied evidence has not reached; it preserves source/cutoff and returns typed evidence requests for any material gap. Neither agent turns web results into numeric facts or substitutes them for identity-pinned runtime data. Both agents return typed outputs or proposed patches and never overwrite another active task’s artifacts. Sol/opus is reserved for a single final disagreement adjudication when it is genuinely required, not broad fan-out.

## Evidence and decision contract

Every research run follows this order: start the typed mode, pin the security or macro identity and cutoff, record competing hypotheses, make adaptive evidence requests, run a saved lens where a numeric target is claimed, and save a decision. The model may change its mind as evidence arrives; it may not silently rewrite the source time, identity, or earlier uncertainty.

`Fact` means a source-backed observation carrying identity binding, provenance, and temporal availability. `Inference` is a falsifiable explanation of facts and must keep competing hypotheses visible. `Action` is the current enum result and must stay distinct from both. Missing, conflicting, stale, or unavailable evidence is an observation, not a license to backfill from memory or an uncited search value.

The catalog carries a `capability_parameters` contract per capability, a JSON Schema the registry validates `provider_parameters` against before it constructs a provider, so a shape no provider could serve is refused by name rather than becoming an uninformative `unavailable` envelope after a real request. `evidence catalog --capability <id>` prints one contract; the bare listing omits them because all of them together are an order of magnitude larger than the capability list. Reads are bounded the same way: `evidence collect` and `evidence read` answer with the value's shape, `--value` opts into the payload, and `evidence read --match REGEX` returns spans with character offsets into the stored string, so a citation stays checkable against the saved artifact. The stored artifact is always complete and hash-anchored; only the read view is bounded. `serenity_harness.py validate` checks that every capability ID named by a skill or agent resolves in the catalog, because the instruction layer is the one surface no test exercises.

Identity is pinned per subject. `snapshot security RUN_ID --subject TICKER` binds one security at a time and attaches as `fact-snapshot-<TICKER>`, keeping the bare `fact-snapshot` name for a single-subject run; a decision whose scope is `single-name` or `cohort` is refused unless every subject is pinned, and the refusal names the ones that are not. `macro` subjects are series identifiers and `sector` subjects are industries, so neither takes a security snapshot -- demanding one would ask for an identity resolution the subject has no meaning for. `snapshot facts RUN_ID --from-evidence RESULT_ID --fact name=..,concept=..,unit=..` turns selected rows of a saved `sec.xbrl-facts` result into a second fact snapshot stamped with the filing's accession URL and raw-byte hash, and `lens run` unions every attached snapshot, so a numeric target can trace to a filing rather than to a provider-computed ratio. Deriving requires the subject already pinned, because the derived snapshot copies its identity from the pinned one.

An `ENTER_ON_TRIGGER` action has an observable current condition. Every action records the strongest bear case and falsifiers. A numeric target requires a valid saved lens with its fact references. Unresolved identity or an invalid required lens forces a typed `BLOCKED` decision, which must be saved and finalized; `PASS` and `MONITOR` are positive honest outcomes, not incomplete recommendations.

## Hook contract

The settings file has one `SessionStart` command hook and one `Stop` command hook, nothing else. No UserPromptSubmit or PostToolUse hook remains, because lifecycle validity belongs to typed artifacts rather than arbitrary assistant prose.

`session_health.py` is local and network-free. It checks shared symlinks, settings shape, current entry files, the presence of the mandatory SEC contact identity, and the consistency of any active pointer/manifest. The two SEC credentials are checked for presence only and never echoed: `SERENITY_SEC_USER_AGENT` or `EDGAR_IDENTITY` gates every identity-pinned run, while `EDGAR_IDENTITY` alone gates SEC filings evidence, so they are reported separately rather than as one satisfied condition. A healthy hook emits no stdout and exits 0. A degraded hook still exits 0 and emits only `hookSpecificOutput.additionalContext`, phrased as a factual local-state diagnostic so ordinary work can continue through transient provider or local setup issues.

`lifecycle_gate.py` ignores `last_assistant_message` and all transcript prose. It reads only `.serenity/active-run.json` and the referenced `.serenity/runs/<run_id>/run-manifest.json`. It recomputes each `content_hash`, checks pointer/manifest identity and status consistency, returns silently for no active pointer or any verified non-OPEN run, and blocks a verified OPEN run with `{ "decision": "block", "reason": "..." }`. A pointer or manifest that claims active state but cannot be verified also blocks with a factual reason. `stop_hook_active: true` returns silently before any check, preventing an infinite Stop loop after one forced continuation.

The stop gate does not validate a decision itself or inspect downstream artifacts. The runtime’s decision contract owns that work; the hook only prevents an OPEN lifecycle from being mistaken for a finished response. Saying `BLOCKED` in an assistant response does not alter the lifecycle: save and finalize a typed BLOCKED decision or abandon with a durable reason.

## Validation

The public seams are the one-JSON `serenity_harness.py validate` command and each hook’s stdin/stdout protocol. `tests/260817/e2e/test_harness_hooks.py` tests those seams with checked-in hook input fixtures, including green startup, soft degradation, no active run, hashed OPEN pointer/manifest, loop guard, and corrupt claimed active state. It intentionally does not test hook helper functions.

Run these after a harness change:

```sh
$SERENITY_PYTHON -m pytest -q tests/260817/e2e/test_harness_hooks.py
"$SERENITY_PYTHON" "$SERENITY_HARNESS" validate
HARNESS_CREATOR_DIR="${CODEX_HOME:-$HOME/.codex}/skills/harness-creator"
python3 "$HARNESS_CREATOR_DIR/scripts/validate_harness.py" --path . --json
python3 "$HARNESS_CREATOR_DIR/scripts/test_hook.py" --settings .claude/settings.json --event SessionStart
python3 "$HARNESS_CREATOR_DIR/scripts/test_hook.py" --settings .claude/settings.json --event Stop --input-field stop_hook_active=false
python3 "$HARNESS_CREATOR_DIR/scripts/test_hook.py" --settings .claude/settings.json --event Stop --input-field stop_hook_active=true
```

Provider boundaries are verified in two tiers, because they fail in two different ways. `pytest tests/ -q` runs offline in CI and replays real captured payloads from `tests/260817/fixtures/recorded/` through the real adapters, so a hand-authored fixture can no longer encode a response shape the provider never returns; `tests/260817/fixtures/recorded/capture_payloads.py` re-captures them by driving each provider's own request builder. `pytest tests/ -q -m live` builds one real object per capability through the adapter itself and asserts the attributes and types it parses — edgartools and yfinance hand back Python objects rather than JSON, so no recorded file can pin `EntityFiling.acceptance_datetime` being a `datetime` or `TenQ` lacking `.risk_factors`. Live probes are excluded by default and never run in CI; run them when a pinned release in `scripts/requirements.txt` moves. `.github/workflows/tests.yml` runs the offline tier on GitHub-hosted runners, deliberately disjoint from the self-hosted scrape workflows and their fork-PR risk.

The harness validator is fast and static: it checks root boundaries, exact inventory, frontmatter, hook wiring, symlinks, absence of legacy prose-hook surfaces, variable-based skill invocation, this spec’s required contracts, and the source-tagged method artifacts (fixed hashes, canonical self-hashes, 12/8/0 tags, synthesis provenance, and resolvable workflow/spec claim IDs). It never calls providers, replays historical data, or grades research.

## Recovery

If SessionStart reports degradation, read the factual diagnostic and repair the named local file or symlink; it has not blocked the session. If Stop blocks an OPEN run, save and finalize a typed BLOCKED decision or abandon with a durable reason, then let the next stop check see its updated pointer; changing answer prose cannot resolve the lifecycle. If it blocks a corrupt pointer or manifest, do not infer the decision state: inspect the two named files, restore a content-hashed consistent pair through the runtime, or explicitly abandon/recreate the run. Do not delete evidence to silence the hook.
