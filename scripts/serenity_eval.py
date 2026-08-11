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

Honesty on stratification: the DB has no archetype/entry-type labels for the general pool, so the
RANDOM remainder cannot be stratified by archetype (naming the archetype is precisely what we're
testing — the harness does it, not the sampler). It stratifies by an ENTRY-TYPE keyword heuristic
and enforces ticker diversity + date spread, and it prints the method so a skew is visible, never
silent. The archetype floor comes from the other direction: `scripts/eval/gold_set.json` force-
includes twelve hand-labeled cases covering all six archetype categories, so a draw can never be
archetype-blind even though the pool is unlabeled.

Three things here exist because the instrument was measuring nothing, and each is worth knowing
before you touch this file:

  * A sampled ticker is RESOLVED before its case is accepted. Verified on the n=25/seed=7 draw:
    SIVE, ASHM, XFAB and APPL all returned empty pipeline data — 16% of the sample had no facts to
    build a `Lens:` line from and scored near-zero on grounds unrelated to doctrine quality. APPL
    is a typo for AAPL in the source post and yfinance happily resolves it to an unrelated mutual
    fund, which is the harness's own ticker-collision gotcha turned on the eval.
  * Resolution answers are CACHED to a committed file, so `sample` stays deterministic. Same
    (n, seed) must yield the same cases or a before/after comparison is meaningless, and a live
    network call makes the sample composition depend on yfinance's mood that afternoon.
  * `archetype` is persisted at sample time rather than re-decided by the judge each pass. A
    borderline case re-scoped on every run can flip n/a<->0 between two scorings of the IDENTICAL
    answer — a false regression with zero underlying change, which no increase in n removes.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sqlite3
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_DB = os.path.join(_HERE, os.pardir, "data", "analysis_Serenity.db")
_DEFAULT_GOLD = os.path.join(_HERE, "eval", "gold_set.json")
_DEFAULT_RESOLUTION_CACHE = os.path.join(_HERE, "eval", "ticker_resolution_cache.json")
_VERDICT_GATE = os.path.join(_HERE, os.pardir, ".claude", "hooks", "verdict_gate.py")

# The two rubric items a non-chokepoint name legitimately has no answer for. Scoring a disruptor 0
# on "did it trace to the recursive bottom hop" manufactures a miss out of a correct answer.
_CHOKEPOINT_SCOPED = {"recursive_bottom_hop", "second_order_and_sibling"}

# Below this many in-scope cases, `report` prints "insufficient n" instead of a percentage. The
# power arithmetic behind it (α=0.05 two-sided, 80% power): detecting a 50%→70% shift needs ≈90
# in-scope cases, 60%→90% needs ≈29, and only a ≈40-point swing drops to ≈20. So no realistic n
# here supports a confident per-move claim, and the floor is not the threshold where the number
# becomes trustworthy — it is the threshold below which it is actively misleading. A 100%-on-one-
# case row is the failure being prevented: it reads as a result.
_DEFAULT_N_FLOOR = 12

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


# A thesis that names a ticker only to DISCLAIM it. Case 2059532571839729902 tags ["DPZ"] and reads
# "This was the company i personally liked... Definitely not $DPZ. But kinda reminds me of Soitec" —
# so `_primary_ticker` returns DPZ (the only regex-valid ticker present) and the blind prompt asks
# for a read on Domino's Pizza while the answer key is about an unnamed European power-semi name.
# Every one of the six binary items is then tallied as a miss.
#
# This is a PROXY and is documented as one: "not X, but something like it" is a normal way to write
# and a regex will keep losing to rhetorical anchoring in general. The structural answer is that the
# standing regression sample is inspected once by a human and FROZEN, not re-drawn every run — this
# guard only keeps the obvious cases out of that one inspection pass.
_NEGATION_RE = re.compile(
	r"(?:\bnot\b|\bisn'?t\b|\bain'?t\b|\bnever\b|\bunlike\b|\bbesides\b|\bother than\b|\bexcept\b"
	r"|아닌|아니라|아니고|말고|제외)"
	r"[^.!?\n]{0,24}$",
	re.IGNORECASE,
)


def _is_disclaimed(ticker: str, content: str) -> bool:
	"""True when EVERY mention of `ticker` sits just after a negation.

	Deliberately not "any mention" — a thesis that says "unlike $INTC, $AMD ..." legitimately
	negates one ticker while being about it. Requiring all mentions to be disclaimed keeps the
	guard on the case it was built for."""
	spans = [m.start() for m in re.finditer(rf"\${ticker}\b|\b{ticker}\b", content, re.IGNORECASE)]
	if not spans:
		return False
	return all(_NEGATION_RE.search(content[max(0, i - 40):i]) for i in spans)


def _load_gold_set(path: str) -> list[dict]:
	"""The twelve hand-curated, archetype-labeled cases that are force-included in every sample.

	Missing file is a hard error, never a silent empty list: a sample that quietly lost its
	archetype floor looks exactly like a healthy one, and the two chokepoint-scoped rubric items
	would go back to whatever a random draw happened to contain."""
	if not os.path.isfile(path):
		print(f"error: gold set not found at {path} (pass --gold, or --no-gold to sample without it)",
			  file=sys.stderr)
		sys.exit(2)
	with open(path, encoding="utf-8") as fh:
		data = json.load(fh)
	cases = data.get("cases") or []
	if not cases:
		print(f"error: gold set at {path} has no `cases`", file=sys.stderr)
		sys.exit(2)
	return cases


def _load_resolution_cache(path: str) -> dict:
	if not os.path.isfile(path):
		return {}
	try:
		with open(path, encoding="utf-8") as fh:
			return (json.load(fh) or {}).get("tickers") or {}
	except (OSError, ValueError):
		return {}


def _save_resolution_cache(path: str, tickers: dict) -> None:
	os.makedirs(os.path.dirname(path), exist_ok=True)
	payload = {
		"_meta": {
			"what": "yfinance resolution answers, cached so `sample` is deterministic and offline-"
					"reproducible. Same (n, seed) must yield the same cases or a before/after "
					"comparison measures the network, not a doctrine edit.",
			"refresh": "delete an entry (or the file) to re-resolve it. Entries do not expire on "
					   "their own: a ticker that resolved once does not stop being a real company, "
					   "and an automatic refresh would reintroduce exactly the run-to-run drift "
					   "this file exists to remove.",
		},
		"tickers": dict(sorted(tickers.items())),
	}
	with open(path, "w", encoding="utf-8") as fh:
		json.dump(payload, fh, indent=2, ensure_ascii=False)
		fh.write("\n")


def _resolve_ticker(ticker: str, cache: dict, allow_network: bool) -> dict:
	"""Is this a real, analyzable security? A FACT check, so it lives in the deterministic sampler.

	The predicate is `marketCap or sector` non-null, plus an explicit ETF branch. That branch is not
	a nicety: `marketCap` and `sector` are null for an ETF BY CONSTRUCTION, so the naive predicate
	false-rejects every ETF — including the curated EWY macro-fade case, whose whole point is
	testing that the harness routes an ETF question to `macro` instead of `analyze`. Doctrine treats
	an ETF as a legitimate thematic vehicle, so rejecting one here would be the sampler overruling
	the doctrine it is measuring."""
	if ticker in cache:
		return cache[ticker]
	if not allow_network:
		return {"ok": False, "reason": "not in cache and --no-network"}
	try:
		import yfinance  # imported lazily: `rubric` and `report` are stdlib-only and offline
		info = yfinance.Ticker(ticker).info or {}
	except Exception as exc:  # noqa: BLE001 — any resolution failure is just "unresolvable"
		res = {"ok": False, "reason": f"{type(exc).__name__}"}
		cache[ticker] = res
		return res
	quote_type = info.get("quoteType")
	name = info.get("shortName") or info.get("longName")
	ok = bool(info.get("marketCap") or info.get("sector")) or bool(quote_type == "ETF" and name)
	res = {
		"ok": ok,
		"market_cap": info.get("marketCap"),
		"sector": info.get("sector"),
		"quote_type": quote_type,
		"name": name,
	}
	if not ok:
		res["reason"] = f"no marketCap/sector (quoteType={quote_type})"
	cache[ticker] = res
	return res


def _blind_prompt(ticker: str, date: str, entry_type: str) -> str:
	"""Reconstruct the SITUATION as a user question, with the thesis hidden. The harness must
	produce its own read; the answer-key thesis is never shown to it.

	All three branches are DATE-ANCHORED. The discovery branch used to say "right now" with no date
	at all, so a September-2025 thesis was asked as a present-tense question ~11 months later while
	the pipeline loaded today's data. If the name has since re-rated, the objectively correct answer
	is "already re-rated, look elsewhere" — and the six binary items would score that as a miss on
	every row. The eval measures method reproduction, not his hit rate, so the question has to be
	asked in the world the thesis was written in."""
	day = (date or "")[:10]
	if entry_type == "fear_dip":
		return (f"{ticker} sold off hard around {day}. Is this a real fundamental break or a fear-dip "
				f"I should be buying? Give me your full read.")
	if entry_type == "event":
		return (f"There's a catalyst on {ticker} around {day} (earnings / news / a filing). What's your "
				f"take — does it change the forward-revenue picture, and is the move an opportunity?")
	if entry_type == "ranking":
		return (f"As of {day}, where is {ticker} in its cycle, and how would you rank and size it "
				f"against the other names in the same chain?")
	return (f"As of {day}, what's your read on {ticker}? Is it structurally mispriced, and if so, how "
			f"would you play it?")


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
	by_id = {str(r.get("id")): r for r in rows}

	# --- the archetype floor: force-include the curated set BEFORE the random draw ---
	# These enter first and bypass BOTH the resolution gate and the distinct-ticker rule. The
	# resolution exemption is reasoned about in gold_set.json (`resolution_exemption`); the ticker
	# exemption is simply that two of the twelve are NBIS — one the asset-financed levered-IRR read,
	# one the strategic-floor read — and they are different theses testing different moves.
	chosen: list[dict] = []
	gold_ids: set[str] = set()
	gold_missing: list[str] = []
	if not args.no_gold:
		for g in _load_gold_set(args.gold):
			gid = str(g["id"])
			r = by_id.get(gid)
			if r is None:
				gold_missing.append(gid)
				continue
			content = (r.get("content") or "").strip()
			ticker = g.get("subject") or _primary_ticker(r.get("tickers") or "")
			gold_ids.add(gid)
			chosen.append({
				"id": gid,
				"ticker": ticker,
				"date": r.get("created_at"),
				"type": r.get("type"),
				# The curated set pins its own framing where the keyword heuristic mis-frames it.
				# Measured on these twelve: the heuristic asks the AXT InP chokepoint read, both
				# NBIS reads, the SNAP margin-inversion read and the cycle-stage meta post as
				# fear-dips, because each mentions a drop somewhere in a long thesis. The blind
				# prompt IS the instrument — asking a discovery thesis "is this a fear-dip?" measures
				# a different question, the same way a mis-selected subject ticker does.
				"entry_type": g.get("entry_type") or _entry_type(content),
				"archetype": g.get("archetype"),
				"archetype_source": "curated",
				"gold": True,
				"gold_label": g.get("label"),
				"gold_tests": g.get("tests"),
				"thesis_text": content,
			})
	if gold_missing:
		# Loud, never silent: the gold set is keyed on DB ids, so a DB swap that drops rows would
		# otherwise quietly shrink the archetype floor while the run still reports a full n.
		print(f"error: {len(gold_missing)} gold case(s) not present in {args.db}: "
			  f"{', '.join(gold_missing)}", file=sys.stderr)
		sys.exit(2)

	# Substantive single-name theses only: a tagged ticker, real length, a first-party post/subscriber
	# (not a reply), and a resolvable primary ticker.
	pool = []
	disclaimed = 0
	for r in rows:
		if r.get("type") not in ("post", "subscriber"):
			continue
		if str(r.get("id")) in gold_ids:
			continue  # already force-included; never draw it twice
		content = (r.get("content") or "").strip()
		if len(content) < args.min_len:
			continue
		ticker = _primary_ticker(r.get("tickers") or "")
		if not ticker:
			continue
		if _is_disclaimed(ticker, content):
			disclaimed += 1
			continue
		pool.append({
			"id": r.get("id"),
			"ticker": ticker,
			"date": r.get("created_at"),
			"type": r.get("type"),
			"entry_type": _entry_type(content),
			"archetype": None,
			"archetype_source": None,
			"gold": False,
			"thesis_text": content,
		})

	if not pool:
		print("error: no eligible theses in the DB after filtering", file=sys.stderr)
		sys.exit(2)

	rng = random.Random(args.seed)
	# Stratify by entry_type; within each bucket enforce distinct tickers, prefer subscriber
	# (deepest) and longer theses, then round-robin the buckets to N so no entry-type dominates.
	buckets: dict[str, list[dict]] = {"fear_dip": [], "event": [], "discovery": []}
	for case in pool:
		buckets[case["entry_type"]].append(case)

	used_tickers: set[str] = {c["ticker"] for c in chosen}
	# The seed controls the sample: shuffle each bucket, then STABLE-sort by depth so the deepest
	# theses (subscriber, or long) come first while their order WITHIN a depth tier stays the seeded
	# shuffle. Same seed → same cases (a true before/after); a different seed → a different subset of
	# comparably-deep theses (broader coverage across rounds), not the same eight every time.
	def _depth(c: dict) -> int:
		return 0 if (c["type"] == "subscriber" or len(c["thesis_text"]) >= 800) else 1

	for b in buckets.values():
		rng.shuffle(b)
		b.sort(key=_depth)

	cache = _load_resolution_cache(args.resolution_cache)
	cache_before = len(cache)
	rejected: list[dict] = []

	def _accept(c: dict) -> bool:
		"""Resolve at PICK time, not over the whole 951-row pool — one network call per candidate
		actually considered, which is the difference between ~30 calls and ~950."""
		res = _resolve_ticker(c["ticker"], cache, allow_network=not args.no_network)
		if res.get("ok"):
			return True
		rejected.append({"id": c["id"], "ticker": c["ticker"], "reason": res.get("reason")})
		return False

	order = ["fear_dip", "event", "discovery"]
	i = 0
	while len(chosen) < args.n and any(buckets[b] for b in order):
		b = order[i % len(order)]
		i += 1
		bucket = buckets[b]
		# pop the next case whose ticker isn't already used AND whose ticker resolves. An
		# unresolvable candidate is dropped and scanning continues, exactly like the ticker filter
		# above it — never a silent under-fill.
		picked = None
		while bucket and picked is None:
			hit = next((idx for idx, c in enumerate(bucket) if c["ticker"] not in used_tickers), None)
			if hit is None:
				hit = 0  # exhausted distinct tickers; allow a repeat rather than under-fill
			cand = bucket.pop(hit)
			if _accept(cand):
				picked = cand
		if picked is not None:
			used_tickers.add(picked["ticker"])
			chosen.append(picked)

	for c in chosen:
		c["blind_prompt"] = _blind_prompt(c["ticker"], c["date"], c["entry_type"])

	if len(cache) != cache_before:
		_save_resolution_cache(args.resolution_cache, cache)

	dist = {b: sum(1 for c in chosen if c["entry_type"] == b) for b in order}
	arch = {}
	for c in chosen:
		arch[c["archetype"] or "unlabeled"] = arch.get(c["archetype"] or "unlabeled", 0) + 1
	out = {
		"meta": {
			"n": len(chosen),
			"requested": args.n,
			"seed": args.seed,
			"min_len": args.min_len,
			"eligible_pool": len(pool),
			"gold_forced": sum(1 for c in chosen if c.get("gold")),
			"entry_type_distribution": dist,
			"archetype_distribution": arch,
			"resolution": {
				"rejected": rejected,
				"disclaimed_skipped": disclaimed,
				"cache": os.path.relpath(args.resolution_cache, os.path.join(_HERE, os.pardir)),
				"network": not args.no_network,
			},
			"stratification": "entry-type keyword heuristic + distinct primary tickers for the random "
							   "remainder; the ARCHETYPE floor comes from the force-included gold set "
							   "(gold_forced above), because the general pool carries no archetype label "
							   "and the harness naming it is what's under test. A skew in "
							   "entry_type_distribution means the DB itself is skewed, not a silent cap.",
			"unlabeled_archetype": "Cases with archetype=null are NOT archetype-scoped by `report`: the "
								   "two chokepoint-only rubric items are left unscored for them rather "
								   "than re-decided per judging pass. Fill the field in by hand during "
								   "the one-time inspection that freezes a standing sample — that is "
								   "what makes the scope stable across runs.",
			"note": "Each case's thesis_text is the ANSWER KEY — pass it, and gold_tests, only to the "
					"judge, NEVER to the harness-under-test. The harness sees blind_prompt alone.",
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
			"scope_is_not_yours_to_decide": "Do NOT re-derive whether a case is chokepoint-scoped. "
					 "`report` applies that split mechanically from the case's persisted `archetype` "
					 "field. Score recursive_bottom_hop / second_order_and_sibling on their merits and "
					 "let the aggregator decide whether they count.",
			"mechanically_pre_scored": "lens_run and bear_and_falsifier are ALSO scored by running the "
					 "live `verdict_gate.py --explain` hook over the answer, and the hook's verdict "
					 "overrides yours where the two disagree. Not a slight on the judge: the hook is "
					 "what actually fires in production, and an item scored 1 by a judge on an answer "
					 "the real hook would have blocked is a measurement of the judge, not the harness. "
					 "Score them anyway — the disagreement rate is itself reported.",
			"time_passed_is_not_a_miss": "These theses are months old and the pipeline loads CURRENT "
					 "data. If the setup has since resolved and the harness therefore reaches a "
					 "DIFFERENT verdict from the thesis — 'already re-rated, look elsewhere' — that is "
					 "a PASS on any item whose method was run properly. This eval measures method "
					 "reproduction, not his hit rate. Score direction-agreement nowhere.",
		},
		"feedback_rule": (
			"For every RECURRING miss (a signature move dropped in >=2 cases), the fix is to GENERALIZE an "
			"EXISTING principle — name the R#/V#/NN#/skill-section that should already cover it, and widen its "
			"trigger or its why. Do NOT add a case-specific rule: that is the per-miss-patching病因 §0 names, and "
			"it grows the spine without covering the 17th case. A one-off miss is a monitoring item, not a delta."
		),
	}, indent=2, ensure_ascii=False))


def _hook_explain(response: str) -> dict | None:
	"""Score the structural items by running the LIVE hook, not a copy of its regexes.

	This is the whole of the "deterministic pre-pass": `verdict_gate.py --explain` reads the same
	payload the Stop hook gets and returns its per-check verdict as JSON. Sharing the hook rather
	than extracting its patterns into a module means the two cannot drift — an eval that scores
	`lens_run = 1` on an answer the production hook would have blocked is measuring its own copy of
	the rule, which is the failure this replaces. It also means the hook's own fixture suite
	regression-covers the eval's oracle for free.

	Returns None when the hook is absent or unusable; the caller degrades to judge-only and SAYS so
	in the report rather than silently reporting judge scores as if they were mechanical."""
	if not os.path.isfile(_VERDICT_GATE):
		return None
	try:
		proc = subprocess.run(
			[sys.executable, _VERDICT_GATE, "--explain"],
			input=json.dumps({"last_assistant_message": response, "stop_hook_active": False}),
			capture_output=True, text=True, timeout=30,
		)
	except (OSError, subprocess.SubprocessError):
		return None
	if proc.returncode != 0:
		return None
	try:
		payload = json.loads(proc.stdout)
	except ValueError:
		return None
	# A hook that predates `--explain` ignores argv, reads the same stdin, and prints ordinary hook
	# output — which is valid JSON and passes a naive parse. The report then says "0 cases scored by
	# the live hook" in the same breath as "mechanical pre-pass: healthy". Demand the contract's own
	# key, so an old hook reads as UNAVAILABLE rather than as available-and-quiet.
	if not isinstance(payload, dict) or not isinstance(payload.get("checks"), dict):
		return None
	return payload


def _mechanical_scores(explain: dict) -> dict:
	"""Map the hook's checks onto the two rubric items it actually owns.

	`null` from the hook means the check did not apply, which is the rubric's `n/a` — never a 0.
	Collapsing those would manufacture misses on exactly the answers the hook deliberately stays
	quiet about."""
	checks = explain.get("checks") or {}
	out: dict = {}
	lens = checks.get("lens_line")
	if lens is not None:
		out["lens_run"] = int(bool(lens))
	down, fals = checks.get("downsides"), checks.get("falsifier")
	if down is not None or fals is not None:
		out["bear_and_falsifier"] = int(bool(down) and bool(fals))
	return out


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
	unstable_scope = 0          # cases whose chokepoint scope came from the judge, not a fixed label
	unlabeled = 0
	unscored = 0                # cases carrying no judge result at all (a failed/killed judge)
	disagreements: list[str] = []
	hook_scored = 0
	hook_available = None

	for c in cases:
		sc = dict(c.get("scores") or {})
		arch = c.get("archetype")
		if arch is None:
			unlabeled += 1
		# A case whose judge failed arrives as `scores: null` and contributes to nothing. Silently
		# it would just shrink every denominator while the header still says "cases: 12" — the
		# pooled rate would be computed over an unstated subset. Observed live: a session limit
		# killed five judges mid-pilot and every one of them came back exactly this way.
		if not sc:
			unscored += 1

		# --- mechanical pre-pass: the live hook overrides the judge on the items it owns ---
		if not args.no_hook and c.get("response"):
			explain = _hook_explain(str(c["response"]))
			if explain is not None:
				hook_available = True
				mech = _mechanical_scores(explain)
				for k, v in mech.items():
					if sc.get(k) in (0, 1) and sc.get(k) != v:
						disagreements.append(f"{c.get('ticker')}/{k}: judge={sc.get(k)} hook={v}")
					sc[k] = v
				if mech:
					hook_scored += 1
			elif hook_available is None:
				hook_available = False

		for k in scored_keys:
			v = sc.get(k)
			if k in _CHOKEPOINT_SCOPED:
				if arch is not None:
					# Mechanical split from the persisted label. Stable across passes by
					# construction: the same case cannot be in scope one run and out the next.
					if arch != "chokepoint":
						continue
				elif v in (0, 1):
					unstable_scope += 1
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
		lines += [f"- cases: {len(cases)} | seed: {meta.get('seed')} | model: "
				  f"`{meta.get('model') or 'UNRECORDED'}` | entry-type dist: "
				  f"{meta.get('entry_type_distribution')}"]
		if not meta.get("model"):
			# 4.7: an unrecorded model makes a before/after separated by weeks unrecoverable — the
			# difference could be a default-model change rather than the doctrine edit under test.
			lines.append("- ⚠ **model not recorded** — this run cannot be compared against another "
						 "run whose model may have differed.")
		lines.append("")
	# overall
	overall_met = sum(m for m, _ in rates.values())
	overall_tot = sum(t for _, t in rates.values())
	overall = (overall_met / overall_tot) if overall_tot else 0.0
	lines += [f"**Pooled reproduction rate: {overall:.0%}** ({overall_met}/{overall_tot} in-scope checks "
			  f"met)", "",
			  "Pooled across distinct moves, so it conflates them — usable as a coarse dashboard number "
			  "and for spotting gross regressions, not as a claim about any single move.", ""]

	lines += ["## Per-move reproduction", "", "| signature move | rate | met / in-scope |", "|---|---|---|"]
	for k in scored_keys:
		met, tot = rates[k]
		if tot == 0:
			r = "—"
		elif tot < args.n_floor:
			# 4.8: a 100%-on-one-case row read as a result is how a broken instrument produces
			# confident wrong conclusions. Detecting a 20-point true shift at 80% power needs ~90
			# in-scope cases; 30 points needs ~29. Below the floor there is no per-move claim to make.
			r = f"insufficient n (<{args.n_floor})"
		else:
			r = f"{(met/tot):.0%}"
		lines.append(f"| {k} | {r} | {met} / {tot} |")
	lines.append("")

	lines += ["## Instrument health", ""]
	if args.no_hook:
		lines.append("- mechanical pre-pass: **skipped** (`--no-hook`); lens_run and bear_and_falsifier "
					 "are judge scores only.")
	elif hook_available is False:
		lines.append(f"- mechanical pre-pass: **unavailable** — `{os.path.relpath(_VERDICT_GATE)}` did "
					 "not answer `--explain`. lens_run and bear_and_falsifier are judge scores only, "
					 "which is a weaker measurement than this report normally makes.")
	else:
		lines.append(f"- mechanical pre-pass: {hook_scored}/{len(cases)} cases scored by the live hook "
					 f"(`verdict_gate.py --explain`), which overrides the judge on lens_run and "
					 f"bear_and_falsifier.")
		lines.append(f"- judge/hook disagreements: **{len(disagreements)}**"
					 + (" — " + "; ".join(disagreements[:8]) if disagreements else ""))
	if unscored:
		lines.append(f"- ⚠ **{unscored}/{len(cases)} case(s) carry no judge result** and contributed to "
					 f"nothing above. Every rate on this page is computed over the remaining "
					 f"{len(cases) - unscored}. Re-run those cases before comparing this report "
					 f"against another.")
	lines.append(f"- archetype labels: {len(cases) - unlabeled}/{len(cases)} cases carry a fixed "
				 f"`archetype`, so their chokepoint scope is stable across passes.")
	if unlabeled:
		lines.append(f"- ⚠ {unlabeled} unlabeled case(s) contributed {unstable_scope} chokepoint-scoped "
					 f"score(s) decided by the judge at scoring time. Those can flip n/a↔0 between two "
					 f"passes of the identical answer. Fill `archetype` in during the one-time "
					 f"inspection that freezes a standing sample.")
	lines.append("")

	lines += ["## Per-case", "",
			  "| ticker | archetype | entry | " + " | ".join(scored_keys) + " | note |",
			  "|---|---|---|" + "|".join("---" for _ in scored_keys) + "|---|"]
	for c in cases:
		sc = c.get("scores") or {}
		arch = c.get("archetype")
		cells = []
		for k in scored_keys:
			v = sc.get(k)
			if k in _CHOKEPOINT_SCOPED and arch is not None and arch != "chokepoint":
				cells.append("–")       # mechanically out of scope, whatever the judge said
			else:
				cells.append("✓" if v == 1 else ("✗" if v == 0 else "–"))
		# `notes` used to be collected by the judge and then read by nothing — the one field that
		# can say "this case is broken" or "different but defensible" was write-only.
		note = str(sc.get("notes") or c.get("notes") or "").replace("|", "/")[:80]
		lines.append(f"| {c.get('ticker')} | {arch or '?'} | {c.get('entry_type')} | "
					 + " | ".join(cells) + f" | {note} |")
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

	# Printed on every report, not left to the reader's statistical literacy. The one recorded
	# measurement before this (n=6, 72%→70%) was described by its own authors as a single stochastic
	# judge flip, and it still got quoted afterwards as though it meant something.
	lines += ["", "## What this run can and cannot claim", "",
			  # 4.4 requires the age policy to be STATED rather than left implicit, because the two
			  # available options measure different things and a reader cannot tell which was used.
			  "**How thesis age is handled:** these cases are months old and the pipeline loads "
			  "current data, so a blind run can see how the setup resolved. The sampler is not biased "
			  "toward recent theses — the curated gold cases are fixed and old by construction, so "
			  "that option does not exist for the archetype floor. Instead the blind prompt states "
			  "the data-timing gap neutrally so every case is answered under the same conditions, and "
			  "the rubric scores decomposition METHOD rather than directional agreement: a harness "
			  "that reaches a different verdict because the setup has since resolved passes any item "
			  "whose method ran properly.", "",
			  "**Can:** gross regressions and breaks (visible well below the power threshold); the "
			  "pooled cross-move number above as a coarse dashboard reading; a running trend across "
			  "successive doctrine edits, which is where this instrument earns its keep.", "",
			  f"**Cannot:** a per-move before/after claim at this n. Any row above showing "
			  f"`insufficient n` is suppressed for that reason, and rows above the floor are still "
			  f"only reliable against swings of roughly 30-40 points. Treat a single-run per-move "
			  f"delta as a monitoring item, never as evidence a doctrine edit worked."]

	print("\n".join(lines))


def main() -> int:
	p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	p.add_argument("--db", default=_DEFAULT_DB, help="Path to analysis_Serenity.db")
	sub = p.add_subparsers(dest="cmd", required=True)

	s = sub.add_parser("sample", help="Stratified, seeded sample of past theses → cases JSON")
	s.add_argument("--n", type=int, default=8, help="Number of cases (default 8)")
	s.add_argument("--seed", type=int, default=7, help="RNG seed (deterministic; default 7)")
	s.add_argument("--min-len", type=int, default=400, help="Min thesis length in chars (default 400)")
	s.add_argument("--gold", default=_DEFAULT_GOLD,
				   help="Curated archetype-labeled cases force-included before the random draw")
	s.add_argument("--no-gold", action="store_true",
				   help="Draw at random only. Leaves the sample archetype-blind — the two chokepoint-"
						"scoped rubric items may end up with an in-scope N of zero.")
	s.add_argument("--resolution-cache", default=_DEFAULT_RESOLUTION_CACHE,
				   help="Committed cache of ticker-resolution answers (keeps `sample` deterministic)")
	s.add_argument("--no-network", action="store_true",
				   help="Resolve from the cache only; a cache miss drops the candidate and is "
						"reported under meta.resolution.rejected, never silently accepted")
	s.set_defaults(func=cmd_sample)

	r = sub.add_parser("rubric", help="Print the signature-move scoring rubric + feedback rule")
	r.set_defaults(func=cmd_rubric)

	rp = sub.add_parser("report", help="Aggregate a scored-cases JSON → markdown report + doctrine deltas")
	rp.add_argument("--results", required=True, help="Path to the scored-cases JSON")
	rp.add_argument("--n-floor", type=int, default=_DEFAULT_N_FLOOR,
					help=f"Suppress a per-move percentage below this many in-scope cases "
						 f"(default {_DEFAULT_N_FLOOR})")
	rp.add_argument("--no-hook", action="store_true",
					help="Skip the mechanical pre-pass and use judge scores for lens_run / "
						 "bear_and_falsifier. Weaker: a judge can score 1 on an answer the live "
						 "hook would block.")
	rp.set_defaults(func=cmd_report)

	args = p.parse_args()
	args.func(args)
	return 0


if __name__ == "__main__":
	sys.exit(main())
