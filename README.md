<div align="center">

# Harness of Serenity

**A typed research runtime for US-listed equity research and conditional-entry analysis.**

[Overview](#1-overview) · [Features](#2-features) · [Quick Start](#3-quick-start) · [Usage](#4-usage) · [Docs](#5-documentation)

</div>

## 1. Overview

This project exists to keep a hard but useful boundary in investment research: software pins identity, facts, sources, availability, and arithmetic; the analyst forms competing explanations and decides what the evidence means. It is for research on US-listed common stock, ADRs, and ETFs, including sector discovery, single-ticker work, and physical supply-chain bottlenecks.

The output can support a research call or a conditional entry trigger, but it does not allocate a portfolio, place trades, or provide personal financial advice. A valid result may just as honestly be `MONITOR`, `PASS`, or `BLOCKED` when the evidence is missing or conflicts.

## 2. Features

- One public lifecycle CLI, [`scripts/serenity.py`](scripts/serenity.py), with JSON-only stdout and explicit run state.
- Versioned schemas under [`schemas/v2`](schemas/v2) for fact snapshots, provider envelopes, evidence, hypotheses, lenses, graphs, decisions, prospective records, and evaluation.
- Source-aware evidence: each result carries an availability state and provenance; time-sensitive work distinguishes when something was effective, observed, available, and fetched.
- Official issuer narrative as typed evidence: SEC filings and already-resolved issuer IR documents retain identity, publication time, exact response bytes, and source hashes before any management claim or cross-company read-through is interpreted.
- Adaptive research rather than a frozen scoring pipeline: the analyst records competing hypotheses and requests evidence that could distinguish them.
- Reproducible arithmetic: a declared lens runs only from saved facts, and numeric targets require a valid lens with traceable inputs.
- Separate corpus, method, harness, and evaluation tools so historical tweets, doctrine, and test answers do not silently enter a routine research decision.
- Candidate-first Codex evaluation: one family-routed Terra candidate uses the shared Harness, then two cleanroom Terra reviewers judge its typed artifact from raw evidence without seeing the Harness or an answer key; Sol is reserved for material disagreement.

## 3. Quick Start

Prerequisites: Python 3.12 or newer, Git, and network access for live providers. The deterministic/offline lifecycle does not need a market-data key, and no Docker or OrbStack runtime is required.

```bash
git clone https://github.com/tjdwls101010/Harness-of-Serenity.git
cd Harness-of-Serenity

python3 -m venv scripts/.venv
scripts/.venv/bin/python -m pip install -r scripts/requirements.txt
cp .env.example .env
```

Codex uses the bundled tracked `.codex -> .claude` symlink, so it loads the same harness without copying a second configuration tree. Git preserves symlinks on platforms that support them; if a platform disables symlink checkout, enable its symlink support and clone again before using Codex.

Create an offline research run. The command emits one JSON object; keep its `run_id` for the next lifecycle commands.

```bash
scripts/.venv/bin/python scripts/serenity.py run start \
  --mode single-name \
  --question "What evidence would change the NVDA thesis?" \
  --subject NVDA \
  --as-of 2026-08-17 \
  --offline
```

The runtime writes active work below `.serenity/runs/<run_id>/`. A normal research flow snapshots the security, stores competing hypotheses, requests/collects evidence, runs a declared lens if needed, validates an analyst-authored decision, and only then finalizes it. Use `--help` on every command before supplying your own JSON documents.

## 4. Usage

Set the interpreter once for the examples below.

```bash
PY=scripts/.venv/bin/python
```

### 4.1. Research lifecycle

```bash
# Inspect or end an active run.
$PY scripts/serenity.py run status RUN_ID
$PY scripts/serenity.py run abandon RUN_ID --reason "research stopped"

# Persist deterministic identity/fact evidence from a frozen packet, or omit
# --frozen-packet on a network-permitted run to use the live provider seam.
$PY scripts/serenity.py snapshot security RUN_ID --frozen-packet path/to/snapshot.json

# Record competing hypotheses before asking for adaptive evidence.
$PY scripts/serenity.py hypothesis put RUN_ID --document path/to/hypotheses.json
$PY scripts/serenity.py evidence request RUN_ID \
  --hypothesis-id hyp-demand-holds \
  --capability-id sec.filings \
  --document path/to/evidence-request.json
$PY scripts/serenity.py evidence collect RUN_ID evidence-request-001

# Run declared arithmetic and validate/finalize an analyst-authored decision.
$PY scripts/serenity.py lens run RUN_ID --spec path/to/lens-spec.json
$PY scripts/serenity.py decision validate RUN_ID \
  --decision path/to/decision.json \
  --evidence-manifest path/to/evidence-manifest.json
$PY scripts/serenity.py decision finalize RUN_ID \
  --decision path/to/decision.json \
  --evidence-manifest path/to/evidence-manifest.json \
  --analysis path/to/analysis.json
```

For issuer narrative, Web search may locate an official issuer-owned URL but does not make the snippet or page a fact. First create the run's fact snapshot through the live SEC/OpenFIGI provider seam; a `--frozen-packet` snapshot remains useful for deterministic tests but cannot authorize a live issuer fetch. Save a request document like the following on a network-permitted run whose provider allowlist includes `issuer-ir`, then request capability `issuer-ir.document` and collect it through the same evidence command. Collection reopens the content-hashed SEC submissions payload from the private raw cache and exact-matches its CIK, issuer name, official website domains, snapshot ID, and request before any network call. The provider then binds publication time, every redirect hop, final URL, response metadata, and exact raw bytes; the analyst separately decides whether a management claim is corroborated or has a cross-company read-through.

```json
{
  "question": "What operating constraint and partner relationship did management disclose?",
  "evidence_type": "issuer-narrative",
  "provider_policy": {
    "providers": ["issuer-ir"],
    "allow_network": true,
    "historical_cutoff": "2026-08-17T23:59:59Z"
  },
  "acceptance_criteria": ["Preserve the official source, publication time, raw hash, and exact narrative location."],
  "requested_at": "2026-08-17T00:00:00Z",
  "provider_parameters": {
    "identity": {"ticker": "TICKER", "cik": "0000000000", "issuer": "Issuer legal name"},
    "document": {"url": "https://investor.example.com/official-document", "kind": "prepared_remarks"},
    "origin_binding": {"issuer_domain": "investor.example.com", "binding_source_ref": "snapshot-SNAPSHOT_ID"}
  }
}
```

```bash
$PY scripts/serenity.py evidence request RUN_ID \
  --hypothesis-id hyp-operating-constraint \
  --capability-id issuer-ir.document \
  --document path/to/issuer-ir-request.json
$PY scripts/serenity.py evidence collect RUN_ID evidence-request-ISSUER_IR
```

Do not use `evidence read --document` to inject an issuer narrative result. That manual frozen-result seam cannot prove the live SEC origin or exact response bytes, so `issuer-ir.document` is accepted only through `evidence collect`.

`graph put` stores a typed sector graph for a supply-chain or Physical AI question. `outcomes register` and `outcomes refresh` record later measurements of a finalized decision; they do not trade or rewrite the original thesis.

```bash
$PY scripts/serenity.py graph put RUN_ID --file path/to/sector-graph.json
$PY scripts/serenity.py outcomes register \
  --decision records/decisions/LINEAGE/v001/decision.json \
  --benchmark-json path/to/benchmark.json \
  --checkpoint-schedule-json path/to/outcome-schedule.json
$PY scripts/serenity.py outcomes refresh outcome-001 --observation path/to/observation.json
```

All commands return one JSON object on stdout. Exit code `0` includes a valid typed unavailable result; `2` is usage/schema, `3` identity/lifecycle, `4` provider, `5` persistence/hash conflict, and `70` an unexpected internal error.

### 4.2. Data availability, time, and provenance

An absent number is never silently treated as zero or current. Evidence states whether it is `available`, `not_disclosed`, `not_applicable`, `unavailable`, `invalid`, `not_requested`, `stale`, or `conflict`, and preserves provider identity, source identifiers, raw-content hash, and retrieval metadata. Historical evaluation uses `available_at` as its cutoff boundary; a period end or event date alone does not prove that the information was available then.

Live FRED evidence needs `FRED_API_KEY`. SEC requests need a contactable user agent through `SERENITY_SEC_USER_AGENT` or the legacy `EDGAR_IDENTITY`; an unresolved identity blocks a final research decision rather than allowing a silently wrong ticker. `issuer-ir.document` fetches one already-resolved official issuer URL and never crawls, selects the “latest” document, or turns a CEO statement into an investment conclusion. The owned `ibd-rs-rating==0.3.0` adapter preserves raw records and dates as evidence only; it is not a score gate or recommendation.

### 4.3. Maintenance and evaluation CLIs

These tools are intentionally separate from the public research lifecycle. Their detailed contracts are available from their own help text.

```bash
# Inventory/audit corpus-method evidence; it never produces a recommendation.
$PY scripts/serenity_corpus.py --help
$PY scripts/serenity_corpus.py inventory --db data/analysis_Serenity.db

# Build, validate, and independently code the source-method corpus.
$PY scripts/serenity_method.py --help
$PY scripts/serenity_method_runner.py --help

# Run deterministic evaluation by default; live candidate/reviewer execution is opt-in and cleanroom-isolated.
$PY scripts/serenity_eval.py --help
$PY scripts/serenity_eval.py

# Check static v2 harness wiring without provider/network research.
$PY scripts/serenity_harness.py validate
```

`serenity_eval.py --execute-cli` first runs a family-routed candidate against the tracked `CLAUDE.md`/skill snapshot, then sends only the typed candidate artifact and permitted evidence into two independent no-Harness reviewer cleanrooms. Live provider captures are transport checkpoints by default and become citable semantic evidence only through an explicit identity- and cutoff-valid invariant binding.

## 5. Documentation

The implementation decision record is [`docs/plans/260817`](docs/plans/260817/00-README.md). It defines the runtime contracts, corpus/method boundary, harness and evaluation design, cutover verification, and recorded cutover evidence; the current hash-valid 18-case result is [`evaluation-report.v2.json`](docs/plans/260817/evaluation-report.v2.json) (`e4e5ae498606ff4489cc06e5e0e587b9b7422165c57cb65d3ccf143878f1fb2d`): 18 Terra candidates, 36 independent Terra reviews, and no Sol adjudication because no material invariant-level disagreement remained. Earlier diagnostic runs are retained separately in the cutover evidence. The current public command surface is authoritative through `scripts/serenity.py --help` and each subcommand’s `--help`.

## 6. Contributing

Contributions are welcome when they preserve the fact-versus-judgment boundary and use the public seams. Read [CONTRIBUTING.md](CONTRIBUTING.md) for setup, test expectations, provider injection, and the repository’s Korean-language Git/PR convention.

## 7. License

Released under the [MIT License](LICENSE).
