#!/usr/bin/env python3
"""PostToolUse hook (Bash) — deterministic data-integrity tripwire on the pipeline's `analyze`.

Non-negotiable N9 opens every single-name read with a data-integrity pass: a ticker-collision /
stale / mis-tagged number is ITSELF the mispricing, and "one bad criterion among a hundred inverts
a call invisibly." This hook fires right after `serenity_pipeline.py analyze ...` returns and
recomputes the identity relationships the numbers MUST satisfy — pure arithmetic, never a thesis
judgment. It renders no verdict; it only flags when the numbers don't cohere (MC != price x shares,
float > shares out, operating margin > gross margin, price outside its 52-week range, EV far from
MC + debt - cash) so the agent reconciles the number BEFORE tagging an archetype. Coherent data ->
silent pass. It never blocks; it injects the flags as context.
"""

import json
import sys


def _num(value):
	return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _rel(a, b):
	"""Relative gap |a-b| / |b|, or None if not computable."""
	if a is None or b is None or not b:
		return None
	return abs(a - b) / abs(b)


def _money(x):
	if x is None:
		return "n/a"
	ax = abs(x)
	for unit, div in (("T", 1e12), ("B", 1e9), ("M", 1e6)):
		if ax >= div:
			return f"${x / div:.2f}{unit}"
	return f"${x:,.0f}"


def _checks(ev):
	kf = ev.get("key_facts") or {}
	dc = ((ev.get("fundamental_inputs") or {}).get("debt_and_cash")) or {}
	flags = []

	mc = _num(kf.get("marketCap"))
	price = _num(kf.get("currentPrice"))
	shares = _num(kf.get("sharesOutstanding"))
	float_sh = _num(kf.get("floatShares"))
	ev_val = _num(kf.get("enterpriseValue"))
	cash = _num(kf.get("totalCash"))
	gm = _num(kf.get("grossMargins"))
	om = _num(kf.get("operatingMargins"))
	lo = _num(kf.get("fiftyTwoWeekLow"))
	hi = _num(kf.get("fiftyTwoWeekHigh"))
	rev_kf = _num(kf.get("totalRevenue"))
	debt = _num(dc.get("total_debt"))
	rev_dc = _num(dc.get("total_revenue"))
	bs_cash = _num(dc.get("cash_and_equivalents"))

	# 1. MC == price x shares (the strongest collision / stale tripwire)
	if mc and price and shares:
		implied = price * shares
		r = _rel(implied, mc)
		if r is not None and r > 0.10:
			flags.append({
				"severity": "HARD" if r > 0.35 else "soft",
				"check": "marketCap vs price x sharesOutstanding",
				"observed": f"MC {_money(mc)} vs price x shares {_money(implied)} ({r * 100:.0f}% gap)",
				"read": "a >35% gap is a likely ticker-collision / stale capture — N9: that mismatch is itself the mispricing; reconcile before sizing. (Or a dual-class / multiple share-class structure, where `sharesOutstanding` is one class and MC counts all — confirm which before treating it as an error; this can't be told apart programmatically.)",
			})

	# 2. float <= shares outstanding (impossible otherwise)
	if float_sh and shares and float_sh > shares * 1.001:
		flags.append({
			"severity": "HARD",
			"check": "floatShares <= sharesOutstanding",
			"observed": f"float {float_sh:,.0f} > shares out {shares:,.0f}",
			"read": "float cannot exceed shares outstanding — a stale / mis-tagged share count.",
		})

	# 3. operating margin <= gross margin (impossible otherwise)
	if gm is not None and om is not None and om > gm + 0.005:
		flags.append({
			"severity": "HARD",
			"check": "operatingMargin <= grossMargin",
			"observed": f"operating {om * 100:.1f}% > gross {gm * 100:.1f}%",
			"read": "operating margin above gross margin is mechanically impossible — a mis-tagged / stale margin line.",
		})

	# 4. price within its own 52-week range
	if price and lo and hi and (price > hi * 1.02 or price < lo * 0.98):
		flags.append({
			"severity": "soft",
			"check": "currentPrice within 52-week range",
			"observed": f"price ${price:.2f} vs range ${lo:.2f}-${hi:.2f}",
			"read": "price sits outside its own 52w hi/lo — one of the two is stale; confirm before any price-extreme read.",
		})

	# 5. EV ~ MC + debt - cash (loose sanity on the EV the EV/Rev lens divides by)
	if ev_val and mc and (debt is not None or cash is not None):
		implied_ev = mc + (debt or 0) - (cash or 0)
		r = _rel(implied_ev, ev_val)
		if r is not None and r > 0.15:
			flags.append({
				"severity": "soft",
				"check": "enterpriseValue vs MC + debt - cash",
				"observed": f"EV {_money(ev_val)} vs MC+debt-cash {_money(implied_ev)} ({r * 100:.0f}% gap)",
				"read": "EV doesn't reconcile to MC + total_debt - cash; check which cash line was used before trusting EV/Rev.",
			})

	# 6. Two revenue figures diverge (informational — pick the denominator deliberately). Tiered
	#    the same way check #1 is: below the floor, timing alone explains part of the gap for a
	#    growing company, since dc.total_revenue is the last completed fiscal year while
	#    kf.totalRevenue (TTM) can run up to a year newer. The ceiling on "timing alone": a company
	#    whose revenue exactly doubles YoY (rare, hypergrowth-tier) viewed at maximum staleness —
	#    TTM = 3 quarters of the new year + 1 shared quarter, annual = 4 quarters of the old year —
	#    produces EXACTLY a 75% gap through timing alone (e.g. four quarters of 100 each vs the new
	#    year's 100+200+200+200: TTM 700 vs annual 400 -> 75%). Past 75%, timing can no longer
	#    explain it even for a name doubling revenue YoY — the two figures are more likely not the
	#    same metric on a different basis at all, i.e. check #1's collision/stale class (N9). The
	#    16th case: a small-cap where a 142%-scale gap would NOT look obviously wrong just from
	#    eyeballing the company's size — tiering by ratio, never by scale, is what catches it anyway.
	if rev_kf and rev_dc:
		r = _rel(rev_kf, rev_dc)
		if r is not None and r > 0.12:
			flags.append({
				"severity": "HARD" if r > 0.75 else "note",
				"check": "revenue figures (key_facts TTM vs debt_and_cash annual)",
				"observed": f"key_facts {_money(rev_kf)} vs debt_and_cash {_money(rev_dc)} ({r * 100:.0f}% apart)",
				"read": "two revenue bases differ (TTM vs annual) — divide each ratio by the one the lens actually calls for, deliberately; past a 75% gap that's beyond plausible timing drift even for a hypergrowth name, so it's likelier a stale/mis-tagged/collision figure (N9) — reconcile which one is real before dividing by either.",
			})

	# 7. Balance identity: Cash + Inventory <= Total Assets (both are line items WITHIN assets).
	#    A violation is mathematically impossible -> a mis-tagged / ticker-collision number; per N9
	#    the error IS the mispricing (the canonical $82M-phantom-inventory data-error catch).
	ta = _num(dc.get("total_assets"))
	inv = _num(dc.get("inventory"))
	if ta and inv is not None and bs_cash is not None and inv > 0:
		room = ta - bs_cash
		if inv > room * 1.02:
			flags.append({
				"severity": "HARD",
				"check": "balance identity: Inventory <= Total Assets - Cash",
				"observed": f"inventory {_money(inv)} > assets-minus-cash room {_money(room)} (TA {_money(ta)} - cash {_money(bs_cash)})",
				"read": "inventory exceeds the room left after cash on the balance sheet — mathematically impossible -> a mis-tagged / ticker-collision number (N9: the data error IS the mispricing). Reconcile via the serenity-filings subagent before tagging an archetype.",
			})

	# 8. Two cash figures diverge (informational — same shape as check #6, for cash instead of
	#    revenue). Check #5's `cash` is kf.totalCash — Yahoo's own info-API aggregate, the same
	#    source as the marketCap/enterpriseValue it reconciles against there. Check #7's `bs_cash`
	#    is dc.cash_and_equivalents — parsed off the raw balance sheet, the same source as the
	#    total_assets/inventory it reconciles against there. Each is internally consistent with ITS
	#    OWN check's other inputs, which is why neither is simply switched to the other's field:
	#    doing that would just relocate the cross-source mismatch into whichever check lost its
	#    matching source. Unlike check #6's two revenue figures (both meant to be the same fiscal
	#    concept, give or take timing), "total cash" and "cash and equivalents" are DEFINITIONALLY
	#    allowed to differ — totalCash routinely folds in short/long-term investments a treasury-
	#    heavy company holds, so a large gap is normal at megacap scale, not evidence of an error.
	#    There is no timing-style ceiling to derive here the way check #6 has one; 0.20 is just a
	#    floor set above ordinary pull-timing/rounding noise between the two data sources, low
	#    enough to still surface the common case (any company running a real investment portfolio)
	#    where the two numbers mean visibly different things. That is exactly why this stays a soft
	#    note unconditionally, never HARD: it exists so a downstream cash-based read (net cash, cash
	#    runway) picks its field on purpose, not by whichever of #5/#7 happened to fire.
	if cash and bs_cash:
		r = _rel(cash, bs_cash)
		if r is not None and r > 0.20:
			flags.append({
				"severity": "soft",
				"check": "cash figures (key_facts totalCash vs debt_and_cash cash_and_equivalents)",
				"observed": f"key_facts {_money(cash)} vs debt_and_cash {_money(bs_cash)} ({r * 100:.0f}% apart)",
				"read": "totalCash (often cash + short/long-term investments) and cash_and_equivalents (balance-sheet line only) are different concepts by definition, not a discrepancy to resolve — confirm which one a cash-based read (net cash, runway) actually means before treating either as THE cash figure.",
			})

	return flags


def main():
	try:
		data = json.load(sys.stdin)
	except Exception:  # noqa: BLE001 — never let a hook crash the turn
		return
	if data.get("tool_name") != "Bash":
		return
	cmd = str((data.get("tool_input") or {}).get("command") or "")
	if "serenity_pipeline" not in cmd or "analyze" not in cmd:
		return
	resp = data.get("tool_response")
	stdout = ""
	if isinstance(resp, dict):
		stdout = str(resp.get("stdout") or "")
	elif isinstance(resp, str):
		stdout = resp
	idx = stdout.find("{")
	if idx < 0:
		return
	try:
		ev = json.loads(stdout[idx:])
	except Exception:  # noqa: BLE001 — piped/truncated output is not a failure
		return
	if not isinstance(ev, dict):
		return
	flags = _checks(ev)
	if not flags:
		return
	lines = ["[data-integrity] Deterministic identity checks on the analyze numbers (NOT a thesis judgment) tripped — reconcile before tagging an archetype (N9):"]
	for f in flags:
		lines.append(f"- [{f['severity']}] {f['check']}: {f['observed']} — {f['read']}")
	lines.append("A HARD flag is a likely phantom / stale / collision number (re-run with fixed args, or confirm via the serenity-filings subagent); a soft/note just means choose the denominator deliberately. Don't let a bad number author the call.")
	ctx = "\n".join(lines)
	print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": ctx}}))


if __name__ == "__main__":
	main()
	sys.exit(0)
