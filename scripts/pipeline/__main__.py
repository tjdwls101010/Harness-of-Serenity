#!/usr/bin/env python3
import argparse
import os
import sys

# Ensure Scripts/ is on sys.path for module imports
_scripts_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, _scripts_dir)
# Also add modules/ for utils import
sys.path.insert(0, os.path.join(_scripts_dir, "modules"))

from pipeline._commands import cmd_macro, cmd_analyze, cmd_discover
from pipeline._evidence import cmd_evidence
from pipeline._regression import cmd_regress


def main():
	parser = argparse.ArgumentParser(
		description="Serenity Pipeline: 6-Level Analytical Hierarchy"
	)
	sub = parser.add_subparsers(dest="command", required=True)

	# macro
	sp_macro = sub.add_parser("legacy-macro", help="Legacy macro regime assessment")
	sp_macro.add_argument(
		"--extended",
		action="store_true",
		default=False,
		help="Include raw DXY and BDI data in output",
	)
	sp_macro.set_defaults(func=cmd_macro)

	# analyze
	sp_analyze = sub.add_parser("legacy-analyze", help="Legacy analysis with judgmentful scaffold fields")
	sp_analyze.add_argument("ticker", help="Stock ticker symbol")
	sp_analyze.add_argument(
		"--skip-macro",
		action="store_true",
		default=False,
		help="Skip Level 1 macro assessment",
	)
	sp_analyze.set_defaults(func=cmd_analyze)

	# discover
	sp_discover = sub.add_parser("legacy-discover", help="Legacy candidate comparator with triage fields")
	sp_discover.add_argument("tickers", nargs="+", help="Ticker symbols to compare (2-30)")
	sp_discover.set_defaults(func=cmd_discover)

	sp_evidence = sub.add_parser("evidence", help="Evidence-only JSON for agent judgment")
	sp_evidence.add_argument("--fixture", required=True, help="Frozen *.inputs.json payload")
	sp_evidence.add_argument("--ticker", default=None, help="Override inferred ticker")
	sp_evidence.add_argument("--json", action="store_true", default=True, help="Emit JSON")
	sp_evidence.set_defaults(func=cmd_evidence)

	sp_regress = sub.add_parser("legacy-regress", help="Legacy golden-grade regression harness")
	sp_regress.add_argument("tickers", nargs="*", help="Subset of golden tickers (default: all)")
	sp_regress.add_argument("--capture", action="store_true", default=False,
		help="Re-run analyze live to refresh frozen scoring inputs")
	sp_regress.add_argument("--bless", action="store_true", default=False,
		help="Re-derive expected.json from the current replay of frozen inputs")
	sp_regress.add_argument("--update", action="store_true", default=False,
		help="--capture then --bless (full refresh)")
	sp_regress.add_argument("--stamp", default=None, help="captured_at date to record (default: today)")
	sp_regress.set_defaults(func=cmd_regress)

	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
