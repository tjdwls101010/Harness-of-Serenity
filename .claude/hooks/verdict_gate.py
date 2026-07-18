#!/usr/bin/env python3
"""Stop hook — the verdict-gate, enforced as a STRUCTURAL contract (not a semantic judge).

WF4's durable finding: under output pressure the model reads the verdict procedures as labels and
skips them — "prose can't fix a firing problem." But a Stop hook cannot judge whether an argument is
*right*; it can only check whether the answer carries the machine-readable MARKS the contract
requires. So the contract (CLAUDE.md "How the answer reads" + analysis §6) mandates one visible token
for a valuation verdict — a `Lens:` line that combines the driver inputs with ×/÷ and ends in
`= <result>` (a forked lens prints two: a floor line and an upside line) — and this hook checks for
that token's PRESENCE, never for the semantics of the math. The old check inferred "arithmetic ran"
from `= <digit>`, which a bare top-down multiple ("EV/Rev = 12x") satisfied — the exact miss it was
meant to catch. Structure, not meaning: is the Lens line there or not.

Calibration: a missing Lens line is returned as SOFT feedback (one corrective round via Stop
additionalContext), never a hard block, until real use confirms no false-fires — then it can be
promoted. The one HARD block is the near-universal, unambiguous miss: a formatted market answer (a
TLDR *and* a finance signal) with no NFI/NFA sign-off, whose absence doctrine says "reads as fake."
A non-market turn (a coding answer that happens to say "TL;DR") is not a finance answer, so it is
never hard-blocked. stop_hook_active guards the loop: one corrective round, then the turn ends.

The `Saved:` branch (the session-archive contract, CLAUDE.md "The session archive") is the same
structural philosophy: a finance VERDICT (single_name or a strong market verdict — NOT a bare
cashtag or a casual macro aside) should carry a visible `Saved: sessions/{yymmdd}.{slug}/` mark, and
the archive folder it names must really exist AND hold at least one `.md` artifact. Checking the
mark's SHAPE + the folder's non-emptiness (never its content quality) keeps this a structural check,
and it stays SOFT — a costless empty `mkdir` or a `Saved: sessions/INDEX.md` token would otherwise
be a compliance token that falsely certifies archiving, which is exactly why the shape/non-empty
checks exist before this could ever be promoted to hard.
"""

import json
import os
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

	# Finance signal — is this a MARKET answer at all (vs. a coding summary with a "TL;DR")? The
	# NFI/NFA sign-off is only contractually required on a market answer, so the hard block gates on
	# this, not on the TLDR alone (a coding answer must never be asked for a financial disclaimer).
	single_name = (
		_has(r"\bDownside", msg)
		or _has(r"\bPT\b|price target|\brating\b|conviction", msg)
		or _has(r"\bLEAPS\b|\bCSP\b|covered call|\bvehicle\b", msg)
		or _has(r"목표가|투자의견|비중|매수|매도|벨류|밸류", msg)
	)
	# Strong, unambiguous market-verdict phrases — safe to gate the hard NFI block on. Bare "pass"
	# ("tests pass") and generic doctrine nouns ("bottleneck" — a perf discussion, or this repo's own
	# doctrine talk) are deliberately EXCLUDED here: they false-fire on a coding / harness-dev answer.
	strong_verdict = _has(
		r"priced[\s-]*in|priced for|overvalued|undervalued|fairly valued|고평가|저평가"
		r"|\bWATCH\b|overweight|underweight|비중확대|비중축소",
		msg,
	)
	# Finance signal — is this a MARKET answer at all (vs. a coding summary that happens to carry a
	# "TL;DR")? The NFI/NFA sign-off is only contractually required on a market answer, so the hard
	# block gates on THIS, not on the TLDR alone. Kept tight so a coding / harness answer is never
	# asked for a financial disclaimer.
	finance_signal = (
		single_name
		or strong_verdict
		or _has(r"\$[A-Za-z]{1,5}\b", msg)  # cashtag
	)
	# Valuation-verdict signal for the (soft) Lens-line check — broader than strong_verdict, since a
	# miss here is only a one-round nudge, but still avoids bare "pass" so "tests pass" can't trip it.
	valuation_verdict = strong_verdict or _has(
		r"\bcheap\b|\bexpensive\b|pass on|hard pass|저평가|고평가", msg
	)

	lens_named = _has(
		r"EV/?\s*(Rev|FCF|EBITDA)|\bPEG\b|forward P/?E|content[\s-]*(x|×)|\$/?MW|per[\s-]*MW"
		r"|levered IRR|replacement[\s-]*(cost|value)|no[\s-]*growth|pro[\s-]*forma|net[\s-]*cash[\s-]*after",
		msg,
	)
	# STRUCTURAL check (not semantic): the contract's `Lens:` driver line — the literal token, a
	# real multiply/divide operator (×/÷/*, the doctrine's driver notation — NOT a bare "/" inside a
	# ratio name or an "x" inside a multiple), and an "=" on the same line. A bare top-down multiple
	# ("EV/Rev = 12x") has no ×/÷/* and so correctly does NOT satisfy this — that is the whole point.
	lens_marker = (
		_has(r"Lens:[^\n]*[×÷*][^\n]*=", msg)
		or _has(r"Lens:[^\n]*=[^\n]*[×÷*]", msg)
	)

	hard = []
	if finance_signal and not signoff:
		hard.append("the NFI/NFA sign-off — doctrine: its absence reads as fake. Add it.")

	soft = []
	# You reached a valuation verdict (named a lens or rendered priced/cheap/pass) but no machine-
	# checkable `Lens:` driver line is present — RUN it on one visible line.
	if (lens_named or valuation_verdict) and not lens_marker:
		soft.append(
			"you rendered a valuation verdict but no machine-checkable `Lens:` line appears — emit it: "
			"`Lens: <name> — <input>×<input>÷<input> = <result>` (a forked lens shows two, floor and "
			"upside), each input traced to key_facts. A named lens with no computed driver line is the "
			"consensus top-down read, not the verdict (N10 / R5)."
		)
	if single_name:
		if not _has(r"\bDownside|\bbear case\b|리스크|하방|약점", msg):
			soft.append("the short Downsides/bear block (2-4 casual bullets, each tagged priced-in / addressed).")
		if not _has(r"breaks if|falsif|kill[\s-]*(signal|condition)|wrong if|thesis breaks|깨지면|틀리면|무효|아니라면", msg):
			soft.append("an explicit falsifier ('breaks if ...') — V7/R6.")
		# Both-legs: the dominant direction-miss is running ONLY the bear/floor/discount leg of a
		# forked lens, which inverts a bull thesis. If a floor/discount figure is present but no
		# upside-direction figure is, nudge to run the bull leg too. SOFT only — a genuine clean-kill
		# verdict may legitimately have a zero bull leg, so never a hard block.
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

	# --- Session-archive Saved: mark (soft; CLAUDE.md "The session archive") ---
	# Gate on a real finance VERDICT (single_name or a strong market verdict), never a bare cashtag
	# or a casual macro aside — a verdict is what doctrine says gets archived. Check the mark's SHAPE
	# and the folder's non-emptiness, never its content: a structural check, like the Lens branch.
	if single_name or strong_verdict:
		mark = re.search(r"Saved:\s*`?(sessions/\d{6}\.[a-z0-9-]+(?:-\d+)?/?)", msg, re.IGNORECASE)
		if not mark:
			if _has(r"Saved:", msg):
				soft.append(
					"a `Saved:` line is present but not a valid session path — it must read "
					"`Saved: sessions/{yymmdd}.{topic-slug}/` (CLAUDE.md, 'The session archive')."
				)
			else:
				soft.append(
					"this verdict isn't archived — write the scorecard/synthesis to "
					"sessions/{yymmdd}.{topic}/, update INDEX.md, and add the `Saved:` line "
					"(CLAUDE.md, 'The session archive')."
				)
		else:
			rel = mark.group(1).rstrip("`.,; ").rstrip("/")
			base = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
			folder = os.path.join(base, rel)
			try:
				is_dir = os.path.isdir(folder)
				has_md = is_dir and any(f.endswith(".md") for f in os.listdir(folder))
			except OSError:
				is_dir, has_md = False, False
			if not is_dir:
				soft.append(
					f"the `Saved:` mark claims `{rel}/` but no such session folder exists — create it "
					"and write the scorecard/synthesis before the answer claims it's archived."
				)
			elif not has_md:
				soft.append(
					f"the `Saved:` folder `{rel}/` exists but holds no `.md` scorecard/synthesis — an "
					"empty folder isn't an archive; write the TICKER.md / _ranking.md into it."
				)

	if hard:
		reason = "Your answer is a serenity market verdict (TLDR + a finance signal) but is missing " + " ".join(hard)
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
