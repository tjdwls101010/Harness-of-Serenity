"""Build and launch isolated Codex QA cases without exposing repository doctrine or history."""

from __future__ import annotations

import errno
import hashlib
import json
import math
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

from jsonschema import Draft202012Validator


QA_CASE_SCHEMA_ID = "urn:serenity:schema:qa-case:1"
QA_RESULT_SCHEMA_ID = "urn:serenity:schema:qa-result:1"
MODEL = "gpt-5.6-terra"
SOL_MODEL = "gpt-5.6-sol"
MODEL_ROLES = {MODEL: "reviewer", SOL_MODEL: "adjudicator"}
WILSON_Z = 1.959963984540054
WILSON_BOUND_TOLERANCE = 0.0005
PROMPT_WRAPPER_VERSION = "serenity-cleanroom-prompt/6"
ISOLATION_MODES = frozenset({"os-enforced", "logical-audited"})
PROMPT_WRAPPER = """You are an independent QA reviewer in a cleanroom with an explicit evidence boundary.

The canonical reviewer case projection and frozen evidence packet are enclosed below. They are the complete evidence boundary. Do not inspect, search for, infer from, or use repository material, prior verdicts, corpus answers, sessions, scores, or external context.

Do not invoke a shell, local file tool, browser, search, network, MCP, or any other tool. The enclosed documents are available now; do not claim they are inaccessible. Evaluate every expected_invariant in the reviewer case projection using only the frozen packet. Derive the aggregate exactly: `fail` if any invariant fails; `pass` only if every invariant passes; otherwise `needs_review`. Set counts to invariant pass/fail counts and total expected invariants, with denominator `expected_invariants`. The enclosed aggregate lookup lists every possible pass count for this case with its canonical two-sided 95% Wilson interval using `z=1.959963984540054`; it does not encode the expected review outcome. Select the row that matches your own invariant results. Report the result exactly in the supplied qa-result schema. Return exactly one schema-valid JSON object and no prose outside it.
"""
PACKAGE_FILENAMES = frozenset({"qa-case.json", "frozen-packet.json", "package-manifest.json", "qa-result.schema.json"})
PAYLOAD_FILENAMES = frozenset({"qa-case.json", "frozen-packet.json", "qa-result.schema.json"})
FORBIDDEN_PARTS = frozenset({"claude.md", "agents.md", ".claude", ".codex", "data", "sessions", "results", "scores", "verdicts"})


class CleanroomError(RuntimeError):
    """A case cannot safely be packaged or launched in isolation."""

    def __init__(self, message: str, *, code: str = "generic") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CleanroomPackage:
    case_id: str
    case_dir: Path
    package_hashes: dict[str, str]


@dataclass(frozen=True)
class CleanroomLaunch:
    model_output_path: Path
    record_path: Path


@dataclass(frozen=True)
class CodexExecutable:
    requested_cli: str
    symlink_path: Path
    resolved_path: Path
    runtime_root: Path


@dataclass(frozen=True)
class TranscriptAudit:
    command_count: int
    tool_event_count: int
    successful_packet_reads: int
    forbidden_path_commands: int
    network_or_search_commands: int
    unapproved_command_tools: int


Runner = Callable[..., Any]


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


def _wilson_interval(passed: int, total: int) -> dict[str, float]:
    proportion = passed / total
    denominator = 1 + WILSON_Z * WILSON_Z / total
    centre = (proportion + WILSON_Z * WILSON_Z / (2 * total)) / denominator
    spread = WILSON_Z * math.sqrt(
        proportion * (1 - proportion) / total + WILSON_Z * WILSON_Z / (4 * total * total)
    ) / denominator
    return {"lower": round(max(0.0, centre - spread), 6), "upper": round(min(1.0, centre + spread), 6)}


def _aggregate_lookup(total: int) -> list[dict[str, Any]]:
    return [
        {
            "passed": passed,
            "total": total,
            "wilson_interval": _wilson_interval(passed, total),
        }
        for passed in range(total + 1)
    ]


def _reviewer_case_projection(qa_case: dict[str, Any]) -> dict[str, Any]:
    """Expose only the non-conclusive QA metadata a reviewer needs to evaluate evidence."""
    return {
        "schema_id": qa_case["schema_id"],
        "case_id": qa_case["case_id"],
        "family": qa_case["family"],
        "cutoff": qa_case["cutoff"],
        "expected_invariants": qa_case["expected_invariants"],
        "isolation_policy": qa_case["isolation_policy"],
    }


def _wrapped_prompt(
    qa_case: dict[str, Any], frozen_packet: dict[str, Any], *, adjudication_input_paths: Sequence[Path] = ()
) -> str:
    adjudication_instruction = ""
    if adjudication_input_paths:
        copied_results = "\n".join(
            f"<prior-review-result-{index}>{_canonical_json(_load_json(path, label='prior reviewer result'))}</prior-review-result-{index}>"
            for index, path in enumerate(adjudication_input_paths, start=1)
        )
        adjudication_instruction = (
            "\nAs the adjudicator, the canonical prior reviewer results below are also within the evidence boundary. "
            "Do not access any other result, ranking, verdict, or session path.\n"
            f"{copied_results}\n"
        )
    return (
        f"{PROMPT_WRAPPER}{adjudication_instruction}\n<reviewer-case-canonical-json>{_canonical_json(_reviewer_case_projection(qa_case))}</reviewer-case-canonical-json>\n"
        f"<frozen-packet-canonical-json>{_canonical_json(frozen_packet)}</frozen-packet-canonical-json>\n"
        f"<aggregate-lookup-canonical-json>{_canonical_json(_aggregate_lookup(len(qa_case['expected_invariants'])))}</aggregate-lookup-canonical-json>\n"
        ""
    )


def _command_events(transcript: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in transcript.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item") if isinstance(event, dict) else None
        if isinstance(item, dict) and item.get("type") == "command_execution" and item.get("status") == "completed":
            events.append(item)
    return events


def _tool_events(transcript: str) -> list[dict[str, Any]]:
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


def _audit_transcript(
    transcript: str,
    *,
    case_dir: Path,
    repo_root: Path,
    approved_adjudication_paths: Sequence[Path] = (),
) -> TranscriptAudit:
    commands = _command_events(transcript)
    tool_events = _tool_events(transcript)
    forbidden_terms = (
        str(repo_root.resolve()),
        str(case_dir.resolve().parent),
        "../",
        "..\\",
        "claude.md",
        "agents.md",
        ".claude",
        ".codex",
        "analysis_serenity.db",
        "sessions",
        "corpus",
        "scores",
        "verdicts",
        "results",
    )
    network_terms = ("http://", "https://", "curl", "wget", "nc ", "ssh ", "browser", "search", "web.run")
    unapproved_terms = (
        "git ",
        "rg ",
        "find ",
        "ls ",
        "pwd",
        "python",
        "node",
        "ruby",
        "perl",
        "osascript",
        "open ",
        "readlink",
        "realpath",
        "source ",
        "eval ",
    )
    forbidden_count = network_count = tool_count = packet_reads = 0
    approved_paths = tuple(str(path.resolve()) for path in approved_adjudication_paths)
    approved_case_paths = {
        str((case_dir / name).resolve())
        for name in ("qa-case.json", "frozen-packet.json", "qa-result.schema.json")
    }
    for item in commands:
        command = str(item.get("command", ""))
        lowered = command.casefold()
        references_prior_copy = any(path in command for path in approved_paths)
        disallowed_terms = tuple(
            term
            for term in forbidden_terms
            if not (term == "results" and references_prior_copy)
        )
        absolute_paths = tuple(
            Path(match.rstrip("'\"`;,|&")).resolve(strict=False)
            for match in re.findall(r"(?<![\w:.])(/[^\s;&|]+)", command)
        )
        system_shells = {Path("/bin/zsh"), Path("/bin/sh"), Path("/bin/bash")}
        reads_outside_case = any(
            path not in system_shells and str(path) not in approved_case_paths and str(path) not in approved_paths
            for path in absolute_paths
        )
        relative_paths = {
            f"./{match.rstrip(chr(39) + chr(34) + '`;,|&')}"
            for match in re.findall(r"(?<!\.)\./([^\s'\"`;,|&]+)", command)
        }
        unapproved_relative_read = bool(relative_paths - {"./qa-case.json", "./frozen-packet.json", "./qa-result.schema.json"})
        shell_expansion = bool(
            re.search(r"\$\{|`|\$\(|\$(?!p(?:['\"]|\b))[A-Za-z_]", command)
            or re.search(r"(?<!\S)~(?:/|(?=\s|$))", command)
            or re.search(r"(?:\./|~/|/)[^\s'\"`;,|&]*[*?]", command)
            or "<" in command
            or ">" in command
        )
        if (
            any(term.casefold() in lowered for term in disallowed_terms)
            or reads_outside_case
            or unapproved_relative_read
            or shell_expansion
        ):
            forbidden_count += 1
        if any(term in lowered for term in network_terms):
            network_count += 1
        if any(term in lowered for term in unapproved_terms):
            tool_count += 1
        if (
            item.get("exit_code") == 0
            and "./qa-case.json" in command
            and "./frozen-packet.json" in command
            and any(tool in lowered for tool in ("cat ", "sed ", "head ", "jq "))
        ):
            packet_reads += 1
    audit = TranscriptAudit(
        command_count=len(commands),
        tool_event_count=len(tool_events),
        successful_packet_reads=packet_reads,
        forbidden_path_commands=forbidden_count,
        network_or_search_commands=network_count,
        unapproved_command_tools=tool_count,
    )
    if audit.tool_event_count:
        raise CleanroomError("transcript audit failed: tool event is forbidden in a sealed cleanroom", code="isolation_violation")
    if audit.forbidden_path_commands or audit.network_or_search_commands or audit.unapproved_command_tools:
        raise CleanroomError(
            "transcript audit failed: forbidden, network/search, or unapproved command tool event",
            code="isolation_violation",
        )
    return audit


def _validate_result_semantics(result: dict[str, Any], *, expected_invariants: Sequence[str]) -> None:
    expected = list(expected_invariants)
    observed = [item["invariant"] for item in result["invariant_results"]]
    if len(observed) != len(set(observed)) or set(observed) != set(expected) or len(observed) != len(expected):
        raise CleanroomError("codex cleanroom result does not cover the expected invariants exactly once", code="invalid_reviewer_output")
    evidence_refs = result["evidence_refs"]
    if len(evidence_refs) != len(set(evidence_refs)):
        raise CleanroomError("codex cleanroom result contains duplicate evidence_refs", code="invalid_reviewer_output")
    evidence_set = set(evidence_refs)
    for item in result["invariant_results"]:
        item_refs = item["evidence_refs"]
        if not item_refs or len(item_refs) != len(set(item_refs)) or not set(item_refs).issubset(evidence_set):
            raise CleanroomError("codex cleanroom invariant result has invalid evidence_refs", code="invalid_reviewer_output")
    passed = sum(item["outcome"] == "pass" for item in result["invariant_results"])
    failed = sum(item["outcome"] == "fail" for item in result["invariant_results"])
    total = len(expected)
    expected_outcome = "fail" if failed else ("pass" if passed == total else "needs_review")
    counts = result["counts"]
    wilson_interval = counts["wilson_interval"]
    expected_interval = _wilson_interval(passed, total)
    def matches_wilson_bound(value: float, expected_value: float) -> bool:
        return math.isclose(value, expected_value, abs_tol=WILSON_BOUND_TOLERANCE)

    if (
        result["reviewer_outcome"] != expected_outcome
        or counts["passed"] != passed
        or counts["failed"] != failed
        or counts["total"] != total
        or counts["denominator"] != "expected_invariants"
        or not matches_wilson_bound(wilson_interval["lower"], expected_interval["lower"])
        or not matches_wilson_bound(wilson_interval["upper"], expected_interval["upper"])
    ):
        raise CleanroomError("codex cleanroom result semantic aggregate does not match invariant results", code="invalid_reviewer_output")


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CleanroomError(f"{label} must be readable JSON: {path}") from exc
    if not isinstance(value, dict):
        raise CleanroomError(f"{label} must be a JSON object: {path}")
    return value


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _require_outside_repo(path: Path, repo_root: Path, *, label: str) -> None:
    if _is_within(path, repo_root):
        raise CleanroomError(f"{label} must be outside the original repository: {path}")


def _require_regular_file(path: Path, *, label: str) -> None:
    if path.is_symlink():
        raise CleanroomError(f"{label} must not be a symlink: {path}")
    if not path.is_file():
        raise CleanroomError(f"{label} must be a regular file: {path}")


def _validate_qa_case(case: dict[str, Any], schema_path: Path) -> None:
    schema = _load_json(schema_path, label="qa-result schema")
    if schema.get("$id") != QA_RESULT_SCHEMA_ID:
        raise CleanroomError(f"unexpected QA result schema: {schema_path}")
    policy = case.get("isolation_policy")
    if case.get("schema_id") != QA_CASE_SCHEMA_ID or not isinstance(policy, dict):
        raise CleanroomError("qa case does not use the required isolation contract")
    if policy.get("exclude_prior_verdicts") is not True or policy.get("exclude_corpus_answers") is not True:
        raise CleanroomError("qa case must exclude prior verdicts and corpus answers")
    for field in ("case_id", "prompt"):
        if not isinstance(case.get(field), str) or not case[field]:
            raise CleanroomError(f"qa case requires a non-empty {field}")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,127}", case["case_id"]) is None:
        raise CleanroomError(f"invalid case_id: {case['case_id']}")


def _forbidden_path(path: Path) -> str | None:
    for part in path.parts:
        if part.casefold() in FORBIDDEN_PARTS:
            return part
    return None


def _validate_case_tree(case_dir: Path, *, expected_hashes: dict[str, str] | None = None) -> dict[str, str]:
    if case_dir.is_symlink() or not case_dir.is_dir():
        raise CleanroomError(f"cleanroom must be a real directory: {case_dir}")
    entries = list(case_dir.iterdir())
    for entry in entries:
        forbidden = _forbidden_path(entry.relative_to(case_dir))
        if forbidden is not None:
            raise CleanroomError(f"cleanroom contains forbidden path: {forbidden}")
        _require_regular_file(entry, label="cleanroom file")
    observed_names = {entry.name for entry in entries}
    if observed_names != PACKAGE_FILENAMES:
        unexpected = sorted(observed_names.symmetric_difference(PACKAGE_FILENAMES))
        raise CleanroomError(f"cleanroom allowlist violation: {', '.join(unexpected)}")
    hashes = {name: _sha256(case_dir / name) for name in PACKAGE_FILENAMES}
    manifest = _load_json(case_dir / "package-manifest.json", label="package manifest")
    listed = manifest.get("payload_sha256")
    if not isinstance(listed, dict) or set(listed) != PAYLOAD_FILENAMES:
        raise CleanroomError("package manifest has an invalid payload allowlist")
    for name in PAYLOAD_FILENAMES:
        if listed.get(name) != hashes[name]:
            raise CleanroomError(f"cleanroom hash mismatch: {name}")
    if expected_hashes is not None and hashes != expected_hashes:
        raise CleanroomError("cleanroom hash mismatch after package creation")
    return hashes


def build_cleanroom(
    *,
    qa_case_path: Path,
    frozen_packet_path: Path,
    qa_result_schema_path: Path,
    cleanroom_root: Path,
    repo_root: Path,
) -> CleanroomPackage:
    """Copy one frozen case into a strict, newly created directory outside the repository."""
    repo_root = repo_root.resolve()
    cleanroom_root = cleanroom_root.resolve()
    _require_outside_repo(cleanroom_root, repo_root, label="cleanroom root")
    for source, label in (
        (qa_case_path, "qa case"),
        (frozen_packet_path, "frozen fact/evidence packet"),
        (qa_result_schema_path, "qa result schema"),
    ):
        _require_regular_file(source, label=label)

    case = _load_json(qa_case_path, label="qa case")
    _validate_qa_case(case, qa_result_schema_path)
    _load_json(frozen_packet_path, label="frozen fact/evidence packet")
    case_id = case["case_id"]
    input_hash = hashlib.sha256(
        b"\0".join(_sha256(path).encode("ascii") for path in (qa_case_path, frozen_packet_path, qa_result_schema_path))
    ).hexdigest()
    case_dir = cleanroom_root / f"{case_id}-{input_hash[:12]}"
    if _forbidden_path(case_dir.relative_to(cleanroom_root)) is not None:
        raise CleanroomError(f"qa case id creates a forbidden cleanroom path: {case_id}")
    try:
        case_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise CleanroomError(f"cleanroom already exists: {case_dir}") from exc

    destinations = {
        "qa-case.json": qa_case_path,
        "frozen-packet.json": frozen_packet_path,
        "qa-result.schema.json": qa_result_schema_path,
    }
    try:
        for name, source in destinations.items():
            shutil.copyfile(source, case_dir / name)
        payload_hashes = {name: _sha256(case_dir / name) for name in PAYLOAD_FILENAMES}
        manifest = {
            "format": "serenity-cleanroom-package/1",
            "case_id": case_id,
            "payload_sha256": payload_hashes,
        }
        (case_dir / "package-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        hashes = _validate_case_tree(case_dir)
    except Exception:
        shutil.rmtree(case_dir, ignore_errors=True)
        raise
    return CleanroomPackage(case_id=case_id, case_dir=case_dir, package_hashes=hashes)


def revalidate_cleanroom(package: CleanroomPackage) -> dict[str, str]:
    """Verify the byte-for-byte payload and reject additions immediately before launch."""
    return _validate_case_tree(package.case_dir, expected_hashes=package.package_hashes)


def _seatbelt_quote(path: Path) -> str:
    return str(path.resolve()).replace("\\", "\\\\").replace('"', '\\"')


def _seatbelt_literal_quote(path: Path) -> str:
    return str(path.absolute()).replace("\\", "\\\\").replace('"', '\\"')


def resolve_codex_executable(requested_cli: str = "codex") -> CodexExecutable:
    """Resolve the binary before sandbox-exec starts, where PATH lookup is unavailable."""
    found = shutil.which(requested_cli)
    if found is None:
        raise CleanroomError(f"Codex CLI was not found on PATH: {requested_cli}", code="isolation_unavailable")
    symlink_path = Path(found).expanduser().absolute()
    try:
        resolved_path = symlink_path.resolve(strict=True)
    except OSError as exc:
        raise CleanroomError(f"Codex CLI cannot be resolved: {symlink_path}", code="isolation_unavailable") from exc
    if not resolved_path.is_file() or not os.access(resolved_path, os.X_OK):
        raise CleanroomError(f"Codex CLI is not an executable file: {resolved_path}", code="isolation_unavailable")
    return CodexExecutable(
        requested_cli=requested_cli,
        symlink_path=symlink_path,
        resolved_path=resolved_path,
        runtime_root=resolved_path.parent.parent,
    )


def _codex_auth_paths() -> tuple[Path, ...]:
    auth_path = Path.home() / ".codex" / "auth.json"
    if not auth_path.exists():
        return ()
    _require_regular_file(auth_path, label="Codex auth file")
    return (auth_path.resolve(),)


def _codex_runtime_helpers(executable: CodexExecutable) -> tuple[Path, ...]:
    helper = executable.resolved_path.with_name("codex-code-mode-host")
    if not helper.exists():
        return ()
    _require_regular_file(helper, label="Codex runtime helper")
    return (helper.resolve(),)


def _stage_codex_runtime_paths(auth_sources: Sequence[Path], *, run_dir: Path) -> tuple[tuple[Path, ...], Path, Path]:
    codex_home = run_dir / "codex-home"
    runtime_tmp = run_dir / "tmp"
    codex_home.mkdir(parents=True, exist_ok=False)
    runtime_tmp.mkdir(parents=True, exist_ok=False)
    staged_auth_paths: list[Path] = []
    for source in auth_sources:
        destination = codex_home / source.name
        shutil.copyfile(source, destination)
        destination.chmod(0o600)
        staged_auth_paths.append(destination)
    return tuple(staged_auth_paths), codex_home, runtime_tmp


def _remove_staged_codex_runtime_paths(*, codex_home: Path, runtime_tmp: Path) -> None:
    shutil.rmtree(codex_home, ignore_errors=True)
    shutil.rmtree(runtime_tmp, ignore_errors=True)


def macos_seatbelt_profile(
    *,
    repo_root: Path,
    case_dir: Path,
    results_root: Path,
    executable: CodexExecutable,
    denied_prior_result_paths: Sequence[Path] = (),
    protected_home: Path | None = None,
    protected_temp: Path | None = None,
    allowed_auth_paths: Sequence[Path] = (),
    allowed_process_paths: Sequence[Path] = (),
) -> str:
    """Deny broad user/temp access, then allow only the active cleanroom execution surface."""
    protected_home = (protected_home or Path.home()).resolve()
    protected_temp_roots = tuple(
        sorted(
            {
                Path(tempfile.gettempdir()).resolve(),
                Path("/private/tmp").resolve(),
                Path("/tmp").resolve(),
                *((Path(protected_temp).resolve(),) if protected_temp is not None else ()),
            },
            key=str,
        )
    )
    profile = ["(version 1)", "(allow default)"]
    for protected_path in (protected_home, *protected_temp_roots):
        profile.append(f'(deny file-read* (subpath "{_seatbelt_quote(protected_path)}"))')
        profile.append(f'(deny file-write* (subpath "{_seatbelt_quote(protected_path)}"))')
    profile.append(f'(allow file-read* (subpath "{_seatbelt_quote(case_dir)}"))')
    profile.append(f'(allow file-read* (subpath "{_seatbelt_quote(results_root)}"))')
    profile.append(f'(allow file-write* (subpath "{_seatbelt_quote(results_root)}"))')
    profile.append(f'(allow file-read* (subpath "{_seatbelt_quote(executable.runtime_root)}"))')
    for path in allowed_auth_paths:
        profile.append(f'(allow file-read* (literal "{_seatbelt_literal_quote(path)}"))')
    metadata_paths: set[Path] = set()
    for target in (case_dir, results_root, executable.runtime_root, *allowed_auth_paths):
        current = target.resolve()
        boundaries = [path for path in (protected_home, *protected_temp_roots) if _is_within(current, path)]
        if not boundaries:
            continue
        boundary = max(boundaries, key=lambda path: len(path.parts))
        while _is_within(current, boundary):
            metadata_paths.add(current)
            if current == boundary:
                break
            current = current.parent
    for path in sorted(metadata_paths):
        profile.append(f'(allow file-read-metadata (literal "{_seatbelt_literal_quote(path)}"))')
    profile.append("(deny process-exec)")
    for path in (executable.resolved_path, *allowed_process_paths):
        profile.append(f'(allow process-exec (literal "{_seatbelt_literal_quote(path)}"))')
    profile.append(f'(deny file-read* (subpath "{_seatbelt_quote(repo_root)}"))')
    profile.append(f'(deny file-write* (subpath "{_seatbelt_quote(repo_root)}"))')
    for path in denied_prior_result_paths:
        profile.append(f'(deny file-read* (literal "{_seatbelt_literal_quote(path)}"))')
        profile.append(f'(deny file-write* (literal "{_seatbelt_literal_quote(path)}"))')
    return "\n".join(profile)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _write_record(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def _validate_model_role(*, model: str, reviewer_role: str) -> None:
    expected_role = MODEL_ROLES.get(model)
    if expected_role != reviewer_role:
        allowed = ", ".join(f"{allowed_model}/{role}" for allowed_model, role in MODEL_ROLES.items())
        raise CleanroomError(f"invalid model/reviewer role combination; allowed: {allowed}")


def _validate_isolation_mode(*, isolation_mode: str, platform_name: str) -> None:
    if isolation_mode not in ISOLATION_MODES:
        raise CleanroomError(f"unsupported isolation mode: {isolation_mode}")
    if isolation_mode == "os-enforced" and platform_name != "Darwin":
        raise CleanroomError(
            "os-enforced cleanroom requires Darwin; use explicit logical-audited mode only when appropriate",
            code="isolation_unavailable",
        )


def _prepare_prior_review_inputs(
    prior_result_paths: Sequence[Path], *, reviewer_role: str, run_dir: Path, repo_root: Path
) -> tuple[tuple[Path, ...], list[dict[str, str]]]:
    if prior_result_paths and reviewer_role != "adjudicator":
        raise CleanroomError("prior reviewer results are allowed only for the sol adjudicator")
    copied_paths: list[Path] = []
    records: list[dict[str, str]] = []
    inputs_dir = run_dir / "adjudication-inputs"
    for index, source in enumerate(prior_result_paths, start=1):
        source = Path(source)
        _require_regular_file(source, label="prior reviewer result")
        _require_outside_repo(source, repo_root, label="prior reviewer result")
        destination = inputs_dir / f"reviewer-{index:02d}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        copied_paths.append(destination)
        records.append({"source_path": str(source.absolute()), "sha256": _sha256(destination), "copied_name": destination.name})
    return tuple(copied_paths), records


def launch_cleanroom(
    package: CleanroomPackage,
    *,
    results_root: Path,
    repo_root: Path,
    runner: Runner = subprocess.run,
    platform_name: str | None = None,
    model: str = MODEL,
    reviewer_role: str = "reviewer",
    isolation_mode: str = "os-enforced",
    prior_result_paths: Sequence[Path] = (),
) -> CleanroomLaunch:
    """Launch a validated package; the model output and execution record never enter it."""
    _validate_model_role(model=model, reviewer_role=reviewer_role)
    platform_name = platform_name or platform.system()
    _validate_isolation_mode(isolation_mode=isolation_mode, platform_name=platform_name)
    repo_root = repo_root.resolve()
    results_root = results_root.resolve()
    _require_outside_repo(results_root, repo_root, label="results root")
    if _is_within(results_root, package.case_dir) or _is_within(package.case_dir, results_root):
        raise CleanroomError("results root must be separate from the cleanroom")
    package_hashes = revalidate_cleanroom(package)
    case = _load_json(package.case_dir / "qa-case.json", label="qa case")
    frozen_packet = _load_json(package.case_dir / "frozen-packet.json", label="frozen fact/evidence packet")
    executable = resolve_codex_executable()
    if _is_within(executable.symlink_path, repo_root) or _is_within(executable.resolved_path, repo_root):
        raise CleanroomError("Codex CLI must be outside the original repository")
    auth_sources = _codex_auth_paths()
    runtime_helpers = _codex_runtime_helpers(executable)
    run_seed = f"{package.case_id}:{_utc_now()}:{os.getpid()}".encode("utf-8")
    run_id = hashlib.sha256(run_seed).hexdigest()[:16]
    run_dir = results_root / package.case_id / run_id
    model_output_path = run_dir / "model-output.json"
    record_path = run_dir / "execution.json"
    run_dir.mkdir(parents=True, exist_ok=False)
    adjudication_inputs, prior_input_records = _prepare_prior_review_inputs(
        prior_result_paths, reviewer_role=reviewer_role, run_dir=run_dir, repo_root=repo_root
    )
    auth_paths, codex_home, runtime_tmp = _stage_codex_runtime_paths(auth_sources, run_dir=run_dir)
    prompt = _wrapped_prompt(case, frozen_packet, adjudication_input_paths=adjudication_inputs)
    codex_argv = [
        str(executable.resolved_path),
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--sandbox",
        "danger-full-access" if isolation_mode == "os-enforced" else "read-only",
        "--cd",
        str(package.case_dir),
        "--model",
        model,
        "--output-schema",
        str(package.case_dir / "qa-result.schema.json"),
        "--json",
        "--output-last-message",
        str(model_output_path),
        prompt,
    ]
    argv: list[str]
    if isolation_mode == "os-enforced":
        profile = macos_seatbelt_profile(
            repo_root=repo_root,
            case_dir=package.case_dir,
            results_root=run_dir,
            executable=executable,
            denied_prior_result_paths=tuple(Path(path) for path in prior_result_paths),
            allowed_auth_paths=auth_paths,
            allowed_process_paths=runtime_helpers,
        )
        argv = ["sandbox-exec", "-p", profile, *codex_argv]
    else:
        argv = codex_argv
    record: dict[str, Any] = {
        "format": "serenity-cleanroom-execution/1",
        "case_id": package.case_id,
        "executed_at": _utc_now(),
        "cli": executable.requested_cli,
        "requested_cli": executable.requested_cli,
        "resolved_cli_path": str(executable.resolved_path),
        "model": model,
        "reviewer_role": reviewer_role,
        "argv": argv,
        "package_sha256": package_hashes,
        "prior_reviewer_inputs": prior_input_records,
        "prompt_wrapper": {
            "version": PROMPT_WRAPPER_VERSION,
            "wrapper_sha256": _sha256_text(PROMPT_WRAPPER),
            "original_task_sha256": _sha256_text(case["prompt"]),
            "wrapped_prompt_sha256": _sha256_text(prompt),
        },
        "os_isolation": {
            "platform": platform_name,
            "mode": isolation_mode,
            "seatbelt": "outer-macos-seatbelt-broad-fs-deny-exact-allow" if isolation_mode == "os-enforced" else "not_available",
            "inner_codex_sandbox": "danger-full-access (disabled to avoid nested macOS seatbelt; outer seatbelt blocks child process execution)" if isolation_mode == "os-enforced" else "read-only",
            "network_policy": "--search is absent; every completed transcript tool event is rejected; outer seatbelt allows provider transport only in the parent Codex process and blocks child process execution",
            "filesystem_policy": "outer seatbelt denies broad home and temporary storage, allowing only the active case, current result directory, resolved Codex runtime, and exact auth files",
            "allowed_auth_paths": [str(path) for path in auth_paths],
            "auth_material": "ephemeral run-local auth copy is removed after the Codex process exits",
            "allowed_process_paths": [str(executable.resolved_path), *(str(path) for path in runtime_helpers)],
            "denied_paths": [str(repo_root), *(str(Path(path).absolute()) for path in prior_result_paths)] if isolation_mode == "os-enforced" else [],
            "residual_surface": (
                "The outer seatbelt proves the recorded broad home/temp/repository denials, exact filesystem/process allowances, and child-exec denial; hosted provider transport remains in the parent Codex process."
                if isolation_mode == "os-enforced"
                else "Logical-audited mode has no OS filesystem enforcement."
            ),
        },
    }
    try:
        completed = runner(
            argv,
            cwd=package.case_dir,
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "CODEX_HOME": str(codex_home), "TMPDIR": str(runtime_tmp), "TMP": str(runtime_tmp), "TEMP": str(runtime_tmp)},
        )
    except PermissionError as exc:
        record["status"] = "sandbox_denied"
        record["error"] = str(exc)
        _write_record(record_path, record)
        if exc.errno == errno.EPERM:
            raise CleanroomError("sandbox denied original repository access", code="isolation_violation") from exc
        raise CleanroomError(f"cleanroom process permission failure: {exc}", code="isolation_violation") from exc
    except OSError as exc:
        record["status"] = "launch_failed"
        record["error"] = str(exc)
        _write_record(record_path, record)
        raise CleanroomError(f"cleanroom process could not launch: {exc}", code="isolation_unavailable") from exc
    finally:
        _remove_staged_codex_runtime_paths(codex_home=codex_home, runtime_tmp=runtime_tmp)
    record["returncode"] = completed.returncode
    record["stdout"] = completed.stdout
    record["stderr"] = completed.stderr
    if completed.returncode != 0:
        record["status"] = "failed"
        _write_record(record_path, record)
        raise CleanroomError(f"codex cleanroom run failed with exit code {completed.returncode}", code="isolation_unavailable")
    try:
        transcript_audit = _audit_transcript(
            completed.stdout,
            case_dir=package.case_dir,
            repo_root=repo_root,
            approved_adjudication_paths=adjudication_inputs,
        )
    except CleanroomError as exc:
        record["status"] = "invalid_transcript"
        record["transcript_audit"] = {"error": str(exc)}
        _write_record(record_path, record)
        raise
    record["transcript_audit"] = {
        "command_count": transcript_audit.command_count,
        "tool_event_count": transcript_audit.tool_event_count,
        "successful_packet_reads": transcript_audit.successful_packet_reads,
        "forbidden_path_commands": transcript_audit.forbidden_path_commands,
        "network_or_search_commands": transcript_audit.network_or_search_commands,
        "unapproved_command_tools": transcript_audit.unapproved_command_tools,
    }
    if not model_output_path.is_file() or model_output_path.is_symlink():
        record["status"] = "missing_output"
        _write_record(record_path, record)
        raise CleanroomError("codex cleanroom run did not produce a regular output file", code="invalid_reviewer_output")
    result = _load_json(model_output_path, label="qa result")
    result_schema = _load_json(package.case_dir / "qa-result.schema.json", label="qa result schema")
    errors = list(Draft202012Validator(result_schema).iter_errors(result))
    if errors:
        record["status"] = "invalid_output"
        record["validation_error"] = errors[0].message
        _write_record(record_path, record)
        raise CleanroomError(
            f"codex cleanroom result does not match qa-result schema: {errors[0].message}",
            code="invalid_reviewer_output",
        )
    try:
        _validate_result_semantics(result, expected_invariants=case["expected_invariants"])
    except CleanroomError as exc:
        record["status"] = "invalid_output"
        record["validation_error"] = str(exc)
        _write_record(record_path, record)
        raise
    record["status"] = "completed"
    record["model_output_sha256"] = _sha256(model_output_path)
    _write_record(record_path, record)
    return CleanroomLaunch(model_output_path=model_output_path, record_path=record_path)
