#!/usr/bin/env python3
"""Public command-line entrypoint for blind method coding packets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from serenity_v2.method_runner import MethodRunnerError, build_method_case, build_method_synthesis_case, launch_method_case, launch_method_synthesis, run_batch_manifest


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "config" / "method-coding-output.schema.json"
SYNTHESIS_SCHEMA = ROOT / "config" / "method-claim-synthesis.schema.json"


def parser() -> argparse.ArgumentParser:
    formatter = argparse.RawDescriptionHelpFormatter
    value = argparse.ArgumentParser(
        prog="serenity_method_runner.py",
        description="Run independent blind open-coding packets in a strict cleanroom.",
        epilog=(
            "Cleanroom contract: each case has an allowlist of one packet-*.json, an output schema, prompt metadata, and a hashed manifest. "
            "Forbidden repository, doctrine, verdict, source-index, symlink, and extra paths are rejected. Codex runs only gpt-5.6-terra in read-only mode with the blind_open_coder role.\n\n"
            "Isolation defaults to os-enforced, which applies the macOS original-repository read/write deny. --isolation logical-audited is an explicit nondefault fallback: it omits the outer seatbelt, preserves Codex read-only mode, and audits the JSON tool transcript for a packet read and forbidden reads. It is detective only, not OS confidentiality, and does not require OrbStack.\n\n"
            "Batch concurrency is bounded by --max-workers. Use repeatable --packet-id only for an explicit verified selection; every selected ID must be in the full manifest and execution records keep the full-manifest hash plus selected IDs. Outputs and failure execution metadata are written outside the case. Resume is deliberately unsupported: old results are separately reconciled, and a failed packet must be launched as a new cleanroom case.\n\n"
            "synthesize is one final, non-fan-out Sol claim synthesis pass over one hash-valid bounded candidate digest. It uses final_method_synthesizer with gpt-5.6-sol, forbids CLAUDE/AGENTS/.claude/.codex/data/sessions/coding/source-index/prior-result inputs, and never accepts augmented engineering claims. On macOS its outer seatbelt denies the original repository and prior result trees while Codex uses inner danger-full-access only to avoid nested read failure; its transcript must prove the exact digest read and no outside/search/network reads.\n\n"
            "Examples:\n"
            "  serenity_method_runner.py packet --packet /tmp/packets/packet-001.json --case-root /tmp/cases --results-root /tmp/results\n"
            "  serenity_method_runner.py batch --manifest /tmp/packets/packet-manifest.json --packet-dir /tmp/packets --case-root /tmp/cases --results-root /tmp/results --max-workers 4"
            "\n  serenity_method_runner.py synthesize --candidate-digest /tmp/candidates/candidate-digest.json --case-root /tmp/cases --results-root /tmp/results"
        ),
        formatter_class=formatter,
    )
    commands = value.add_subparsers(dest="command", required=True)
    for name in ("packet", "batch"):
        command = commands.add_parser(
            name,
            description=(
                "Build and launch a blind packet case. The case allowlist and hashes are revalidated before launch; forbidden paths, symlinks, and extra files fail safely. "
                "Results are output outside the case. Resume is unsupported: failures create an execution record and require a new case. The nondefault logical-audited isolation is detective, not OS confidentiality."
                if name == "packet"
                else "Build and launch every verified packet in a manifest with bounded batch concurrency, or an explicit repeatable --packet-id subset. Every selected ID must hash-match in the full manifest before cases are created. Outputs remain outside cases. Resume is unsupported: old results are separately reconciled and failures require new cases. The nondefault logical-audited isolation is detective, not OS confidentiality."
            ),
            epilog=(
                "Example: serenity_method_runner.py packet --packet /tmp/packets/packet-001.json --case-root /tmp/cases --results-root /tmp/results"
                if name == "packet"
                else "Example: serenity_method_runner.py batch --manifest /tmp/packets/packet-manifest.json --packet-dir /tmp/packets --case-root /tmp/cases --results-root /tmp/results --packet-id packet-039 --packet-id packet-040 --max-workers 4"
            ),
            formatter_class=formatter,
        )
        command.add_argument("--case-root", required=True, type=Path, help="Outside-repository root for newly created immutable cleanroom cases.")
        command.add_argument("--results-root", required=True, type=Path, help="Outside-repository root for model output and failure execution records.")
        command.add_argument("--repo-root", type=Path, default=ROOT, help="Original repository to deny from the macOS sandbox.")
        command.add_argument("--output-schema", type=Path, default=SCHEMA, help="Method-coding JSON output schema copied into every case.")
        command.add_argument("--isolation", choices=("os-enforced", "logical-audited"), default="os-enforced", help="os-enforced is the default OS boundary; logical-audited is an explicit transcript-audited fallback without OS confidentiality.")
    commands.choices["packet"].add_argument("--packet", required=True, type=Path, help="One already-generated packet-*.json file.")
    commands.choices["batch"].add_argument("--manifest", required=True, type=Path, help="Verified packet-manifest.json listing every packet and hash.")
    commands.choices["batch"].add_argument("--packet-dir", required=True, type=Path, help="Directory containing manifest-referenced packet files.")
    commands.choices["batch"].add_argument("--packet-id", action="append", help="Repeat for an explicit verified subset; duplicate, unknown, or empty selections fail before case creation. Default: every manifest packet. This is not implicit resume.")
    commands.choices["batch"].add_argument("--max-workers", type=int, default=4, help="Maximum concurrent Codex launches; must be positive.")
    synthesize = commands.add_parser(
        "synthesize",
        description="Run exactly one final non-fan-out claim synthesis from one hash-valid bounded candidate digest. The case allowlist allows only that digest, the strict output schema, hashed prompt metadata, and a package manifest. CLAUDE, AGENTS, .claude, .codex, data, sessions, coding, source-index, and prior results are forbidden. Claims can be sourced or unverified only; augmented engineering claims are forbidden. macOS uses an outer repository/prior-results deny plus inner Codex danger-full-access to avoid nested read failure; transcript audit still requires the exact digest read and rejects outside, search, or network reads.",
        epilog="Example: serenity_method_runner.py synthesize --candidate-digest /tmp/candidates/candidate-digest.json --case-root /tmp/cases --results-root /tmp/results\n\nThis is a single final gpt-5.6-sol final_method_synthesizer pass, never a broad fan-out or implicit resume. Outputs and failure records are written outside the case.",
        formatter_class=formatter,
    )
    synthesize.add_argument("--candidate-digest", required=True, type=Path, help="One hash-valid bounded candidate-digest.json; no coding, source-index, or prior-result input is accepted.")
    synthesize.add_argument("--case-root", required=True, type=Path, help="Outside-repository root for the immutable final synthesis case.")
    synthesize.add_argument("--results-root", required=True, type=Path, help="Outside-repository root for final synthesis output and execution metadata.")
    synthesize.add_argument("--repo-root", type=Path, default=ROOT, help="Original repository denied by the macOS outer seatbelt.")
    synthesize.add_argument("--output-schema", type=Path, default=SYNTHESIS_SCHEMA, help="Strict serenity-method-claim-synthesis/1 Structured Outputs schema.")
    synthesize.add_argument("--isolation", choices=("os-enforced",), default="os-enforced", help="Required macOS outer repository/prior-results boundary; no logical-only synthesis mode exists.")
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "packet":
            package = build_method_case(packet_path=args.packet, output_schema_path=args.output_schema, case_root=args.case_root, repo_root=args.repo_root)
            launch = launch_method_case(package, results_root=args.results_root, repo_root=args.repo_root, isolation=args.isolation)
            result = {"packet_id": package.packet_id, "output": str(launch.model_output_path), "execution": str(launch.record_path)}
        elif args.command == "batch":
            launches = run_batch_manifest(manifest_path=args.manifest, packet_dir=args.packet_dir, output_schema_path=args.output_schema, case_root=args.case_root, results_root=args.results_root, repo_root=args.repo_root, max_workers=args.max_workers, isolation=args.isolation, packet_ids=args.packet_id)
            result = {"count": len(launches), "outputs": [str(item.model_output_path) for item in launches], "executions": [str(item.record_path) for item in launches]}
        else:
            package = build_method_synthesis_case(candidate_digest_path=args.candidate_digest, output_schema_path=args.output_schema, case_root=args.case_root, repo_root=args.repo_root)
            launch = launch_method_synthesis(package, results_root=args.results_root, repo_root=args.repo_root, isolation=args.isolation)
            result = {"candidate_digest_content_hash": package.candidate_digest_content_hash, "output": str(launch.model_output_path), "execution": str(launch.record_path)}
    except MethodRunnerError as exc:
        parser().error(str(exc))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
