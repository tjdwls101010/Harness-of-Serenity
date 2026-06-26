#!/usr/bin/env python3
"""Quarantined legacy entry — the OLD judgment-laden pipeline.

This is NOT the harness's runtime surface. It survives only so the historical
golden-regression capture (`legacy-regress --capture`, which shells `python -m
pipeline.legacy legacy-analyze`) can still replay, and as a reference for what the
code used to decide. The live harness uses `scripts/serenity_pipeline.py`, which loads
EVIDENCE only and leaves every judgment to the agent. Do not wire new work here.
"""
import argparse
import os
import sys

_scripts_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, os.path.join(_scripts_dir, "modules"))

from pipeline.legacy._commands import cmd_macro, cmd_analyze, cmd_discover
from pipeline.legacy._regression import cmd_regress


def main():
	parser = argparse.ArgumentParser(description="Serenity LEGACY pipeline (judgmentful; reference only)")
	sub = parser.add_subparsers(dest="command", required=True)

	sp_macro = sub.add_parser("legacy-macro")
	sp_macro.add_argument("--extended", action="store_true", default=False)
	sp_macro.set_defaults(func=cmd_macro)

	sp_analyze = sub.add_parser("legacy-analyze")
	sp_analyze.add_argument("ticker")
	sp_analyze.add_argument("--skip-macro", action="store_true", default=False)
	sp_analyze.set_defaults(func=cmd_analyze)

	sp_discover = sub.add_parser("legacy-discover")
	sp_discover.add_argument("tickers", nargs="+")
	sp_discover.set_defaults(func=cmd_discover)

	sp_regress = sub.add_parser("legacy-regress")
	sp_regress.add_argument("tickers", nargs="*")
	sp_regress.add_argument("--capture", action="store_true", default=False)
	sp_regress.add_argument("--bless", action="store_true", default=False)
	sp_regress.add_argument("--update", action="store_true", default=False)
	sp_regress.add_argument("--stamp", default=None)
	sp_regress.set_defaults(func=cmd_regress)

	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
