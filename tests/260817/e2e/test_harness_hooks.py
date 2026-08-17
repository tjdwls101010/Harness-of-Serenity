from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
HARNESS = ROOT / "scripts" / "serenity_harness.py"
SESSION_START = ROOT / ".claude" / "hooks" / "session_health.py"
STOP = ROOT / ".claude" / "hooks" / "lifecycle_gate.py"
FIXTURES = Path(__file__).with_name("fixtures") / "harness-hooks"
CANONICAL_HARNESS = '"$SERENITY_PYTHON" "$SERENITY_HARNESS" validate'
CANONICAL_CLI = '"$SERENITY_PYTHON" "$SERENITY_CLI" run start --mode '
METHOD_LEDGER = ROOT / "method" / "claim-ledger.v1.json"
METHOD_DIGEST = ROOT / "method" / "candidate-digest.v1.json"
METHOD_SYNTHESIS = ROOT / "method" / "synthesis-evidence.v1.json"


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _run_hook(path: Path, payload: dict[str, object], *, cwd: Path) -> tuple[int, str, str]:
    completed = subprocess.run(
        [sys.executable, str(path)],
        cwd=cwd,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode, completed.stdout, completed.stderr


def _write_open_run(root: Path) -> str:
    run_id = "run-hook-fixture"
    manifest = {
        "schema_id": "urn:serenity:schema:run-manifest:2",
        "run_id": run_id,
        "status": "OPEN",
        "mode": "single-name",
        "question": "Fixture question",
        "subjects": ["NVDA"],
        "as_of": "2026-08-17",
        "started_at": "2026-08-17T00:00:00Z",
        "updated_at": "2026-08-17T00:00:00Z",
        "actor": {"kind": "test", "id": "fixture"},
        "source_policy": {"policy_id": "fixture", "allow_network": False},
        "current_phase": "started",
        "events": [{"at": "2026-08-17T00:00:00Z", "type": "run_started"}],
        "artifacts": {},
    }
    manifest["content_hash"] = _canonical_hash(manifest)
    run_path = root / ".serenity" / "runs" / run_id / "run-manifest.json"
    run_path.parent.mkdir(parents=True)
    run_path.write_text(json.dumps(manifest), encoding="utf-8")
    pointer = {"run_id": run_id, "status": "OPEN", "updated_at": manifest["updated_at"]}
    pointer["content_hash"] = _canonical_hash(pointer)
    active_path = root / ".serenity" / "active-run.json"
    active_path.parent.mkdir(parents=True, exist_ok=True)
    active_path.write_text(json.dumps(pointer), encoding="utf-8")
    return run_id


def test_harness_validator_reports_the_active_inventory() -> None:
    completed = subprocess.run([sys.executable, str(HARNESS), "validate"], cwd=ROOT, text=True, capture_output=True, check=False)

    assert completed.returncode == 0, completed.stdout
    assert completed.stderr == ""
    report = json.loads(completed.stdout)
    assert report["ok"] is True
    assert report["format"] == "serenity-harness-report/1"
    assert "version" not in report
    assert report["skills"] == ["serenity-cohort", "serenity-discovery", "serenity-macro-event", "serenity-single-name"]
    assert report["agents"] == ["peer-blind-candidate", "serenity-filings"]
    assert report["hooks"] == {"SessionStart": 1, "Stop": 1}
    assert report["errors"] == []


def test_harness_root_and_validate_help_are_detailed_and_io_free(tmp_path: Path) -> None:
    root_help = subprocess.run([sys.executable, str(HARNESS), "--help"], cwd=tmp_path, text=True, capture_output=True, check=False)
    validate_help = subprocess.run([sys.executable, str(HARNESS), "validate", "--help"], cwd=tmp_path, text=True, capture_output=True, check=False)

    assert (root_help.returncode, root_help.stderr) == (0, "")
    assert "validate" in root_help.stdout
    assert "one-JSON report" in root_help.stdout

    assert (validate_help.returncode, validate_help.stderr) == (0, "")
    for detail in (
        "Checks:",
        "source-tagged method artifacts",
        "Does not check:",
        "JSON output and exit codes:",
        "Hook tests are separate:",
        "Examples:",
        "scripts/serenity_harness.py validate",
        "test_hook.py",
    ):
        assert detail in validate_help.stdout


def test_harness_docs_run_python_scripts_through_the_declared_interpreter() -> None:
    root = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    spec = (ROOT / ".claude" / "harness-spec.md").read_text(encoding="utf-8")

    assert CANONICAL_HARNESS in root
    assert CANONICAL_HARNESS in spec
    assert "`$SERENITY_HARNESS validate`" not in root + spec
    assert "old runtime" not in spec.lower()
    assert "Historical recovery points live on GitHub rather than in the runtime tree." in spec

    expected_modes = {
        "serenity-macro-event": "macro-event",
        "serenity-discovery": "discovery",
        "serenity-single-name": "single-name",
        "serenity-cohort": "cohort",
    }
    for skill, mode in expected_modes.items():
        text = (ROOT / ".claude" / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
        assert CANONICAL_CLI + mode in text
        assert '"$SERENITY_PYTHON" "$SERENITY_CLI" run start --help' in text
        assert "with `$SERENITY_CLI`" not in text


def test_codex_symlink_is_bundle_ready_without_a_duplicate_harness() -> None:
    codex = ROOT / ".codex"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    ignored = subprocess.run(["git", "check-ignore", ".codex"], cwd=ROOT, text=True, capture_output=True, check=False)

    assert codex.is_symlink()
    assert codex.readlink() == Path(".claude")
    assert "/.codex" not in gitignore.splitlines()
    assert ignored.returncode == 1
    assert "tracked `.codex -> .claude` symlink" in readme
    assert "without copying" in readme


def test_root_identity_is_generic_and_always_on_capabilities_are_compact() -> None:
    root = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    spec = (ROOT / ".claude" / "harness-spec.md").read_text(encoding="utf-8")
    help_result = subprocess.run([sys.executable, str(HARNESS), "validate", "--help"], cwd=ROOT, text=True, capture_output=True, check=False)

    for contract in (
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
    ):
        assert contract in root
    assert "Seongjin" not in root
    assert "the user" in root
    assert "cosplay or exact phrase imitation" in root
    assert "generic multi-user identity" in spec
    assert "Its generic multi-user identity names Harness of Serenity" in spec
    assert (help_result.returncode, help_result.stderr) == (0, "")
    for text in (root, spec, help_result.stdout):
        assert "Seongjin" not in text
        assert "성진" not in text
        assert "/Users/seongjin" not in text
    assert 'HARNESS_CREATOR_DIR="${CODEX_HOME:-$HOME/.codex}/skills/harness-creator"' in spec
    assert "HARNESS_CREATOR_DIR" in help_result.stdout


def test_source_tagged_method_contract_drives_each_workflow() -> None:
    root = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    spec = (ROOT / ".claude" / "harness-spec.md").read_text(encoding="utf-8")
    ledger = json.loads(METHOD_LEDGER.read_text(encoding="utf-8"))
    digest = json.loads(METHOD_DIGEST.read_text(encoding="utf-8"))
    synthesis = json.loads(METHOD_SYNTHESIS.read_text(encoding="utf-8"))
    report = json.loads(subprocess.run([sys.executable, str(HARNESS), "validate"], cwd=ROOT, text=True, capture_output=True, check=False).stdout)

    assert "active method contract is source-tagged" in root
    assert "`sourced`" in root and "`augmented`" in root
    assert "unverified" in root and "not a rule" in root
    assert len(ledger["claims"]) == 20
    assert {claim["provenance_tag"] for claim in ledger["claims"]} == {"sourced", "augmented"}
    assert digest["format"] == "serenity-method-candidate-digest/1"
    assert synthesis["final_claim_ledger"]["content_hash"] == ledger["content_hash"]
    assert "original jq // false-positive" in spec
    assert "read-only revalidation" in spec
    assert "single Sol final synthesis" in spec
    assert report["ok"] is True
    assert report["method_contract"] == {
        "ledger_content_hash": ledger["content_hash"],
        "sourced_claims": 12,
        "augmented_claims": 8,
    }

    expected_claims = {
        "serenity-macro-event": ("claim-01-screen-price-and-positioning-before-inference", "claim-06-test-catalyst-conversion-capacity", "aug-adaptive-evidence-not-decision-code"),
        "serenity-discovery": ("claim-02-validate-every-causal-hop", "claim-03-verify-identity-and-revenue-linkage", "aug-physical-chain-and-vehicle-contract"),
        "serenity-single-name": ("claim-07-evaluate-capital-by-per-share-conversion", "claim-09-use-milestone-falsifiers-not-price-alone", "aug-fact-referenced-lens-validity", "aug-immutable-action-lifecycle"),
        "serenity-cohort": ("claim-03-verify-identity-and-revenue-linkage", "claim-11-evaluate-process-with-complete-attribution", "aug-blind-method-and-evaluation-boundary"),
    }
    for skill, claim_ids in expected_claims.items():
        text = (ROOT / ".claude" / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
        for claim_id in claim_ids:
            assert claim_id in text


def test_candidate_cleanroom_gets_a_self_contained_method_interface_from_each_skill() -> None:
    essentials = {
        "serenity-macro-event": ("company disclosures", "demand, supply, pricing, financing, or only sentiment", "usable capacity", "falsifier"),
        "serenity-discovery": ("material intensity", "qualification", "substitutability", "no clean US-listed vehicle"),
        "serenity-single-name": ("adjusted net asset value", "per-share", "premium hurdle", "observable primary trigger", "Any non-null identifier conflict is unresolved identity", "`MONITOR` is not a substitute", "prepared remarks", "Q&A", "management claim", "hard operating observation", "disclosed", "corroborated", "inferred", "contradicted", "omission or evasion"),
        "serenity-cohort": ("common comparison question", "blind challenge", "evidence quality", "relative fit"),
    }
    shared_sections = ("Question frame", "Competing hypotheses", "Evidence sought", "Inference", "Action and falsifier", "Deliverable and hand-off")

    for skill, required in essentials.items():
        text = (ROOT / ".claude" / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
        assert len(text.splitlines()) >= 32
        for section in shared_sections + required:
            assert section in text
        assert "Method claims:" in text
        assert "fixed pipeline" not in text.lower()
        assert "hardcoded threshold" not in text.lower()


def test_discovery_keeps_structural_concentration_distinct_from_investability_and_single_name_limits_nfa() -> None:
    discovery = (ROOT / ".claude" / "skills" / "serenity-discovery" / "SKILL.md").read_text(encoding="utf-8")
    single_name = (ROOT / ".claude" / "skills" / "serenity-single-name" / "SKILL.md").read_text(encoding="utf-8")
    report = json.loads(subprocess.run([sys.executable, str(HARNESS), "validate"], cwd=ROOT, text=True, capture_output=True, check=False).stdout)

    assert "Determine structural concentration from the binding relationship and revenue linkage before testing investability." in discovery
    assert "Investability, the US-listed vehicle, and action are separate gates." in discovery
    assert "examples when raw evidence supports them; allow another mechanism" in discovery
    assert "Do not force every case through the same checklist." in discovery
    assert "Any non-null identifier conflict is unresolved identity" in single_name
    assert "`MONITOR` is not a substitute" in single_name
    assert "Use `NFA` only for actionable `RECOMMEND_NOW` or `ENTER_ON_TRIGGER` conclusions." in single_name
    assert report["ok"] is True


def test_discovery_does_not_promote_a_ticker_or_venue_into_direct_security_linkage() -> None:
    discovery = (ROOT / ".claude" / "skills" / "serenity-discovery" / "SKILL.md").read_text(encoding="utf-8")
    report = json.loads(subprocess.run([sys.executable, str(HARNESS), "validate"], cwd=ROOT, text=True, capture_output=True, check=False).stdout)

    assert "A ticker-like label or trading venue is not issuer/security identity or revenue linkage." in discovery
    assert "Never call a vehicle direct until identity binding is evidenced." in discovery
    assert "If the link is missing, preserve it as unresolved and choose `BLOCKED`, `MONITOR`, or `PASS` as the facts warrant." in discovery
    assert "Do not fabricate a direct-versus-indirect relation." in discovery
    assert report["ok"] is True


def test_lifecycle_text_and_help_match_the_stop_gate_contract(tmp_path: Path) -> None:
    root = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    spec = (ROOT / ".claude" / "harness-spec.md").read_text(encoding="utf-8")
    help_result = subprocess.run([sys.executable, str(HARNESS), "validate", "--help"], cwd=tmp_path, text=True, capture_output=True, check=False)

    assert "save and finalize a typed decision (including BLOCKED)" in root
    assert "abandon it with a recorded reason" in root
    assert "merely says BLOCKED has no lifecycle effect" in root
    assert "leave the answer explicitly BLOCKED before stopping" not in root
    assert "save and finalize a typed BLOCKED decision" in spec
    assert "abandon with a durable reason" in spec
    assert (help_result.returncode, help_result.stderr) == (0, "")
    assert "saying BLOCKED in assistant prose does not resolve an OPEN run" in help_result.stdout
    assert "save and finalize a typed BLOCKED decision or abandon it with a recorded reason" in help_result.stdout


def test_peer_blind_candidate_has_read_only_narrative_research_tools() -> None:
    agent = (ROOT / ".claude" / "agents" / "peer-blind-candidate.md").read_text(encoding="utf-8")
    spec = (ROOT / ".claude" / "harness-spec.md").read_text(encoding="utf-8")

    assert "tools: Read, Grep, Glob, Bash, WebSearch, WebFetch" in agent
    assert "current narrative sources" in agent
    assert "never use web results as numeric facts" in agent.lower()
    assert "WebSearch/WebFetch" in spec
    assert "typed evidence requests" in spec


def test_filings_agent_collects_official_issuer_narrative_without_deciding_the_thesis() -> None:
    agent = (ROOT / ".claude" / "agents" / "serenity-filings.md").read_text(encoding="utf-8")
    single_name = (ROOT / ".claude" / "skills" / "serenity-single-name" / "SKILL.md").read_text(encoding="utf-8")
    spec = (ROOT / ".claude" / "harness-spec.md").read_text(encoding="utf-8")

    assert "tools: Read, Grep, Glob, Bash, WebSearch, WebFetch" in agent
    for contract in (
        "official issuer-owned URL",
        "issuer-ir.document",
        "source discovery only",
        "prepared remarks",
        "Q&A",
        "management_claim",
        "hard_operating_observation",
        "relationship_status",
        "disclosed",
        "corroborated",
        "inferred",
        "contradicted",
        "omission_or_evasion",
        "cross_company_read_through_candidate",
        "never becomes the thesis or action",
    ):
        assert contract in agent
    assert "WebSearch/WebFetch" in spec
    assert "official issuer documents" in spec
    assert "issuer-ir.document" in spec
    assert "management claim" in single_name
    assert "hard operating observation" in single_name
    assert "Cross-company read-through remains an inference candidate" in single_name


def test_session_start_is_silent_when_local_health_is_green() -> None:
    payload = json.loads((FIXTURES / "session-start-healthy.json").read_text(encoding="utf-8"))
    payload["cwd"] = str(ROOT)

    code, stdout, stderr = _run_hook(SESSION_START, payload, cwd=ROOT)

    assert code == 0
    assert stdout == ""
    assert stderr == ""


def test_session_start_reports_local_degradation_without_blocking(tmp_path: Path) -> None:
    payload = {"hook_event_name": "SessionStart", "cwd": str(tmp_path), "source": "startup"}

    code, stdout, stderr = _run_hook(SESSION_START, payload, cwd=tmp_path)

    assert code == 0
    assert stderr == ""
    result = json.loads(stdout)
    assert result["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "local health is degraded" in result["hookSpecificOutput"]["additionalContext"]


def test_stop_is_silent_without_an_active_run(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "stop-inactive.json").read_text(encoding="utf-8"))
    payload["cwd"] = str(tmp_path)

    code, stdout, stderr = _run_hook(STOP, payload, cwd=tmp_path)

    assert (code, stdout, stderr) == (0, "", "")


def test_stop_blocks_a_content_hashed_open_run(tmp_path: Path) -> None:
    run_id = _write_open_run(tmp_path)
    payload = {"hook_event_name": "Stop", "cwd": str(tmp_path), "stop_hook_active": False, "last_assistant_message": "BLOCKED"}

    code, stdout, stderr = _run_hook(STOP, payload, cwd=tmp_path)

    assert code == 0
    assert stderr == ""
    assert json.loads(stdout) == {
        "decision": "block",
        "reason": f"An OPEN research run ({run_id}) remains active; its lifecycle is not resolved.",
    }


def test_stop_loop_guard_is_silent_even_for_a_corrupt_claimed_state(tmp_path: Path) -> None:
    (tmp_path / ".serenity").mkdir()
    (tmp_path / ".serenity" / "active-run.json").write_text("{not json", encoding="utf-8")
    payload = json.loads((FIXTURES / "stop-loop-guard.json").read_text(encoding="utf-8"))
    payload["cwd"] = str(tmp_path)

    code, stdout, stderr = _run_hook(STOP, payload, cwd=tmp_path)

    assert (code, stdout, stderr) == (0, "", "")


def test_stop_conservatively_blocks_a_corrupt_claimed_active_state(tmp_path: Path) -> None:
    (tmp_path / ".serenity").mkdir()
    (tmp_path / ".serenity" / "active-run.json").write_text("{not json", encoding="utf-8")
    payload = {"hook_event_name": "Stop", "cwd": str(tmp_path), "stop_hook_active": False}

    code, stdout, stderr = _run_hook(STOP, payload, cwd=tmp_path)

    assert code == 0
    assert stderr == ""
    result = json.loads(stdout)
    assert result["decision"] == "block"
    assert result["reason"].startswith("The claimed active research run cannot be verified:")
