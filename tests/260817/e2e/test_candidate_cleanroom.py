from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest
from jsonschema import Draft202012Validator

from serenity_core.candidate_cleanroom import CandidateCleanroomError, build_candidate_cleanroom, launch_candidate_cleanroom, revalidate_candidate_result


ROOT = Path(__file__).resolve().parents[3]


def strict_object_nodes(value: object) -> list[dict]:
    if isinstance(value, dict):
        nodes = [value] if value.get("type") == "object" and "properties" in value else []
        return nodes + [node for item in value.values() for node in strict_object_nodes(item)]
    if isinstance(value, list):
        return [node for item in value for node in strict_object_nodes(item)]
    return []


def test_candidate_result_schema_is_provider_strict_output_compatible() -> None:
    schema = json.loads((ROOT / "schemas/candidate-result-1.schema.json").read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    for node in strict_object_nodes(schema):
        assert set(node.get("required", [])) == set(node["properties"])
    assert "uniqueItems" not in json.dumps(schema)
    for node in [schema, *[item for item in schema["$defs"].values() if isinstance(item, dict)]]:
        for property_schema in node.get("properties", {}).values():
            if isinstance(property_schema, dict) and ("const" in property_schema or "enum" in property_schema):
                assert property_schema.get("type") == "string"


def write_json(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def candidate_case(*, family: str = "single-ticker") -> dict:
    return {
        "schema_id": "urn:serenity:schema:candidate-case:1",
        "case_id": "candidate-cleanroom-001",
        "family": family,
        "question": "ACME의 구조적 리스크와 매수 조건을 분석해줘.",
        "cutoff": "2026-08-17T00:00:00Z",
        "isolation_policy": {"network_mode": "recorded", "exclude_prior_outputs": True},
    }


def frozen_packet() -> dict:
    return {
        "facts": [{"fact_id": "fact-acme-fcf", "claim": "ACME has negative free cash flow.", "availability": "available"}],
        "evidence": [{"evidence_id": "evidence-acme-10q", "claim": "Frozen filing excerpt records negative free cash flow."}],
    }


def candidate_body() -> dict:
    return {
        "decision": {"stance": "mixed", "statement": "The packet supports a conditional watch, not a completed thesis.", "evidence_refs": ["evidence-acme-10q"]},
        "action": {"kind": "MONITOR", "statement": "Wait for free cash flow to improve.", "evidence_refs": ["evidence-acme-10q"]},
        "facts": [{"fact_id": "fact-acme-fcf", "claim": "ACME has negative free cash flow.", "evidence_refs": ["evidence-acme-10q"]}],
        "inferences": [{"inference_id": "inference-acme-watch", "claim": "Funding risk warrants a monitored entry condition.", "evidence_refs": ["evidence-acme-10q"]}],
        "trigger": {"statement": "Free cash flow turns positive.", "evidence_refs": ["evidence-acme-10q"]},
        "bear_case": {"statement": "Cash burn persists and forces dilution.", "evidence_refs": ["evidence-acme-10q"]},
        "falsifiers": [{"statement": "The financing risk changes if cash flow improves.", "evidence_refs": ["evidence-acme-10q"]}],
        "evidence_refs": ["evidence-acme-10q"],
        "user_artifact": {"locale": "ko-KR", "markdown": "TLDR: 지금은 추적. FCF가 개선되면 다시 보자. NFI"},
    }


def completed(*, stdout: str = "") -> object:
    return type("Completed", (), {"returncode": 0, "stdout": stdout, "stderr": ""})()


def test_build_candidate_cleanroom_copies_only_the_hashed_harness_snapshot_and_candidate_inputs(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    harness_root = tmp_path / "harness"
    (harness_root / ".claude/skills/serenity-cohort").mkdir(parents=True)
    (harness_root / ".claude/skills/serenity-discovery").mkdir(parents=True)
    (harness_root / ".claude/skills/serenity-macro-event").mkdir(parents=True)
    (harness_root / ".claude/skills/serenity-single-name").mkdir(parents=True)
    (harness_root / ".claude/agents").mkdir(parents=True)
    (harness_root / ".claude/hooks").mkdir(parents=True)
    (harness_root / "CLAUDE.md").write_text("shared harness instruction", encoding="utf-8")
    (harness_root / "AGENTS.md").symlink_to("CLAUDE.md")
    (harness_root / ".codex").symlink_to(".claude")
    (harness_root / ".claude/settings.json").write_text("{}", encoding="utf-8")
    (harness_root / ".claude/harness-spec.md").write_text("spec", encoding="utf-8")
    for name in ("peer-blind-candidate.md", "serenity-filings.md"):
        (harness_root / ".claude/agents" / name).write_text(name, encoding="utf-8")
    for name in ("serenity-cohort", "serenity-discovery", "serenity-macro-event", "serenity-single-name"):
        (harness_root / ".claude/skills" / name / "SKILL.md").write_text(name, encoding="utf-8")
    for name in ("lifecycle_gate.py", "session_health.py"):
        (harness_root / ".claude/hooks" / name).write_text(name, encoding="utf-8")
    (harness_root / "data").mkdir()
    (harness_root / "data/forbidden.db").write_text("must not copy", encoding="utf-8")
    inputs = tmp_path / "inputs"
    inputs.mkdir()

    package = build_candidate_cleanroom(
        candidate_case_path=write_json(inputs / "candidate-case.json", candidate_case()),
        frozen_packet_path=write_json(inputs / "frozen-packet.json", frozen_packet()),
        candidate_result_schema_path=ROOT / "schemas/candidate-result-1.schema.json",
        harness_root=harness_root,
        cleanroom_root=tmp_path / "outside-candidate-cleanrooms",
        repo_root=repo_root,
    )

    names = {path.relative_to(package.case_dir).as_posix() for path in package.case_dir.rglob("*") if path.is_file() or path.is_symlink()}
    assert names == {
        "candidate-case.json",
        "frozen-packet.json",
        "candidate-result.schema.json",
        "package-manifest.json",
        "harness/CLAUDE.md",
        "harness/AGENTS.md",
        "harness/.codex",
        "harness/.claude/settings.json",
        "harness/.claude/harness-spec.md",
        "harness/.claude/agents/peer-blind-candidate.md",
        "harness/.claude/agents/serenity-filings.md",
        "harness/.claude/skills/serenity-cohort/SKILL.md",
        "harness/.claude/skills/serenity-discovery/SKILL.md",
        "harness/.claude/skills/serenity-macro-event/SKILL.md",
        "harness/.claude/skills/serenity-single-name/SKILL.md",
        "harness/.claude/hooks/lifecycle_gate.py",
        "harness/.claude/hooks/session_health.py",
    }
    agents = package.case_dir / "harness/AGENTS.md"
    assert agents.is_symlink()
    assert agents.readlink() == Path("CLAUDE.md")
    assert (package.case_dir / "harness/.codex").readlink() == Path(".claude")
    assert "data/forbidden.db" not in names
    assert set(package.package_hashes) == names - {"package-manifest.json"}


def test_launch_candidate_cleanroom_envelopes_a_strict_model_body_with_trusted_receipts(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    package = build_candidate_cleanroom(
        candidate_case_path=write_json(inputs / "candidate-case.json", candidate_case()),
        frozen_packet_path=write_json(inputs / "frozen-packet.json", frozen_packet()),
        candidate_result_schema_path=ROOT / "schemas/candidate-result-1.schema.json",
        harness_root=ROOT,
        cleanroom_root=tmp_path / "outside-candidate-cleanrooms",
        repo_root=repo_root,
    )
    captured: dict[str, object] = {}

    def runner(argv: list[str], **kwargs: object) -> object:
        captured["argv"] = argv
        Path(str(argv[argv.index("--output-last-message") + 1])).write_text(json.dumps(candidate_body()), encoding="utf-8")
        return completed()

    launched = launch_candidate_cleanroom(
        package,
        results_root=tmp_path / "outside-candidate-results",
        repo_root=repo_root,
        runner=runner,
        platform_name="Linux",
        isolation_mode="logical-audited",
    )

    argv = captured["argv"]
    assert "--search" not in argv
    assert argv[argv.index("--model") + 1] == "gpt-5.6-terra"
    assert Path(str(argv[argv.index("--output-schema") + 1])).name == "candidate-body.schema.json"
    assert Path(str(argv[argv.index("--output-schema") + 1])) != package.case_dir / "candidate-result.schema.json"
    prompt = str(argv[-1])
    assert candidate_case()["question"] in prompt
    assert json.dumps(frozen_packet(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) in prompt
    assert "expected_invariants" not in prompt
    assert "shared-harness-instruction integration" in prompt
    assert "top-level evidence[].evidence_id values" in prompt
    result = json.loads(launched.result_path.read_text(encoding="utf-8"))
    assert result["schema_id"] == "urn:serenity:schema:candidate-result:1"
    assert result["case_id"] == package.case_id
    assert result["model"] == "gpt-5.6-terra"
    assert result["packet_sha256"] == package.package_hashes["frozen-packet.json"]
    assert result["loaded_instruction_paths"] == ["CLAUDE.md", ".claude/skills/serenity-single-name/SKILL.md"]
    assert result["harness_hashes"] == [
        {"path": path, "sha256": package.harness_hashes[path]} for path in sorted(package.harness_hashes)
    ]
    assert len(result["canonical_sha256"]) == 64
    assert launched.record_path.parent == launched.result_path.parent


@pytest.mark.parametrize(
    ("family", "expected_paths"),
    [
        ("discovery", ["CLAUDE.md", ".claude/skills/serenity-discovery/SKILL.md"]),
        ("single-ticker", ["CLAUDE.md", ".claude/skills/serenity-single-name/SKILL.md"]),
        ("degraded-data", ["CLAUDE.md", ".claude/skills/serenity-single-name/SKILL.md"]),
        ("physical-ai", ["CLAUDE.md", ".claude/skills/serenity-discovery/SKILL.md"]),
        ("near-miss", ["CLAUDE.md", ".claude/skills/serenity-discovery/SKILL.md"]),
        ("displacement-fear", ["CLAUDE.md", ".claude/skills/serenity-macro-event/SKILL.md", ".claude/skills/serenity-single-name/SKILL.md"]),
    ],
)
def test_candidate_launch_loads_only_the_family_routed_harness_interfaces(tmp_path: Path, family: str, expected_paths: list[str]) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    package = build_candidate_cleanroom(
        candidate_case_path=write_json(inputs / "candidate-case.json", candidate_case(family=family)),
        frozen_packet_path=write_json(inputs / "frozen-packet.json", frozen_packet()),
        candidate_result_schema_path=ROOT / "schemas/candidate-result-1.schema.json",
        harness_root=ROOT,
        cleanroom_root=tmp_path / "outside-candidate-cleanrooms",
        repo_root=repo_root,
    )
    captured: dict[str, object] = {}

    def runner(argv: list[str], **kwargs: object) -> object:
        captured["prompt"] = argv[-1]
        Path(str(argv[argv.index("--output-last-message") + 1])).write_text(json.dumps(candidate_body()), encoding="utf-8")
        return completed()

    launched = launch_candidate_cleanroom(
        package,
        results_root=tmp_path / "outside-candidate-results",
        repo_root=repo_root,
        runner=runner,
        platform_name="Linux",
        isolation_mode="logical-audited",
    )

    record = json.loads(launched.record_path.read_text(encoding="utf-8"))
    result = json.loads(launched.result_path.read_text(encoding="utf-8"))
    assert record["loaded_instruction_paths"] == expected_paths
    assert result["loaded_instruction_paths"] == expected_paths
    prompt = str(captured["prompt"])
    assert '"path":".claude/harness-spec.md"' not in prompt
    assert '"path":".claude/agents/peer-blind-candidate.md"' not in prompt
    assert '"path":".claude/hooks/lifecycle_gate.py"' not in prompt
    for path in expected_paths:
        assert f'"path":"{path}"' in prompt


def test_revalidate_candidate_result_rejects_unknown_evidence_tampered_receipts_and_non_action_nfa(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    package = build_candidate_cleanroom(
        candidate_case_path=write_json(inputs / "candidate-case.json", candidate_case()),
        frozen_packet_path=write_json(inputs / "frozen-packet.json", frozen_packet()),
        candidate_result_schema_path=ROOT / "schemas/candidate-result-1.schema.json",
        harness_root=ROOT,
        cleanroom_root=tmp_path / "outside-candidate-cleanrooms",
        repo_root=repo_root,
    )
    result_path = tmp_path / "candidate-result.json"
    result = {
        "schema_id": "urn:serenity:schema:candidate-result:1",
        "result_id": "candidate-result-001",
        "case_id": package.case_id,
        "run_id": "candidate-run-001",
        "model": "gpt-5.6-terra",
        "capability": "shared-harness-instruction-integration",
        "harness_hashes": [{"path": path, "sha256": package.harness_hashes[path]} for path in sorted(package.harness_hashes)],
        "loaded_instruction_paths": ["CLAUDE.md", ".claude/skills/serenity-single-name/SKILL.md"],
        "packet_sha256": package.package_hashes["frozen-packet.json"],
        **candidate_body(),
        "canonical_sha256": "0" * 64,
    }
    result_path.write_text(json.dumps(result), encoding="utf-8")

    with pytest.raises(CandidateCleanroomError, match="canonical hash"):
        revalidate_candidate_result(result_path, package=package, run_id="candidate-run-001", model="gpt-5.6-terra")

    result["facts"][0]["evidence_refs"] = ["unknown-evidence"]
    result["canonical_sha256"] = canonical_hash_without_receipt(result)
    result_path.write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(CandidateCleanroomError, match="unknown evidence"):
        revalidate_candidate_result(result_path, package=package, run_id="candidate-run-001", model="gpt-5.6-terra")

    result["facts"][0]["evidence_refs"] = ["evidence-acme-10q"]
    result["user_artifact"]["markdown"] += " NFA"
    result["canonical_sha256"] = canonical_hash_without_receipt(result)
    result_path.write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(CandidateCleanroomError, match="NFA is allowed only"):
        revalidate_candidate_result(result_path, package=package, run_id="candidate-run-001", model="gpt-5.6-terra")


def test_revalidate_candidate_result_requires_blocked_for_a_single_ticker_identity_conflict(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    packet = {
        "evidence": [
            {
                "evidence_id": "evidence-acme-10q",
                "artifact": {
                    "identity_bindings": {"ticker": "FIXT"},
                    "value": {
                        "observations": [
                            {"subject": "FICT", "predicate": "maps_to_cik", "object": "0000000001"},
                            {"subject": "Fixture Inc.", "predicate": "reported_cash", "measure": {"amount": 100, "unit": "USDm"}},
                        ]
                    },
                },
            }
        ]
    }
    package = build_candidate_cleanroom(
        candidate_case_path=write_json(inputs / "candidate-case.json", candidate_case()),
        frozen_packet_path=write_json(inputs / "frozen-packet.json", packet),
        candidate_result_schema_path=ROOT / "schemas/candidate-result-1.schema.json",
        harness_root=ROOT,
        cleanroom_root=tmp_path / "outside-candidate-cleanrooms",
        repo_root=repo_root,
    )
    result = {
        "schema_id": "urn:serenity:schema:candidate-result:1",
        "result_id": "candidate-result-001",
        "case_id": package.case_id,
        "run_id": "candidate-run-001",
        "model": "gpt-5.6-terra",
        "capability": "shared-harness-instruction-integration",
        "harness_hashes": [{"path": path, "sha256": package.harness_hashes[path]} for path in sorted(package.harness_hashes)],
        "loaded_instruction_paths": ["CLAUDE.md", ".claude/skills/serenity-single-name/SKILL.md"],
        "packet_sha256": package.package_hashes["frozen-packet.json"],
        **candidate_body(),
        "canonical_sha256": "",
    }
    result["canonical_sha256"] = canonical_hash_without_receipt(result)
    result_path = tmp_path / "candidate-result.json"
    result_path.write_text(json.dumps(result), encoding="utf-8")

    with pytest.raises(CandidateCleanroomError, match="identity conflict requires BLOCKED"):
        revalidate_candidate_result(result_path, package=package, run_id="candidate-run-001", model="gpt-5.6-terra")

    result["action"] = {
        "kind": "BLOCKED",
        "statement": "The conflicting ticker identifiers must be reconciled before using the financial facts.",
        "evidence_refs": ["evidence-acme-10q"],
    }
    result["canonical_sha256"] = canonical_hash_without_receipt(result)
    result_path.write_text(json.dumps(result), encoding="utf-8")

    validated = revalidate_candidate_result(result_path, package=package, run_id="candidate-run-001", model="gpt-5.6-terra")
    assert validated["action"]["kind"] == "BLOCKED"


def test_launch_candidate_cleanroom_reports_invalid_strict_model_body_as_typed_output_error(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    package = build_candidate_cleanroom(
        candidate_case_path=write_json(inputs / "candidate-case.json", candidate_case()),
        frozen_packet_path=write_json(inputs / "frozen-packet.json", frozen_packet()),
        candidate_result_schema_path=ROOT / "schemas/candidate-result-1.schema.json",
        harness_root=ROOT,
        cleanroom_root=tmp_path / "outside-candidate-cleanrooms",
        repo_root=repo_root,
    )

    def invalid_body_runner(argv: list[str], **kwargs: object) -> object:
        Path(str(argv[argv.index("--output-last-message") + 1])).write_text("{}", encoding="utf-8")
        return completed()

    with pytest.raises(CandidateCleanroomError, match="candidate model output is invalid") as error:
        launch_candidate_cleanroom(
            package,
            results_root=tmp_path / "outside-candidate-results",
            repo_root=repo_root,
            runner=invalid_body_runner,
            platform_name="Linux",
            isolation_mode="logical-audited",
        )
    assert error.value.code == "invalid_candidate_output"


def test_revalidate_candidate_result_rejects_a_nested_non_evidence_id_even_when_its_packet_contains_it(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    packet = {**frozen_packet(), "metadata": {"request_id": "request-not-evidence-001"}}
    package = build_candidate_cleanroom(
        candidate_case_path=write_json(inputs / "candidate-case.json", candidate_case()),
        frozen_packet_path=write_json(inputs / "frozen-packet.json", packet),
        candidate_result_schema_path=ROOT / "schemas/candidate-result-1.schema.json",
        harness_root=ROOT,
        cleanroom_root=tmp_path / "outside-candidate-cleanrooms",
        repo_root=repo_root,
    )
    result = {
        "schema_id": "urn:serenity:schema:candidate-result:1",
        "result_id": "candidate-result-001",
        "case_id": package.case_id,
        "run_id": "candidate-run-001",
        "model": "gpt-5.6-terra",
        "capability": "shared-harness-instruction-integration",
        "harness_hashes": [{"path": path, "sha256": package.harness_hashes[path]} for path in sorted(package.harness_hashes)],
        "loaded_instruction_paths": ["CLAUDE.md", ".claude/skills/serenity-single-name/SKILL.md"],
        "packet_sha256": package.package_hashes["frozen-packet.json"],
        **candidate_body(),
        "canonical_sha256": "",
    }
    result["inferences"][0]["evidence_refs"] = ["request-not-evidence-001"]
    result["canonical_sha256"] = canonical_hash_without_receipt(result)
    result_path = tmp_path / "candidate-result.json"
    result_path.write_text(json.dumps(result), encoding="utf-8")

    with pytest.raises(CandidateCleanroomError, match="unknown evidence"):
        revalidate_candidate_result(result_path, package=package, run_id="candidate-run-001", model="gpt-5.6-terra")


def test_launch_candidate_cleanroom_does_not_inherit_provider_secrets_into_child_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    package = build_candidate_cleanroom(
        candidate_case_path=write_json(inputs / "candidate-case.json", candidate_case()),
        frozen_packet_path=write_json(inputs / "frozen-packet.json", frozen_packet()),
        candidate_result_schema_path=ROOT / "schemas/candidate-result-1.schema.json",
        harness_root=ROOT,
        cleanroom_root=tmp_path / "outside-candidate-cleanrooms",
        repo_root=repo_root,
    )
    monkeypatch.setenv("FRED_API_KEY", "candidate-cleanroom-test-secret")
    captured: dict[str, object] = {}

    def runner(argv: list[str], **kwargs: object) -> object:
        captured["argv"] = argv
        captured["env"] = kwargs["env"]
        Path(str(argv[argv.index("--output-last-message") + 1])).write_text(json.dumps(candidate_body()), encoding="utf-8")
        return completed()

    launched = launch_candidate_cleanroom(
        package,
        results_root=tmp_path / "outside-candidate-results",
        repo_root=repo_root,
        runner=runner,
        platform_name="Linux",
        isolation_mode="logical-audited",
    )

    assert "FRED_API_KEY" not in captured["env"]
    assert "candidate-cleanroom-test-secret" not in json.dumps(captured["argv"])
    assert "candidate-cleanroom-test-secret" not in launched.record_path.read_text(encoding="utf-8")


@pytest.mark.skipif(__import__("platform").system() != "Darwin", reason="candidate OS boundary uses macOS seatbelt")
def test_macos_candidate_launch_allows_only_the_resolved_codex_runtime_helpers(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    package = build_candidate_cleanroom(
        candidate_case_path=write_json(inputs / "candidate-case.json", candidate_case()),
        frozen_packet_path=write_json(inputs / "frozen-packet.json", frozen_packet()),
        candidate_result_schema_path=ROOT / "schemas/candidate-result-1.schema.json",
        harness_root=ROOT,
        cleanroom_root=tmp_path / "outside-candidate-cleanrooms",
        repo_root=repo_root,
    )
    captured: dict[str, object] = {}

    def runner(argv: list[str], **kwargs: object) -> object:
        captured["argv"] = argv
        Path(str(argv[argv.index("--output-last-message") + 1])).write_text(json.dumps(candidate_body()), encoding="utf-8")
        return completed()

    launch_candidate_cleanroom(
        package,
        results_root=tmp_path / "outside-candidate-results",
        repo_root=repo_root,
        runner=runner,
        platform_name="Darwin",
        isolation_mode="os-enforced",
    )

    profile = str(captured["argv"][2])
    executable = Path(str(captured["argv"][3])).resolve()
    helper = executable.with_name("codex-code-mode-host")
    assert f'(allow process-exec (literal "{helper}"))' in profile
    assert "(deny process-exec)" in profile
    run_dir = Path(str(captured["argv"][captured["argv"].index("--output-last-message") + 1])).parent
    assert f'(allow file-read-metadata (literal "{run_dir}"))' in profile


def canonical_hash_without_receipt(result: dict) -> str:
    canonical = {key: value for key, value in result.items() if key != "canonical_sha256"}
    return __import__("hashlib").sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
