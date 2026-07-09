#!/usr/bin/env python3
"""SubagentStart hook — carry the harness discipline into the serenity-filings subagent.

Workflow/Task subagents do NOT inherit the main session's UserPromptSubmit hook (the exact confound
WF4 surfaced), so a spawned reader leans on its own .md alone. This hook reinforces, at spawn time,
the one rule that — if it slips — fabricates the evidence a thesis rests on: the filings reader
EXTRACTS, never judges, and silence is null, never a number from memory. Matched to the
serenity-filings agent only, so generic Explore/Plan subagents stay noise-free. Inject only.
"""

import json
import sys

_FILINGS = """[serenity-filings discipline] You are the filing's honest reader inside the Serenity harness:
- EXTRACT, never judge — no archetype, no moat/dilution verdict, no buy/sell. Report "sales to one customer were 22% of revenue"; the caller decides what it means.
- Silence is null, never zero and never a guess. If the filing doesn't disclose a name/%, the field is absent — do not infer it from memory, the ticker, or "everyone knows."
- Quote the filing and cite where (form + item/section, or the XBRL concept). A counterparty / share / contract / number you report MUST be in the filing you read.
- Chase the DEGREE (% of revenue, $ value, contract term), and flag any UNEXPECTED counterparty / program / strategic stake ("UNEXPECTED: ...") — that's often half of a confidential link the caller is reconstructing.
- Numbers come byte-stable from scripts/serenity_filings.py; on a SEC throttle, retry or fall back to an older filing — never invent the number."""


def main():
	try:
		data = json.load(sys.stdin)
	except Exception:  # noqa: BLE001 — never let a hook crash subagent spawn
		return
	if data.get("agent_type") != "serenity-filings":
		return
	print(json.dumps({"hookSpecificOutput": {"hookEventName": "SubagentStart", "additionalContext": _FILINGS}}))


if __name__ == "__main__":
	main()
	sys.exit(0)
