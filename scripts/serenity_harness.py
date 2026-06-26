#!/usr/bin/env python3
"""Serenity harness self-check — does the wiring still hold the line?

`validate` answers one question: is the harness still structurally sound — the spine
present, the skills loadable, and above all the code/judgment boundary intact (the
evidence layer emits NO verdict, score, regime label, or archetype tag)? It is the
guardrail that catches a judgment leak creeping back into the deterministic layer.

	scripts/serenity_harness.py validate            # JSON report; exit 1 on any hard fail
	scripts/serenity_harness.py validate --verbose  # include per-fixture detail

It replays every frozen golden payload through `build_evidence` and asserts the evidence
INVARIANTS (contract present, no forbidden keys/values, the load-bearing fields exist) —
the regression that matters now that the code grades nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPTS)
sys.path.insert(0, _SCRIPTS)
sys.path.insert(0, os.path.join(_SCRIPTS, "modules"))

SKILLS = ("serenity-discovery", "serenity-analysis", "serenity-macro")


def _walk_keys(value):
	if isinstance(value, dict):
		for k, v in value.items():
			yield str(k)
			yield from _walk_keys(v)
	elif isinstance(value, list):
		for c in value:
			yield from _walk_keys(c)


def _walk_strings(value):
	if isinstance(value, str):
		yield value
	elif isinstance(value, dict):
		for v in value.values():
			yield from _walk_strings(v)
	elif isinstance(value, list):
		for c in value:
			yield from _walk_strings(c)


def _frontmatter_fields(path):
	"""Pull `name`/`description` from a SKILL.md YAML frontmatter without a YAML dep."""
	try:
		text = open(path, encoding="utf-8").read()
	except OSError:
		return {}
	m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
	block = m.group(1) if m else ""
	fields = {}
	for key in ("name", "description"):
		fm = re.search(rf"^{key}:\s*(.+)$", block, re.MULTILINE)
		if fm:
			fields[key] = fm.group(1).strip().strip("\"'")
	return fields


def _check_evidence_invariants(checks):
	"""Replay every golden *.inputs.json through build_evidence and assert the contract."""
	from pipeline._evidence import (
		build_evidence,
		FORBIDDEN_EVIDENCE_KEYS,
		FORBIDDEN_VALUE_PATTERN,
		FORBIDDEN_EVIDENCE_VALUES,
		_key_is_forbidden,
	)

	golden_dir = os.path.join(_SCRIPTS, "tests", "golden")
	fixtures = sorted(f for f in os.listdir(golden_dir) if f.endswith(".inputs.json")) \
		if os.path.isdir(golden_dir) else []
	if not fixtures:
		checks.append(("evidence_invariants", "warn", "no golden fixtures found"))
		return

	per_fixture = {}
	all_ok = True
	for fn in fixtures:
		ticker = fn.split(".", 1)[0].upper()
		problems = []
		try:
			payload = json.load(open(os.path.join(golden_dir, fn), encoding="utf-8"))
			ev = build_evidence(payload, ticker)
		except Exception as e:  # noqa: BLE001
			per_fixture[ticker] = [f"build_evidence raised: {type(e).__name__}: {e}"]
			all_ok = False
			continue

		# Contract
		if ev.get("evidence_contract", {}).get("judgment_owner") != "agent":
			problems.append("evidence_contract.judgment_owner != agent")

		# No forbidden keys — literal, normalized, AND the namespaced-judgment substrings
		# (catches vix_regime / x_risk_level), via the same matcher the sanitizer uses.
		keys = set(_walk_keys(ev))
		if keys & FORBIDDEN_EVIDENCE_KEYS:
			problems.append(f"forbidden keys: {sorted(keys & FORBIDDEN_EVIDENCE_KEYS)}")
		norm_hits = [k for k in keys if _key_is_forbidden(k)]
		if norm_hits:
			problems.append(f"forbidden/namespaced-judgment keys: {norm_hits}")

		# No verdict-shaped value strings. Scan everything EXCEPT the filing-narrative
		# subtree: filing_evidence is objective reproduced filing text that legitimately
		# contains "buy"/"sell" as ordinary verbs ("agreed to issue and sell"). The scan
		# targets a CODE-emitted verdict label, never the filing's own words — and the
		# forbidden-KEY scan above still covers the whole tree, so no field can be NAMED
		# like a verdict even inside filing_evidence.
		ev_scannable = {k: v for k, v in ev.items() if k != "filing_evidence"}
		vals = {v.strip() for v in _walk_strings(ev_scannable)}
		if vals & FORBIDDEN_EVIDENCE_VALUES:
			problems.append(f"forbidden values: {sorted(vals & FORBIDDEN_EVIDENCE_VALUES)}")
		bad_vals = [v for v in vals if FORBIDDEN_VALUE_PATTERN.search(v)]
		if bad_vals:
			problems.append(f"verdict-shaped values: {bad_vals[:3]}")

		# Load-bearing fields exist — assert key_facts carries the anchors WHEN the fixture's
		# info actually has them. Some stale captures are degenerate (a delisted ticker that
		# returned no market cap or price); a thin fixture is not a code bug, an empty
		# key_facts despite a real market cap / price IS.
		info = (payload.get("l4") or {}).get("info") or {}
		has_anchor = isinstance(info, dict) and (info.get("marketCap") is not None or info.get("currentPrice") is not None)
		if has_anchor and not ev.get("key_facts"):
			problems.append("key_facts empty despite info carrying marketCap/currentPrice")
		if "ev_multiples" not in ev.get("valuation_inputs", {}):
			problems.append("valuation_inputs.ev_multiples missing")
		er = ev.get("catalyst_inputs", {}).get("estimate_revisions")
		# Tolerate the documented graceful-degradation shape: a rate-limited revisions call
		# returns {"error": ...}, the same contract the rest of the pipeline uses.
		if not isinstance(er, dict) or ("by_horizon" not in er and "error" not in er):
			problems.append("catalyst_inputs.estimate_revisions.by_horizon missing")

		# When the fixture carries SEC supply-chain facts, the dossier must surface them
		sc = (((payload.get("sec_sc") or {}).get("sec_supply_chain") or {}).get("data") or {}).get("classification") or {}
		has_sc = any(sc.get(k) for k in ("company_relationships", "country_exposure", "critical_inputs", "financing_facts"))
		if has_sc and not ev.get("filing_evidence", {}).get("dossier"):
			problems.append("SEC facts present in payload but filing_evidence.dossier missing")

		per_fixture[ticker] = problems
		all_ok = all_ok and not problems

	failed = {t: p for t, p in per_fixture.items() if p}
	checks.append((
		"evidence_invariants",
		"pass" if all_ok else "fail",
		f"{len(fixtures) - len(failed)}/{len(fixtures)} golden fixtures clean"
		+ ("" if all_ok else f"; failing: {failed}"),
	))


def _check_macro_sanitizer(checks):
	"""Synthetic l1 with judgment-shaped keys must come out as raw gauges only — the macro
	path none of the golden fixtures exercise (they all have l1=None)."""
	from pipeline._evidence import build_evidence, _key_is_forbidden
	payload = {
		"l1": {"vix_spot": 18.9, "real_rate": 1.2,
			   "vix_regime": "panic", "regime": "risk_off", "macro_risk_level": "high"},
		"l4": {}, "l5": {}, "sec_sc": {},
	}
	mi = build_evidence(payload, "SYNTH").get("macro_inputs") or {}
	leaked = [k for k in mi if _key_is_forbidden(k)]
	kept = "vix_spot" in mi and "real_rate" in mi
	ok = not leaked and kept
	checks.append(("macro_sanitizer", "pass" if ok else "fail",
		"raw gauges kept; regime/risk_level stripped" if ok else f"leaked={leaked} gauges_kept={kept}"))


def _check_sec_xbrl_path(checks):
	"""The production SEC path: deterministic XBRL (no prose). A synthetic xbrl block with a
	high-risk-region revenue share must surface the dossier's geographic_concentration AND the
	high_risk_region_revenue flag WITHOUT the editorial `signal` string. None of the golden
	fixtures exercise this (they carry the OLD sec-analyzer enum schema)."""
	from pipeline._evidence import build_evidence
	payload = {
		"l1": None, "l4": {}, "l5": {},
		"sec_sc": {
			"sec_supply_chain": {"data": {"filing": {"form": "10-K"}, "classification": {}, "xbrl": {
				"geographic_revenue": [
					{"region": "Taiwan", "revenue_pct": 50.0, "revenue_amount": "$5.0B", "source": "xbrl"},
					{"region": "United States", "revenue_pct": 50.0, "revenue_amount": "$5.0B", "source": "xbrl"},
				],
				"revenue_concentration": [{"entity": "Customer One", "revenue_pct": 30.0, "source": "xbrl"}],
			}}},
			"sec_events": {},
		},
	}
	fe = build_evidence(payload, "SYNTH").get("filing_evidence", {})
	dossier = fe.get("dossier") or {}
	geo_ok = bool(dossier.get("geographic_concentration")) and bool(dossier.get("customer_concentration"))
	flags = fe.get("absence_evidence_flags") or []
	hr_ok = any(isinstance(f, dict) and f.get("type") == "high_risk_region_revenue" for f in flags)
	no_editorial = all(isinstance(f, dict) and "signal" not in f for f in flags)
	ok = geo_ok and hr_ok and no_editorial
	checks.append(("sec_xbrl_path", "pass" if ok else "fail",
		"XBRL dossier + high-risk-region flag surfaced, no editorial signal" if ok
		else f"dossier_geo={geo_ok} hr_flag={hr_ok} no_editorial={no_editorial}"))


def cmd_validate(args):
	checks = []  # (name, status, detail)

	# 1. Spine present
	claude_md = os.path.join(_ROOT, "CLAUDE.md")
	checks.append(("claude_md", "pass" if os.path.isfile(claude_md) else "fail",
		claude_md if os.path.isfile(claude_md) else "CLAUDE.md missing"))

	# 2. Skills present with valid frontmatter
	for skill in SKILLS:
		path = os.path.join(_ROOT, ".claude", "skills", skill, "SKILL.md")
		if not os.path.isfile(path):
			checks.append((f"skill:{skill}", "fail", "SKILL.md missing"))
			continue
		fields = _frontmatter_fields(path)
		if fields.get("name") and fields.get("description"):
			checks.append((f"skill:{skill}", "pass", f"name+description present ({len(fields['description'])} char desc)"))
		else:
			checks.append((f"skill:{skill}", "fail", f"frontmatter incomplete: {fields}"))

	# 3. Pipeline entry importable + clean commands wired
	try:
		import serenity_pipeline  # noqa: F401
		from pipeline._evidence_commands import cmd_analyze, cmd_macro, cmd_discover  # noqa: F401
		checks.append(("pipeline_entry", "pass", "serenity_pipeline + clean commands import"))
	except Exception as e:  # noqa: BLE001
		checks.append(("pipeline_entry", "fail", f"{type(e).__name__}: {e}"))

	# 4. Evidence invariants over the golden corpus (the real regression)
	_check_evidence_invariants(checks)

	# 4b. Exercise the two layers the golden corpus can't (all fixtures have l1=None and
	# carry the OLD SEC enum schema): the macro sanitizer and the SEC prose/flag path.
	_check_macro_sanitizer(checks)
	_check_sec_xbrl_path(checks)

	# 5. Boundary: the active path must not pull in any legacy (judgment) module
	leaked = sorted(m for m in sys.modules if "pipeline.legacy" in m)
	checks.append(("judgment_boundary", "pass" if not leaked else "fail",
		"active path loads no legacy module" if not leaked else f"LEGACY LEAK: {leaked}"))

	# 6. SEC layer artifacts — soft (built in the SEC bundle; warn, don't fail)
	for rel, label in (
		(os.path.join("scripts", "serenity_filings.py"), "serenity_filings.py"),
		(os.path.join(".claude", "agents", "serenity-filings.md"), "serenity-filings agent"),
	):
		p = os.path.join(_ROOT, rel)
		checks.append((f"sec_layer:{label}", "pass" if os.path.isfile(p) else "warn",
			"present" if os.path.isfile(p) else "not built yet"))

	hard_fail = [c for c in checks if c[1] == "fail"]
	report = {
		"harness": "serenity",
		"ok": not hard_fail,
		"summary": {
			"pass": sum(1 for c in checks if c[1] == "pass"),
			"warn": sum(1 for c in checks if c[1] == "warn"),
			"fail": len(hard_fail),
		},
		"checks": [
			{"check": n, "status": s, **({"detail": d} if (args.verbose or s != "pass") else {})}
			for n, s, d in checks
		],
	}
	json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
	print()
	sys.exit(0 if not hard_fail else 1)


def main():
	parser = argparse.ArgumentParser(prog="serenity_harness.py", description="Serenity harness self-check")
	sub = parser.add_subparsers(dest="command", required=True)
	sp = sub.add_parser("validate", help="Structural + evidence-boundary self-check")
	sp.add_argument("--verbose", action="store_true", default=False, help="Include detail for passing checks too")
	sp.set_defaults(func=cmd_validate)
	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
