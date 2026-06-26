#!/usr/bin/env python3
"""PreToolUse hook (WebSearch | WebFetch) — keep the web to NARRATIVE, never numbers.

A standing prohibition: never use a web snippet for a number a script can load. This hook
fires right before a web call and reminds the agent where each kind of fact actually comes
from. It does NOT block — web research is essential for second-order context, supply-chain
mapping past the filing, and US-listed substitutes. Exit 0 with the reminder on stdout, which
the harness surfaces; the search proceeds.
"""

import json
import sys

_REMINDER = """[web-number-guard] Web is for NARRATIVE only — never a number a script can load.
- MC / price / multiples / margins / financials / dilution / regime gauges: cite from scripts/serenity_pipeline.py (key_facts / macro), NOT a web snippet.
- A filing's named counterparties, country %, or financing terms: prefer the serenity-filings subagent (it reads the 10-K/8-K) over a web summary.
- Good uses here: second-order supply-chain mapping past the filing, a datable step-change, a US-listed expression/substitute, sentiment context — narrative the pipeline can't load. NFI/NFA."""


def main() -> None:
	try:
		data = json.load(sys.stdin)
	except Exception:  # noqa: BLE001 — never let a hook crash the call
		return
	if data.get("tool_name") in ("WebSearch", "WebFetch"):
		print(_REMINDER)


if __name__ == "__main__":
	main()
	sys.exit(0)
