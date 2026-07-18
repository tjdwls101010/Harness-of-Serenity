#!/usr/bin/env python3
"""UserPromptSubmit hook — the just-in-time ACTION nudge on an equity/macro question.

The doctrine (archetype -> lens, run both legs, the funnel order) already lives in CLAUDE.md and
is always in context, so re-teaching it here would only dilute the three things that are genuinely
time-sensitive at the moment a market question arrives: run the pipeline first (before reasoning
from memory), scan for a dated catalyst (so an event isn't mis-read as a standalone single-name
call), and pick the lens at intake (not at the verdict). This hook carries ONLY those actions and
points at the in-context doctrine for the rest. It fires on a detected equity/macro intent, stays
silent on a coding/harness-dev prompt, and never blocks: exit 0, print the reminder as context.
"""

import json
import re
import sys

# Equity/macro intent — specific enough to NOT fire on this repo's own coding prompts.
# Cashtags, finance nouns, and the user's Korean market phrasings; omits bare ALL-CAPS.
_INTENT = re.compile(
	r"(\$[A-Za-z]{1,5}\b)"
	r"|stock|ticker|equit|\bshares?\b|valuation|price target|\bP/?E\b|\bPEG\b|fair value"
	r"|moat|bottleneck|archetype|chokepoint|hyperscaler|\bcapex\b|dilution|\bATM\b|convertible"
	r"|buyback|earnings|short interest|float\b|\bregime\b|liquidity|the fed|rate cut|macro"
	r"|portfolio|invest|overweight|underweight|drawdown|sell-?off|short squeeze"
	r"|\ba (buy|sell|short)\b|buy the dip|should i (buy|sell|own|short|add|hold)|worth (buying|owning)"
	r"|priced in|too late to (buy|get in)|fair price"
	r"|뭐\s*사|사도|살까|팔까|매수|매도|종목|장\s*어때|거시|밸류|분석해|이거\s*어때|들어가|물타|존버",
	re.IGNORECASE,
)

# Meta / harness-development guard. A prompt ABOUT this repo (hooks, skills, the pipeline code, a
# plan) can trip _INTENT on words like "analyze" / "invest" / "valuation" without being a market
# question — observed firing on this session's own planning prompts. Suppress ONLY when the prompt
# reads as harness dev AND carries no concrete market anchor (a cashtag or a buy/sell/valuation ask).
# The bias is deliberate: an extra fire is cheap context, a suppressed real market question is not,
# so the anchor list stays generous and only unambiguous dev prompts get skipped.
_META = re.compile(
	r"harness|하네스|\bhook\b|\bhooks\b|훅\b|\bskill\b|스킬|SKILL\.md|CLAUDE\.md|settings\.json"
	r"|\.py\b|pipeline code|subagent|verdict[_\s-]?gate|evidence[_\s-]?discipline|exec-form"
	r"|refactor|리팩터|\beval\b|workflow|워크플로|commit|커밋|\b계획\b|구현|스펙|spec\b",
	re.IGNORECASE,
)
_MARKET_ANCHOR = re.compile(
	r"\$[A-Za-z]{1,5}\b"
	r"|매수|매도|사도|살까|팔까|종목|장\s*어때|물타|존버|목표가|밸류|벨류|배당"
	r"|should i (buy|sell|own|short|add|hold)|buy the dip|price target|\bPT\b|valuation|dividend|earnings",
	re.IGNORECASE,
)

_REMINDER = """[evidence-discipline] Reads as an equity/macro question — before answering:
- Run scripts/serenity_pipeline.py FIRST (macro | analyze TICKER [--skip-macro] | discover) and reason from its JSON — never MC / price / multiples / margins / the regime from memory. For the filing's words AND its disclosure numbers (customer % / country % / inventory / obligations), invoke the serenity-filings subagent.
- Scan the prompt for a DATED catalyst (selloff / crash / cost-scare / conflict / earnings / policy date) FIRST — a known ticker arriving with one is an EVENT (macro catalyst test + cost-shock margin math), not a standalone single-name read.
- Pick the archetype's valuation lens at INTAKE, not at the verdict — the archetype forces it. Which lens, and running BOTH legs of a fork, is already in context (N10 / analysis §6); this is the reminder to actually RUN it, arithmetic shown.
- If sessions/INDEX.md lists these tickers, plan to reconcile deltas AFTER fresh scorecards — never re-derive blind, never read the old ranking first (the index is verdict-free; a ticker grep is safe)."""


def main() -> None:
	try:
		data = json.load(sys.stdin)
	except Exception:  # noqa: BLE001 — never let a hook crash the turn
		return
	prompt = str(data.get("prompt") or "")
	if not prompt.strip():
		return
	# Harness-dev prompt with no market anchor -> not a market question, stay silent.
	if _META.search(prompt) and not _MARKET_ANCHOR.search(prompt):
		return
	if _INTENT.search(prompt):
		print(_REMINDER)


if __name__ == "__main__":
	main()
	sys.exit(0)
