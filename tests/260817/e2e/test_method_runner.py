from __future__ import annotations

import errno
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from serenity_core.method_runner import MethodRunnerError, build_method_case, build_method_synthesis_case, launch_method_case, launch_method_synthesis, macos_method_seatbelt_profile, resolve_codex_executable, revalidate_method_case, revalidate_method_synthesis_result, run_batch_manifest


def canonical_hash(value: dict) -> str:
    return hashlib.sha256(json.dumps({key: item for key, item in value.items() if key != "content_hash"}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write_json(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def packet(packet_id: str = "packet-001") -> dict:
    value = {"format": "serenity-method-blind-packet/1", "leak_policy": {"excluded_fields": ["answer_key", "created_at", "date", "ticker"], "redactions": {"date": "[DATE]", "ticker": "[TICKER]"}}, "source_index_hash": "a" * 64, "chunks": [{"chunk_id": "chunk-one-0001", "source_refs": ["source-one"], "source_hash": "b" * 64, "kind": "text", "text": "Demand changed after a supplier constraint."}, {"chunk_id": "chunk-two-0002", "source_refs": ["source-two"], "source_hash": "c" * 64, "kind": "media", "text": "Management described an unverified catalyst."}]}
    value["content_hash"] = canonical_hash(value)
    return value


def output(packet_value: dict, *, packet_sha256: str, packet_id: str = "packet-001", wrong_chunk: bool = False) -> dict:
    chunk_ids = [chunk["chunk_id"] for chunk in packet_value["chunks"]]
    if wrong_chunk:
        chunk_ids[1] = "chunk-wrong-9999"
    return {"schema_id": "urn:serenity:schema:method-coding-output:1", "packet_id": packet_id, "packet_sha256": packet_sha256, "dispositions": [{"chunk_id": chunk_ids[0], "disposition": "coded", "coding": {"trigger": "constraint", "evidence_sought": "supplier disclosure", "inference": "supply may limit sales", "action_horizon": {"action": "monitor", "horizon": "next filing"}, "falsifier": "capacity expands", "codes": [{"axis": "causal_hop", "label": "constraint", "rationale": "links input to sales"}]}, "uncertainty_notes": ["quantity is absent"], "contradiction_notes": []}, {"chunk_id": chunk_ids[1], "disposition": "no_reusable_move", "coding": None, "uncertainty_notes": ["no reusable causal sequence"], "contradiction_notes": ["catalyst is unverified"]}]}


def build(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    value = packet()
    return repo_root, value, build_method_case(packet_path=write_json(inputs / "packet-001.json", value), output_schema_path=Path(__file__).resolve().parents[3] / "config/method-coding-output.schema.json", case_root=tmp_path / "outside-cases", repo_root=repo_root)


def write_manifest(packet_dir: Path, packet_ids: list[str]) -> Path:
    records = []
    for packet_id in packet_ids:
        value = packet(packet_id)
        path = write_json(packet_dir / f"{packet_id}.json", value)
        records.append({"packet_id": packet_id, "path": path.name, "content_hash": value["content_hash"]})
    manifest = {"format": "serenity-method-packet-manifest/1", "packets": records}
    manifest["content_hash"] = canonical_hash(manifest)
    return write_json(packet_dir / "packet-manifest.json", manifest)


def candidate_digest() -> dict:
    value = {
        "format": "serenity-method-candidate-digest/1",
        "packet_manifest_content_hash": "d" * 64,
        "packet_results": [],
        "coverage": {"packets": 1, "chunks": 2, "coded_chunks": 2, "no_reusable_move_chunks": 0, "all_disposition_coverage_hash": "e" * 64},
        "bounded_summary": {
            "axis_label_frequency": [{"axis": "causal_hop", "entries": [{"axis": "causal_hop", "label": "constraint", "representatives": [{"unit_id": "unit-one", "source_refs": ["chunk-one"], "semantic_content": {"matching_code": {"axis": "causal_hop", "label": "constraint"}}}]}]}],
            "counterexample_refs": {"entries": [{"unit_id": "unit-two", "counterexample": {"unit_id": "unit-two"}}]},
            "contradiction_refs": {"entries": [{"unit_id": "unit-two"}]},
            "uncertainty_refs": {"entries": [{"unit_id": "unit-one"}]},
        },
        "input_hashes": {"codebook": "f" * 64, "coding": "1" * 64, "claim_ledger": "2" * 64},
    }
    value["content_hash"] = canonical_hash(value)
    return value


def synthesis_output(digest: dict, *, digest_sha256: str) -> dict:
    return {
        "schema_id": "urn:serenity:schema:method-claim-synthesis:1",
        "format": "serenity-method-claim-synthesis/1",
        "candidate_digest_content_hash": digest["content_hash"],
        "candidate_digest_sha256": digest_sha256,
        "claims": [{"claim_id": "claim-one", "claim": "A constraint can be a reusable candidate.", "provenance_tag": "sourced", "shown_unit_refs": ["unit-one"], "shown_code_refs": [{"axis": "causal_hop", "label": "constraint"}], "counterexample_refs": ["unit-two"], "counterexample_search_scope": "shown candidate digest", "counterexample_status": "found", "why": "The shown unit explicitly links the constraint to an inference.", "uncertainty_notes": ["The digest is bounded."], "contradiction_notes": ["A shown counterexample remains."]}],
    }


def test_builds_a_single_packet_case_without_current_doctrine(tmp_path: Path) -> None:
    repo_root, _, package = build(tmp_path)
    assert package.case_dir.is_relative_to(tmp_path / "outside-cases")
    assert not package.case_dir.is_relative_to(repo_root)
    assert {entry.name for entry in package.case_dir.iterdir()} == {"packet-001.json", "method-coding-output.schema.json", "prompt.json", "package-manifest.json"}
    prompt = json.loads((package.case_dir / "prompt.json").read_text(encoding="utf-8"))["prompt"].casefold()
    assert "current doctrine" not in prompt
    assert "answer key" not in prompt
    assert "first read ./packet-001.json" in prompt
    metadata = json.loads((package.case_dir / "prompt.json").read_text(encoding="utf-8"))
    assert metadata["chunk_count"] == 2
    assert metadata["chunk_ids"] == ["chunk-one-0001", "chunk-two-0002"]
    assert revalidate_method_case(package) == package.package_hashes


def test_build_normalizes_a_symlinked_case_root_before_passing_it_to_codex(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    target_root = tmp_path / "outside-cases"
    target_root.mkdir()
    alias_root = tmp_path / "cases-alias"
    alias_root.symlink_to(target_root, target_is_directory=True)

    package = build_method_case(packet_path=write_json(inputs / "packet-001.json", packet()), output_schema_path=Path(__file__).resolve().parents[3] / "config/method-coding-output.schema.json", case_root=alias_root, repo_root=repo_root)

    assert package.case_dir.parent == target_root.resolve()


def test_synthesis_launch_uses_one_hash_bound_digest_and_the_final_sol_cleanroom(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    digest_path = write_json(inputs / "candidate-digest.json", candidate_digest())
    case = build_method_synthesis_case(candidate_digest_path=digest_path, output_schema_path=Path(__file__).resolve().parents[3] / "config/method-claim-synthesis.schema.json", case_root=tmp_path / "outside-cases", repo_root=repo_root)
    assert {entry.name for entry in case.case_dir.iterdir()} == {"candidate-digest.json", "method-claim-synthesis.schema.json", "prompt.json", "package-manifest.json"}
    prompt = json.loads((case.case_dir / "prompt.json").read_text())["prompt"].casefold()
    for requirement in ("omitted semantics", "reusable principles and interfaces", "ticker, name, or example-specific", "fixed thresholds", "voice imitation", "portfolio sizing", "frozen pipeline rail", "trigger → evidence sought → inference → action/horizon → falsifier", "thin evidence", "frequency or representativeness", "contradictions and counterexamples", "dense and nonduplicative", "materially supported dimensions"):
        assert requirement in prompt
    captured: dict[str, object] = {}

    def runner(argv: list[str], **kwargs: object) -> object:
        captured["argv"] = argv
        Path(str(argv[argv.index("--output-last-message") + 1])).write_text(json.dumps(synthesis_output(candidate_digest(), digest_sha256=case.candidate_digest_sha256)), encoding="utf-8")
        transcript = json.dumps({"type": "item.started", "item": {"id": "digest-read", "type": "command_execution", "command": '/bin/zsh -lc "jq -C . ./candidate-digest.json"', "aggregated_output": "", "exit_code": None, "status": "in_progress"}}) + "\n"
        transcript += json.dumps({"type": "item.completed", "item": {"id": "digest-read", "type": "command_execution", "command": '/bin/zsh -lc "jq -C . ./candidate-digest.json"', "aggregated_output": "digest content", "exit_code": 0, "status": "completed"}}) + "\n"
        transcript += json.dumps({"type": "item.completed", "item": {"id": "jq-alternative", "type": "command_execution", "command": '/bin/zsh -lc "jq -r \' .bounded_summary.counterexamples // empty\' ./candidate-digest.json"', "aggregated_output": "", "exit_code": 0, "status": "completed"}}) + "\n"
        return type("Completed", (), {"returncode": 0, "stdout": transcript, "stderr": ""})()

    launch = launch_method_synthesis(case, results_root=tmp_path / "outside-results", repo_root=repo_root, runner=runner, platform_name="Darwin")

    argv = captured["argv"]
    assert argv[0] == "sandbox-exec"
    assert f'(deny file-read* (subpath "{repo_root}"))' in argv[2]
    codex_argv = argv[3:]
    assert codex_argv[:8] == [str(resolve_codex_executable().resolved_path), "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check", "--sandbox", "danger-full-access"]
    assert "gpt-5.6-sol" in codex_argv
    assert not any(flag in codex_argv for flag in ("--search", "--add-dir", "resume"))
    record = json.loads(launch.record_path.read_text())
    assert record["role"] == "final_method_synthesizer"
    assert record["model"] == "gpt-5.6-sol"
    assert record["single_final_synthesis"] is True
    assert record["candidate_digest_content_hash"] == candidate_digest()["content_hash"]
    assert record["transcript_audit"] == {"forbidden_read_events": 0, "packet_read_events": 2, "tool_events": 2}
    revalidated = revalidate_method_synthesis_result(case_dir=case.case_dir, result_dir=launch.record_path.parent, repo_root=repo_root)
    assert revalidated["status"] == "valid"
    assert revalidated["output_sha256"] == record["output_sha256"]


def test_synthesis_rejects_claim_refs_not_shown_by_the_candidate_digest(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    digest_path = write_json(inputs / "candidate-digest.json", candidate_digest())
    case = build_method_synthesis_case(candidate_digest_path=digest_path, output_schema_path=Path(__file__).resolve().parents[3] / "config/method-claim-synthesis.schema.json", case_root=tmp_path / "outside-cases", repo_root=repo_root)

    def runner(argv: list[str], **kwargs: object) -> object:
        result = synthesis_output(candidate_digest(), digest_sha256=case.candidate_digest_sha256)
        result["claims"][0]["shown_unit_refs"] = ["unit-not-shown"]
        Path(str(argv[argv.index("--output-last-message") + 1])).write_text(json.dumps(result), encoding="utf-8")
        transcript = json.dumps({"type": "item.completed", "item": {"id": "digest-read", "type": "command_execution", "command": '/bin/zsh -lc "cat ./candidate-digest.json"', "exit_code": 0, "status": "completed"}}) + "\n"
        return type("Completed", (), {"returncode": 0, "stdout": transcript, "stderr": ""})()

    with pytest.raises(MethodRunnerError, match="shown by the candidate digest"):
        launch_method_synthesis(case, results_root=tmp_path / "outside-results", repo_root=repo_root, runner=runner, platform_name="Linux")


def test_synthesis_rejects_a_non_digest_command_even_after_a_successful_digest_read(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    digest_path = write_json(inputs / "candidate-digest.json", candidate_digest())
    case = build_method_synthesis_case(candidate_digest_path=digest_path, output_schema_path=Path(__file__).resolve().parents[3] / "config/method-claim-synthesis.schema.json", case_root=tmp_path / "outside-cases", repo_root=repo_root)

    def runner(argv: list[str], **kwargs: object) -> object:
        Path(str(argv[argv.index("--output-last-message") + 1])).write_text(json.dumps(synthesis_output(candidate_digest(), digest_sha256=case.candidate_digest_sha256)), encoding="utf-8")
        transcript = json.dumps({"type": "item.completed", "item": {"id": "digest-read", "type": "command_execution", "command": '/bin/zsh -lc "cat ./candidate-digest.json"', "exit_code": 0, "status": "completed"}}) + "\n"
        transcript += json.dumps({"type": "item.completed", "item": {"id": "outside-copy", "type": "command_execution", "command": "/bin/cp /tmp/old-result.json ./copy.json", "exit_code": 0, "status": "completed"}}) + "\n"
        return type("Completed", (), {"returncode": 0, "stdout": transcript, "stderr": ""})()

    with pytest.raises(MethodRunnerError, match="outside the candidate digest evidence boundary"):
        launch_method_synthesis(case, results_root=tmp_path / "outside-results", repo_root=repo_root, runner=runner, platform_name="Linux")


def test_launch_validates_exact_coverage_and_exact_codex_argv(tmp_path: Path) -> None:
    repo_root, packet_value, package = build(tmp_path)
    captured: dict[str, object] = {}

    def runner(argv: list[str], **kwargs: object) -> object:
        captured["argv"] = argv
        Path(str(argv[argv.index("--output-last-message") + 1])).write_text(json.dumps(output(packet_value, packet_sha256=package.package_hashes["packet-001.json"])), encoding="utf-8")
        return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    launch = launch_method_case(package, results_root=tmp_path / "outside-results", repo_root=repo_root, runner=runner, platform_name="Linux")
    argv = captured["argv"]
    assert argv == [str(resolve_codex_executable().resolved_path), "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check", "--sandbox", "read-only", "--cd", str(package.case_dir), "--model", "gpt-5.6-terra", "--output-schema", str(package.case_dir / "method-coding-output.schema.json"), "--json", "--output-last-message", str(launch.model_output_path), json.loads((package.case_dir / "prompt.json").read_text())["prompt"]]
    assert not any(flag in argv for flag in ("--search", "--add-dir", "resume"))
    record = json.loads(launch.record_path.read_text())
    assert record["status"] == "completed"
    assert record["role"] == "blind_open_coder"
    assert record["requested_cli"] == "codex"
    assert record["resolved_cli_path"] == argv[0]
    assert record["output_sha256"] == hashlib.sha256(launch.model_output_path.read_bytes()).hexdigest()


def test_macos_profile_denies_repo_but_allows_case_and_results(tmp_path: Path) -> None:
    repo_root, _, package = build(tmp_path)
    captured: dict[str, object] = {}

    def denied(argv: list[str], **kwargs: object) -> object:
        captured["argv"] = argv
        raise PermissionError(errno.EPERM, "Operation not permitted", repo_root / "data")

    with pytest.raises(MethodRunnerError, match="sandbox denied"):
        launch_method_case(package, results_root=tmp_path / "outside-results", repo_root=repo_root, runner=denied, platform_name="Darwin")
    profile = str(captured["argv"][2])
    assert "(allow default)" in profile
    assert f'(deny file-read* (subpath "{repo_root}"))' in profile
    assert f'(deny file-write* (subpath "{repo_root}"))' in profile


def test_macos_launch_uses_resolved_codex_path_and_allows_symlink_target(tmp_path: Path) -> None:
    repo_root, packet_value, package = build(tmp_path)
    launcher_dir = tmp_path / "launcher-bin"
    target_dir = tmp_path / "standalone-bin"
    launcher_dir.mkdir()
    target_dir.mkdir()
    target = target_dir / "codex"
    target.write_text("#!/bin/sh\n", encoding="utf-8")
    target.chmod(0o755)
    launcher = launcher_dir / "codex"
    launcher.symlink_to(target)
    captured: dict[str, object] = {}

    def runner(argv: list[str], **kwargs: object) -> object:
        captured["argv"] = argv
        Path(str(argv[argv.index("--output-last-message") + 1])).write_text(json.dumps(output(packet_value, packet_sha256=package.package_hashes["packet-001.json"])), encoding="utf-8")
        return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    launch = launch_method_case(package, results_root=tmp_path / "outside-results", repo_root=repo_root, runner=runner, platform_name="Darwin", codex_executable=launcher)

    argv = captured["argv"]
    assert argv[3] == str(target.resolve())
    profile = str(argv[2])
    assert "(allow default)" in profile
    assert f'(deny file-read* (subpath "{repo_root}"))' in profile
    record = json.loads(launch.record_path.read_text())
    assert record["requested_cli"] == str(launcher)
    assert record["resolved_cli_path"] == str(target.resolve())


@pytest.mark.skipif(sys.platform != "darwin", reason="sandbox-exec is a macOS boundary")
def test_macos_seatbelt_probe_denies_original_repository_read(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    protected = repo_root / "CLAUDE.md"
    protected.write_text("must not be readable", encoding="utf-8")
    profile = macos_method_seatbelt_profile(repo_root=repo_root, case_dir=tmp_path / "case", results_root=tmp_path / "results", executable=resolve_codex_executable())

    completed = subprocess.run(["sandbox-exec", "-p", profile, "/bin/cat", str(protected)], check=False, capture_output=True, text=True)

    assert "(allow default)" in profile
    assert completed.returncode != 0
    assert "Operation not permitted" in completed.stderr


def test_revalidation_rejects_tamper_extra_and_symlink(tmp_path: Path) -> None:
    _, _, package = build(tmp_path)
    (package.case_dir / "packet-001.json").write_text("{}", encoding="utf-8")
    with pytest.raises(MethodRunnerError, match="hash mismatch"):
        revalidate_method_case(package)
    (package.case_dir / "packet-001.json").unlink()
    (package.case_dir / "packet-001.json").symlink_to(package.case_dir / "prompt.json")
    with pytest.raises(MethodRunnerError, match="symlink"):
        revalidate_method_case(package)
    (package.case_dir / "packet-001.json").unlink()
    write_json(package.case_dir / "packet-001.json", packet())
    (package.case_dir / "extra.json").write_text("{}", encoding="utf-8")
    with pytest.raises(MethodRunnerError, match="allowlist"):
        revalidate_method_case(package)


def test_launch_rejects_wrong_chunk_and_missing_output(tmp_path: Path) -> None:
    repo_root, packet_value, package = build(tmp_path)

    def wrong_runner(argv: list[str], **kwargs: object) -> object:
        Path(str(argv[argv.index("--output-last-message") + 1])).write_text(json.dumps(output(packet_value, packet_sha256=package.package_hashes["packet-001.json"], wrong_chunk=True)), encoding="utf-8")
        return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    with pytest.raises(MethodRunnerError, match="coverage"):
        launch_method_case(package, results_root=tmp_path / "outside-results", repo_root=repo_root, runner=wrong_runner, platform_name="Linux")

    with pytest.raises(MethodRunnerError, match="did not produce"):
        launch_method_case(package, results_root=tmp_path / "other-results", repo_root=repo_root, runner=lambda *args, **kwargs: type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})(), platform_name="Linux")


def test_launch_rejects_full_coverage_output_that_reports_repeated_input_read_failure(tmp_path: Path) -> None:
    repo_root, packet_value, package = build(tmp_path)
    results_root = tmp_path / "outside-results"

    def unreadable_runner(argv: list[str], **kwargs: object) -> object:
        result = output(packet_value, packet_sha256=package.package_hashes["packet-001.json"])
        for item in result["dispositions"]:
            item["disposition"] = "no_reusable_move"
            item["coding"] = None
            item["uncertainty_notes"] = ["Exact required packet read returned an operation-not-permitted error."]
            item["contradiction_notes"] = []
        Path(str(argv[argv.index("--output-last-message") + 1])).write_text(json.dumps(result), encoding="utf-8")
        return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    with pytest.raises(MethodRunnerError, match="input_unreadable"):
        launch_method_case(package, results_root=results_root, repo_root=repo_root, runner=unreadable_runner, platform_name="Linux")
    record_path = next(results_root.glob("packet-001/*/execution.json"))
    record = json.loads(record_path.read_text())
    assert record["status"] == "input_unreadable"
    assert record["review_state"] == "needs_review"


def test_logical_audited_launch_requires_packet_read_evidence_and_marks_its_limitations(tmp_path: Path) -> None:
    repo_root, packet_value, package = build(tmp_path)
    transcript = json.dumps({"type": "item.completed", "item": {"id": "item-0", "type": "command_execution", "command": "/bin/zsh -lc \"jq -C . packet-001.json\"", "aggregated_output": "ordinary packet text can include /data without reading an external path", "exit_code": 0, "status": "completed"}}) + "\n"
    captured: dict[str, object] = {}

    def runner(argv: list[str], **kwargs: object) -> object:
        captured["argv"] = argv
        Path(str(argv[argv.index("--output-last-message") + 1])).write_text(json.dumps(output(packet_value, packet_sha256=package.package_hashes["packet-001.json"])), encoding="utf-8")
        return type("Completed", (), {"returncode": 0, "stdout": transcript, "stderr": ""})()

    launch = launch_method_case(package, results_root=tmp_path / "outside-results", repo_root=repo_root, runner=runner, platform_name="Darwin", isolation="logical-audited")
    record = json.loads(launch.record_path.read_text())
    assert record["isolation_level"] == "logical_audited"
    assert record["repo_read_denial"] == "unavailable"
    assert "not OS-enforced" in record["residual_limitation"]
    assert captured["argv"][0] == str(resolve_codex_executable().resolved_path)
    assert record["transcript_sha256"] == hashlib.sha256(transcript.encode()).hexdigest()
    assert record["transcript_audit"] == {"forbidden_read_events": 0, "packet_read_events": 1, "tool_events": 1}
    assert Path(record["transcript_path"]).read_text() == transcript
    assert launch.record_path.parent.joinpath("model-output.json").exists()


def test_logical_audited_launch_recovers_a_completed_packet_read_split_by_raw_output_newlines(tmp_path: Path) -> None:
    repo_root, packet_value, package = build(tmp_path)
    command = '/bin/zsh -lc "cat ./packet-001.json"'
    transcript = json.dumps({"type": "item.started", "item": {"id": "read-1", "type": "command_execution", "command": command, "aggregated_output": "", "exit_code": None, "status": "in_progress"}}) + "\n"
    transcript += json.dumps({"type": "item.completed", "item": {"id": "read-1", "type": "command_execution", "command": command, "aggregated_output": "packet payload begins\nand continues", "exit_code": 0, "status": "completed"}}).replace("\\n", "\n") + "\n"

    def runner(argv: list[str], **kwargs: object) -> object:
        Path(str(argv[argv.index("--output-last-message") + 1])).write_text(json.dumps(output(packet_value, packet_sha256=package.package_hashes["packet-001.json"])), encoding="utf-8")
        return type("Completed", (), {"returncode": 0, "stdout": transcript, "stderr": ""})()

    launch = launch_method_case(package, results_root=tmp_path / "outside-results", repo_root=repo_root, runner=runner, platform_name="Darwin", isolation="logical-audited")

    assert json.loads(launch.record_path.read_text())["transcript_audit"] == {"forbidden_read_events": 0, "packet_read_events": 1, "tool_events": 1}


def test_logical_audited_launch_does_not_link_a_packet_read_start_to_another_command_completion(tmp_path: Path) -> None:
    repo_root, packet_value, package = build(tmp_path)
    transcript = json.dumps({"type": "item.started", "item": {"id": "read-1", "type": "command_execution", "command": '/bin/zsh -lc "cat ./packet-001.json"', "aggregated_output": "", "exit_code": None, "status": "in_progress"}}) + "\n"
    transcript += json.dumps({"type": "item.completed", "item": {"id": "other-2", "type": "command_execution", "command": "/bin/true", "aggregated_output": "unrelated\noutput", "exit_code": 0, "status": "completed"}}).replace("\\n", "\n") + "\n"

    def runner(argv: list[str], **kwargs: object) -> object:
        Path(str(argv[argv.index("--output-last-message") + 1])).write_text(json.dumps(output(packet_value, packet_sha256=package.package_hashes["packet-001.json"])), encoding="utf-8")
        return type("Completed", (), {"returncode": 0, "stdout": transcript, "stderr": ""})()

    with pytest.raises(MethodRunnerError, match="input_unreadable"):
        launch_method_case(package, results_root=tmp_path / "outside-results", repo_root=repo_root, runner=runner, platform_name="Darwin", isolation="logical-audited")


@pytest.mark.parametrize(
    ("transcript", "error", "status"),
    [
        ("", "input_unreadable", "input_unreadable"),
        (json.dumps({"type": "item.completed", "item": {"type": "command_execution", "command": "cat /repo/CLAUDE.md", "exit_code": 0}}) + "\n", "forbidden_read_observed", "forbidden_read_observed"),
        (json.dumps({"type": "item.completed", "item": {"type": "command_execution", "command": "sed -n '1,20p' ../CLAUDE.md", "exit_code": 0}}) + "\n", "forbidden_read_observed", "forbidden_read_observed"),
        (json.dumps({"type": "item.completed", "item": {"type": "command_execution", "command": "curl https://example.test/packet.json", "exit_code": 0}}) + "\n", "forbidden_read_observed", "forbidden_read_observed"),
    ],
)
def test_logical_audited_launch_rejects_missing_or_forbidden_read_evidence(tmp_path: Path, transcript: str, error: str, status: str) -> None:
    repo_root, packet_value, package = build(tmp_path)

    def runner(argv: list[str], **kwargs: object) -> object:
        Path(str(argv[argv.index("--output-last-message") + 1])).write_text(json.dumps(output(packet_value, packet_sha256=package.package_hashes["packet-001.json"])), encoding="utf-8")
        return type("Completed", (), {"returncode": 0, "stdout": transcript, "stderr": ""})()

    results_root = tmp_path / "outside-results"
    with pytest.raises(MethodRunnerError, match=error):
        launch_method_case(package, results_root=results_root, repo_root=repo_root, runner=runner, platform_name="Darwin", isolation="logical-audited")
    record = json.loads(next(results_root.glob("packet-001/*/execution.json")).read_text())
    assert record["status"] == status


def test_output_schema_uses_structured_output_subset_and_runner_enforces_disposition_condition(tmp_path: Path) -> None:
    schema = json.loads((Path(__file__).resolve().parents[3] / "config/method-coding-output.schema.json").read_text())

    def has_one_of(value: object) -> bool:
        if isinstance(value, dict):
            return "oneOf" in value or any(has_one_of(item) for item in value.values())
        return isinstance(value, list) and any(has_one_of(item) for item in value)

    assert not has_one_of(schema)

    def missing_property_type(value: object) -> bool:
        if not isinstance(value, dict):
            return isinstance(value, list) and any(missing_property_type(item) for item in value)
        properties = value.get("properties")
        if isinstance(properties, dict) and any(not isinstance(item, dict) or "type" not in item for item in properties.values()):
            return True
        return any(missing_property_type(item) for item in value.values())

    assert not missing_property_type(schema)
    repo_root, packet_value, package = build(tmp_path)

    def inconsistent_runner(argv: list[str], **kwargs: object) -> object:
        result = output(packet_value, packet_sha256=package.package_hashes["packet-001.json"])
        result["dispositions"][0]["coding"] = None
        Path(str(argv[argv.index("--output-last-message") + 1])).write_text(json.dumps(result), encoding="utf-8")
        return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    with pytest.raises(MethodRunnerError, match="coded disposition requires coding"):
        launch_method_case(package, results_root=tmp_path / "outside-results", repo_root=repo_root, runner=inconsistent_runner, platform_name="Linux")

    def nonreusable_with_coding_runner(argv: list[str], **kwargs: object) -> object:
        result = output(packet_value, packet_sha256=package.package_hashes["packet-001.json"])
        result["dispositions"][1]["coding"] = result["dispositions"][0]["coding"]
        Path(str(argv[argv.index("--output-last-message") + 1])).write_text(json.dumps(result), encoding="utf-8")
        return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    with pytest.raises(MethodRunnerError, match="no_reusable_move disposition requires null coding"):
        launch_method_case(package, results_root=tmp_path / "other-results", repo_root=repo_root, runner=nonreusable_with_coding_runner, platform_name="Linux")


def test_batch_explicit_packet_selection_records_full_manifest_and_selected_ids(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    packet_dir = tmp_path / "packets"
    packet_dir.mkdir()
    manifest_path = write_manifest(packet_dir, ["packet-001", "packet-002", "packet-003"])
    observed: list[str] = []

    def runner(argv: list[str], **kwargs: object) -> object:
        case_dir = Path(str(argv[argv.index("--cd") + 1]))
        packet_path = next(case_dir.glob("packet-*.json"))
        packet_id = packet_path.stem
        observed.append(packet_id)
        Path(str(argv[argv.index("--output-last-message") + 1])).write_text(json.dumps(output(json.loads(packet_path.read_text()), packet_id=packet_id, packet_sha256=hashlib.sha256(packet_path.read_bytes()).hexdigest())), encoding="utf-8")
        return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    launches = run_batch_manifest(manifest_path=manifest_path, packet_dir=packet_dir, output_schema_path=Path(__file__).resolve().parents[3] / "config/method-coding-output.schema.json", case_root=tmp_path / "cases", results_root=tmp_path / "results", repo_root=repo_root, max_workers=1, runner=runner, platform_name="Linux", packet_ids=("packet-002", "packet-003"))

    assert observed == ["packet-002", "packet-003"]
    assert len(launches) == 2
    manifest = json.loads(manifest_path.read_text())
    for launch in launches:
        record = json.loads(launch.record_path.read_text())
        assert record["full_manifest_content_hash"] == manifest["content_hash"]
        assert record["full_manifest_sha256"] == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        assert record["selected_packet_ids"] == ["packet-002", "packet-003"]
        assert record["selected_packet_count"] == 2


def test_batch_defaults_to_all_manifest_packets(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    packet_dir = tmp_path / "packets"
    packet_dir.mkdir()
    manifest_path = write_manifest(packet_dir, ["packet-001", "packet-002"])
    observed: list[str] = []

    def runner(argv: list[str], **kwargs: object) -> object:
        case_dir = Path(str(argv[argv.index("--cd") + 1]))
        packet_path = next(case_dir.glob("packet-*.json"))
        packet_id = packet_path.stem
        observed.append(packet_id)
        Path(str(argv[argv.index("--output-last-message") + 1])).write_text(json.dumps(output(json.loads(packet_path.read_text()), packet_id=packet_id, packet_sha256=hashlib.sha256(packet_path.read_bytes()).hexdigest())), encoding="utf-8")
        return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    launches = run_batch_manifest(manifest_path=manifest_path, packet_dir=packet_dir, output_schema_path=Path(__file__).resolve().parents[3] / "config/method-coding-output.schema.json", case_root=tmp_path / "cases", results_root=tmp_path / "results", repo_root=repo_root, max_workers=1, runner=runner, platform_name="Linux")

    assert observed == ["packet-001", "packet-002"]
    assert len(launches) == 2


@pytest.mark.parametrize(
    ("packet_ids", "error"),
    [
        ((), "selection cannot be empty"),
        (("packet-002", "packet-002"), "selection cannot repeat"),
        (("packet-999",), "not present in packet manifest"),
    ],
)
def test_batch_selection_rejects_empty_duplicate_or_unknown_before_creating_cases(tmp_path: Path, packet_ids: tuple[str, ...], error: str) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    packet_dir = tmp_path / "packets"
    packet_dir.mkdir()
    manifest_path = write_manifest(packet_dir, ["packet-001", "packet-002"])
    case_root = tmp_path / "cases"

    with pytest.raises(MethodRunnerError, match=error):
        run_batch_manifest(manifest_path=manifest_path, packet_dir=packet_dir, output_schema_path=Path(__file__).resolve().parents[3] / "config/method-coding-output.schema.json", case_root=case_root, results_root=tmp_path / "results", repo_root=repo_root, packet_ids=packet_ids)

    assert not case_root.exists()


@pytest.mark.parametrize(
    ("packet_ids", "error"),
    [
        (("",), "selection requires non-empty"),
        (("packet-001", "packet-001"), "selection cannot repeat"),
        (("packet-999",), "not present in packet manifest"),
    ],
)
def test_batch_cli_rejects_invalid_explicit_selection_before_creating_cases(tmp_path: Path, packet_ids: tuple[str, ...], error: str) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    packet_dir = tmp_path / "packets"
    packet_dir.mkdir()
    manifest_path = write_manifest(packet_dir, ["packet-001"])
    script = Path(__file__).resolve().parents[3] / "scripts" / "serenity_method_runner.py"
    case_root = tmp_path / "cases"

    arguments = [sys.executable, str(script), "batch", "--manifest", str(manifest_path), "--packet-dir", str(packet_dir), "--case-root", str(case_root), "--results-root", str(tmp_path / "results"), "--repo-root", str(repo_root)]
    for packet_id in packet_ids:
        arguments.extend(("--packet-id", packet_id))
    completed = subprocess.run(arguments, cwd=tmp_path, check=False, capture_output=True, text=True)

    assert completed.returncode == 2
    assert error in completed.stderr
    assert not case_root.exists()


def test_cli_help_is_detailed_and_performs_no_io(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[3] / "scripts" / "serenity_method_runner.py"
    for arguments, terms in ((["--help"], ("blind", "allowlist", "forbidden", "gpt-5.6-terra", "gpt-5.6-sol", "role", "batch", "concurrency", "output", "resume", "failure", "example", "logical-audited", "orbstack", "selection", "synthesis")), (["packet", "--help"], ("packet", "allowlist", "output", "failure", "resume", "logical-audited")), (["batch", "--help"], ("batch", "manifest", "concurrency", "output", "failure", "resume", "logical-audited", "packet-id", "selection")), (["synthesize", "--help"], ("synthesis", "candidate-digest", "gpt-5.6-sol", "final", "one", "allowlist", "forbidden", "danger-full-access", "output", "failure", "example"))):
        completed = subprocess.run([sys.executable, str(script), *arguments], cwd=tmp_path, check=False, capture_output=True, text=True)
        assert completed.returncode == 0
        assert completed.stderr == ""
        assert all(term in completed.stdout.casefold() for term in terms)
    assert list(tmp_path.iterdir()) == []
