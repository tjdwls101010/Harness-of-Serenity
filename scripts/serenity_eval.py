#!/usr/bin/env python3
"""serenity_eval.py — the reproduction-measurement harness (design-review plan §5).

This is NOT a runtime tool the analyst uses. It exists to answer one question the doctrine
can't answer by inspection: does the harness actually REPRODUCE Serenity's method on real past
cases — and where it misses, is the fix a *generalized principle* or (the anti-pattern §0 names)
another case-specific rule? WF4 found the harness reproduces the framework but skips signature
moves; this makes that check repeatable instead of one-off.

Three DETERMINISTIC subcommands live here (no tokens, no LLM, no network):

  sample  — a stratified, SEEDED sample of N past theses from analysis_Serenity.db → a cases
            JSON. Each case carries a BLIND prompt (the situation, with the thesis hidden) and
            the answer-key thesis (shown only to the judge, never to the harness-under-test).
            Deterministic: same (n, seed) → same cases, so a re-run after a doctrine edit is a
            true before/after.
  rubric  — the signature-move scoring checklist, as data — the single source of truth the judge
            scores against and the report aggregates.
  report  — aggregate a scored-cases JSON → a markdown eval report + a prioritized DOCTRINE-DELTA
            list, where every delta names the EXISTING principle to generalize (never a new rule).

The token-spending middle — blind-running each case through the harness and judging the output —
is a dynamic workflow the USER triggers explicitly (see scripts/eval/README.md). That keeps this
aligned with N8: the thesis DB is an answer key, touched only on an explicit request.

Honesty on stratification: the DB has no archetype/entry-type labels, so this CANNOT stratify by
archetype (naming the archetype is precisely what we're testing — the harness does it, not the
sampler). It stratifies by an ENTRY-TYPE keyword heuristic and enforces ticker diversity + date
spread, and it prints the method so a skew is visible, never silent.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sqlite3
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_DB = os.path.join(_HERE, os.pardir, "data", "analysis_Serenity.db")

# ---------------------------------------------------------------------------
# The scoring rubric — signature-move reproduction. Single source of truth.
# ---------------------------------------------------------------------------
# Each item is one checklist question the judge answers per case. `scope: chokepoint` items
# are scored only when the harness (or the answer-key thesis) framed the name as a chokepoint —
# a disruptor/evolution case legitimately has no recursive-bottom-hop, so scoring it there would
# manufacture a miss. `free` items collect prose (the missed moves), not a 0/1.
RUBRIC = [
	{
		"key": "archetype_named",
		"scope": "all",
		"question": "Did it NAME the archetype (chokepoint / disruption / evolution) off the name's own "
					"economics, without escaping to a softer lens than the name earns?",
	},
	{
		"key": "lens_run",
		"scope": "all",
		"question": "Was the archetype's valuation lens RUN — driver arithmetic shown (content×vol÷MC, "
					"$/MW levered IRR, replacement-cost/unit, pro-forma FCF, supply-shock ASP), each input "
					"traced — and BOTH legs shown if the lens forks (floor AND upside)? A named-but-not-run "
					"lens, or a bare top-down multiple, scores 0.",
	},
	{
		"key": "recursive_bottom_hop",
		"scope": "chokepoint",
		"question": "Was the chain traced to its RECURSIVE bottom hop (the feedstock / purity / crystal-growth "
					"substep under the headline node — bottleneck within a bottleneck), not just the visible node?",
	},
	{
		"key": "second_order_and_sibling",
		"scope": "chokepoint",
		"question": "Did it surface at least one SECOND-ORDER allocation effect (who stockpiles / buys out "
					"allocation / acquires the node) AND rank at least one chain-sibling (substrate↔component↔module)?",
	},
	{
		"key": "bear_and_falsifier",
		"scope": "all",
		"question": "Did it carry an explicit BEAR case AND a falsifier ('breaks if …') — not a one-sided pitch?",
	},
	{
		"key": "priced_in_decomposed",
		"scope": "all",
		"question": "Did it decompose what is vs. isn't priced in (the mispricing gap named), rather than "
					"restating consensus multiples?",
	},
	{
		"key": "missed_signature_moves",
		"scope": "free",
		"question": "Which signature moves that Serenity ACTUALLY used in the answer-key thesis did the harness "
					"MISS or get materially weaker on? List each as a short phrase (empty list if none).",
	},
	{
		"key": "notes",
		"scope": "free",
		"question": "One-line overall: did the harness reach the SAME structural insight as the thesis, a weaker "
					"version, or a different (and defensible?) one?",
	},
]

# Entry-type heuristics — keyword signals only; the archetype itself is NOT guessed here.
_EVENT_RE = re.compile(
	r"\b(earnings|guidance|8-?K|10-?[KQ]|results|reported|beat|missed|acquisition|acqui|merger|"
	r"contract|award|offtake|downgrade|upgrade|guided|pre-?announce|filing|lawsuit|recall|"
	r"export control|sanction|tariff)\b",
	re.IGNORECASE,
)
_FEAR_RE = re.compile(
	r"(sell-?off|selloff|crash|plunge|plunged|tanked|dropped|fell|crater|-\s?\d{2}\s?%|down\s?\d{2}\s?%|"
	r"oversold|fear|panic|dip|bottom|blood|dislocat|knife|capitulat)",
	re.IGNORECASE,
)


def _entry_type(content: str) -> str:
	"""fear_dip / event / discovery from content keywords. discovery is the default — a
	'why is X this cheap / X is the bottleneck' thesis with no crash or catalyst framing."""
	if _FEAR_RE.search(content):
		return "fear_dip"
	if _EVENT_RE.search(content):
		return "event"
	return "discovery"


def _primary_ticker(tickers_raw: str) -> str | None:
	"""First plausible US ticker from the JSON `tickers` array (1-5 alpha chars)."""
	try:
		arr = json.loads(tickers_raw or "[]")
	except Exception:  # noqa: BLE001
		return None
	for t in arr if isinstance(arr, list) else []:
		t = str(t).strip().upper()
		if re.fullmatch(r"[A-Z]{1,5}", t):
			return t
	return None


def _blind_prompt(ticker: str, date: str, entry_type: str) -> str:
	"""Reconstruct the SITUATION as a user question, with the thesis hidden. The harness must
	produce its own read; the answer-key thesis is never shown to it."""
	day = (date or "")[:10]
	if entry_type == "fear_dip":
		return (f"{ticker} sold off hard around {day}. Is this a real fundamental break or a fear-dip "
				f"I should be buying? Give me your full read.")
	if entry_type == "event":
		return (f"There's a catalyst on {ticker} around {day} (earnings / news / a filing). What's your "
				f"take — does it change the forward-revenue picture, and is the move an opportunity?")
	return (f"What's your read on {ticker}? Is it structurally mispriced right now, and if so, how would "
			f"you play it?")


def _load_rows(db_path: str) -> list[dict]:
	if not os.path.isfile(db_path):
		print(f"error: DB not found at {db_path} (pass --db)", file=sys.stderr)
		sys.exit(2)
	con = sqlite3.connect(db_path)
	con.row_factory = sqlite3.Row
	try:
		rows = con.execute(
			"SELECT id, created_at, type, tickers, content FROM tweets"
		).fetchall()
	finally:
		con.close()
	return [dict(r) for r in rows]


def cmd_sample(args) -> None:
	rows = _load_rows(args.db)
	# Substantive single-name theses only: a tagged ticker, real length, a first-party post/subscriber
	# (not a reply), and a resolvable primary ticker.
	pool = []
	seen_by_ticker: dict[str, list[dict]] = {}
	for r in rows:
		if r.get("type") not in ("post", "subscriber"):
			continue
		content = (r.get("content") or "").strip()
		if len(content) < args.min_len:
			continue
		ticker = _primary_ticker(r.get("tickers") or "")
		if not ticker:
			continue
		case = {
			"id": r.get("id"),
			"ticker": ticker,
			"date": r.get("created_at"),
			"type": r.get("type"),
			"entry_type": _entry_type(content),
			"thesis_text": content,
		}
		pool.append(case)
		seen_by_ticker.setdefault(ticker, []).append(case)

	if not pool:
		print("error: no eligible theses in the DB after filtering", file=sys.stderr)
		sys.exit(2)

	rng = random.Random(args.seed)
	# Stratify by entry_type; within each bucket enforce distinct tickers, prefer subscriber
	# (deepest) and longer theses, then round-robin the buckets to N so no entry-type dominates.
	buckets: dict[str, list[dict]] = {"fear_dip": [], "event": [], "discovery": []}
	for case in pool:
		buckets[case["entry_type"]].append(case)

	chosen: list[dict] = []
	used_tickers: set[str] = set()
	# The seed controls the sample: shuffle each bucket, then STABLE-sort by depth so the deepest
	# theses (subscriber, or long) come first while their order WITHIN a depth tier stays the seeded
	# shuffle. Same seed → same cases (a true before/after); a different seed → a different subset of
	# comparably-deep theses (broader coverage across rounds), not the same eight every time.
	def _depth(c: dict) -> int:
		return 0 if (c["type"] == "subscriber" or len(c["thesis_text"]) >= 800) else 1

	for b in buckets.values():
		rng.shuffle(b)
		b.sort(key=_depth)

	order = ["fear_dip", "event", "discovery"]
	i = 0
	while len(chosen) < args.n and any(buckets[b] for b in order):
		b = order[i % len(order)]
		i += 1
		bucket = buckets[b]
		# pop the next case whose ticker isn't already used
		picked = None
		for idx, c in enumerate(bucket):
			if c["ticker"] not in used_tickers:
				picked = bucket.pop(idx)
				break
		if picked is None and bucket:
			picked = bucket.pop(0)  # exhausted distinct tickers; allow a repeat rather than under-fill
		if picked is not None:
			used_tickers.add(picked["ticker"])
			picked["blind_prompt"] = _blind_prompt(picked["ticker"], picked["date"], picked["entry_type"])
			chosen.append(picked)

	dist = {b: sum(1 for c in chosen if c["entry_type"] == b) for b in order}
	out = {
		"meta": {
			"n": len(chosen),
			"requested": args.n,
			"seed": args.seed,
			"min_len": args.min_len,
			"eligible_pool": len(pool),
			"entry_type_distribution": dist,
			"stratification": "entry-type keyword heuristic + distinct primary tickers; archetype is "
							   "NOT stratified (undeterminable from the DB — the harness names it, that's "
							   "what's under test). A skew in entry_type_distribution above means the DB "
							   "itself is skewed, not a silent cap.",
			"note": "Each case's thesis_text is the ANSWER KEY — pass it only to the judge, NEVER to the "
					"harness-under-test. The harness sees blind_prompt alone.",
		},
		"cases": chosen,
	}
	print(json.dumps(out, indent=2, ensure_ascii=False))


def cmd_rubric(args) -> None:
	print(json.dumps({
		"rubric": RUBRIC,
		"scoring": {
			"scale": "each non-free item: 1 (met), 0 (not met), or \"n/a\" (out of scope for this case's "
					 "archetype). free items: prose.",
			"reproduction_rate": "mean of the 0/1 items that are in-scope (n/a excluded) across cases.",
		},
		"feedback_rule": (
			"For every RECURRING miss (a signature move dropped in >=2 cases), the fix is to GENERALIZE an "
			"EXISTING principle — name the R#/V#/NN#/skill-section that should already cover it, and widen its "
			"trigger or its why. Do NOT add a case-specific rule: that is the per-miss-patching病因 §0 names, and "
			"it grows the spine without covering the 17th case. A one-off miss is a monitoring item, not a delta."
		),
	}, indent=2, ensure_ascii=False))


def cmd_report(args) -> None:
	with open(args.results, encoding="utf-8") as fh:
		data = json.load(fh)
	cases = data.get("cases") if isinstance(data, dict) else data
	if not isinstance(cases, list) or not cases:
		print("error: results JSON has no `cases` list", file=sys.stderr)
		sys.exit(2)

	scored_keys = [it["key"] for it in RUBRIC if it["scope"] != "free"]
	# per-item reproduction rate (n/a excluded)
	rates: dict[str, tuple[int, int]] = {k: (0, 0) for k in scored_keys}  # (met, in_scope)
	missed_tally: dict[str, int] = {}
	for c in cases:
		sc = c.get("scores") or {}
		for k in scored_keys:
			v = sc.get(k)
			if v in (0, 1):
				met, tot = rates[k]
				rates[k] = (met + int(v == 1), tot + 1)
		for m in (sc.get("missed_signature_moves") or c.get("missed_signature_moves") or []):
			key = str(m).strip().lower()
			if key:
				missed_tally[key] = missed_tally.get(key, 0) + 1

	lines = ["# Serenity harness — reproduction eval report", ""]
	meta = data.get("meta") if isinstance(data, dict) else None
	if meta:
		lines += [f"- cases: {len(cases)} | seed: {meta.get('seed')} | entry-type dist: "
				  f"{meta.get('entry_type_distribution')}", ""]
	# overall
	overall_met = sum(m for m, _ in rates.values())
	overall_tot = sum(t for _, t in rates.values())
	overall = (overall_met / overall_tot) if overall_tot else 0.0
	lines += [f"**Overall reproduction rate: {overall:.0%}** ({overall_met}/{overall_tot} in-scope checks met)", ""]

	lines += ["## Per-move reproduction", "", "| signature move | rate | met / in-scope |", "|---|---|---|"]
	for k in scored_keys:
		met, tot = rates[k]
		r = f"{(met/tot):.0%}" if tot else "—"
		lines.append(f"| {k} | {r} | {met} / {tot} |")
	lines.append("")

	lines += ["## Per-case", "", "| ticker | entry | " + " | ".join(scored_keys) + " | note |",
			  "|---|---|" + "|".join("---" for _ in scored_keys) + "|---|"]
	for c in cases:
		sc = c.get("scores") or {}
		cells = []
		for k in scored_keys:
			v = sc.get(k)
			cells.append("✓" if v == 1 else ("✗" if v == 0 else "–"))
		note = str(sc.get("notes") or c.get("notes") or "").replace("|", "/")[:80]
		lines.append(f"| {c.get('ticker')} | {c.get('entry_type')} | " + " | ".join(cells) + f" | {note} |")
	lines.append("")

	lines += ["## Doctrine deltas (recurring misses → GENERALIZE an existing principle)", ""]
	recurring = sorted(((m, n) for m, n in missed_tally.items() if n >= 2), key=lambda x: -x[1])
	if recurring:
		lines.append("Each recurring miss below must be closed by widening an EXISTING principle's trigger/why "
					 "(name it), NOT by a new case-rule (§0). One-off misses are monitoring items, listed after.")
		lines.append("")
		for m, n in recurring:
			lines.append(f"- **{m}** — missed in {n} cases → which existing R#/V#/NN#/skill-section should "
						 f"already trigger this? Generalize that. (fill in)")
	else:
		lines.append("No move was missed in ≥2 cases — no doctrine delta warranted (per-miss patching guard).")
	oneoffs = sorted((m for m, n in missed_tally.items() if n == 1))
	if oneoffs:
		lines += ["", "Monitoring items (one-off misses — do NOT add a rule): " + ", ".join(oneoffs)]

	print("\n".join(lines))


def main() -> int:
	p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	p.add_argument("--db", default=_DEFAULT_DB, help="Path to analysis_Serenity.db")
	sub = p.add_subparsers(dest="cmd", required=True)

	s = sub.add_parser("sample", help="Stratified, seeded sample of past theses → cases JSON")
	s.add_argument("--n", type=int, default=8, help="Number of cases (default 8)")
	s.add_argument("--seed", type=int, default=7, help="RNG seed (deterministic; default 7)")
	s.add_argument("--min-len", type=int, default=400, help="Min thesis length in chars (default 400)")
	s.set_defaults(func=cmd_sample)

	r = sub.add_parser("rubric", help="Print the signature-move scoring rubric + feedback rule")
	r.set_defaults(func=cmd_rubric)

	rp = sub.add_parser("report", help="Aggregate a scored-cases JSON → markdown report + doctrine deltas")
	rp.add_argument("--results", required=True, help="Path to the scored-cases JSON")
	rp.set_defaults(func=cmd_report)

	args = p.parse_args()
	args.func(args)
	return 0


if __name__ == "__main__":
	sys.exit(main())
