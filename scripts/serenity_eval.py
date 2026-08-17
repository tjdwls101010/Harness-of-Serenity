#!/usr/bin/env python3
"""Run the v2 evaluation harness and print exactly one JSON object."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from serenity_core.evaluation import EvaluationError, evaluate, load_live_packet_dir


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_CONFIG = ROOT / "config" / "evaluation.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="""Run the v2 evaluation root command. This CLI has no evaluator subcommands; every invocation evaluates the configured family descriptors.

Tracks:
  A — retrospective independent-first: make a fresh decision from the cutoff packet before any answer-key comparison; answer keys and old verdicts are excluded from the cleanroom.
  B — cutoff-frozen current packets: run current code against an explicitly frozen availability cutoff to expose leakage, provider drift, and schema/provenance breaks.
  C — prospective tracking: retain the original decision and append later checkpoints without rewriting its thesis.

Cases:
  Each family has deterministic fixture cases and opt-in live descriptors. A live descriptor is not provider evidence or a model run until an executed provider packet meets its declared provider, availability, fetched_at, and raw-content-hash requirements. A post-cutoff capture may be accepted as transport_only and reported as checkpoint_role=provider_transport_only, eligible_for_case_evidence=false; it is not copied into candidate/reviewer evidence or citations. Semantic live evidence requires exact subject identity and availability at or before the cutoff, plus an explicit invariant mapping. The default report therefore leaves unexecuted live cases needs_review.

Candidate protocol:
  With --execute-cli, one shared-Harness candidate runs before reviewers for every executable case. It receives the user question, frozen typed evidence, and a family-routed Harness root/skill snapshot; it returns a hash-bound typed candidate result and user-facing artifact (decision/action). No configured hook lifecycle is executed in this isolated candidate run. Expected case behavior remains evaluator-only and is never placed in a candidate or reviewer packet.

Review protocol:
  Deterministic validators run first. Only after a validated shared-Harness candidate artifact is present does a valid executed case receive two independent Codex terra reviews; reviewers assess the candidate against raw typed evidence in their own no-Harness cleanroom. One Codex sol adjudication only for material disagreement is allowed. Every model run uses an isolated cleanroom boundary, whose allowlist excludes repository doctrine, corpus answers, old verdicts, and results.

Reporting:
  Every family reports passed, failed, needs_review, and total. The denominator is all cases; unresolved needs_review cases are not successes and remain visible in the Wilson interval. There is no aggregate quality score. --out writes the canonical-hashed report atomically while stdout remains one JSON object for normal evaluation runs.

Exit behavior:
  exit 0: successful evaluation, including a deterministic-only/default report with needs_review cases.
  exit 2: invalid config, schema, cleanroom, provider-packet, or persistence contract. Diagnostics are encoded in the one JSON stdout object for normal runs.
""",
        epilog="""Examples:
  scripts/.venv/bin/python scripts/serenity_eval.py
  scripts/.venv/bin/python scripts/serenity_eval.py --out reports/evaluation.json
  scripts/.venv/bin/python scripts/serenity_eval.py --live-packet-dir /secure/provider-packets --live-raw-cache-dir /secure/provider-raw
  scripts/.venv/bin/python scripts/serenity_eval.py --execute-cli --cleanroom-root /tmp/serenity-cleanrooms --results-root /tmp/serenity-results
  scripts/.venv/bin/python scripts/serenity_eval.py --execute-cli --live-packet-dir /secure/provider-packets --live-raw-cache-dir /secure/provider-raw --cleanroom-root /tmp/serenity-cleanrooms --results-root /tmp/serenity-results --out /tmp/serenity-evaluation.json
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Evaluation descriptor config; default: config/evaluation.json.")
    parser.add_argument("--execute-cli", action="store_true", help="Opt in to cleanroom Codex execution; without it no model or network call is made.")
    parser.add_argument("--cleanroom-root", type=Path, help="Outside-repository directory for allowlisted cleanroom packages; required in durable CLI execution workflows.")
    parser.add_argument("--results-root", type=Path, help="Outside-repository directory for cleanroom command transcripts and output hashes.")
    parser.add_argument("--out", type=Path, help="Atomically persist the canonical-hashed report at this path; stdout still emits one JSON object.")
    parser.add_argument("--live-packet-dir", type=Path, help="Directory of actual case-id keyed serialized provider-envelope packets; requires --live-raw-cache-dir to verify raw-byte digests.")
    parser.add_argument("--live-raw-cache-dir", type=Path, help="Private raw cache root containing sha256/<digest> bytes bound by each live provider envelope; never copied into the cleanroom.")
    args = parser.parse_args()
    try:
        live_packets = load_live_packet_dir(args.live_packet_dir) if args.live_packet_dir else None
        report = evaluate(
            args.config,
            repo_root=ROOT,
            execute_cli=args.execute_cli,
            cleanroom_root=args.cleanroom_root,
            results_root=args.results_root,
            out_path=args.out,
            live_provider_packets=live_packets,
            live_raw_cache_root=args.live_raw_cache_dir,
        )
    except EvaluationError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, separators=(",", ":")))
        return 2
    print(json.dumps({"ok": True, "report": report}, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
