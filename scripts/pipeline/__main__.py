#!/usr/bin/env python3
"""`python -m pipeline` — the evidence-only commands, identical to serenity_pipeline.py.

The harness's documented entry is `scripts/serenity_pipeline.py`; this module mirrors it
so `python -m pipeline analyze TICKER` works too. The OLD judgment-laden commands live in
the quarantined `pipeline.legacy` package (`python -m pipeline.legacy legacy-analyze …`).
"""
import argparse
import os
import sys

_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, os.path.join(_scripts_dir, "modules"))

from pipeline._evidence_commands import cmd_macro, cmd_analyze, cmd_discover
from pipeline._evidence import cmd_evidence


def main():
	parser = argparse.ArgumentParser(
		prog="python -m pipeline",
		description="Serenity evidence pipeline (code loads evidence; the agent judges).",
	)
	sub = parser.add_subparsers(dest="command", required=True)

	sp_macro = sub.add_parser("macro", help="Raw macro gauges (no regime classification)")
	sp_macro.add_argument("--no-capex", action="store_true", default=False)
	sp_macro.set_defaults(func=cmd_macro)

	sp_analyze = sub.add_parser("analyze", help="Full single-name evidence dossier")
	sp_analyze.add_argument("ticker")
	sp_analyze.add_argument("--skip-macro", action="store_true", default=False)
	sp_analyze.set_defaults(func=cmd_analyze)

	sp_discover = sub.add_parser("discover", help="Side-by-side comparator across tickers")
	sp_discover.add_argument("tickers", nargs="+")
	sp_discover.set_defaults(func=cmd_discover)

	sp_evidence = sub.add_parser("evidence", help="Replay a frozen *.inputs.json payload")
	sp_evidence.add_argument("--fixture", required=True)
	sp_evidence.add_argument("--ticker", default=None)
	sp_evidence.add_argument("--json", action="store_true", default=True)
	sp_evidence.set_defaults(func=cmd_evidence)

	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
