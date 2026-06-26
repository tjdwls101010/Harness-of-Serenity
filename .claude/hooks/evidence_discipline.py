#!/usr/bin/env python3
"""UserPromptSubmit hook — reinforce the evidence discipline on equity/macro questions.

The non-negotiables already live in CLAUDE.md; this hook is the deterministic nudge at
the exact moment a market question arrives: run the pipeline first, never cite numbers (or
a regime) from memory, route to the right lens, and reach for the serenity-filings subagent
for the filing's words. It only fires on a detected equity/macro intent — a coding or
unrelated prompt passes through silently (no noise). It never blocks: exit 0, and on intent
it prints a short reminder that the harness adds to the turn's context.
"""

import json
import re
import sys

# Equity/macro intent — kept specific enough to NOT fire on this repo's own coding prompts
# ("fix the API", "refactor analyze()"). Cashtags, finance nouns, and the user's Korean
# market phrasings; deliberately omits bare ALL-CAPS and generic "analyze/buy".
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

_REMINDER = """[evidence-discipline] This reads as an equity/macro question — before answering:
- Run scripts/serenity_pipeline.py FIRST (macro | analyze TICKER [--skip-macro] | discover) and reason from its JSON. Never cite MC / price / multiples / margins from memory, and never vibe the regime — it's YOUR read of the raw gauges, not a quoted label.
- Walk the funnel in dependency order: serenity-macro (regime / catalyst) -> serenity-discovery (find a US-listed name) -> serenity-analysis (gate, value, time, rate one name).
- The pipeline ships XBRL numbers only; invoke the serenity-filings subagent (Task tool) for the filing's relationship / financing narrative.
- If a ticker arrives WITH a selloff / crash / cost-scare / war-date, it's an EVENT first (macro catalyst test + cost-shock margin math) before the single-name read; and run the data-integrity identity (Total Assets >= Cash + Inventory + ...) before tagging an archetype — a phantom/stale number is itself the mispricing.
- Don't print priced / cheap / WATCH until the named valuation lens is RUN — show the bottom-up arithmetic (content x volume / MC, $/MW levered IRR, replacement-cost / unit, pro-forma FCF), each input traced; a standalone top-down multiple (the subject's own EV/Rev or PEG) is the consensus lens, not the verdict. On a comparable name, run `discover SUBJECT PEERS...` and rank.
- Carry a 3+-hop causal chain, a priced-in decomposition, an explicit bear case + falsifier; close with a rating + vehicle and sign off NFI/NFA."""


def main() -> None:
	try:
		data = json.load(sys.stdin)
	except Exception:  # noqa: BLE001 — never let a hook crash the turn
		return
	prompt = str(data.get("prompt") or "")
	if prompt.strip() and _INTENT.search(prompt):
		print(_REMINDER)


if __name__ == "__main__":
	main()
	sys.exit(0)
