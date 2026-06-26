#!/usr/bin/env python3
"""Serenity evidence pipeline — the deterministic data layer.

This is the harness's one job-separation made executable: the code LOADS objective,
decision-grade evidence (yfinance numbers, SEC narrative) and the agent JUDGES from it.
Nothing here emits a verdict, a regime label, a score, or an archetype tag.

	serenity_pipeline.py macro                  # raw macro gauges (no regime label)
	serenity_pipeline.py analyze TICKER         # full single-name evidence dossier
	serenity_pipeline.py analyze TICKER --skip-macro   # batch: reuse one macro read
	serenity_pipeline.py discover T1 T2 …       # side-by-side comparator (not a ranking)
	serenity_pipeline.py evidence --fixture F   # replay a frozen payload (testing)

All output is JSON. Never truncate it — the fields that look skippable (financing
terms, country %, revision counts) are exactly what a read turns on.
"""

import argparse
import os
import sys

# Make `scripts/` and `scripts/modules/` importable regardless of CWD.
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, os.path.join(_scripts_dir, "modules"))

from pipeline._evidence_commands import cmd_analyze, cmd_macro, cmd_discover
from pipeline._evidence import cmd_evidence


def main():
	parser = argparse.ArgumentParser(
		prog="serenity_pipeline.py",
		description="Serenity evidence pipeline (code loads evidence; the agent judges).",
	)
	sub = parser.add_subparsers(dest="command", required=True)

	sp_macro = sub.add_parser("macro", help="Raw macro gauges (no regime classification)")
	sp_macro.add_argument("--no-capex", action="store_true", default=False,
		help="Skip the hyperscaler CapEx cascade fetch (faster)")
	sp_macro.set_defaults(func=cmd_macro)

	sp_analyze = sub.add_parser("analyze", help="Full single-name evidence dossier")
	sp_analyze.add_argument("ticker", help="Stock ticker symbol")
	sp_analyze.add_argument("--skip-macro", action="store_true", default=False,
		help="Skip the macro fetch (batch: reuse one `macro` call across names)")
	sp_analyze.set_defaults(func=cmd_analyze)

	sp_discover = sub.add_parser("discover", help="Side-by-side comparator across tickers")
	sp_discover.add_argument("tickers", nargs="+", help="Ticker symbols to compare")
	sp_discover.set_defaults(func=cmd_discover)

	sp_evidence = sub.add_parser("evidence", help="Replay a frozen *.inputs.json payload (testing)")
	sp_evidence.add_argument("--fixture", required=True, help="Frozen *.inputs.json payload")
	sp_evidence.add_argument("--ticker", default=None, help="Override inferred ticker")
	sp_evidence.add_argument("--json", action="store_true", default=True, help="Emit JSON")
	sp_evidence.set_defaults(func=cmd_evidence)

	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
