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

	# 1. MC == price x shares (the strongest collision / stale tripwire)
	if mc and price and shares:
		implied = price * shares
		r = _rel(implied, mc)
		if r is not None and r > 0.10:
			flags.append({
				"severity": "HARD" if r > 0.35 else "soft",
				"check": "marketCap vs price x sharesOutstanding",
				"observed": f"MC {_money(mc)} vs price x shares {_money(implied)} ({r * 100:.0f}% gap)",
				"read": "a >35% gap is a likely ticker-collision / stale capture — N9: that mismatch is itself the mispricing; reconcile before sizing.",
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

	# 6. Two revenue figures diverge (informational — pick the denominator deliberately)
	if rev_kf and rev_dc:
		r = _rel(rev_kf, rev_dc)
		if r is not None and r > 0.12:
			flags.append({
				"severity": "note",
				"check": "revenue figures (key_facts TTM vs debt_and_cash annual)",
				"observed": f"key_facts {_money(rev_kf)} vs debt_and_cash {_money(rev_dc)} ({r * 100:.0f}% apart)",
				"read": "two revenue bases differ (TTM vs annual) — divide each ratio by the one the lens actually calls for, deliberately.",
			})

	# 7. Balance identity: Cash + Inventory <= Total Assets (both are line items WITHIN assets).
	#    A violation is mathematically impossible -> a mis-tagged / ticker-collision number; per N9
	#    the error IS the mispricing (the canonical $82M-phantom-inventory data-error catch).
	ta = _num(dc.get("total_assets"))
	inv = _num(dc.get("inventory"))
	bs_cash = _num(dc.get("cash_and_equivalents"))
	if ta and inv is not None and bs_cash is not None and inv > 0:
		room = ta - bs_cash
		if inv > room * 1.02:
			flags.append({
				"severity": "HARD",
				"check": "balance identity: Inventory <= Total Assets - Cash",
				"observed": f"inventory {_money(inv)} > assets-minus-cash room {_money(room)} (TA {_money(ta)} - cash {_money(bs_cash)})",
				"read": "inventory exceeds the room left after cash on the balance sheet — mathematically impossible -> a mis-tagged / ticker-collision number (N9: the data error IS the mispricing). Reconcile via the serenity-filings subagent before tagging an archetype.",
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
