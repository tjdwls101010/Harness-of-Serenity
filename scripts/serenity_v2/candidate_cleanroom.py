"""Run a Codex investment candidate against an exact, isolated Harness snapshot."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from jsonschema import Draft202012Validator, ValidationError

from serenity_v2.schema import SchemaViolation, validate_document


CANDIDATE_CASE_SCHEMA_ID = "urn:serenity:schema:candidate-case:1"
CANDIDATE_RESULT_SCHEMA_ID = "urn:serenity:schema:candidate-result:1"
CANDIDATE_PACKAGE_FILES = frozenset({"candidate-case.json", "frozen-packet.json", "candidate-result.schema.json"})
HARNESS_REGULAR_PATHS = (
    "CLAUDE.md",
    ".claude/settings.json",
    ".claude/harness-spec.md",
    ".claude/agents/peer-blind-candidate.md",
    ".claude/agents/serenity-filings.md",
    ".claude/skills/serenity-cohort/SKILL.md",
    ".claude/skills/serenity-discovery/SKILL.md",
    ".claude/skills/serenity-macro-event/SKILL.md",
    ".claude/skills/serenity-single-name/SKILL.md",
    ".claude/hooks/lifecycle_gate.py",
    ".claude/hooks/session_health.py",
)
HARNESS_SYMLINKS = {"AGENTS.md": "CLAUDE.md", ".codex": ".claude"}
FAMILY_INSTRUCTION_PATHS = {
    "discovery": ("CLAUDE.md", ".claude/skills/serenity-discovery/SKILL.md"),
    "single-ticker": ("CLAUDE.md", ".claude/skills/serenity-single-name/SKILL.md"),
    "degraded-data": ("CLAUDE.md", ".claude/skills/serenity-single-name/SKILL.md"),
    "physical-ai": ("CLAUDE.md", ".claude/skills/serenity-discovery/SKILL.md"),
    "near-miss": ("CLAUDE.md", ".claude/skills/serenity-discovery/SKILL.md"),
    "displacement-fear": ("CLAUDE.md", ".claude/skills/serenity-macro-event/SKILL.md", ".claude/skills/serenity-single-name/SKILL.md"),
}
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")


class CandidateCleanroomError(RuntimeError):
    """A candidate cannot safely be packaged or launched in isolation."""

    def __init__(self, message: str, *, code: str = "generic") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CandidatePackage:
    case_id: str
    case_dir: Path
    package_hashes: dict[str, str]
    harness_hashes: dict[str, str]


@dataclass(frozen=True)
class CandidateLaunch:
    result_path: Path
    record_path: Path


@dataclass(frozen=True)
class CandidateExecutable:
    requested_cli: str
    resolved_path: Path
    runtime_root: Path


CandidateRunner = Callable[..., Any]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateCleanroomError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise CandidateCleanroomError(f"{label} must be a JSON object")
    return value


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _require_regular_file(path: Path, *, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise CandidateCleanroomError(f"{label} must be a regular file: {path}")


def _require_outside_repo(path: Path, repo_root: Path, *, label: str) -> None:
    if _is_within(path, repo_root):
        raise CandidateCleanroomError(f"{label} must be outside the original repository: {path}")


def _validate_candidate_case(case: dict[str, Any]) -> None:
    required = {"schema_id", "case_id", "family", "question", "cutoff", "isolation_policy"}
    if set(case) != required:
        raise CandidateCleanroomError("candidate case has an invalid field set")
    if case["schema_id"] != CANDIDATE_CASE_SCHEMA_ID:
        raise CandidateCleanroomError("candidate case has an invalid schema_id")
    if not isinstance(case["case_id"], str) or not ID_PATTERN.fullmatch(case["case_id"]):
        raise CandidateCleanroomError("candidate case has an invalid case_id")
    if not all(isinstance(case[name], str) and case[name] for name in ("family", "question", "cutoff")):
        raise CandidateCleanroomError("candidate case requires family, question, and cutoff strings")
    policy = case["isolation_policy"]
    if not isinstance(policy, dict) or policy != {"network_mode": "recorded", "exclude_prior_outputs": True}:
        raise CandidateCleanroomError("candidate case has an invalid isolation_policy")


def _snapshot_harness(harness_root: Path) -> tuple[dict[str, Path], dict[str, str]]:
    sources: dict[str, Path] = {}
    hashes: dict[str, str] = {}
    for relative in HARNESS_REGULAR_PATHS:
        source = harness_root / relative
        _require_regular_file(source, label=f"harness snapshot file {relative}")
        destination = f"harness/{relative}"
        sources[destination] = source
        hashes[relative] = _sha256(source)
    for relative, target in HARNESS_SYMLINKS.items():
        link = harness_root / relative
        if not link.is_symlink() or os.readlink(link) != target:
            raise CandidateCleanroomError(f"harness {relative} must be the relative {target} symlink")
        sources[f"harness/{relative}"] = link
        hashes[relative] = _sha256_text(f"symlink:{target}")
    return sources, hashes


def _package_manifest_hashes(case_dir: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in case_dir.rglob("*"):
        if path.is_symlink():
            relative = path.relative_to(case_dir).as_posix()
            hashes[relative] = _sha256_text(f"symlink:{os.readlink(path)}")
        elif path.is_file() and path.name != "package-manifest.json":
            hashes[path.relative_to(case_dir).as_posix()] = _sha256(path)
    return hashes


def _validate_candidate_tree(package: CandidatePackage | Path, *, expected_hashes: dict[str, str] | None = None) -> dict[str, str]:
    case_dir = package.case_dir if isinstance(package, CandidatePackage) else package
    expected_names = {name for name in CANDIDATE_PACKAGE_FILES}
    expected_names.update(f"harness/{name}" for name in HARNESS_REGULAR_PATHS)
    expected_names.update(f"harness/{name}" for name in HARNESS_SYMLINKS)
    actual_hashes = _package_manifest_hashes(case_dir)
    if set(actual_hashes) != expected_names:
        raise CandidateCleanroomError("candidate package has an invalid allowlist")
    for relative, target in HARNESS_SYMLINKS.items():
        link = case_dir / "harness" / relative
        if not link.is_symlink() or os.readlink(link) != target:
            raise CandidateCleanroomError(f"candidate package has an invalid {relative} symlink")
    manifest = _load_json(case_dir / "package-manifest.json", label="candidate package manifest")
    if manifest.get("format") != "serenity-candidate-cleanroom-package/1" or manifest.get("payload_sha256") != actual_hashes:
        raise CandidateCleanroomError("candidate package manifest does not match payload hashes")
    if expected_hashes is not None and actual_hashes != expected_hashes:
        raise CandidateCleanroomError("candidate package hash mismatch after package creation")
    return actual_hashes


def build_candidate_cleanroom(
    *,
    candidate_case_path: Path,
    frozen_packet_path: Path,
    candidate_result_schema_path: Path,
    harness_root: Path,
    cleanroom_root: Path,
    repo_root: Path,
) -> CandidatePackage:
    """Build an external candidate package with only a pinned Harness snapshot and evidence."""
    repo_root = repo_root.resolve()
    cleanroom_root = cleanroom_root.resolve()
    _require_outside_repo(cleanroom_root, repo_root, label="candidate cleanroom root")
    for source, label in ((candidate_case_path, "candidate case"), (frozen_packet_path, "frozen typed evidence"), (candidate_result_schema_path, "candidate result schema")):
        _require_regular_file(source, label=label)
    case = _load_json(candidate_case_path, label="candidate case")
    _validate_candidate_case(case)
    _load_json(frozen_packet_path, label="frozen typed evidence")
    schema = _load_json(candidate_result_schema_path, label="candidate result schema")
    if schema.get("$id") != CANDIDATE_RESULT_SCHEMA_ID:
        raise CandidateCleanroomError("candidate result schema has an invalid $id")
    harness_sources, harness_hashes = _snapshot_harness(harness_root.resolve())
    input_hash = hashlib.sha256(
        b"\0".join(_sha256(path).encode("ascii") for path in (candidate_case_path, frozen_packet_path, candidate_result_schema_path))
    ).hexdigest()
    case_dir = cleanroom_root / f"{case['case_id']}-{input_hash[:12]}"
    try:
        case_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise CandidateCleanroomError(f"candidate cleanroom already exists: {case_dir}") from exc
    try:
        destinations = {
            "candidate-case.json": candidate_case_path,
            "frozen-packet.json": frozen_packet_path,
            "candidate-result.schema.json": candidate_result_schema_path,
            **harness_sources,
        }
        for name, source in destinations.items():
            target = case_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_symlink():
                target.symlink_to(os.readlink(source))
            else:
                shutil.copyfile(source, target)
        hashes = _package_manifest_hashes(case_dir)
        (case_dir / "package-manifest.json").write_text(
            _canonical_json({"format": "serenity-candidate-cleanroom-package/1", "case_id": case["case_id"], "payload_sha256": hashes}) + "\n",
            encoding="utf-8",
        )
        _validate_candidate_tree(case_dir, expected_hashes=hashes)
    except Exception:
        shutil.rmtree(case_dir, ignore_errors=True)
        raise
    return CandidatePackage(case_id=case["case_id"], case_dir=case_dir, package_hashes=hashes, harness_hashes=harness_hashes)


def revalidate_candidate_cleanroom(package: CandidatePackage) -> dict[str, str]:
    """Verify the candidate package immediately before a launch."""
    return _validate_candidate_tree(package, expected_hashes=package.package_hashes)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _resolve_codex_executable(requested_cli: str = "codex") -> CandidateExecutable:
    found = shutil.which(requested_cli)
    if found is None:
        raise CandidateCleanroomError(f"Codex CLI was not found on PATH: {requested_cli}", code="isolation_unavailable")
    try:
        resolved = Path(found).expanduser().resolve(strict=True)
    except OSError as exc:
        raise CandidateCleanroomError(f"Codex CLI cannot be resolved: {found}", code="isolation_unavailable") from exc
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise CandidateCleanroomError(f"Codex CLI is not an executable file: {resolved}", code="isolation_unavailable")
    return CandidateExecutable(requested_cli=requested_cli, resolved_path=resolved, runtime_root=resolved.parent.parent)


def _stage_auth(*, run_dir: Path) -> tuple[tuple[Path, ...], Path, Path]:
    codex_home = run_dir / "candidate-codex-home"
    runtime_tmp = run_dir / "candidate-tmp"
    codex_home.mkdir(parents=True, exist_ok=False)
    runtime_tmp.mkdir(parents=True, exist_ok=False)
    source = Path.home() / ".codex" / "auth.json"
    if not source.exists():
        return (), codex_home, runtime_tmp
    _require_regular_file(source, label="Codex auth file")
    destination = codex_home / "auth.json"
    shutil.copyfile(source, destination)
    destination.chmod(0o600)
    return (destination,), codex_home, runtime_tmp


def _candidate_body_schema(final_schema: dict[str, Any]) -> dict[str, Any]:
    fields = ("decision", "action", "facts", "inferences", "trigger", "bear_case", "falsifiers", "evidence_refs", "user_artifact")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:serenity:schema:candidate-body:1",
        "type": "object",
        "additionalProperties": False,
        "required": list(fields),
        "properties": {field: final_schema["properties"][field] for field in fields},
        "$defs": final_schema["$defs"],
    }


def _loaded_instruction_paths(case: dict[str, Any]) -> tuple[str, ...]:
    paths = FAMILY_INSTRUCTION_PATHS.get(case["family"])
    if paths is None:
        raise CandidateCleanroomError(f"candidate case has no routed Harness interface: {case['family']}")
    return paths


def _harness_prompt_snapshot(package: CandidatePackage, *, loaded_instruction_paths: Sequence[str]) -> list[dict[str, str]]:
    snapshot: list[dict[str, str]] = []
    for relative in loaded_instruction_paths:
        snapshot.append(
            {
                "path": relative,
                "sha256": package.harness_hashes[relative],
                "content": (package.case_dir / "harness" / relative).read_text(encoding="utf-8"),
            }
        )
    return snapshot


def _candidate_prompt(*, case: dict[str, Any], packet: dict[str, Any], package: CandidatePackage, loaded_instruction_paths: Sequence[str]) -> str:
    return (
        "You are producing an investment candidate using an exact shared Harness instruction snapshot and frozen typed evidence. "
        "This run's capability is shared-harness-instruction integration: the supplied Harness bytes guide your reasoning, but no configured hook lifecycle is executed. "
        "The question, Harness snapshot, and frozen packet below are the complete boundary. Do not invoke a shell, local file tool, browser, search, network, MCP, or any other tool. "
        "Never access repository material, corpus, data, sessions, evaluator expectations, prior outputs, or external context. "
        "Ground every evidence_refs value only in top-level evidence[].evidence_id values from the frozen packet; never cite a fact_id as an evidence ref. Keep fact and inference distinct; state a trigger, bear case, and falsifiers. "
        "Use NFA in user_artifact.markdown only when action.kind is RECOMMEND_NOW or ENTER_ON_TRIGGER. Return exactly one schema-valid JSON object and no prose outside it.\n"
        f"<candidate-case-canonical-json>{_canonical_json(case)}</candidate-case-canonical-json>\n"
        f"<frozen-typed-evidence-canonical-json>{_canonical_json(packet)}</frozen-typed-evidence-canonical-json>\n"
        f"<shared-harness-snapshot-canonical-json>{_canonical_json(_harness_prompt_snapshot(package, loaded_instruction_paths=loaded_instruction_paths))}</shared-harness-snapshot-canonical-json>"
    )


def _completed_tool_events(transcript: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in transcript.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item") if isinstance(event, dict) else None
        if isinstance(item, dict) and item.get("status") == "completed" and item.get("type") not in {"agent_message", "reasoning"}:
            events.append(item)
    return events


def _audit_no_tools(transcript: str) -> dict[str, int]:
    events = _completed_tool_events(transcript)
    if events:
        raise CandidateCleanroomError("candidate transcript contains a forbidden tool event", code="isolation_violation")
    return {"tool_event_count": 0, "command_count": 0, "network_or_search_events": 0}


def _seatbelt_quote(path: Path) -> str:
    return str(path.resolve()).replace("\\", "\\\\").replace('"', '\\"')


def _candidate_macos_profile(
    *, repo_root: Path, case_dir: Path, results_root: Path, run_dir: Path, executable: CandidateExecutable, auth_paths: Sequence[Path], runtime_helpers: Sequence[Path]
) -> str:
    protected_roots = {Path.home().resolve(), Path(tempfile.gettempdir()).resolve(), Path("/private/tmp").resolve(), Path("/tmp").resolve(), results_root.resolve()}
    profile = ["(version 1)", "(allow default)"]
    for root in sorted(protected_roots, key=str):
        profile.extend((f'(deny file-read* (subpath "{_seatbelt_quote(root)}"))', f'(deny file-write* (subpath "{_seatbelt_quote(root)}"))'))
    for path, permissions in ((case_dir, ("file-read*",)), (run_dir, ("file-read*", "file-write*")), (executable.runtime_root, ("file-read*",))):
        for permission in permissions:
            profile.append(f'(allow {permission} (subpath "{_seatbelt_quote(path)}"))')
    for path in auth_paths:
        profile.append(f'(allow file-read* (literal "{_seatbelt_quote(path)}"))')
    metadata_paths: set[Path] = set()
    for target in (case_dir, run_dir, executable.runtime_root, *auth_paths):
        current = target.resolve()
        boundaries = [root for root in protected_roots if _is_within(current, root)]
        if not boundaries:
            continue
        boundary = max(boundaries, key=lambda path: len(path.parts))
        while _is_within(current, boundary):
            metadata_paths.add(current)
            if current == boundary:
                break
            current = current.parent
    for path in sorted(metadata_paths, key=str):
        profile.append(f'(allow file-read-metadata (literal "{_seatbelt_quote(path)}"))')
    profile.append("(deny process-exec)")
    for path in (executable.resolved_path, *runtime_helpers):
        profile.append(f'(allow process-exec (literal "{_seatbelt_quote(path)}"))')
    profile.extend((f'(deny file-read* (subpath "{_seatbelt_quote(repo_root)}"))', f'(deny file-write* (subpath "{_seatbelt_quote(repo_root)}"))'))
    return "\n".join(profile)


def _packet_evidence_ids(packet: dict[str, Any]) -> set[str]:
    evidence = packet.get("evidence")
    if not isinstance(evidence, list):
        return set()
    return {
        item["evidence_id"]
        for item in evidence
        if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)
    }


def _single_ticker_identity_conflict(packet: dict[str, Any]) -> bool:
    bound_tickers: set[str] = set()
    observed_tickers: set[str] = set()
    evidence = packet.get("evidence")
    if not isinstance(evidence, list):
        return False
    for item in evidence:
        artifact = item.get("artifact") if isinstance(item, dict) else None
        if not isinstance(artifact, dict):
            continue
        bindings = artifact.get("identity_bindings")
        if isinstance(bindings, dict):
            for key in ("ticker", "symbol"):
                value = bindings.get(key)
                if isinstance(value, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9.-]{0,9}", value.strip()):
                    bound_tickers.add(value.strip().upper())
        value = artifact.get("value")
        observations = value.get("observations") if isinstance(value, dict) else None
        if not isinstance(observations, list):
            continue
        for observation in observations:
            if not isinstance(observation, dict) or observation.get("predicate") != "maps_to_cik":
                continue
            subject = observation.get("subject")
            if isinstance(subject, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9.-]{0,9}", subject.strip()):
                observed_tickers.add(subject.strip().upper())
    return bool(bound_tickers and observed_tickers and bound_tickers != observed_tickers)


def _all_result_ref_lists(result: dict[str, Any]) -> list[list[str]]:
    lists = [result["evidence_refs"], result["decision"]["evidence_refs"], result["action"]["evidence_refs"], result["trigger"]["evidence_refs"], result["bear_case"]["evidence_refs"]]
    lists.extend(item["evidence_refs"] for item in result["facts"])
    lists.extend(item["evidence_refs"] for item in result["inferences"])
    lists.extend(item["evidence_refs"] for item in result["falsifiers"])
    return lists


def _canonical_result_hash(result: dict[str, Any]) -> str:
    return _sha256_text(_canonical_json({key: value for key, value in result.items() if key != "canonical_sha256"}))


def _candidate_runtime_helpers(executable: CandidateExecutable) -> tuple[Path, ...]:
    helper = executable.resolved_path.with_name("codex-code-mode-host")
    if not helper.exists():
        return ()
    _require_regular_file(helper, label="Codex runtime helper")
    return (helper.resolve(),)


def revalidate_candidate_result(result_path: Path, *, package: CandidatePackage, run_id: str, model: str) -> dict[str, Any]:
    """Validate the runner-bound candidate envelope and every evidence reference."""
    result = _load_json(result_path, label="candidate result")
    try:
        validate_document(result, CANDIDATE_RESULT_SCHEMA_ID)
    except SchemaViolation as exc:
        raise CandidateCleanroomError(f"candidate result does not match schema: {exc}", code="invalid_candidate_output") from exc
    expected_hashes = [{"path": path, "sha256": package.harness_hashes[path]} for path in sorted(package.harness_hashes)]
    if result["case_id"] != package.case_id or result["run_id"] != run_id or result["model"] != model:
        raise CandidateCleanroomError("candidate result has a tampered provenance receipt", code="invalid_candidate_output")
    case = _load_json(package.case_dir / "candidate-case.json", label="candidate case")
    if result["harness_hashes"] != expected_hashes or result["loaded_instruction_paths"] != list(_loaded_instruction_paths(case)) or result["packet_sha256"] != package.package_hashes["frozen-packet.json"]:
        raise CandidateCleanroomError("candidate result has a tampered provenance receipt", code="invalid_candidate_output")
    if result["canonical_sha256"] != _canonical_result_hash(result):
        raise CandidateCleanroomError("candidate result canonical hash mismatch", code="invalid_candidate_output")
    packet = _load_json(package.case_dir / "frozen-packet.json", label="frozen typed evidence")
    packet_ids = _packet_evidence_ids(packet)
    for refs in _all_result_ref_lists(result):
        if len(refs) != len(set(refs)):
            raise CandidateCleanroomError("candidate result has duplicate evidence refs", code="invalid_candidate_output")
        if not set(refs).issubset(packet_ids):
            raise CandidateCleanroomError("candidate result references unknown evidence", code="invalid_candidate_output")
    contains_nfa = bool(re.search(r"\bNFA\b", result["user_artifact"]["markdown"], flags=re.IGNORECASE))
    action_bearing = result["action"]["kind"] in {"RECOMMEND_NOW", "ENTER_ON_TRIGGER"}
    if contains_nfa != action_bearing:
        raise CandidateCleanroomError("NFA is allowed only for action-bearing candidate output", code="invalid_candidate_output")
    if case["family"] == "single-ticker" and _single_ticker_identity_conflict(packet) and result["action"]["kind"] != "BLOCKED":
        raise CandidateCleanroomError("single-ticker identity conflict requires BLOCKED", code="invalid_candidate_output")
    return result


def _candidate_child_env(*, codex_home: Path, runtime_tmp: Path) -> dict[str, str]:
    allowed_names = {"PATH", "LANG", "TERM", "TZ", "SSL_CERT_FILE", "SSL_CERT_DIR", "NO_COLOR"}
    environment = {
        name: value
        for name, value in os.environ.items()
        if name in allowed_names or name.startswith("LC_")
    }
    environment.update({"CODEX_HOME": str(codex_home), "TMPDIR": str(runtime_tmp), "TMP": str(runtime_tmp), "TEMP": str(runtime_tmp)})
    return environment


def launch_candidate_cleanroom(
    package: CandidatePackage,
    *,
    results_root: Path,
    repo_root: Path,
    runner: CandidateRunner = subprocess.run,
    platform_name: str | None = None,
    model: str = "gpt-5.6-terra",
    isolation_mode: str = "os-enforced",
) -> CandidateLaunch:
    """Run one no-tool Codex candidate and bind its body to trusted provenance receipts."""
    if model != "gpt-5.6-terra":
        raise CandidateCleanroomError("candidate cleanroom permits only gpt-5.6-terra")
    platform_name = platform_name or platform.system()
    if isolation_mode not in {"os-enforced", "logical-audited"}:
        raise CandidateCleanroomError(f"unsupported candidate isolation mode: {isolation_mode}")
    if isolation_mode == "os-enforced" and platform_name != "Darwin":
        raise CandidateCleanroomError("os-enforced candidate cleanroom requires Darwin", code="isolation_unavailable")
    repo_root = repo_root.resolve()
    results_root = results_root.resolve()
    _require_outside_repo(results_root, repo_root, label="candidate results root")
    package_hashes = revalidate_candidate_cleanroom(package)
    case = _load_json(package.case_dir / "candidate-case.json", label="candidate case")
    packet = _load_json(package.case_dir / "frozen-packet.json", label="frozen typed evidence")
    loaded_instruction_paths = _loaded_instruction_paths(case)
    executable = _resolve_codex_executable()
    if _is_within(executable.resolved_path, repo_root):
        raise CandidateCleanroomError("Codex CLI must be outside the original repository")
    runtime_helpers = _candidate_runtime_helpers(executable)
    run_id = hashlib.sha256(f"{package.case_id}:{_utc_now()}:{os.getpid()}".encode("utf-8")).hexdigest()[:16]
    run_dir = results_root / package.case_id / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    raw_body_path = run_dir / "candidate-model-body.json"
    result_path = run_dir / "candidate-result.json"
    record_path = run_dir / "candidate-execution.json"
    final_schema = _load_json(package.case_dir / "candidate-result.schema.json", label="candidate result schema")
    body_schema_path = run_dir / "candidate-body.schema.json"
    body_schema_path.write_text(_canonical_json(_candidate_body_schema(final_schema)) + "\n", encoding="utf-8")
    auth_paths, codex_home, runtime_tmp = _stage_auth(run_dir=run_dir)
    prompt = _candidate_prompt(case=case, packet=packet, package=package, loaded_instruction_paths=loaded_instruction_paths)
    codex_argv = [str(executable.resolved_path), "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check", "--sandbox", "danger-full-access" if isolation_mode == "os-enforced" else "read-only", "--cd", str(package.case_dir), "--model", model, "--output-schema", str(body_schema_path), "--json", "--output-last-message", str(raw_body_path), prompt]
    argv = codex_argv
    if isolation_mode == "os-enforced":
        argv = ["sandbox-exec", "-p", _candidate_macos_profile(repo_root=repo_root, case_dir=package.case_dir, results_root=results_root, run_dir=run_dir, executable=executable, auth_paths=auth_paths, runtime_helpers=runtime_helpers), *codex_argv]
    record: dict[str, Any] = {
        "format": "serenity-candidate-cleanroom-execution/1",
        "case_id": package.case_id,
        "run_id": run_id,
        "model": model,
        "capability": "shared-harness-instruction-integration",
        "package_sha256": package_hashes,
        "harness_hashes": package.harness_hashes,
        "loaded_instruction_paths": list(loaded_instruction_paths),
        "prompt_sha256": _sha256_text(prompt),
        "argv": argv,
        "isolation": {"mode": isolation_mode, "seatbelt": "outer-macos-candidate-fs-deny-exact-allow" if isolation_mode == "os-enforced" else "not_available", "hook_lifecycle": "not executed; shared Harness instructions are inline", "network_policy": "--search absent; completed tool events rejected; parent provider transport remains required", "separate_auth_dir": str(codex_home), "allowed_process_paths": [str(executable.resolved_path), *(str(path) for path in runtime_helpers)]},
    }
    try:
        completed = runner(argv, cwd=package.case_dir, check=False, capture_output=True, text=True, env=_candidate_child_env(codex_home=codex_home, runtime_tmp=runtime_tmp))
    except OSError as exc:
        record.update({"status": "launch_failed", "error": str(exc)})
        record_path.write_text(_canonical_json(record) + "\n", encoding="utf-8")
        raise CandidateCleanroomError(f"candidate process could not launch: {exc}", code="isolation_unavailable") from exc
    finally:
        shutil.rmtree(codex_home, ignore_errors=True)
        shutil.rmtree(runtime_tmp, ignore_errors=True)
    record.update({"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr})
    if completed.returncode != 0:
        record["status"] = "failed"
        record_path.write_text(_canonical_json(record) + "\n", encoding="utf-8")
        raise CandidateCleanroomError(f"candidate cleanroom run failed with exit code {completed.returncode}", code="isolation_unavailable")
    try:
        record["transcript_audit"] = _audit_no_tools(completed.stdout)
        raw_body = _load_json(raw_body_path, label="candidate model body")
        Draft202012Validator(_candidate_body_schema(final_schema)).validate(raw_body)
        result = {
            "schema_id": CANDIDATE_RESULT_SCHEMA_ID,
            "result_id": f"candidate-result-{run_id}",
            "case_id": package.case_id,
            "run_id": run_id,
            "model": model,
            "capability": "shared-harness-instruction-integration",
            "harness_hashes": [{"path": path, "sha256": package.harness_hashes[path]} for path in sorted(package.harness_hashes)],
            "loaded_instruction_paths": list(loaded_instruction_paths),
            "packet_sha256": package_hashes["frozen-packet.json"],
            **raw_body,
            "canonical_sha256": "",
        }
        result["canonical_sha256"] = _canonical_result_hash(result)
        result_path.write_text(_canonical_json(result) + "\n", encoding="utf-8")
        revalidate_candidate_result(result_path, package=package, run_id=run_id, model=model)
    except (CandidateCleanroomError, json.JSONDecodeError, OSError, ValidationError, ValueError) as exc:
        record.update({"status": "invalid_output", "validation_error": str(exc)})
        record_path.write_text(_canonical_json(record) + "\n", encoding="utf-8")
        if isinstance(exc, CandidateCleanroomError):
            raise
        raise CandidateCleanroomError(f"candidate model output is invalid: {exc}", code="invalid_candidate_output") from exc
    record.update({"status": "completed", "model_body_sha256": _sha256(raw_body_path), "candidate_result_sha256": _sha256(result_path)})
    record_path.write_text(_canonical_json(record) + "\n", encoding="utf-8")
    return CandidateLaunch(result_path=result_path, record_path=record_path)
