#!/usr/bin/env python3
"""Stop hook — the verdict-gate, enforced (Hybrid: structure blocks, the firing-problem nudges).

WF4's durable finding: under output pressure the model reads the verdict procedures as labels and
skips them — "prose can't fix a firing problem." CLAUDE.md mandates a contract for every serenity
answer: a TLDR, the valuation lens RUN (arithmetic shown) not just named, a Downsides/bear block, a
falsifier, visible -> chains, and an NFI/NFA sign-off whose absence "reads as fake." This hook reads
the finished answer and holds that contract at the only place it can't be skipped — the end.

HYBRID (the chosen calibration): it HARD-BLOCKS only the near-universal, unambiguous miss — a
formatted serenity answer (carries a TLDR) with no NFI/NFA sign-off. The judgment-fuzzier gaps — a
valuation lens NAMED with no arithmetic anywhere (the exact 0/6 failure), a missing Downsides block,
no falsifier — are returned as Stop additionalContext, which continues the turn ONE round so the
model revises, shown as feedback rather than an error. A non-analysis turn (no TLDR) passes silently;
stop_hook_active guards against looping (one corrective round, then it lets the turn end).
"""

import json
import re
import sys


def _has(pattern, text):
	return re.search(pattern, text, re.IGNORECASE) is not None


def main():
	try:
		data = json.load(sys.stdin)
	except Exception:  # noqa: BLE001 — never let a hook crash the turn
		return
	# One corrective round only — if we're already continuing from this hook, let it stop.
	if data.get("stop_hook_active"):
		return
	msg = str(data.get("last_assistant_message") or "")
	if not msg.strip():
		return
	# Only gate a FORMATTED serenity answer — the contract requires a TLDR on every A/B/C/D/E reply.
	if not _has(r"\bTL;?DR\b", msg):
		return

	# Sign-off (EN + KO) — NFI/NFA is used verbatim even in Korean answers, but accept the
	# spelled-out forms too so a complete Korean verdict is never false-blocked.
	signoff = (
		_has(r"\bNF[IA]\b", msg)
		or _has(r"not (financial|investment) advice", msg)
		or _has(r"투자\s*(조언|자문|권유)\s*(아|x|X)", msg)
	)

	# Single-name signature — only then are the Downsides block / falsifier contractually required.
	single_name = (
		_has(r"\bDownside", msg)
		or _has(r"\bPT\b|price target|\brating\b|conviction", msg)
		or _has(r"\bLEAPS\b|\bCSP\b|covered call|\bvehicle\b", msg)
		or _has(r"목표가|투자의견|비중|매수|매도|벨류|밸류", msg)
	)

	lens_named = _has(
		r"EV/?\s*(Rev|FCF|EBITDA)|\bPEG\b|forward P/?E|content[\s-]*(x|×)|\$/?MW|per[\s-]*MW"
		r"|levered IRR|replacement[\s-]*(cost|value)|no[\s-]*growth|pro[\s-]*forma|net[\s-]*cash[\s-]*after",
		msg,
	)
	# Did any real arithmetic appear? a x / ÷ between numbers, an "= $", or a traced ratio.
	arithmetic = (
		_has(r"\d[\d.,]*\s*[BbMmTtKk%$]?\s*[×x*/÷]\s*\$?\d", msg)
		or _has(r"=\s*\$?\d", msg)
		or _has(r"÷", msg)
		or _has(r"\d[\d.,]*\s*(B|bn|billion|M|%)\b.*[/÷].*\b(MC|market\s*cap)", msg)
	)

	hard = []
	if not signoff:
		hard.append("the NFI/NFA sign-off — doctrine: its absence reads as fake. Add it.")

	soft = []
	if lens_named and not arithmetic:
		soft.append(
			"you NAMED a valuation lens but no arithmetic appears — RUN it: show the driver math "
			"(content×volume÷MC · $/MW levered IRR · replacement-cost-per-unit · "
			"pro-forma FCF · floor+option), each input traced to key_facts. A standalone top-down "
			"multiple is the consensus read, not the verdict (N10/R5)."
		)
	if single_name:
		if not _has(r"\bDownside|\bbear case\b|리스크|하방|약점", msg):
			soft.append("the short Downsides/bear block (2-4 casual bullets, each tagged priced-in / addressed).")
		if not _has(r"breaks if|falsif|kill[\s-]*(signal|condition)|wrong if|thesis breaks|깨지면|틀리면|무효|아니라면", msg):
			soft.append("an explicit falsifier ('breaks if ...') — V7/R6.")
		# Both-legs: the dominant direction-miss is running ONLY the bear/floor/discount leg of a
		# forked lens, which inverts a bull thesis. If a floor/discount/dilution figure is present
		# but no upside-direction figure is, nudge to run the bull leg too. SOFT only — a genuine
		# clean-kill verdict may legitimately have a zero bull leg, so never a hard block.
		bear_leg = _has(r"floor|discount|dilut|net[\s-]*debt|\bATM\b|priced for|bear[\s-]*leg|overhang", msg)
		bull_leg = _has(
			r"upside|re-?rate|leapfrog|replacement[\s-]*(cost|value)|bridge|pro[\s-]*forma|levered IRR"
			r"|\$/?MW|content[\s-]*(x|×)|supply[\s-]*shock|snapback|asymmetr|option leg|out-?multiple",
			msg,
		)
		if bear_leg and not bull_leg:
			soft.append(
				"you ran the floor/discount/bear leg but the UPSIDE leg is qualitative — a forked lens "
				"is HALF-run (R5): show the bull-leg arithmetic (the re-rate / replacement-cost steal / "
				"FCF bridge / content-leapfrog / supply-shock ASP) beside the floor and let the two legs "
				"FIGHT. A bear-leg-only call silently inverts a power-law long into a pass — run both "
				"legs, NOT 'resolve bullish'."
			)

	if hard:
		reason = "Your answer is a serenity verdict (it has a TLDR) but is missing " + " ".join(hard)
		if soft:
			reason += " While revising, also confirm: " + " ".join(soft)
		print(json.dumps({"decision": "block", "reason": reason}))
		return
	if soft:
		ctx = "[verdict-gate] Before this answer stands, close the contract: " + " ".join(soft)
		print(json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": ctx}}))


if __name__ == "__main__":
	main()
	sys.exit(0)
