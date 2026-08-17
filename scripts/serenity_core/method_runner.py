"""Launch one blinded method packet in a filesystem-isolated Codex case."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from jsonschema import Draft202012Validator


METHOD_OUTPUT_SCHEMA_ID = "urn:serenity:schema:method-coding-output:1"
METHOD_SYNTHESIS_SCHEMA_ID = "urn:serenity:schema:method-claim-synthesis:1"
MODEL = "gpt-5.6-terra"
ROLE = "blind_open_coder"
SYNTHESIS_MODEL = "gpt-5.6-sol"
SYNTHESIS_ROLE = "final_method_synthesizer"
ISOLATION_MODES = ("os-enforced", "logical-audited")
_PACKET_NAME = re.compile(r"packet-[A-Za-z0-9][A-Za-z0-9._-]*\.json$")
_HEX = re.compile(r"[0-9a-f]{64}$")
_READ_FAILURE_NOTE = re.compile(r"(?:operation(?:[- ]not)?[- ]permitted|permission denied|access denied|inaccessible|unavailable|cannot read|unable to read|read error)", re.IGNORECASE)
_AXES = frozenset(
    {
        "observation_type", "causal_hop", "value_capture", "identity_provenance", "lens", "catalyst_mechanism",
        "funding_capital_structure", "bear_falsifier", "timing_entry", "recommendation_scope", "confidence_hedge",
        "contradiction", "outcome_postmortem",
    }
)
_LEAK_POLICY = {
    "excluded_fields": ["answer_key", "created_at", "date", "ticker"],
    "redactions": {"date": "[DATE]", "ticker": "[TICKER]"},
}
_CASE_FILENAMES = frozenset({"method-coding-output.schema.json", "prompt.json", "package-manifest.json"})
_SYNTHESIS_CASE_FILENAMES = frozenset({"method-claim-synthesis.schema.json", "prompt.json", "package-manifest.json"})
_FORBIDDEN_PARTS = frozenset({"claude.md", "agents.md", ".claude", ".codex", "data", "sessions", "results", "scores", "verdicts"})


class MethodRunnerError(RuntimeError):
    """A method coding case is invalid, exposed, or cannot be launched safely."""


@dataclass(frozen=True)
class MethodCase:
    packet_id: str
    case_dir: Path
    package_hashes: dict[str, str]


@dataclass(frozen=True)
class MethodLaunch:
    model_output_path: Path
    record_path: Path


@dataclass(frozen=True)
class MethodSynthesisCase:
    candidate_digest_content_hash: str
    candidate_digest_sha256: str
    case_dir: Path
    package_hashes: dict[str, str]


@dataclass(frozen=True)
class MethodSynthesisLaunch:
    model_output_path: Path
    record_path: Path


@dataclass(frozen=True)
class CodexExecutable:
    requested_cli: str
    resolved_path: Path
    read_paths: tuple[Path, ...]


Runner = Callable[..., Any]


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _document_hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical({key: item for key, item in value.items() if key != "content_hash"}).encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MethodRunnerError(f"{label} must be readable JSON: {path}") from exc
    if not isinstance(value, dict):
        raise MethodRunnerError(f"{label} must be a JSON object: {path}")
    return value


def _require_regular_file(path: Path, *, label: str) -> None:
    if path.is_symlink():
        raise MethodRunnerError(f"{label} must not be a symlink: {path}")
    if not path.is_file():
        raise MethodRunnerError(f"{label} must be a regular file: {path}")


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _require_outside_repo(path: Path, repo_root: Path, *, label: str) -> None:
    if _is_within(path, repo_root):
        raise MethodRunnerError(f"{label} must be outside the original repository: {path}")


def _forbidden_path(path: Path) -> str | None:
    return next((part for part in path.parts if part.casefold() in _FORBIDDEN_PARTS), None)


def _validate_packet(packet: Mapping[str, Any], *, packet_name: str) -> list[str]:
    if not _PACKET_NAME.fullmatch(packet_name):
        raise MethodRunnerError(f"packet filename must match packet-*.json: {packet_name}")
    if packet.get("format") != "serenity-method-blind-packet/1":
        raise MethodRunnerError("packet uses an unsupported format")
    if packet.get("leak_policy") != _LEAK_POLICY:
        raise MethodRunnerError("packet does not use the fixed blind leak policy")
    if not isinstance(packet.get("source_index_hash"), str) or _HEX.fullmatch(packet["source_index_hash"]) is None:
        raise MethodRunnerError("packet requires a source index SHA-256")
    if packet.get("content_hash") != _document_hash(packet):
        raise MethodRunnerError("packet content_hash does not match canonical content")
    chunks = packet.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        raise MethodRunnerError("packet must contain at least one chunk")
    chunk_ids: list[str] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            raise MethodRunnerError("packet chunk must be an object")
        chunk_id = chunk.get("chunk_id")
        if not isinstance(chunk_id, str) or not chunk_id:
            raise MethodRunnerError("packet chunk requires chunk_id")
        if chunk_id in chunk_ids:
            raise MethodRunnerError("packet cannot repeat chunk_id")
        if chunk.get("kind") not in {"text", "media"} or not isinstance(chunk.get("text"), str) or not chunk["text"].strip():
            raise MethodRunnerError("packet chunk requires a non-empty blind text and supported kind")
        if not isinstance(chunk.get("source_refs"), list) or not chunk["source_refs"]:
            raise MethodRunnerError("packet chunk requires source references")
        if not isinstance(chunk.get("source_hash"), str) or _HEX.fullmatch(chunk["source_hash"]) is None:
            raise MethodRunnerError("packet chunk requires a source SHA-256")
        chunk_ids.append(chunk_id)
    return chunk_ids


def _validate_output_schema(schema_path: Path) -> None:
    _require_regular_file(schema_path, label="method coding output schema")
    schema = _load_json(schema_path, label="method coding output schema")
    if schema.get("$id") != METHOD_OUTPUT_SCHEMA_ID:
        raise MethodRunnerError(f"unexpected method coding output schema: {schema_path}")
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        raise MethodRunnerError(f"method coding output schema is invalid: {exc}") from exc


def _prompt(packet_id: str, packet_sha256: str, chunk_ids: Sequence[str]) -> str:
    expected_ids = ", ".join(chunk_ids)
    return (
        "You are an independent blind open coder. Work only from the single packet in this directory. "
        "Do not inspect, search for, or infer any existing methodology, verdict, ranking, repository material, or external context. "
        f"First read ./{packet_id}.json using the available local file or shell tool; it is present and is the complete evidence boundary. Do not claim it is unavailable unless that exact read returns an error. "
        f"Then emit one disposition for each of these {len(chunk_ids)} chunk IDs in this exact packet order: {expected_ids}. "
        f"Set packet_id to exactly {packet_id} and packet_sha256 to exactly {packet_sha256}. "
        "For each chunk choose coded only when it contains a reusable analytical move; otherwise choose no_reusable_move. "
        "A coded item must state trigger, evidence sought, inference, action and horizon, falsifier, and one or more codes using only the schema axes. "
        "Always state uncertainty and contradiction notes explicitly; use an empty list when none are observed. Return only schema-valid JSON."
    )


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical(value) + "\n", encoding="utf-8")


def _validate_case_tree(case_dir: Path, *, expected_hashes: dict[str, str] | None = None) -> dict[str, str]:
    if case_dir.is_symlink() or not case_dir.is_dir():
        raise MethodRunnerError(f"method case must be a real directory: {case_dir}")
    entries = list(case_dir.iterdir())
    for entry in entries:
        forbidden = _forbidden_path(entry.relative_to(case_dir))
        if forbidden is not None:
            raise MethodRunnerError(f"method case contains forbidden path: {forbidden}")
        _require_regular_file(entry, label="method case file")
    packet_entries = [entry.name for entry in entries if _PACKET_NAME.fullmatch(entry.name)]
    if len(packet_entries) != 1 or {entry.name for entry in entries} != _CASE_FILENAMES | set(packet_entries):
        raise MethodRunnerError("method case allowlist violation")
    names = set(_CASE_FILENAMES) | set(packet_entries)
    hashes = {name: _sha256(case_dir / name) for name in names}
    if expected_hashes is not None and hashes != expected_hashes:
        raise MethodRunnerError("method case hash mismatch after package creation")
    packet_name = packet_entries[0]
    packet = _load_json(case_dir / packet_name, label="packet")
    chunk_ids = _validate_packet(packet, packet_name=packet_name)
    _validate_output_schema(case_dir / "method-coding-output.schema.json")
    prompt = _load_json(case_dir / "prompt.json", label="prompt metadata")
    if prompt.get("format") != "serenity-method-coding-prompt/1" or prompt.get("packet_id") != Path(packet_name).stem:
        raise MethodRunnerError("prompt metadata has an invalid contract")
    if prompt.get("chunk_ids") != chunk_ids or prompt.get("chunk_count") != len(chunk_ids):
        raise MethodRunnerError("prompt metadata does not enumerate packet chunks exactly")
    if prompt.get("packet_sha256") != hashes[packet_name] or prompt.get("schema_sha256") != hashes["method-coding-output.schema.json"]:
        raise MethodRunnerError("prompt metadata hash mismatch")
    if not isinstance(prompt.get("prompt"), str) or not prompt["prompt"].strip() or prompt.get("content_hash") != _document_hash(prompt):
        raise MethodRunnerError("prompt metadata content hash mismatch")
    manifest = _load_json(case_dir / "package-manifest.json", label="package manifest")
    if manifest.get("format") != "serenity-method-coding-case/1" or manifest.get("packet_id") != Path(packet_name).stem:
        raise MethodRunnerError("package manifest has an invalid contract")
    listed = manifest.get("payload_sha256")
    payload_names = names - {"package-manifest.json"}
    if not isinstance(listed, dict) or set(listed) != payload_names or any(listed[name] != hashes[name] for name in payload_names):
        raise MethodRunnerError("package manifest hash mismatch")
    if manifest.get("content_hash") != _document_hash(manifest):
        raise MethodRunnerError("package manifest content hash mismatch")
    return hashes


def build_method_case(*, packet_path: Path, output_schema_path: Path, case_root: Path, repo_root: Path) -> MethodCase:
    """Copy one already blinded packet to a newly created, strict outside-repository case."""
    packet_path, output_schema_path, case_root, repo_root = map(Path, (packet_path, output_schema_path, case_root, repo_root))
    packet_path = packet_path.resolve()
    output_schema_path = output_schema_path.resolve()
    case_root = case_root.resolve()
    repo_root = repo_root.resolve()
    _require_outside_repo(case_root, repo_root, label="case root")
    _require_regular_file(packet_path, label="packet")
    _validate_output_schema(output_schema_path)
    packet = _load_json(packet_path, label="packet")
    chunk_ids = _validate_packet(packet, packet_name=packet_path.name)
    if not chunk_ids:
        raise MethodRunnerError("packet must contain chunks")
    packet_id = packet_path.stem
    source_hash = _sha256(packet_path)
    case_dir = case_root / f"{packet_id}-{source_hash[:12]}"
    if _forbidden_path(case_dir.relative_to(case_root)) is not None:
        raise MethodRunnerError("packet name creates a forbidden case path")
    try:
        case_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise MethodRunnerError(f"method case already exists: {case_dir}") from exc
    try:
        packet_name = packet_path.name
        shutil.copyfile(packet_path, case_dir / packet_name)
        shutil.copyfile(output_schema_path, case_dir / "method-coding-output.schema.json")
        prompt = {"format": "serenity-method-coding-prompt/1", "packet_id": packet_id, "packet_sha256": _sha256(case_dir / packet_name), "schema_sha256": _sha256(case_dir / "method-coding-output.schema.json"), "chunk_ids": chunk_ids, "chunk_count": len(chunk_ids)}
        prompt["prompt"] = _prompt(packet_id, prompt["packet_sha256"], chunk_ids)
        prompt["content_hash"] = _document_hash(prompt)
        _write_json(case_dir / "prompt.json", prompt)
        payload_names = (packet_name, "method-coding-output.schema.json", "prompt.json")
        manifest = {"format": "serenity-method-coding-case/1", "packet_id": packet_id, "payload_sha256": {name: _sha256(case_dir / name) for name in payload_names}}
        manifest["content_hash"] = _document_hash(manifest)
        _write_json(case_dir / "package-manifest.json", manifest)
        hashes = _validate_case_tree(case_dir)
    except Exception:
        shutil.rmtree(case_dir, ignore_errors=True)
        raise
    return MethodCase(packet_id=packet_id, case_dir=case_dir, package_hashes=hashes)


def revalidate_method_case(package: MethodCase) -> dict[str, str]:
    """Reject changed, extra, forbidden, or linked files immediately before execution."""
    return _validate_case_tree(package.case_dir, expected_hashes=package.package_hashes)


def _validate_synthesis_output_schema(schema_path: Path) -> None:
    _require_regular_file(schema_path, label="method claim synthesis schema")
    schema = _load_json(schema_path, label="method claim synthesis schema")
    if schema.get("$id") != METHOD_SYNTHESIS_SCHEMA_ID:
        raise MethodRunnerError(f"unexpected method claim synthesis schema: {schema_path}")
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        raise MethodRunnerError(f"method claim synthesis schema is invalid: {exc}") from exc


def _shown_candidate_digest_refs(digest: Mapping[str, Any]) -> tuple[set[str], set[tuple[str, str]]]:
    if digest.get("format") != "serenity-method-candidate-digest/1" or digest.get("content_hash") != _document_hash(digest):
        raise MethodRunnerError("candidate digest content hash mismatch")
    summary = digest.get("bounded_summary")
    if not isinstance(summary, dict):
        raise MethodRunnerError("candidate digest requires a bounded summary")
    units: set[str] = set()
    codes: set[tuple[str, str]] = set()
    frequency = summary.get("axis_label_frequency")
    if not isinstance(frequency, list):
        raise MethodRunnerError("candidate digest requires shown axis labels")
    for axis_entry in frequency:
        if not isinstance(axis_entry, dict) or not isinstance(axis_entry.get("entries"), list):
            raise MethodRunnerError("candidate digest axis labels are invalid")
        for entry in axis_entry["entries"]:
            if not isinstance(entry, dict) or not isinstance(entry.get("representatives"), list):
                raise MethodRunnerError("candidate digest representatives are invalid")
            for representative in entry["representatives"]:
                if not isinstance(representative, dict) or not isinstance(representative.get("unit_id"), str):
                    raise MethodRunnerError("candidate digest representative requires unit_id")
                semantic = representative.get("semantic_content")
                matching = semantic.get("matching_code") if isinstance(semantic, dict) else None
                if not isinstance(matching, dict) or not isinstance(matching.get("axis"), str) or not isinstance(matching.get("label"), str):
                    raise MethodRunnerError("candidate digest representative requires shown matching code")
                units.add(representative["unit_id"])
                codes.add((matching["axis"], matching["label"]))
    for section_name in ("counterexample_refs", "contradiction_refs", "uncertainty_refs"):
        section = summary.get(section_name)
        entries = section.get("entries") if isinstance(section, dict) else None
        if not isinstance(entries, list):
            raise MethodRunnerError(f"candidate digest requires shown {section_name}")
        for entry in entries:
            if not isinstance(entry, dict):
                raise MethodRunnerError(f"candidate digest {section_name} entry is invalid")
            for value in (entry.get("unit_id"), entry.get("counterexample", {}).get("unit_id") if isinstance(entry.get("counterexample"), dict) else None):
                if isinstance(value, str):
                    units.add(value)
    if not units or not codes:
        raise MethodRunnerError("candidate digest does not expose shown unit and code references")
    return units, codes


def _synthesis_prompt(digest_content_hash: str, digest_sha256: str) -> str:
    return (
        "You are the single final method synthesizer. Work only from the one candidate digest in this directory. "
        "Do not inspect, search for, or infer CLAUDE, AGENTS, .claude, .codex, data, sessions, coding artifacts, source indexes, prior results, repository material, or external context. "
        "First read ./candidate-digest.json using the available local file or shell tool; it is present and is the complete evidence boundary. "
        "Do not claim it is unavailable unless that exact read returns an error. "
        f"Set candidate_digest_content_hash to exactly {digest_content_hash} and candidate_digest_sha256 to exactly {digest_sha256}. "
        "Return only final claims tagged sourced or unverified. Never invent augmented engineering claims. "
        "Every sourced claim must use shown unit and shown code references, plus actual shown counterexample references or an exact none_found scope and status. "
        "Every claim must preserve why, uncertainty notes, and contradiction notes. Return only schema-valid JSON."
        " Treat digest policy, coverage, and omitted counts honestly; never infer omitted semantics or upgrade frequency or representativeness. "
        "Synthesize reusable principles and interfaces across the shown canonical axes, not ticker, name, or example-specific calls, fixed thresholds, voice imitation, portfolio sizing, or a frozen pipeline rail. "
        "Where shown, preserve trigger → evidence sought → inference → action/horizon → falsifier semantics. "
        "Mark thin evidence unverified, and use shown contradictions and counterexamples. "
        "Keep claims dense and nonduplicative and cover materially supported dimensions rather than emitting one generic claim."
    )


def _validate_synthesis_case_tree(case_dir: Path, *, expected_hashes: dict[str, str] | None = None) -> tuple[dict[str, str], dict[str, Any]]:
    if case_dir.is_symlink() or not case_dir.is_dir():
        raise MethodRunnerError(f"method synthesis case must be a real directory: {case_dir}")
    entries = list(case_dir.iterdir())
    for entry in entries:
        forbidden = _forbidden_path(entry.relative_to(case_dir))
        if forbidden is not None:
            raise MethodRunnerError(f"method synthesis case contains forbidden path: {forbidden}")
        _require_regular_file(entry, label="method synthesis case file")
    names = set(_SYNTHESIS_CASE_FILENAMES) | {"candidate-digest.json"}
    if {entry.name for entry in entries} != names:
        raise MethodRunnerError("method synthesis case allowlist violation")
    hashes = {name: _sha256(case_dir / name) for name in names}
    if expected_hashes is not None and hashes != expected_hashes:
        raise MethodRunnerError("method synthesis case hash mismatch after package creation")
    digest = _load_json(case_dir / "candidate-digest.json", label="candidate digest")
    _shown_candidate_digest_refs(digest)
    _validate_synthesis_output_schema(case_dir / "method-claim-synthesis.schema.json")
    prompt = _load_json(case_dir / "prompt.json", label="synthesis prompt metadata")
    if prompt.get("format") != "serenity-method-claim-synthesis-prompt/1" or prompt.get("candidate_digest_content_hash") != digest.get("content_hash") or prompt.get("candidate_digest_sha256") != hashes["candidate-digest.json"] or not isinstance(prompt.get("prompt"), str) or prompt.get("content_hash") != _document_hash(prompt):
        raise MethodRunnerError("synthesis prompt metadata has an invalid contract")
    manifest = _load_json(case_dir / "package-manifest.json", label="synthesis package manifest")
    payload_names = names - {"package-manifest.json"}
    if manifest.get("format") != "serenity-method-claim-synthesis-case/1" or manifest.get("payload_sha256") != {name: hashes[name] for name in payload_names} or manifest.get("content_hash") != _document_hash(manifest):
        raise MethodRunnerError("synthesis package manifest hash mismatch")
    return hashes, digest


def build_method_synthesis_case(*, candidate_digest_path: Path, output_schema_path: Path, case_root: Path, repo_root: Path) -> MethodSynthesisCase:
    """Copy only a hash-valid bounded candidate digest into a new final synthesis case."""
    candidate_digest_path, output_schema_path, case_root, repo_root = map(Path, (candidate_digest_path, output_schema_path, case_root, repo_root))
    candidate_digest_path, output_schema_path, case_root, repo_root = candidate_digest_path.resolve(), output_schema_path.resolve(), case_root.resolve(), repo_root.resolve()
    _require_outside_repo(case_root, repo_root, label="case root")
    _require_regular_file(candidate_digest_path, label="candidate digest")
    _validate_synthesis_output_schema(output_schema_path)
    digest = _load_json(candidate_digest_path, label="candidate digest")
    _shown_candidate_digest_refs(digest)
    source_hash = _sha256(candidate_digest_path)
    case_dir = case_root / f"method-synthesis-{source_hash[:12]}"
    try:
        case_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise MethodRunnerError(f"method synthesis case already exists: {case_dir}") from exc
    try:
        shutil.copyfile(candidate_digest_path, case_dir / "candidate-digest.json")
        shutil.copyfile(output_schema_path, case_dir / "method-claim-synthesis.schema.json")
        prompt = {"format": "serenity-method-claim-synthesis-prompt/1", "candidate_digest_content_hash": digest["content_hash"], "candidate_digest_sha256": _sha256(case_dir / "candidate-digest.json")}
        prompt["prompt"] = _synthesis_prompt(prompt["candidate_digest_content_hash"], prompt["candidate_digest_sha256"])
        prompt["content_hash"] = _document_hash(prompt)
        _write_json(case_dir / "prompt.json", prompt)
        payload_names = ("candidate-digest.json", "method-claim-synthesis.schema.json", "prompt.json")
        manifest = {"format": "serenity-method-claim-synthesis-case/1", "payload_sha256": {name: _sha256(case_dir / name) for name in payload_names}}
        manifest["content_hash"] = _document_hash(manifest)
        _write_json(case_dir / "package-manifest.json", manifest)
        hashes, copied_digest = _validate_synthesis_case_tree(case_dir)
    except Exception:
        shutil.rmtree(case_dir, ignore_errors=True)
        raise
    return MethodSynthesisCase(candidate_digest_content_hash=copied_digest["content_hash"], candidate_digest_sha256=hashes["candidate-digest.json"], case_dir=case_dir, package_hashes=hashes)


def revalidate_method_synthesis_case(package: MethodSynthesisCase) -> dict[str, str]:
    hashes, digest = _validate_synthesis_case_tree(package.case_dir, expected_hashes=package.package_hashes)
    if digest.get("content_hash") != package.candidate_digest_content_hash or hashes["candidate-digest.json"] != package.candidate_digest_sha256:
        raise MethodRunnerError("method synthesis case candidate digest binding mismatch")
    return hashes


def _seatbelt_quote(path: Path) -> str:
    return str(path.resolve()).replace("\\", "\\\\").replace('"', '\\"')


def resolve_codex_executable(requested_cli: str | Path | None = None) -> CodexExecutable:
    """Resolve the executable before sandboxing so deny-default cannot break PATH lookup."""
    requested = "codex" if requested_cli is None else str(requested_cli)
    located = shutil.which(requested)
    candidate = Path(located) if located is not None else Path(requested).expanduser()
    if not candidate.is_absolute():
        candidate = candidate.absolute()
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise MethodRunnerError(f"Codex executable could not be resolved: {requested}") from exc
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise MethodRunnerError(f"Codex executable is not an executable regular file: {resolved}")
    read_paths = tuple(sorted({candidate.parent.resolve(), resolved.parent}, key=str))
    return CodexExecutable(requested_cli=requested, resolved_path=resolved, read_paths=read_paths)


def macos_method_seatbelt_profile(*, repo_root: Path, case_dir: Path, results_root: Path, executable: CodexExecutable) -> str:
    """Preserve Codex's macOS runtime surface while enforcing an OS-level repository deny."""
    profile = ["(version 1)", "(allow default)"]
    profile.append(f'(deny file-read* (subpath "{_seatbelt_quote(repo_root)}"))')
    profile.append(f'(deny file-write* (subpath "{_seatbelt_quote(repo_root)}"))')
    return "\n".join(profile)


def macos_synthesis_seatbelt_profile(*, repo_root: Path, prior_result_paths: Sequence[Path]) -> str:
    """Deny the original repository and every pre-existing result subtree around a Sol synthesis."""
    profile = ["(version 1)", "(allow default)", f'(deny file-read* (subpath "{_seatbelt_quote(repo_root)}"))', f'(deny file-write* (subpath "{_seatbelt_quote(repo_root)}"))']
    for path in prior_result_paths:
        profile.extend((f'(deny file-read* (subpath "{_seatbelt_quote(path)}"))', f'(deny file-write* (subpath "{_seatbelt_quote(path)}"))'))
    return "\n".join(profile)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _reject_unreadable_input(dispositions: Sequence[Mapping[str, Any]]) -> None:
    """Do not mistake mechanically complete fallback rows for a coding pass."""
    if any(item["disposition"] == "coded" for item in dispositions):
        return
    note_sets = [tuple(note.strip() for note in [*item["uncertainty_notes"], *item["contradiction_notes"]] if note.strip()) for item in dispositions]
    if not note_sets or not all(note_sets) or any(notes != note_sets[0] for notes in note_sets[1:]):
        return
    if any(_READ_FAILURE_NOTE.search(note) for note in note_sets[0]):
        raise MethodRunnerError("input_unreadable: every chunk reports the same packet read failure")


def _audit_logical_transcript(transcript: str, *, packet_name: str, repo_root: Path, case_dir: Path, require_only_resource_commands: bool = False) -> dict[str, int]:
    """Require an auditable local packet read and reject any observed boundary escape."""
    tool_events = 0
    read_tool = re.compile(r"\b(?:cat|sed|head|tail|less|more|jq|awk|perl|python(?:3)?)\b", re.IGNORECASE)
    search_or_network = re.compile(r"\b(?:rg|grep|find|locate|mdfind|curl|wget|nc|ssh)\b|https?://", re.IGNORECASE)
    forbidden_target = re.compile(r"(?:^|[\s/'\"])(?:claude(?:\.md)?|agents(?:\.md)?|\.claude|\.codex|data|sessions|coding|source(?:-|_)index|previous(?:-|_)results?)(?:$|[\s/'\"])", re.IGNORECASE)
    absolute_path = re.compile(r"(?<![A-Za-z0-9_.-])(/[^\s'\";|&)]+)")
    shell_executables = {"/bin/sh", "/bin/bash", "/bin/zsh", "/usr/bin/env"}
    event_boundary = re.compile(r'^\{\s*"type"\s*:\s*"item\.(?:started|completed)"')
    completed_command = re.compile(r'^\s*\{\s*"type"\s*:\s*"item\.completed"\s*,\s*"item"\s*:\s*\{\s*"id"\s*:\s*"(?P<id>[^"\\]+)"\s*,\s*"type"\s*:\s*"command_execution"')
    completed_success_tail = re.compile(r',\s*"exit_code"\s*:\s*0\s*,\s*"status"\s*:\s*"completed"\s*\}\s*\}\s*\Z')
    blocks: list[str] = []
    current: list[str] = []
    for line in transcript.splitlines(keepends=True):
        if event_boundary.match(line) and current:
            blocks.append("".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append("".join(current))
    packet_read_starts: set[str] = set()
    packet_read_completions: set[str] = set()
    observed_command_ids: set[str] = set()

    def audit_command(command: str, command_id: str | None) -> bool:
        nonlocal tool_events
        if command_id is None or command_id not in observed_command_ids:
            tool_events += 1
            if command_id is not None:
                observed_command_ids.add(command_id)
        if search_or_network.search(command):
            raise MethodRunnerError("forbidden_read_observed: transcript contains a search or network command")
        if re.search(r"(?:^|[\s/])\.\.(?:[\s/]|$)", command):
            raise MethodRunnerError("forbidden_read_observed: transcript contains parent traversal")
        if read_tool.search(command):
            if str(repo_root).casefold() in command.casefold() or forbidden_target.search(command):
                raise MethodRunnerError("forbidden_read_observed: transcript reads a forbidden target")
            for raw_path in absolute_path.findall(command):
                candidate = raw_path.rstrip(".,:")
                if candidate == "//":
                    continue
                if candidate in shell_executables:
                    continue
                if not _is_within(Path(candidate), case_dir):
                    raise MethodRunnerError("forbidden_read_observed: transcript reads outside the case")
        is_packet_read = packet_name in command and read_tool.search(command) is not None
        if require_only_resource_commands and not is_packet_read:
            raise MethodRunnerError("forbidden_read_observed: transcript command is outside the candidate digest evidence boundary")
        return is_packet_read

    for block in blocks:
        try:
            event = json.loads(block)
        except json.JSONDecodeError:
            completed = completed_command.match(block)
            if completed is not None and completed_success_tail.search(block) and completed.group("id") in packet_read_starts:
                packet_read_completions.add(completed.group("id"))
            continue
        item = event.get("item") if isinstance(event, dict) else None
        if not isinstance(item, dict) or item.get("type") != "command_execution":
            continue
        command = item.get("command")
        command_id = item.get("id") if isinstance(item.get("id"), str) else None
        if not isinstance(command, str):
            continue
        is_packet_read = audit_command(command, command_id)
        if event.get("type") == "item.started" and command_id is not None and is_packet_read:
            packet_read_starts.add(command_id)
        if event.get("type") == "item.completed" and item.get("exit_code") == 0 and item.get("status") == "completed" and is_packet_read:
            packet_read_completions.add(command_id or command)
    if tool_events == 0 or not packet_read_completions:
        raise MethodRunnerError("input_unreadable: transcript does not prove a successful packet read")
    return {"tool_events": tool_events, "packet_read_events": len(packet_read_completions), "forbidden_read_events": 0}


def _validate_model_output(path: Path, *, package: MethodCase, packet_sha256: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise MethodRunnerError("codex method coding run did not produce a regular output file")
    result = _load_json(path, label="method coding output")
    schema = _load_json(package.case_dir / "method-coding-output.schema.json", label="method coding output schema")
    errors = list(Draft202012Validator(schema).iter_errors(result))
    if errors:
        raise MethodRunnerError(f"method coding output does not match schema: {errors[0].message}")
    if result.get("packet_id") != package.packet_id or result.get("packet_sha256") != packet_sha256:
        raise MethodRunnerError("method coding output packet hash mismatch")
    packet_name = next(entry.name for entry in package.case_dir.iterdir() if _PACKET_NAME.fullmatch(entry.name))
    expected_ids = _validate_packet(_load_json(package.case_dir / packet_name, label="packet"), packet_name=packet_name)
    observed_ids = [item["chunk_id"] for item in result["dispositions"]]
    if len(observed_ids) != len(set(observed_ids)) or set(observed_ids) != set(expected_ids):
        raise MethodRunnerError("method coding output coverage does not exactly match packet chunks")
    _reject_unreadable_input(result["dispositions"])
    for item in result["dispositions"]:
        coding = item["coding"]
        if item["disposition"] == "coded":
            if coding is None:
                raise MethodRunnerError("coded disposition requires coding")
            for code in item["coding"]["codes"]:
                if code["axis"] not in _AXES:
                    raise MethodRunnerError("method coding output uses a noncanonical axis")
        elif coding is not None:
            raise MethodRunnerError("no_reusable_move disposition requires null coding")


def _validate_synthesis_output(path: Path, *, package: MethodSynthesisCase) -> None:
    if not path.is_file() or path.is_symlink():
        raise MethodRunnerError("codex method synthesis run did not produce a regular output file")
    result = _load_json(path, label="method claim synthesis output")
    schema = _load_json(package.case_dir / "method-claim-synthesis.schema.json", label="method claim synthesis schema")
    errors = list(Draft202012Validator(schema).iter_errors(result))
    if errors:
        raise MethodRunnerError(f"method claim synthesis output does not match schema: {errors[0].message}")
    if result.get("candidate_digest_content_hash") != package.candidate_digest_content_hash or result.get("candidate_digest_sha256") != package.candidate_digest_sha256:
        raise MethodRunnerError("method claim synthesis output candidate digest binding mismatch")
    digest = _load_json(package.case_dir / "candidate-digest.json", label="candidate digest")
    shown_units, shown_codes = _shown_candidate_digest_refs(digest)
    claim_ids: set[str] = set()
    for claim in result["claims"]:
        if claim["claim_id"] in claim_ids:
            raise MethodRunnerError("method claim synthesis output cannot repeat claim_id")
        claim_ids.add(claim["claim_id"])
        shown_unit_refs = claim["shown_unit_refs"]
        counterexample_refs = claim["counterexample_refs"]
        shown_code_refs = {(item["axis"], item["label"]) for item in claim["shown_code_refs"]}
        if not shown_unit_refs or not set(shown_unit_refs) <= shown_units or not shown_code_refs or not shown_code_refs <= shown_codes:
            raise MethodRunnerError("method claim synthesis refs must be shown by the candidate digest")
        if len(set(shown_unit_refs)) != len(shown_unit_refs) or len(set(counterexample_refs)) != len(counterexample_refs) or len(shown_code_refs) != len(claim["shown_code_refs"]):
            raise MethodRunnerError("method claim synthesis output cannot repeat references")
        if not set(counterexample_refs) <= shown_units or set(counterexample_refs) & set(shown_unit_refs):
            raise MethodRunnerError("method claim synthesis counterexample refs must be shown and distinct")
        if claim["provenance_tag"] == "sourced":
            if counterexample_refs:
                if claim["counterexample_status"] != "found" or not isinstance(claim["counterexample_search_scope"], str) or not claim["counterexample_search_scope"].strip():
                    raise MethodRunnerError("sourced claim counterexamples require found status and scope")
            elif claim["counterexample_status"] != "none_found" or not isinstance(claim["counterexample_search_scope"], str) or not claim["counterexample_search_scope"].strip():
                raise MethodRunnerError("sourced claim without counterexample requires exact none_found scope")
        elif counterexample_refs or claim["counterexample_status"] is not None or claim["counterexample_search_scope"] is not None:
            raise MethodRunnerError("unverified claim cannot present sourced counterexample evidence")


def launch_method_synthesis(package: MethodSynthesisCase, *, results_root: Path, repo_root: Path, runner: Runner = subprocess.run, platform_name: str | None = None, codex_executable: str | Path | None = None, isolation: str = "os-enforced") -> MethodSynthesisLaunch:
    """Launch exactly one final Sol synthesis from an immutable, hash-bound candidate digest."""
    if isolation != "os-enforced":
        raise MethodRunnerError("method synthesis requires os-enforced isolation")
    results_root, repo_root = Path(results_root).resolve(), Path(repo_root).resolve()
    _require_outside_repo(results_root, repo_root, label="results root")
    if _is_within(results_root, package.case_dir) or _is_within(package.case_dir, results_root):
        raise MethodRunnerError("results root must be separate from the method synthesis case")
    package_hashes = revalidate_method_synthesis_case(package)
    synthesis_root = results_root / "method-synthesis"
    synthesis_root.mkdir(parents=True, exist_ok=True)
    prior_result_paths = tuple(entry for entry in results_root.iterdir() if entry != synthesis_root) + tuple(synthesis_root.iterdir())
    run_dir = synthesis_root / uuid.uuid4().hex
    run_dir.mkdir(exist_ok=False)
    model_output_path, record_path, transcript_path = run_dir / "claim-synthesis.json", run_dir / "execution.json", run_dir / "codex-transcript.jsonl"
    executable = resolve_codex_executable(codex_executable)
    prompt = _load_json(package.case_dir / "prompt.json", label="synthesis prompt metadata")["prompt"]
    codex_argv = [str(executable.resolved_path), "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check", "--sandbox", "danger-full-access", "--cd", str(package.case_dir), "--model", SYNTHESIS_MODEL, "--output-schema", str(package.case_dir / "method-claim-synthesis.schema.json"), "--json", "--output-last-message", str(model_output_path), prompt]
    system_name = platform_name or platform.system()
    outer_enforced = system_name == "Darwin"
    argv = ["sandbox-exec", "-p", macos_synthesis_seatbelt_profile(repo_root=repo_root, prior_result_paths=prior_result_paths), *codex_argv] if outer_enforced else codex_argv
    record: dict[str, Any] = {"format": "serenity-method-claim-synthesis-execution/1", "executed_at": _utc_now(), "cli": "codex", "requested_cli": executable.requested_cli, "resolved_cli_path": str(executable.resolved_path), "model": SYNTHESIS_MODEL, "role": SYNTHESIS_ROLE, "single_final_synthesis": True, "broad_fan_out": "forbidden", "isolation_level": "os_enforced", "repo_read_denial": "enforced" if outer_enforced else "unavailable", "prior_results_denied_count": len(prior_result_paths) if outer_enforced else 0, "sandbox_boundary": "macos_outer_repo_and_prior_results_denied__codex_inner_danger_full_access" if outer_enforced else "codex_danger_full_access_without_macos_outer_boundary", "candidate_digest_content_hash": package.candidate_digest_content_hash, "candidate_digest_sha256": package.candidate_digest_sha256, "package_sha256": package_hashes, "argv": argv}
    try:
        completed = runner(argv, cwd=package.case_dir, check=False, capture_output=True, text=True)
    except PermissionError as exc:
        record.update(status="sandbox_denied", error=str(exc))
        _write_json(record_path, record)
        raise MethodRunnerError("synthesis sandbox denied access") from exc
    except OSError as exc:
        record.update(status="launch_failed", error=str(exc))
        _write_json(record_path, record)
        raise MethodRunnerError(f"method synthesis process could not launch: {exc}") from exc
    transcript = completed.stdout or ""
    transcript_path.write_text(transcript, encoding="utf-8")
    record.update(returncode=completed.returncode, stdout=transcript, stderr=completed.stderr, transcript_path=str(transcript_path), transcript_sha256=_sha256(transcript_path))
    if completed.returncode != 0:
        record["status"] = "failed"
        _write_json(record_path, record)
        raise MethodRunnerError(f"codex method synthesis run failed with exit code {completed.returncode}")
    try:
        record["transcript_audit"] = _audit_logical_transcript(transcript, packet_name="candidate-digest.json", repo_root=repo_root, case_dir=package.case_dir, require_only_resource_commands=True)
        _validate_synthesis_output(model_output_path, package=package)
    except MethodRunnerError as exc:
        status = "missing_output" if "did not produce" in str(exc) else "forbidden_read_observed" if str(exc).startswith("forbidden_read_observed:") else "input_unreadable" if str(exc).startswith("input_unreadable:") else "invalid_output"
        record.update(status=status, validation_error=str(exc))
        if status in {"input_unreadable", "forbidden_read_observed"}:
            record.update(review_state="needs_review", blocker="final synthesis transcript did not prove an allowlisted candidate digest read" if status == "input_unreadable" else "final synthesis transcript observed a forbidden read boundary")
        _write_json(record_path, record)
        raise
    record.update(status="completed", output_sha256=_sha256(model_output_path))
    _write_json(record_path, record)
    return MethodSynthesisLaunch(model_output_path=model_output_path, record_path=record_path)


def revalidate_method_synthesis_result(*, case_dir: Path, result_dir: Path, repo_root: Path) -> dict[str, Any]:
    """Read-only validation of an already-produced final synthesis artifact; never relaunches Codex or changes records."""
    case_dir, result_dir, repo_root = Path(case_dir).resolve(), Path(result_dir).resolve(), Path(repo_root).resolve()
    _require_outside_repo(result_dir, repo_root, label="result directory")
    record_path = result_dir / "execution.json"
    output_path = result_dir / "claim-synthesis.json"
    transcript_path = result_dir / "codex-transcript.jsonl"
    for path, label in ((record_path, "synthesis execution record"), (output_path, "method claim synthesis output"), (transcript_path, "Codex transcript")):
        _require_regular_file(path, label=label)
    record = _load_json(record_path, label="synthesis execution record")
    if record.get("format") != "serenity-method-claim-synthesis-execution/1":
        raise MethodRunnerError("synthesis execution record has an invalid format")
    package_hashes = record.get("package_sha256")
    if not isinstance(package_hashes, dict) or not all(isinstance(name, str) and isinstance(value, str) for name, value in package_hashes.items()):
        raise MethodRunnerError("synthesis execution record requires package hashes")
    hashes, digest = _validate_synthesis_case_tree(case_dir, expected_hashes=package_hashes)
    package = MethodSynthesisCase(candidate_digest_content_hash=digest["content_hash"], candidate_digest_sha256=hashes["candidate-digest.json"], case_dir=case_dir, package_hashes=hashes)
    if record.get("candidate_digest_content_hash") != package.candidate_digest_content_hash or record.get("candidate_digest_sha256") != package.candidate_digest_sha256:
        raise MethodRunnerError("synthesis execution record candidate digest binding mismatch")
    transcript_sha256 = _sha256(transcript_path)
    if record.get("transcript_sha256") != transcript_sha256:
        raise MethodRunnerError("synthesis execution record transcript hash mismatch")
    transcript_audit = _audit_logical_transcript(transcript_path.read_text(encoding="utf-8"), packet_name="candidate-digest.json", repo_root=repo_root, case_dir=case_dir, require_only_resource_commands=True)
    _validate_synthesis_output(output_path, package=package)
    output_sha256 = _sha256(output_path)
    if record.get("output_sha256") is not None and record["output_sha256"] != output_sha256:
        raise MethodRunnerError("synthesis execution record output hash mismatch")
    return {"status": "valid", "candidate_digest_content_hash": package.candidate_digest_content_hash, "candidate_digest_sha256": package.candidate_digest_sha256, "package_sha256": hashes, "transcript_audit": transcript_audit, "transcript_sha256": transcript_sha256, "output_sha256": output_sha256}


def launch_method_case(package: MethodCase, *, results_root: Path, repo_root: Path, runner: Runner = subprocess.run, platform_name: str | None = None, codex_executable: str | Path | None = None, isolation: str = "os-enforced", batch_metadata: Mapping[str, Any] | None = None) -> MethodLaunch:
    """Run exact Codex arguments and persist output/metadata outside the immutable case."""
    results_root, repo_root = Path(results_root).resolve(), Path(repo_root).resolve()
    if isolation not in ISOLATION_MODES:
        raise MethodRunnerError(f"unsupported isolation mode: {isolation}")
    _require_outside_repo(results_root, repo_root, label="results root")
    if _is_within(results_root, package.case_dir) or _is_within(package.case_dir, results_root):
        raise MethodRunnerError("results root must be separate from the method case")
    package_hashes = revalidate_method_case(package)
    packet_name = next(name for name in package_hashes if _PACKET_NAME.fullmatch(name))
    packet_sha256 = package_hashes[packet_name]
    prompt = _load_json(package.case_dir / "prompt.json", label="prompt metadata")["prompt"]
    executable = resolve_codex_executable(codex_executable)
    run_dir = results_root / package.packet_id / uuid.uuid4().hex
    run_dir.mkdir(parents=True, exist_ok=False)
    model_output_path, record_path, transcript_path = run_dir / "model-output.json", run_dir / "execution.json", run_dir / "codex-transcript.jsonl"
    codex_argv = [str(executable.resolved_path), "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check", "--sandbox", "read-only", "--cd", str(package.case_dir), "--model", MODEL, "--output-schema", str(package.case_dir / "method-coding-output.schema.json"), "--json", "--output-last-message", str(model_output_path), prompt]
    system_name = platform_name or platform.system()
    outer_enforced = isolation == "os-enforced" and system_name == "Darwin"
    argv = ["sandbox-exec", "-p", macos_method_seatbelt_profile(repo_root=repo_root, case_dir=package.case_dir, results_root=results_root, executable=executable), *codex_argv] if outer_enforced else codex_argv
    record: dict[str, Any] = {"format": "serenity-method-coding-execution/1", "packet_id": package.packet_id, "executed_at": _utc_now(), "cli": "codex", "requested_cli": executable.requested_cli, "resolved_cli_path": str(executable.resolved_path), "model": MODEL, "role": ROLE, "isolation_level": "logical_audited" if isolation == "logical-audited" else "os_enforced", "repo_read_denial": "unavailable" if isolation == "logical-audited" else "enforced" if outer_enforced else "unavailable", "residual_limitation": "Logical auditing is not OS-enforced: original repository read denial is unavailable; transcript checks can only detect observed reads." if isolation == "logical-audited" else None, "sandbox_boundary": "macos_allow_default_with_original_repo_read_write_denied" if outer_enforced else "codex_read_only", "residual_runtime_surface": "macOS allow-default preserves OS, authentication, temporary-file, Keychain, and Mach-service access; the original repository remains explicitly denied" if outer_enforced else None, "argv": argv, "package_sha256": package_hashes}
    if batch_metadata is not None:
        record.update(batch_metadata)
    try:
        completed = runner(argv, cwd=package.case_dir, check=False, capture_output=True, text=True)
    except PermissionError as exc:
        record.update(status="sandbox_denied", error=str(exc))
        _write_json(record_path, record)
        if exc.errno == errno.EPERM:
            raise MethodRunnerError("sandbox denied original repository access") from exc
        raise MethodRunnerError(f"method coding process permission failure: {exc}") from exc
    except OSError as exc:
        record.update(status="launch_failed", error=str(exc))
        _write_json(record_path, record)
        raise MethodRunnerError(f"method coding process could not launch: {exc}") from exc
    transcript = completed.stdout or ""
    transcript_path.write_text(transcript, encoding="utf-8")
    record.update(returncode=completed.returncode, stdout=transcript, stderr=completed.stderr, transcript_path=str(transcript_path), transcript_sha256=_sha256(transcript_path))
    if completed.returncode != 0:
        record["status"] = "failed"
        _write_json(record_path, record)
        raise MethodRunnerError(f"codex method coding run failed with exit code {completed.returncode}")
    try:
        if isolation == "logical-audited":
            record["transcript_audit"] = _audit_logical_transcript(transcript, packet_name=packet_name, repo_root=repo_root, case_dir=package.case_dir)
        _validate_model_output(model_output_path, package=package, packet_sha256=packet_sha256)
    except MethodRunnerError as exc:
        status = "missing_output" if "did not produce" in str(exc) else "forbidden_read_observed" if str(exc).startswith("forbidden_read_observed:") else "input_unreadable" if str(exc).startswith("input_unreadable:") else "invalid_output"
        record.update(status=status, validation_error=str(exc))
        if status in {"input_unreadable", "forbidden_read_observed"}:
            record.update(review_state="needs_review", blocker="nested macOS and Codex read-only sandboxes did not yield a readable packet" if status == "input_unreadable" else "logical transcript observed a forbidden read boundary")
        _write_json(record_path, record)
        raise
    record.update(status="completed", output_sha256=_sha256(model_output_path))
    _write_json(record_path, record)
    return MethodLaunch(model_output_path=model_output_path, record_path=record_path)


def run_batch_manifest(*, manifest_path: Path, packet_dir: Path, output_schema_path: Path, case_root: Path, results_root: Path, repo_root: Path, max_workers: int = 4, runner: Runner = subprocess.run, platform_name: str | None = None, codex_executable: str | Path | None = None, isolation: str = "os-enforced", packet_ids: Sequence[str] | None = None) -> list[MethodLaunch]:
    """Launch all packet records from a verified manifest with bounded parallelism."""
    if max_workers <= 0:
        raise MethodRunnerError("max_workers must be greater than zero")
    manifest_path, packet_dir = Path(manifest_path), Path(packet_dir)
    _require_regular_file(manifest_path, label="packet manifest")
    manifest = _load_json(manifest_path, label="packet manifest")
    if manifest.get("format") != "serenity-method-packet-manifest/1" or manifest.get("content_hash") != _document_hash(manifest):
        raise MethodRunnerError("packet manifest content hash mismatch")
    packets = manifest.get("packets")
    if not isinstance(packets, list) or not packets:
        raise MethodRunnerError("packet manifest must list packets")
    paths_by_id: dict[str, Path] = {}
    for record in packets:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str) or not _PACKET_NAME.fullmatch(record["path"]):
            raise MethodRunnerError("packet manifest has an invalid packet path")
        packet_id = record.get("packet_id")
        if not isinstance(packet_id, str) or packet_id != Path(record["path"]).stem:
            raise MethodRunnerError("packet manifest has an invalid packet ID")
        if packet_id in paths_by_id:
            raise MethodRunnerError("packet manifest cannot repeat a packet ID")
        path = packet_dir / record["path"]
        _require_regular_file(path, label="manifest packet")
        if record.get("content_hash") != _load_json(path, label="manifest packet").get("content_hash"):
            raise MethodRunnerError("packet manifest packet hash mismatch")
        paths_by_id[packet_id] = path
    if len(set(paths_by_id.values())) != len(paths_by_id):
        raise MethodRunnerError("packet manifest cannot repeat a packet")
    selected_ids = tuple(paths_by_id) if packet_ids is None else tuple(packet_ids)
    if not selected_ids:
        raise MethodRunnerError("packet selection cannot be empty")
    if any(not isinstance(packet_id, str) or not packet_id for packet_id in selected_ids):
        raise MethodRunnerError("packet selection requires non-empty packet IDs")
    if len(set(selected_ids)) != len(selected_ids):
        raise MethodRunnerError("packet selection cannot repeat a packet ID")
    unknown = [packet_id for packet_id in selected_ids if packet_id not in paths_by_id]
    if unknown:
        raise MethodRunnerError(f"selected packet is not present in packet manifest: {unknown[0]}")
    paths = [paths_by_id[packet_id] for packet_id in selected_ids]
    batch_metadata = {
        "full_manifest_content_hash": manifest["content_hash"],
        "full_manifest_sha256": _sha256(manifest_path),
        "selected_packet_ids": list(selected_ids),
        "selected_packet_count": len(selected_ids),
    }
    cases = [build_method_case(packet_path=path, output_schema_path=output_schema_path, case_root=case_root, repo_root=repo_root) for path in paths]
    with ThreadPoolExecutor(max_workers=min(max_workers, len(cases))) as executor:
        futures = [executor.submit(launch_method_case, case, results_root=results_root, repo_root=repo_root, runner=runner, platform_name=platform_name, codex_executable=codex_executable, isolation=isolation, batch_metadata=batch_metadata) for case in cases]
        return [future.result() for future in futures]
