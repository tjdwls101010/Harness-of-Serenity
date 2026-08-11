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
import subprocess
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


def _check_xbrl_module_boundary(checks):
	"""The filing's disclosure numbers (customer %, geographic %, inventory, purchase obligations)
	consolidated into the `serenity-filings` subagent, and the brittle `_sec_xbrl` parser retired to
	`pipeline/legacy/`. This check guards exactly one thing: that no `_sec_xbrl` module outside
	`legacy` has been imported into the active path.

	It is named for what it guards, which it was not before. It used to also assert that
	`_extract_sec_supply_chain("AAPL")` returned an empty `xbrl` and an empty `classification` — but
	that function is an unconditional `return {...empty...}` that ignores its ticker argument, so both
	conjuncts were True by construction for every possible input while the failure message printed all
	three as if independently informative.

	The general lesson, worth more than this check: an assertion whose subject is a hardcoded literal
	tests the source code, not the behavior. It cannot fail, so it cannot inform — and a suite of
	fifteen checks where one is decorative is worse than fourteen real ones, because the count is what
	gets quoted as evidence of coverage."""
	leaked = sorted(m for m in sys.modules if "_sec_xbrl" in m and "legacy" not in m)
	checks.append(("xbrl_module_boundary", "pass" if not leaked else "fail",
		"no active-path _sec_xbrl import; filing numbers come from the serenity-filings subagent"
		if not leaked else f"active_xbrl_leak={leaked}"))


def _check_hook_fixtures(checks):
	"""Run the committed hook fixtures and adopt their exit code.

	This is the check whose absence made every other check untrustworthy. The `hooks` check asserts
	that four scripts exist on disk and are named in settings.json — existence, not behavior. A hook
	can be present, correctly wired, and completely broken, and nothing noticed: the suite sat at
	19/22 while `validate` reported green and `session_status.py`, which is gated on `report.ok`,
	stayed silent through it.

	Gates on the EXIT CODE, never on parsing "N/M fixtures passed" out of stdout. A hardcoded
	expected count would rot the moment anyone adds a fixture, and asserting a literal instead of a
	behavior is the same defect this pass removed from the XBRL boundary check.

	Runs in a subprocess rather than importing the runner, because the runner spawns hooks with a
	deliberately overridden CLAUDE_PROJECT_DIR and its own cwd; importing it would entangle this
	process's environment with the suite's."""
	runner = os.path.join(_ROOT, ".claude", "hooks", "tests", "run_fixtures.py")
	if not os.path.isfile(runner):
		checks.append(("hook_fixtures", "fail", "no .claude/hooks/tests/run_fixtures.py — the hook layer has no behavioral guard"))
		return
	try:
		p = subprocess.run([sys.executable, runner], capture_output=True, text=True, timeout=120, cwd=_ROOT)
	except subprocess.TimeoutExpired:
		checks.append(("hook_fixtures", "fail", "fixture suite did not finish within 120s"))
		return
	except Exception as e:  # noqa: BLE001
		checks.append(("hook_fixtures", "fail", f"could not run the fixture suite: {type(e).__name__}: {e}"))
		return
	tail = [ln for ln in p.stdout.splitlines() if ln.strip()]
	if p.returncode == 0:
		checks.append(("hook_fixtures", "pass", tail[-1] if tail else "fixture suite exited 0"))
	else:
		failures = "; ".join(ln for ln in tail if ln.startswith("FAIL")) or (p.stderr.strip()[:300] or "no detail")
		checks.append(("hook_fixtures", "fail", f"{tail[-1] if tail else 'suite failed'} — {failures}"))


def _check_reproducibility(checks):
	"""The decision-reproducibility layer's wiring (plan 2026-07-18): the scorecard agent that
	pins the per-name schema, the session-archive doctrine in the spine, and the retrieval index.
	Structure only — never sessions/ CONTENT, which is runtime data, not harness wiring."""
	# (a) serenity-scorecard agent: present, frontmatter name/tools, body carries the schema sentinels.
	agent = os.path.join(_ROOT, ".claude", "agents", "serenity-scorecard.md")
	if not os.path.isfile(agent):
		checks.append(("agent:serenity-scorecard", "fail", "missing"))
	else:
		text = open(agent, encoding="utf-8").read()
		m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
		block = m.group(1) if m else ""
		name_ok = bool(re.search(r"^name:\s*serenity-scorecard\s*$", block, re.MULTILINE))
		tools_m = re.search(r"^tools:\s*(.+)$", block, re.MULTILINE)
		tools = tools_m.group(1) if tools_m else ""
		tools_ok = all(t in tools for t in ("Bash", "Read", "Grep", "Write"))
		sentinels = "gate_strength:" in text and "conviction:" in text
		ok = name_ok and tools_ok and sentinels
		checks.append(("agent:serenity-scorecard", "pass" if ok else "fail",
			"name+tools+schema sentinels present" if ok
			else f"name_ok={name_ok} tools_ok={tools_ok} schema_sentinels={sentinels}"))

	# (b) CLAUDE.md carries the session-archive doctrine (the heading + the Saved: mark token).
	try:
		cm = open(os.path.join(_ROOT, "CLAUDE.md"), encoding="utf-8").read()
	except OSError:
		cm = ""
	archive_ok = "The session archive" in cm and "Saved:" in cm
	checks.append(("session_archive_doctrine", "pass" if archive_ok else "fail",
		"CLAUDE.md carries the archive heading + Saved: token" if archive_ok
		else "CLAUDE.md missing the 'The session archive' heading or the Saved: token"))

	# (c) sessions/INDEX.md present with the verdict-free retrieval rule.
	index = os.path.join(_ROOT, "sessions", "INDEX.md")
	if not os.path.isfile(index):
		checks.append(("sessions_index", "fail", "sessions/INDEX.md missing"))
	else:
		idx = open(index, encoding="utf-8").read()
		verdict_free = "verdict-free" in idx or "NO verdicts" in idx
		checks.append(("sessions_index", "pass" if verdict_free else "fail",
			"present with the verdict-free rule" if verdict_free
			else "present but missing the verdict-free rule"))


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

	# 4b. Exercise the two layers the golden corpus can't (all fixtures have l1=None): the macro
	# sanitizer, and the XBRL module boundary (active path imports no in-pipeline XBRL parser).
	_check_macro_sanitizer(checks)
	_check_xbrl_module_boundary(checks)

	# 5. Boundary: the active path must not pull in any legacy (judgment) module
	leaked = sorted(m for m in sys.modules if "pipeline.legacy" in m)
	checks.append(("judgment_boundary", "pass" if not leaked else "fail",
		"active path loads no legacy module" if not leaked else f"LEGACY LEAK: {leaked}"))

	# 6. SEC layer artifacts — soft (warn, don't fail). The filing's disclosure numbers
	# consolidated into the subagent, so the in-pipeline `_sec_xbrl` parser is intentionally
	# retired to legacy and is NOT expected here; the live SEC surface is the CLI + the agent.
	for rel, label in (
		(os.path.join("scripts", "serenity_filings.py"), "serenity_filings.py"),
		(os.path.join(".claude", "agents", "serenity-filings.md"), "serenity-filings agent"),
	):
		p = os.path.join(_ROOT, rel)
		checks.append((f"sec_layer:{label}", "pass" if os.path.isfile(p) else "warn",
			"present" if os.path.isfile(p) else "not built yet"))

	# 7. Hooks: settings.json valid + every wired event maps to a present hook script. The
	#    harness steers Claude with deterministic rails at each lifecycle point — a wired event
	#    whose script is missing is a silent dead rail, so the check is event -> script presence.
	settings = os.path.join(_ROOT, ".claude", "settings.json")
	# Lean wiring: four hooks at the four points where determinism earns its cost — session
	# start (fail-loud self-check), prompt arrival (JIT action nudge), post-analyze (identity
	# tripwire), and the answer's end (the verdict-gate contract). web_number_guard (PreToolUse)
	# and subagent_discipline (SubagentStart) were retired: each only re-stated context already
	# in CLAUDE.md / the serenity-filings agent's own system prompt at the same lifecycle point.
	expected = {
		"SessionStart": "session_status.py",
		"UserPromptSubmit": "evidence_discipline.py",
		"PostToolUse": "data_integrity_guard.py",
		"Stop": "verdict_gate.py",
	}
	if not os.path.isfile(settings):
		checks.append(("hooks", "warn", "no .claude/settings.json"))
	else:
		try:
			cfg = json.load(open(settings, encoding="utf-8"))
			events = (cfg.get("hooks") or {})
			missing_event = [e for e in expected if e not in events]
			missing_script = [
				s for s in expected.values()
				if not os.path.isfile(os.path.join(_ROOT, ".claude", "hooks", s))
			]
			ok = not missing_event and not missing_script
			detail = f"{len(expected) - len(missing_event)}/{len(expected)} events wired, all scripts present" if ok \
				else f"missing_event={missing_event} missing_script={missing_script}"
			checks.append(("hooks", "pass" if ok else "fail", detail))
		except Exception as e:  # noqa: BLE001
			checks.append(("hooks", "fail", f"settings.json invalid: {e}"))

	# 8. Decision-reproducibility layer wiring (scorecard agent, archive doctrine, retrieval index)
	_check_reproducibility(checks)

	# 9. The hooks actually BEHAVE — not merely exist. Check 7 above asserts the event-to-script
	# wiring; this runs every committed fixture and takes the suite's exit code.
	_check_hook_fixtures(checks)

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


def _parse_ranking(path):
	"""Parse a `_ranking.md`'s fixed tier table (`| ticker | tier | rung | gates | why |`) and its
	`Tier cut:` line. Pure fact-loading — diffing two files the analyst already wrote — so it lives
	on the code side of the fact/judge seam and renders NO judgment about which ranking is right."""
	tiers, order, tier_cut = {}, [], None
	for raw in open(path, encoding="utf-8"):
		s = raw.strip()
		if s.lower().startswith("tier cut:"):
			tier_cut = s.split(":", 1)[1].strip()
			continue
		if not s.startswith("|"):
			continue
		cells = [c.strip() for c in s.strip("|").split("|")]
		if len(cells) < 2:
			continue
		tkr, tier = cells[0], cells[1]
		if tkr.lower() == "ticker" or not tkr or set(tkr) <= set("-: "):  # header / separator row
			continue
		key = tkr.upper()
		if key not in tiers:
			order.append(key)
		tiers[key] = tier
	return tiers, order, tier_cut


def cmd_rankdiff(args):
	a_tiers, _a_order, a_cut = _parse_ranking(args.a)
	b_tiers, _b_order, b_cut = _parse_ranking(args.b)
	a_keys, b_keys = set(a_tiers), set(b_tiers)
	common = sorted(a_keys & b_keys)
	agree = sum(1 for t in common if a_tiers[t] == b_tiers[t])
	per_ticker = [
		{"ticker": t, "a": a_tiers[t], "b": b_tiers[t], "changed": a_tiers[t] != b_tiers[t]}
		for t in common
	]
	report = {
		"a": args.a,
		"b": args.b,
		"intersection": len(common),
		"agree": agree,
		"agreement_pct": round(100.0 * agree / len(common), 1) if common else None,
		"changed": [c for c in per_ticker if c["changed"]],
		"per_ticker": per_ticker,
		"only_in_a": sorted(a_keys - b_keys),
		"only_in_b": sorted(b_keys - a_keys),
		"tier_cut_a": a_cut,
		"tier_cut_b": b_cut,
		"tier_cut_differs": (a_cut or "") != (b_cut or ""),
	}
	json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
	print()
	sys.exit(0)


def main():
	parser = argparse.ArgumentParser(prog="serenity_harness.py", description="Serenity harness self-check")
	sub = parser.add_subparsers(dest="command", required=True)
	sp = sub.add_parser("validate", help="Structural + evidence-boundary self-check")
	sp.add_argument("--verbose", action="store_true", default=False, help="Include detail for passing checks too")
	sp.set_defaults(func=cmd_validate)
	rd = sub.add_parser("rankdiff", help="Deterministic tier-table diff of two _ranking.md files (no judgment)")
	rd.add_argument("a", help="prior _ranking.md (A)")
	rd.add_argument("b", help="current _ranking.md (B)")
	rd.set_defaults(func=cmd_rankdiff)
	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
