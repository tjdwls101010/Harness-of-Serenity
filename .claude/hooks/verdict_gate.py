#!/usr/bin/env python3
"""Stop hook — the verdict-gate, enforced as a STRUCTURAL contract (not a semantic judge).

WF4's durable finding: under output pressure the model reads the verdict procedures as labels and
skips them — "prose can't fix a firing problem." But a Stop hook cannot judge whether an argument is
*right*; it can only check whether the answer carries the machine-readable MARKS the contract
requires. So the contract (CLAUDE.md "How the answer reads" + analysis §6) mandates one visible token
for a valuation verdict — a `Lens:` line that combines the driver inputs with an arithmetic operator
and ends in `= <result>` (a forked lens prints two: a floor line and an upside line) — and this hook
checks for that token's PRESENCE, never for the semantics of the math. The old check inferred
"arithmetic ran" from `= <digit>`, which a bare top-down multiple ("EV/Rev = 12x") satisfied — the
exact miss it was meant to catch. Structure, not meaning: is the Lens line there or not.

Calibration: a missing Lens line is returned as SOFT feedback (one corrective round via Stop
additionalContext), never a hard block, until real use confirms no false-fires — then it can be
promoted. The one HARD block is the near-universal, unambiguous miss: a formatted market answer (a
TLDR *and* a finance signal) with no NFI/NFA sign-off, whose absence doctrine says "reads as fake."
A non-market turn (a coding answer that happens to say "TL;DR") is not a finance answer, so it is
never hard-blocked. stop_hook_active guards the loop: one corrective round, then the turn ends.

Entry gate: `finance_signal OR the TLDR token` — never the TLDR token alone. The gate used to be a
single `if not TLDR: return`, which meant a verdict that opened "Bottom line:" instead of "TLDR:", a
Korean equivalent, or an answer that simply forgot the token, produced EMPTY output with every
downstream check dead behind that one `if`. A verdict is identifiable by its CONTENT (a cashtag, a
rating, a vehicle, Korean market vocabulary) whether or not it also carries the one literal word the
contract asks for — so `finance_signal` (computed from content, further down this docstring) now
decides entry, and a missing TLDR token becomes its own independent SOFT nudge instead of the switch
that turns every other check off.

Label-as-content: a structural check that only tests for a section LABEL (`\\bDownside`, or `falsif`
— which even matches inside the word "Falsifier" itself) is satisfied by the label alone, so
`Downsides: none that matter` or `Falsifier: can't think of one` passed silently while the body
explicitly negated what the label promised. Left alone, a check like that actively trains the model
to emit compliance tokens instead of real content — the deepest risk in this hook layer. The fix
stays structural (no judgment of whether the reasoning is GOOD): when the literal label is present,
its body — the same-line remainder, or the following bulleted lines up to the next section label —
must clear a minimum length, or, if it leads with a null token (none / n/a / 없음 / can't think of),
the clause AFTER that token must itself clear a minimum length. A clean-kill verdict can legitimately
have nothing left to list, so a null token is never rejected outright — only a null token with no
stated reason after it (`_is_null_section`). When no literal label is present at all, this falls back
to the original broad, label-agnostic scan of the whole message (a falsifier phrased as prose, e.g.
"this breaks if utilization stalls," without a "Falsifier:" header, still counts) — narrowing that
path too would mean judging whether prose IS a falsifier, which is semantic judgment, not structural,
and stays out of scope here.

The `Lens:` marker accepts `×÷*` (multiply/divide) outright, a `/` flanked by numeric-or-currency
tokens (never a bare ratio NAME like `EV/Rev`), or `+`/`-`/`\u2212` flanked by numeric-or-currency
tokens — because the doctrine's own driver list writes replacement-cost as `replacement-cost/unit`
and prices sum-of-parts as pure addition with no multiply or divide at all ("a stake value PLUS an
operating value against parent MC"). The check is "an arithmetic expression is present," never "one
specific operator is present." Because `-` is also this doctrine's compound-word joiner
("asset-heavy", "step-change"), a bare `+`/`-`/`\u2212` counts ONLY when numeric tokens sit tight
against it with no word between — a looser bridge would fire on nearly every line of prose. `/` gets
a wider, bounded word-bridge (\u226420 chars) on each side instead, because the doctrine's own real
example needs one ("$4.2B rebuild cost / 12 reactors"); this is intentionally the looser of the two
and can, in a contrived sentence, treat an unrelated nearby number and a ratio name's slash as
arithmetic (e.g. a stray figure a few words before "EV/Rev of 18x"). Accepted, not fixed, per the
standing instruction to prefer over-accepting a soft nudge over misfiring on correct arithmetic — a
precise fix would need grammatical parsing this hook does not do.

Accepted limit — the `Lens:` numeric bar is LINE-LEVEL, not per-operand. A `Lens:` line must contain
the operator *and* an `=` *and* at least one digit somewhere on that line — not one digit per leg. A
forked lens's upside leg is legitimately often all words (`content×volume ÷ MC = the re-rate leg`)
while the floor leg on the SAME line carries the real numbers; requiring every operand to be numeric
would reject that correct, doctrine-shaped answer. So this verifies "a real computation is happening
on this line," not "every leg of a forked lens is numeric" — a `Lens:` line whose only numbers sit
outside the fork it claims to compute could still slip through. Promoting this to a per-leg check
would need parsing the line into its floor/upside clauses, which this hook does not do.

Known limit — a bare prose verdict with no listed vocabulary is invisible. "TLDR: Nvidia is a
screaming buy right now" has no cashtag, no `PT`/`rating`/`vehicle`, no Korean market phrase —
nothing in `finance_signal`'s closed vocabulary. Catching it honestly needs proper-noun-plus-verb
detection or a company-name alias list, and an alias list would itself be the closed-list failure
this harness is trying to remove (it would also miss a name's first mention). Left uncovered on
purpose — the compensating control is that CLAUDE.md is always loaded, so the doctrine (NFI/NFA, the
Lens line, the falsifier) is in context whether or not this hook fires.

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


# --- Label-as-content helpers (2.2) --------------------------------------------------------------
# A small, closed set of doctrine section headers — used only to find where one section's body ends
# and the next begins (a bulleted `Downsides:` block runs until `Falsifier:`, `Rating:`, etc.). This
# is a fixed list grounded in CLAUDE.md's own "How the answer reads" template, not an open-ended name
# list, so it stays a structural boundary rather than semantic parsing.
_SECTION_LABEL = re.compile(
	r"^\s*(?:Downsides?|Falsifier|Rating|Saved|Lens|Winner[\s-]*gates?|Structural position|Forward revenue)\s*:",
	re.IGNORECASE,
)
_NULL_LEAD = re.compile(
	r"^(none|n/?a|없음|can'?t think of(?:\s+(?:one|any|anything))?)\b\s*[:\-—,]*\s*",
	re.IGNORECASE,
)
_MIN_SECTION_LEN = 6   # a bare label with nothing after it at all, anywhere
_MIN_REASON_LEN = 30   # a null token's trailing clause must clear this to count as "said why"


def _section_body(label, msg):
	"""Text belonging to a `<label>:` section: the label's own line remainder, plus any following
	lines up to the next recognized section label or a blank line. The doctrine's real shape is
	multi-line and bulleted (`Downsides:\\n- ...\\n- ...`); a same-line compliance token
	(`Downsides: none`) is the failure mode being closed. Checking only the same line would misflag
	every real bulleted answer as empty, so both shapes are scanned.
	"""
	m = re.search(r"\b" + label + r"\s*:", msg, re.IGNORECASE)
	if not m:
		return None
	lines = msg[m.end():].split("\n")
	body_lines = []
	for i, line in enumerate(lines):
		if i == 0:
			body_lines.append(line)
			continue
		if not line.strip() or _SECTION_LABEL.match(line):
			break
		body_lines.append(line)
	return "\n".join(body_lines)


def _is_null_section(body):
	"""True when a section body is content-free: absent, a bare label, or a null token (none / n/a /
	없음 / can't think of) with nothing substantial after it. A null token FOLLOWED BY a clause long
	enough to be a reason (`none — thesis already closed, no live downside left to price`) is
	accepted: doctrine only needs the model to say why a section is empty, not fabricate content that
	isn't there — a clean-kill verdict can legitimately have no downside/bull leg left to list.
	"""
	if body is None:
		return True
	stripped = re.sub(r"^[\s:\-—*•]+", "", body)
	stripped = re.sub(r"\s+", " ", stripped).strip()
	if len(stripped) < _MIN_SECTION_LEN:
		return True
	lead = _NULL_LEAD.match(stripped)
	if not lead:
		return False
	return len(stripped[lead.end():]) < _MIN_REASON_LEN


def _section_missing(label, broad_pattern, msg):
	"""True when neither a genuine `<label>:` section nor an alternate broad-pattern mention is
	present. When the literal label exists, its content is checked for null-ness — this closes the
	label-as-content loophole (`\\bDownside` and `falsif` both match their own header regardless of
	what follows). When the label is absent, this falls back to the original whole-message scan, so a
	falsifier phrased as prose without a header ("this breaks if utilization stalls") still counts —
	narrowing THAT path too would mean judging whether prose IS a falsifier, which this hook declines.
	"""
	if re.search(r"\b" + label + r"\s*:", msg, re.IGNORECASE):
		return _is_null_section(_section_body(label, msg))
	return not _has(broad_pattern, msg)


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

	has_tldr = _has(r"\bTL;?DR\b", msg)

	# Content-based finance signal, computed BEFORE the entry gate (2.1) — see module docstring.
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
	other_finance_signal = single_name or strong_verdict

	# Harness-dev suppression (2.4a) — ported from evidence_discipline.py's `_META`/`_MARKET_ANCHOR`
	# split (duplicated here, not imported: the two hooks deliberately share no code). A bare cashtag
	# inside obvious harness-dev prose ("fixed the verdict_gate cashtag regex so a $NVDA-style
	# example...") is not a market ask and must never trigger the NFI/NFA hard block. The override
	# that beats dev context is a cashtag PLUS another finance signal, or a Korean market phrase —
	# never a bare cashtag alone; both of those already set other_finance_signal, so the override
	# falls out for free below and this only has to suppress the CASHTAG-ONLY path.
	dev_context = _has(
		r"harness|하네스|\bhook\b|\bhooks\b|훅\b|\bskill\b|스킬|SKILL\.md|CLAUDE\.md|settings\.json"
		r"|\.py\b|pipeline code|subagent|verdict[_\s-]?gate|evidence[_\s-]?discipline|exec-form"
		r"|refactor|리팩터|\beval\b|workflow|워크플로|commit|커밋|\b계획\b|구현|스펙|spec\b",
		msg,
	)
	cashtag = _has(r"\$[A-Za-z]{1,5}\b", msg)
	cashtag_signal = cashtag and not (dev_context and not other_finance_signal)
	finance_signal = other_finance_signal or cashtag_signal

	# Entry gate (2.1): a formatted serenity answer OR any finance signal — never the TLDR token
	# alone. Closes the 16th case: any opener that isn't the literal token ("Quick take:", a Korean
	# equivalent, or an answer that simply forgets it) no longer kills every check below it.
	if not (has_tldr or finance_signal):
		return

	# Sign-off (EN + KO) — NFI/NFA is used verbatim even in Korean answers, but accept the
	# spelled-out forms too so a complete Korean verdict is never false-blocked.
	signoff = (
		_has(r"\bNF[IA]\b", msg)
		or _has(r"not (financial|investment) advice", msg)
		or _has(r"투자\s*(조언|자문|권유)\s*(아|x|X)", msg)
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
	# STRUCTURAL check (not semantic): the contract's `Lens:` driver line, scoped to that one physical
	# line — an arithmetic operator, an "=", and (2.2) at least one digit somewhere on the line so a
	# placeholder-only line ("EV/Rev N/A × N/A ÷ N/A = still good") can't pass on the operator alone.
	# Operators (2.3): ×÷* outright; `/` counts when flanked by numeric-or-currency tokens with a
	# bounded word-bridge (doctrine's own example needs one: "$4.2B rebuild cost / 12 reactors");
	# `+`/`-`/minus-sign count only with numeric tokens TIGHT against them, no bridge — `-` (and
	# this doctrine's own em-dash separator, "floor — EV/Rev 18") is everywhere in ordinary prose,
	# so a bridged additive operator would satisfy the marker on a bare top-down multiple that
	# merely has a dash and two unrelated numbers nearby. A bare ratio NAME ("EV/Rev = 12x", no real
	# division shown) still correctly fails either way — that is the whole point. See the module
	# docstring for the accepted limits on both the line-level numeric bar and the `/` bridge.
	lens_line_match = re.search(r"Lens:[^\n]*", msg, re.IGNORECASE)
	lens_line = lens_line_match.group(0) if lens_line_match else ""
	lens_operator = _has(
		r"[×÷*]"
		r"|\d[\d,.]*\s?[%TtBbMmKk]?[^/\n]{0,20}/[^\d$₩€£\n]{0,20}[$₩€£]?\d"
		r"|[$₩€£]?\d[\d,.]*\s?[%TtBbMmKk]?\s*[+\-−]\s*[$₩€£]?\d[\d,.]*\s?[%TtBbMmKk]?",
		lens_line,
	)
	lens_marker = lens_operator and "=" in lens_line and _has(r"\d", lens_line)

	hard = []
	if finance_signal and not signoff:
		hard.append("the NFI/NFA sign-off — doctrine: its absence reads as fake. Add it.")

	soft = []
	# TLDR opener (2.1) — independent SOFT nudge now that entry no longer depends on it.
	if finance_signal and not has_tldr:
		soft.append(
			"open with the literal `TLDR:` (or `TL;DR:`) token — doctrine requires it on every "
			"market answer (CLAUDE.md, 'How the answer reads'); the contract can't depend on the "
			"model remembering the one word that used to turn this whole check on."
		)
	# You reached a valuation verdict (named a lens or rendered priced/cheap/pass) but no machine-
	# checkable `Lens:` driver line is present — RUN it on one visible line. Gated on single_name
	# (2.4c), not the broader valuation_verdict alone: a macro-only call ("overweight semis,
	# underweight defensives") trips strong_verdict's vocabulary without naming any company to run a
	# driver computation on, so nudging for a company-level Lens: line there is a false fire.
	if single_name and (lens_named or valuation_verdict) and not lens_marker:
		soft.append(
			"you rendered a valuation verdict but no machine-checkable `Lens:` line appears — emit it: "
			"`Lens: <name> — <input>×<input>÷<input> = <result>` (a forked lens shows two, floor and "
			"upside), each input traced to key_facts. A named lens with no computed driver line is the "
			"consensus top-down read, not the verdict (N10 / R5)."
		)
	if single_name:
		# Label-as-content (2.2): see _section_missing docstring — a header alone no longer satisfies
		# these checks; the body must be non-null or carry a stated reason for being empty.
		if _section_missing(r"Downsides?", r"\bDownside|\bbear case\b|리스크|하방|약점", msg):
			soft.append("the short Downsides/bear block (2-4 casual bullets, each tagged priced-in / addressed).")
		if _section_missing(
			r"Falsifier",
			r"breaks if|falsif|kill[\s-]*(signal|condition)|wrong if|thesis breaks|깨지면|틀리면|무효|아니라면",
			msg,
		):
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
