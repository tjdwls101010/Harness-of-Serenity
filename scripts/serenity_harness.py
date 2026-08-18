#!/usr/bin/env python3
"""Fast static validator for the active research harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("serenity-cohort", "serenity-discovery", "serenity-macro-event", "serenity-single-name")
AGENTS = ("peer-blind-candidate", "serenity-filings")
HOOKS = {
    "SessionStart": ".claude/hooks/session_health.py",
    "Stop": ".claude/hooks/lifecycle_gate.py",
}
SKILL_MODES = {
    "serenity-cohort": "cohort",
    "serenity-discovery": "discovery",
    "serenity-macro-event": "macro-event",
    "serenity-single-name": "single-name",
}
CANONICAL_HARNESS = '"$SERENITY_PYTHON" "$SERENITY_HARNESS" validate'
CANONICAL_CLI = '"$SERENITY_PYTHON" "$SERENITY_CLI" run start'
METHOD_LEDGER = ROOT / "method" / "claim-ledger.v1.json"
METHOD_DIGEST = ROOT / "method" / "candidate-digest.v1.json"
METHOD_SYNTHESIS = ROOT / "method" / "synthesis-evidence.v1.json"
METHOD_LEDGER_CONTENT_HASH = "dba5fe018b2061048cb97d0207b363f6ac0ecddef6735bef7f1f2fdbc369aaab"
METHOD_DIGEST_CONTENT_HASH = "3056087bca1f24c5ee660bfce20a47bfdc93961f7b8e1f090efdd8949632d6f3"
METHOD_ROOT_CONTRACT = (
    "active method contract is source-tagged",
    "`sourced`",
    "`augmented`",
    "unverified",
    "not a rule",
)
WORKFLOW_CLAIMS = {
    "serenity-macro-event": (
        "claim-01-screen-price-and-positioning-before-inference",
        "claim-06-test-catalyst-conversion-capacity",
        "aug-adaptive-evidence-not-decision-code",
    ),
    "serenity-discovery": (
        "claim-02-validate-every-causal-hop",
        "claim-03-verify-identity-and-revenue-linkage",
        "aug-physical-chain-and-vehicle-contract",
    ),
    "serenity-single-name": (
        "claim-07-evaluate-capital-by-per-share-conversion",
        "claim-09-use-milestone-falsifiers-not-price-alone",
        "aug-fact-referenced-lens-validity",
        "aug-immutable-action-lifecycle",
    ),
    "serenity-cohort": (
        "claim-03-verify-identity-and-revenue-linkage",
        "claim-11-evaluate-process-with-complete-attribution",
        "aug-blind-method-and-evaluation-boundary",
    ),
}
SKILL_METHOD_ESSENTIALS = {
    "serenity-macro-event": ("Question frame", "Competing hypotheses", "Evidence sought", "Inference", "Action and falsifier", "Deliverable and hand-off", "company disclosures", "demand, supply, pricing, financing, or only sentiment", "usable capacity"),
    "serenity-discovery": ("Question frame", "Competing hypotheses", "Evidence sought", "Inference", "Action and falsifier", "Deliverable and hand-off", "material intensity", "qualification", "substitutability", "no clean US-listed vehicle", "Determine structural concentration from the binding relationship and revenue linkage before testing investability.", "Investability, the US-listed vehicle, and action are separate gates.", "examples when raw evidence supports them; allow another mechanism", "Do not force every case through the same checklist.", "A ticker-like label or trading venue is not issuer/security identity or revenue linkage.", "Never call a vehicle direct until identity binding is evidenced.", "If the link is missing, preserve it as unresolved and choose `BLOCKED`, `MONITOR`, or `PASS` as the facts warrant.", "Do not fabricate a direct-versus-indirect relation."),
    "serenity-single-name": ("Question frame", "Competing hypotheses", "Evidence sought", "Inference", "Action and falsifier", "Deliverable and hand-off", "adjusted net asset value", "per-share", "premium hurdle", "observable primary trigger", "Any non-null identifier conflict is unresolved identity", "`MONITOR` is not a substitute", "prepared remarks", "Q&A", "management claim", "hard operating observation", "disclosed", "corroborated", "inferred", "contradicted", "omission or evasion", "Use `NFA` only for actionable `RECOMMEND_NOW` or `ENTER_ON_TRIGGER` conclusions."),
    "serenity-cohort": ("Question frame", "Competing hypotheses", "Evidence sought", "Inference", "Action and falsifier", "Deliverable and hand-off", "common comparison question", "blind challenge", "evidence quality", "relative fit"),
}
CLAIM_REFERENCE = re.compile(r"\b(?:claim-\d{2}-[a-z0-9-]+|aug-[a-z0-9-]+)\b")
PERSONA_CONTRACT = (
    "# Harness of Serenity",
    "You are Harness of Serenity",
    "US-listed equity research harness",
    "adopt, verify, and outperform the source method independently",
    "always-loaded core capabilities",
    "economic-power concentration and dependency graphs",
    "SEC/issuer-narrative and market-fact provenance",
    "capital flows and macro",
    "competing hypotheses and falsifiers",
    "priced-in",
    "saved lens",
    "conditional actions",
    "decisive but adversarial toward your own favorite thesis",
    "consensus summary",
    "promising industries, sectors, and US tickers",
    "single-name deep dive and observable conditional entry",
    "Physical AI recursive physical bottleneck",
    "US expression or no-clean-vehicle",
    "macro/headline forward-economics",
    "cohort comparison",
    "typed fact, evidence, lens, graph, and outcome interfaces",
    "explicit post-analysis cross-validation",
    "sharp, collaborative Korean-friendly peer",
    "TLDR:",
    "plain uncertainty",
    "not cosplay or exact phrase imitation",
    "NFA",
)

ROOT_HELP = """Validate the active harness wiring without calling providers or replaying research.

`validate` writes one-JSON report to stdout. Run `validate --help` for the exact static checks, exclusions, exit codes, hook-test boundary, and examples. Help is I/O-free."""

VALIDATE_HELP = """Check the active harness as a fast static inventory check.

Checks:
  - root research boundaries and required runtime variables
  - AGENTS.md and the tracked .codex -> .claude symlink
  - the exact four skills and two agents, including frontmatter contracts
  - settings.json's one SessionStart and one Stop command hook
  - narrow hook source contracts, legacy prose-hook removal, and the harness spec
  - source-tagged method artifacts: fixed ledger/digest hashes, self-hashes, 12 sourced + 8 augmented tags, synthesis provenance, and resolved workflow/spec claim IDs

Does not check:
  - provider availability, market data, filing facts, or network access
  - a research decision's artifact validity, lens calculation, or investment conclusion
  - hook execution; use the harness-creator hook tester separately

JSON output and exit codes:
  - stdout is one JSON report with ok, inventory, errors, and warnings
  - exit 0 means errors is empty; exit 1 means one or more static errors
  - help itself is I/O-free and exits 0

Hook tests are separate:
  HARNESS_CREATOR_DIR="${CODEX_HOME:-$HOME/.codex}/skills/harness-creator"
  python3 "$HARNESS_CREATOR_DIR/scripts/test_hook.py" --settings .claude/settings.json --event SessionStart
  python3 "$HARNESS_CREATOR_DIR/scripts/test_hook.py" --settings .claude/settings.json --event Stop --input-field stop_hook_active=false

Lifecycle recovery:
  - saying BLOCKED in assistant prose does not resolve an OPEN run because the Stop hook does not read prose
  - save and finalize a typed BLOCKED decision or abandon it with a recorded reason

Examples:
  scripts/.venv/bin/python scripts/serenity_harness.py validate
  scripts/.venv/bin/python scripts/serenity_harness.py validate | jq .
"""


def _read(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"unreadable {path.relative_to(ROOT)}: {exc}")
        return ""


def _load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(f"unreadable {path.relative_to(ROOT)}: {exc}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON {path.relative_to(ROOT)}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path.relative_to(ROOT)} must be a JSON object")
        return {}
    return value


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        field = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", line)
        if field:
            values[field.group(1)] = field.group(2).strip().strip("\"'")
    return values


def _check_symlink(path: Path, target: str, errors: list[str]) -> None:
    if not path.is_symlink() or os.readlink(path) != target:
        errors.append(f"{path.name} must be the {target} symlink")


def _check_root(errors: list[str], warnings: list[str]) -> None:
    text = _read(ROOT / "CLAUDE.md", errors)
    if not text:
        return
    lines = len(text.splitlines())
    if lines >= 200:
        warnings.append(f"CLAUDE.md is {lines} lines; keep the always-loaded root under 200")
    if not text.startswith("# Harness of Serenity\n"):
        errors.append("CLAUDE.md title must be exactly # Harness of Serenity")
    private_identity = ("Seongjin", "성진", "/Users/seongjin")
    if any(token in text for token in private_identity):
        errors.append("CLAUDE.md must keep a generic multi-user identity without private names or paths")
    required = (
        "US-listed",
        "RECOMMEND_NOW",
        "ENTER_ON_TRIGGER",
        "Fact",
        "Inference",
        "Action",
        "SERENITY_CLI",
        "NFA",
    )
    for token in required:
        if token not in text:
            errors.append(f"CLAUDE.md is missing required boundary: {token}")
    if "portfolio allocations" not in text:
        errors.append("CLAUDE.md must exclude portfolio allocation advice")
    if "Do not freeze an archetype" not in text:
        errors.append("CLAUDE.md must reject frozen archetype-first routing")
    if CANONICAL_HARNESS not in text or "`$SERENITY_HARNESS validate`" in text:
        errors.append("CLAUDE.md must invoke validate through the declared Python interpreter")
    lifecycle = ("save and finalize a typed decision (including BLOCKED)", "abandon it with a recorded reason", "merely says BLOCKED has no lifecycle effect")
    if any(contract not in text for contract in lifecycle):
        errors.append("CLAUDE.md must align OPEN recovery with the typed Stop lifecycle")
    missing_persona = [contract for contract in PERSONA_CONTRACT if contract not in text]
    if missing_persona:
        errors.append(f"CLAUDE.md is missing persona/capability contract: {missing_persona}")
    missing_method = [contract for contract in METHOD_ROOT_CONTRACT if contract not in text]
    if missing_method:
        errors.append(f"CLAUDE.md is missing source-tagged method contract: {missing_method}")
    _check_symlink(ROOT / "AGENTS.md", "CLAUDE.md", errors)
    _check_symlink(ROOT / ".codex", ".claude", errors)


def _check_codex_distribution(errors: list[str]) -> None:
    gitignore = _read(ROOT / ".gitignore", errors)
    if "/.codex" in gitignore.splitlines():
        errors.append(".gitignore must not exclude the tracked .codex -> .claude symlink")
    readme = _read(ROOT / "README.md", errors)
    for contract in ("tracked `.codex -> .claude` symlink", "without copying"):
        if contract not in readme:
            errors.append(f"README Quick Start must explain Codex distribution: {contract}")


def _declared_capabilities() -> tuple[set[str], set[str]]:
    catalog = json.loads((ROOT / "config" / "evidence-catalog.v1.json").read_text(encoding="utf-8"))
    return (
        {entry["provider_id"] for entry in catalog["providers"]},
        {capability for entry in catalog["providers"] for capability in entry["capabilities"]},
    )


def _check_capability_references(path: Path, text: str, errors: list[str]) -> None:
    """A capability ID written in prose is a pointer, so it has to resolve.

    Named wrongly it sends the model to build a request the registry refuses, and
    the instruction layer is the one surface no test exercises. Only tokens whose
    prefix is a declared provider are checked, which is what keeps `serenity.py`
    and a `sec.*` glob from reading as capability names.
    """

    providers, capabilities = _declared_capabilities()
    for token in re.findall(r"`([a-z][a-z0-9.-]*)`", text):
        prefix, separator, _ = token.partition(".")
        if separator and prefix in providers and token not in capabilities:
            errors.append(f"{path.relative_to(ROOT)} names a capability the evidence catalog does not declare: {token}")


def _check_skills(errors: list[str]) -> list[str]:
    directory = ROOT / ".claude" / "skills"
    observed = sorted(path.parent.name for path in directory.glob("*/SKILL.md")) if directory.is_dir() else []
    if observed != list(SKILLS):
        errors.append(f"active skills must be exactly {list(SKILLS)}; found {observed}")
    for name in SKILLS:
        path = directory / name / "SKILL.md"
        text = _read(path, errors)
        fields = _frontmatter(text)
        if fields.get("name") != name:
            errors.append(f"{path.relative_to(ROOT)} frontmatter name must be {name}")
        if not fields.get("description"):
            errors.append(f"{path.relative_to(ROOT)} needs a trigger description")
        command = f"{CANONICAL_CLI} --mode {SKILL_MODES[name]}"
        if command not in text or f"{CANONICAL_CLI} --help" not in text or "with `$SERENITY_CLI`" in text:
            errors.append(f"{path.relative_to(ROOT)} must use the interpreter-backed run start command and its help")
        if re.search(r"(?<!\$)scripts/", text):
            errors.append(f"{path.relative_to(ROOT)} hard-codes a scripts/ path instead of a CLAUDE variable")
        missing_method = [contract for contract in SKILL_METHOD_ESSENTIALS[name] if contract not in text]
        if missing_method:
            errors.append(f"{path.relative_to(ROOT)} must be self-contained for a root-plus-skill cleanroom: {missing_method}")
        for forbidden in ("fixed pipeline", "hardcoded threshold", "v1 encyclopedia", "voice cosplay"):
            if forbidden in text.lower():
                errors.append(f"{path.relative_to(ROOT)} must not restore a legacy method rail: {forbidden}")
        _check_capability_references(path, text, errors)
    return observed


def _check_agents(errors: list[str]) -> list[str]:
    directory = ROOT / ".claude" / "agents"
    observed = sorted(path.stem for path in directory.glob("*.md")) if directory.is_dir() else []
    if observed != list(AGENTS):
        errors.append(f"active agents must be exactly {list(AGENTS)}; found {observed}")
    names: list[str] = []
    for filename in AGENTS:
        path = directory / f"{filename}.md"
        text = _read(path, errors)
        fields = _frontmatter(text)
        name = fields.get("name", "")
        names.append(name)
        if name != filename:
            errors.append(f"{path.relative_to(ROOT)} frontmatter name must be {filename}")
        if not fields.get("description"):
            errors.append(f"{path.relative_to(ROOT)} needs a delegation description")
        if fields.get("model") != "sonnet":
            errors.append(f"{path.relative_to(ROOT)} must use the default sonnet exploration tier")
        _check_capability_references(path, text, errors)
    if len(names) != len(set(names)):
        errors.append("agent frontmatter names must be unique")
    filings = _read(directory / "serenity-filings.md", errors)
    for forbidden in ("recommendation", "price target", "rank candidates"):
        if forbidden not in filings:
            errors.append(f"serenity-filings must explicitly prohibit {forbidden}")
    filings_fields = _frontmatter(filings)
    if filings_fields.get("tools") != "Read, Grep, Glob, Bash, WebSearch, WebFetch":
        errors.append("serenity-filings must have the narrow official-source discovery tools")
    for contract in ("official issuer-owned URL", "source discovery only", "issuer-ir.document", "management_claim", "hard_operating_observation", "relationship_status", "cross_company_read_through_candidate", "omission_or_evasion", "never becomes the thesis or action"):
        if contract not in filings:
            errors.append(f"serenity-filings must preserve issuer narrative evidence semantics: {contract}")
    blind = _read(directory / "peer-blind-candidate.md", errors)
    if "Do not request or inspect prior candidate decisions, rankings" not in blind:
        errors.append("peer-blind-candidate must preserve blind input")
    blind_fields = _frontmatter(blind)
    if blind_fields.get("tools") != "Read, Grep, Glob, Bash, WebSearch, WebFetch":
        errors.append("peer-blind-candidate must have the narrow read-only narrative research tools")
    for contract in ("current narrative sources", "never use web results as numeric facts", "typed evidence request"):
        if contract not in blind.lower():
            errors.append(f"peer-blind-candidate must preserve its narrative evidence boundary: {contract}")
    return observed


def _check_settings(errors: list[str]) -> dict[str, int]:
    path = ROOT / ".claude" / "settings.json"
    try:
        settings = json.loads(_read(path, errors))
    except json.JSONDecodeError as exc:
        errors.append(f".claude/settings.json is invalid JSON: {exc}")
        return {}
    hooks = settings.get("hooks") if isinstance(settings, dict) else None
    if not isinstance(hooks, dict):
        errors.append(".claude/settings.json must contain hooks")
        return {}
    if set(hooks) != set(HOOKS):
        errors.append(f"settings hook events must be exactly {sorted(HOOKS)}; found {sorted(hooks)}")
    counts: dict[str, int] = {}
    for event, script in HOOKS.items():
        groups = hooks.get(event)
        entries = groups[0].get("hooks") if isinstance(groups, list) and len(groups) == 1 and isinstance(groups[0], dict) else None
        counts[event] = len(entries) if isinstance(entries, list) else 0
        if not isinstance(entries, list) or len(entries) != 1:
            errors.append(f"{event} must have exactly one exec hook")
            continue
        entry = entries[0]
        if not isinstance(entry, dict) or entry.get("type") != "command":
            errors.append(f"{event} must use a command hook")
            continue
        command = entry.get("command") if isinstance(entry, dict) else None
        expected_command = "${CLAUDE_PROJECT_DIR}/scripts/.venv/bin/python"
        if command != expected_command or entry.get("args") != [script]:
            errors.append(f"{event} must invoke {script}")
        if not (ROOT / script).is_file():
            errors.append(f"{script} is missing")
    return counts


def _check_hooks(errors: list[str]) -> None:
    session = _read(ROOT / HOOKS["SessionStart"], errors)
    for token in ("hookSpecificOutput", "additionalContext", "return 0"):
        if token not in session:
            errors.append(f"session health hook must implement {token}")
    stop = _read(ROOT / HOOKS["Stop"], errors)
    for token in ("stop_hook_active", "content_hash", '"decision": "block"', "run-manifest.json"):
        if token not in stop:
            errors.append(f"lifecycle gate must implement {token}")
    if "last_assistant_message" in stop:
        errors.append("lifecycle gate must not inspect assistant prose")
    legacy = ("data_integrity_guard.py", "evidence_discipline.py", "scorecard_guard.py", "session_status.py", "verdict_gate.py")
    for relative in legacy:
        if (ROOT / ".claude" / relative).exists():
            errors.append(f"legacy natural-language hook surface remains: .claude/{relative}")
    if (ROOT / ".claude" / "hooks" / "tests").exists() and any(path.is_file() for path in (ROOT / ".claude" / "hooks" / "tests").rglob("*")):
        errors.append("legacy natural-language hook fixtures remain under .claude/hooks/tests")


def _check_spec(errors: list[str]) -> None:
    text = _read(ROOT / ".claude" / "harness-spec.md", errors)
    for token in ("active harness", "active-run.json", "run-manifest.json", "Historical recovery points live on GitHub"):
        if token not in text:
            errors.append(f"harness spec is missing {token}")
    if CANONICAL_HARNESS not in text or "`$SERENITY_HARNESS validate`" in text:
        errors.append("harness spec must invoke validate through the declared Python interpreter")
    if "historical recovery points live on github rather than in the runtime tree" not in text.lower():
        errors.append("harness spec must keep historical recovery outside the runtime tree")
    lifecycle = ("save and finalize a typed BLOCKED decision", "abandon with a durable reason")
    if any(contract not in text for contract in lifecycle):
        errors.append("harness spec must align recovery with the typed Stop lifecycle")
    if "generic multi-user identity" not in text or any(token in text for token in ("Seongjin", "성진", "/Users/seongjin")):
        errors.append("harness spec must retain generic multi-user identity and portable public examples")


def _check_method_contract(errors: list[str]) -> dict[str, Any]:
    ledger = _load_json(METHOD_LEDGER, errors)
    digest = _load_json(METHOD_DIGEST, errors)
    synthesis = _load_json(METHOD_SYNTHESIS, errors)
    if not ledger or not digest or not synthesis:
        return {}

    unsigned_ledger = {key: value for key, value in ledger.items() if key != "content_hash"}
    ledger_hash = ledger.get("content_hash")
    if ledger.get("format") != "serenity-method-claim-ledger/1" or ledger_hash != METHOD_LEDGER_CONTENT_HASH or ledger_hash != _canonical_hash(unsigned_ledger):
        errors.append("method claim ledger must have a valid canonical self-hash")
    claims = ledger.get("claims")
    if not isinstance(claims, list):
        errors.append("method claim ledger must contain claims")
        claims = []
    claim_tags: dict[str, str] = {}
    for claim in claims:
        if not isinstance(claim, dict) or not isinstance(claim.get("claim_id"), str) or not isinstance(claim.get("provenance_tag"), str):
            errors.append("method claim ledger claims need claim_id and provenance_tag")
            continue
        claim_id = claim["claim_id"]
        if claim_id in claim_tags:
            errors.append(f"method claim ledger repeats claim_id: {claim_id}")
        claim_tags[claim_id] = claim["provenance_tag"]
    sourced = sum(tag == "sourced" for tag in claim_tags.values())
    augmented = sum(tag == "augmented" for tag in claim_tags.values())
    unverified = sum(tag == "unverified" for tag in claim_tags.values())
    if len(claim_tags) != 20 or sourced != 12 or augmented != 8 or unverified != 0 or set(claim_tags.values()) != {"sourced", "augmented"}:
        errors.append("method claim ledger must contain exactly 12 sourced and 8 augmented claims, with no unverified rule")

    digest_unsigned = {key: value for key, value in digest.items() if key != "content_hash"}
    if digest.get("format") != "serenity-method-candidate-digest/1" or digest.get("content_hash") != METHOD_DIGEST_CONTENT_HASH or digest.get("content_hash") != _canonical_hash(digest_unsigned):
        errors.append("method candidate digest must have a valid canonical self-hash")
    synthesis_ledger = synthesis.get("final_claim_ledger")
    if not isinstance(synthesis_ledger, dict) or synthesis_ledger.get("content_hash") != ledger_hash or synthesis_ledger.get("sha256") != hashlib.sha256(METHOD_LEDGER.read_bytes()).hexdigest() or synthesis_ledger.get("sourced_claims") != sourced or synthesis_ledger.get("augmented_claims") != augmented or synthesis_ledger.get("unverified_claims") != unverified:
        errors.append("method synthesis evidence must attest to the current ledger hash and tag counts")
    synthesis_digest = synthesis.get("candidate_digest")
    if not isinstance(synthesis_digest, dict) or synthesis_digest.get("content_hash") != digest.get("content_hash") or synthesis_digest.get("sha256") != hashlib.sha256(METHOD_DIGEST.read_bytes()).hexdigest():
        errors.append("method synthesis evidence must attest to the current candidate digest")
    if synthesis.get("format") != "serenity-method-synthesis-evidence/1" or synthesis.get("model") != "gpt-5.6-sol" or synthesis.get("single_final_synthesis") is not True or synthesis.get("invocation_count") != 1:
        errors.append("method synthesis evidence must record one final Sol synthesis")
    revalidation = synthesis.get("read_only_revalidation")
    if not isinstance(revalidation, dict) or revalidation.get("status") != "valid" or revalidation.get("relaunch_performed") is not False or revalidation.get("record_rewritten") is not False:
        errors.append("method synthesis evidence must retain the valid read-only revalidation")
    historical = synthesis.get("historical_execution_record")
    if not isinstance(historical, dict) or historical.get("status") != "forbidden_read_observed" or historical.get("preserved_unchanged") is not True:
        errors.append("method synthesis evidence must preserve the original jq false-positive record")

    referenced_paths = [ROOT / "CLAUDE.md", ROOT / ".claude" / "harness-spec.md"] + [ROOT / ".claude" / "skills" / name / "SKILL.md" for name in SKILLS]
    for path in referenced_paths:
        references = set(CLAIM_REFERENCE.findall(_read(path, errors)))
        unknown = sorted(references - set(claim_tags))
        if unknown:
            errors.append(f"{path.relative_to(ROOT)} cites unknown method claims: {unknown}")
        adopted_unverified = sorted(claim_id for claim_id in references if claim_tags.get(claim_id) == "unverified")
        if adopted_unverified:
            errors.append(f"{path.relative_to(ROOT)} adopts unverified method claims as rules: {adopted_unverified}")
    for skill, required_claims in WORKFLOW_CLAIMS.items():
        text = _read(ROOT / ".claude" / "skills" / skill / "SKILL.md", errors)
        missing = [claim_id for claim_id in required_claims if claim_id not in text]
        if missing:
            errors.append(f"{skill} must route its method claims: {missing}")
    return {"ledger_content_hash": ledger_hash, "sourced_claims": sourced, "augmented_claims": augmented}


def validate() -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    _check_root(errors, warnings)
    _check_codex_distribution(errors)
    skills = _check_skills(errors)
    agents = _check_agents(errors)
    hooks = _check_settings(errors)
    _check_hooks(errors)
    _check_spec(errors)
    method_contract = _check_method_contract(errors)
    return {
        "ok": not errors,
        "format": "serenity-harness-report/1",
        "skills": skills,
        "agents": agents,
        "hooks": hooks,
        "method_contract": method_contract,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=ROOT_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", title="commands", required=True)
    commands.add_parser(
        "validate",
        help="emit the one-JSON static harness report",
        description=VALIDATE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    args = parser.parse_args()
    if args.command == "validate":
        report = validate()
        json.dump(report, sys.stdout, ensure_ascii=False, sort_keys=True)
        print()
        return 0 if report["ok"] else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
