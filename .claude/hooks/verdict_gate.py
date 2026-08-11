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
a bounded word-bridge (\u226420 chars) on each side, because the doctrine's own real example needs one
("$4.2B rebuild cost / 12 reactors") — but the slash must ALSO be space-flanked, or else sit tight
between two digits ("4.2/12"). That last requirement is what separates division from a ratio NAME:
`EV/Rev` presses letters against the slash on both sides, and arithmetic essentially never does.
Without it the bridge reached across intervening prose, so "down 12% recently, and EV/Rev of 18x = …"
counted the stray price-decline figure as a numerator and passed the exact bare top-down multiple this
check exists to reject. The docstring claimed a ratio name "still correctly fails either way" while it
did not — a described behavior that was never true is worse than a documented gap, because nobody
goes looking for it.

Accepted limit — the `Lens:` numeric bar is LINE-LEVEL, not per-operand. A `Lens:` line must contain
the operator *and* an `=` *and* at least one digit somewhere on that line — not one digit per leg. A
forked lens's upside leg is legitimately often all words (`content×volume ÷ MC = the re-rate leg`)
while the floor leg on the SAME line carries the real numbers; requiring every operand to be numeric
would reject that correct, doctrine-shaped answer. So this verifies "a real computation is happening
on this line," not "every leg of a forked lens is numeric" — a `Lens:` line whose only numbers sit
outside the fork it claims to compute could still slip through. Promoting this to a per-leg check
would need parsing the line into its floor/upside clauses, which this hook does not do.

ACCEPTED LIMIT, MEASURED — this hook fires on harness-development writing about itself, and both
obvious fixes are worse than the disease. Recorded with the numbers because the fixes are tempting,
plausible, and each takes an hour to disprove.

The mechanism: `single_name` matches the answer template's own section names (`Downside`, `rating`,
`conviction`, `vehicle`). Discussing this file necessarily uses them, so an engineering report reads
as a market verdict. It happened eight times in the session that wrote this, twice to messages whose
entire content was explaining that it happens.

  Fix A, "require a subject" — make template vocabulary count only alongside a cashtag or company
  reference. Prototyped: **2 of 71 fixtures flip from correctly-blocking to not-blocking**, including
  `real_verdict_still_blocks`, written specifically to prove a real verdict still blocks, and
  `macro_hard`, a genuine regime call that has no cashtag because it names no single company. A
  correct verdict missing only its NFI/NFA sign-off goes SILENT. It trades a nuisance for a hole in
  the one hard guarantee. There is also no clean subject test: a capitalized-proper-noun rule is the
  alias-list failure this harness rejects, and an ALL-CAPS ticker rule collides with `PT`, `MC`, `EV`,
  `FCF`, `PEG`, `IRR`, `ATM`, `LEAPS`, `CSP`, `HBM` — doctrine vocabulary, several load-bearing right
  here. The doctrine's own casual voice ("Nvidia's still the cleanest chokepoint long") makes the
  cashtag-less verdict normal, not marginal.

  Fix B, "strip code spans" — read markdown's use/mention distinction, since a report QUOTES
  `Downsides:` while a verdict WRITES it. Prototyped: costs nothing (71/71) and cannot be gamed by
  fencing a verdict. But run against REAL blocked messages rather than reconstructions of them, it
  cleared **zero of two** — both mixed backticked and bare mentions, written by someone actively
  thinking about this failure mode. It works only for an author who fences every mention, which is a
  formatting habit nobody reliably holds. Note the methodological trap: reconstructing the messages
  to test made them artificially consistent and scored ~2/3. Test the artifact, not your memory of it.

So the limit stands. The compensating control is that the block costs one corrective round, not a
lost turn (`stop_hook_active`), and CLAUDE.md is always loaded, so the doctrine is in context whether
or not this fires. The correct response to a false fire is to say so and move on — NOT to add a
sign-off to an engineering report, which manufactures the compliance token this hook's own
label-as-content check exists to reject.

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
# Leading `[\s*_#>`]*` absorbs markdown decoration (`**Downsides:**`, `## Downsides`, `> Lens:`) and
# the trailing `(?::|$)` accepts a header that is the whole line with no colon at all — which is the
# shape the pinned scorecard schema uses. Both were required before, and both are the shapes a model
# actually emits, so a decorated or heading-style header was not recognized as a section boundary:
# the next section got absorbed into the previous one's body, inflating a null block past the reason
# bar and silencing the hook. `-` is deliberately absent from the decoration class — a bullet
# (`- Downsides are already priced in`) is body text, and treating it as a boundary would truncate
# the very block being measured.
# A section header is a LINE-STRUCTURAL thing, and that single idea replaces what was three rounds of
# decoration-character whack-a-mole. The pieces:
#
#   _DECOR  — what may precede the label on its line: bullet, emphasis, heading, blockquote. A bullet
#             marker is safe to allow here ONLY because a separator is also required below; without
#             that requirement, `- Downsides are priced in` (body text) would read as a header.
#   _AFTER  — decoration BETWEEN the label and its separator. `**Downsides**: ` puts the closing
#             emphasis before the colon, where `**Downsides:** ` puts it after — the two shapes were
#             handled asymmetrically, so one worked and the other silently bypassed the whole check.
#   _SEP    — what separates the label from its body: ASCII colon, FULLWIDTH colon (this doctrine is
#             bilingual, so a Korean-keyboard colon is an ordinary typo, not an exotic one), an em or
#             en dash (the doctrine's own separator style — its `Lens:` examples read
#             `floor — EV/Rev 18`), or end-of-line for a bare `## Downsides` heading.
#             ASCII `-` is deliberately NOT a separator: it is this doctrine's compound-word joiner
#             ("asset-heavy") and its bullet marker, so accepting it would fire on ordinary prose.
_DECOR = r"[ \t*_#>`~-]*"
_AFTER = r"[ \t*_`~]*"
_SEP = "[:：—–]"
_LABELS = (r"Downsides?|Falsifier|Rating|Saved|Lens|Winner[\s-]*gates?|Structural position"
           r"|Forward revenue")

# THE BOUNDARY SCAN DEMANDS A STRONGER SEPARATOR THAN THE HEADER SEARCH. Not a patch — the two ask
# different questions with very different exposure.
#
# `_find_section_header` asks "where is the Downsides section?" One known label, and the contract
# says it should be there, so a dash is fair evidence.
#
# `_SECTION_LABEL` asks "does ANY of six other sections start on this line?" — six chances to
# misfire, evaluated against every line of every body. `Rating`, `Saved` and `Lens` are ordinary
# English words, so once a dash counted as a separator, a wrapped prose line beginning "Rating — not
# the equity rating, the credit outlook…" read as a section boundary. The walk stopped there and the
# 200 characters of real explanation after it were discarded, so a substantial section measured as
# null and a correct answer got told it was empty. Adding the dash to `_SEP` — done to catch the
# doctrine's own separator style — caused it, which is the lesson: widening a signal is safe in
# proportion to how specific the thing you are matching is.
#
# Residual, and the cheaper failure: a genuine next section written `Rating — overweight` no longer
# ends the previous one, so that body over-absorbs and a null section could hide behind it. That
# needs a dash-style header, which is rare; the bug it replaces needed an ordinary wrapped sentence,
# which is not. Prefer under-detecting a boundary over discarding a real body — the first stays
# silent on a correct answer, the second calls it broken.
_SEP_BOUNDARY = "[:：]"
_SECTION_LABEL = re.compile(rf"^{_DECOR}(?:{_LABELS}){_AFTER}(?:{_SEP_BOUNDARY}|$)", re.IGNORECASE)
# The dash-tolerant boundary, used ONLY inside a section whose own header was dash-styled.
_SECTION_LABEL_ANY = re.compile(rf"^{_DECOR}(?:{_LABELS}){_AFTER}(?:{_SEP}|$)", re.IGNORECASE)
_NULL_LEAD = re.compile(
	r"^(none|n/?a|없음|can'?t think of(?:\s+(?:one|any|anything))?)\b\s*[:\-—,]*\s*",
	re.IGNORECASE,
)
_MIN_SECTION_LEN = 6   # a bare label with nothing after it at all, anywhere
# A null token's trailing clause must clear this to count as "said why". Heuristic, and flagged as
# such rather than dressed up: unlike the 0.75 revenue-divergence threshold in data_integrity_guard,
# which is derivable from TTM-vs-annual timing math, there is nothing to derive here — "long enough
# to be a reason" has no closed form. 30 characters is roughly a short clause; it is chosen to sit
# BELOW anything a real reason needs and above a bare token, and it is SOFT-only, so the cost of it
# being slightly wrong is one nudge on a terse answer, never a block. If it starts firing on real
# concise answers, lower it — do not add a vocabulary list of "acceptable reasons," which would be
# the semantic judgment this layer declines.
_MIN_REASON_LEN = 30
# Markdown decoration a line may carry before its section label. `-` is deliberately NOT here: a
# bullet (`- Downsides are already priced in`) is body text, and treating it as a section boundary
# would truncate the very block being measured.


def _find_section_header(label, msg):
	"""The match for `<label>`'s section header, or None. THE single definition of "this answer has
	a real <label> section" — used by both the gate in `_section_missing` and the body walk in
	`_section_body`.

	It is one function because it was briefly two, and they disagreed: the gate accepted only a
	colon form while the body-finder had been widened to accept headings, so a heading-style answer
	skipped the null-content check entirely and the widening did nothing. Two implementations of one
	predicate is how the predicate stops being one.

	Two shapes, because the doctrine uses both: `Downsides:` inline (CLAUDE.md's answer contract) and
	`## Downsides` with NO colon (the pinned scorecard schema's own section headers) — so the one
	format the schema prescribes was the one that bypassed the check. The colon is optional ONLY on a
	line that is nothing but the header; mid-sentence prose ("the downsides here are priced in") must
	never read as a section header."""
	found = list(re.finditer(rf"^{_DECOR}{label}{_AFTER}(?:{_SEP}|$)", msg,
	                         re.IGNORECASE | re.MULTILINE))
	# THE LAST match, and line-anchored — the two properties that matter, both learned the hard way.
	#
	# Unanchored `re.search` took the FIRST `Downsides:` anywhere in the message, including one buried
	# mid-sentence. That broke in both directions on real text. A correct answer with a proper
	# bulleted section got nudged as empty, because a throwaway earlier clause ("earlier I wrote
	# Downsides: none, wrongly") was measured instead of the real section. And a genuinely empty
	# section was missed, because an earlier mention happened to look substantial. Neither is exotic:
	# quoting a section name as example text and correcting oneself mid-answer are both ordinary.
	#
	# Last-match is right because the answer contract fixes the order — the operative Downsides block
	# is the one in the closing structure, after the Lens line, not a passing reference above it.
	# Residual, accepted: an answer whose real section is followed by a LATER passing reference would
	# measure the reference. That inverts the common case for the rare one, and unlike the first-match
	# version it cannot be triggered by an ordinary preamble.
	return found[-1] if found else None


def _section_body(label, msg):
	"""Text belonging to a `<label>:` section: the label's own line remainder, plus any following
	lines up to the next recognized section label or a blank line. The doctrine's real shape is
	multi-line and bulleted (`Downsides:\\n- ...\\n- ...`); a same-line compliance token
	(`Downsides: none`) is the failure mode being closed. Checking only the same line would misflag
	every real bulleted answer as empty, so both shapes are scanned.
	"""
	m = _find_section_header(label, msg)
	if not m:
		return None
	# The boundary follows THIS ANSWER'S OWN header convention, read off the header just matched.
	#
	# A fixed global answer was wrong in both directions. Accepting a dash for every boundary let an
	# ordinary wrapped line ("Rating — not the equity rating, …") truncate a real body. Requiring a
	# colon for every boundary meant a genuinely dash-styled `Falsifier — …` did not end the previous
	# section, so a null block hid behind it.
	#
	# Neither is necessary, because the answer already told us which style it uses. A model that
	# writes `Downsides — none` is writing dash-style headers throughout; it does not switch back to a
	# colon one line later. So a dash counts as a boundary exactly when the section being measured was
	# itself dash-headed. In a colon-styled answer — the doctrine's own template, and what CLAUDE.md
	# reinforces on every load — a dash stays ordinary prose and cannot truncate anything.
	#
	# Reading the document's convention rather than legislating one is what makes this different from
	# the three decoration-class rounds before it: nothing here is a list that a new formatting habit
	# can fall outside of.
	boundary = _SECTION_LABEL_ANY if m.group(0).rstrip().endswith(("—", "–")) else _SECTION_LABEL
	lines = msg[m.end():].split("\n")
	body_lines = []
	for i, line in enumerate(lines):
		if i == 0:
			body_lines.append(line)
			continue
		# Match the boundary against the line with markdown decoration stripped. `**Falsifier:**` and
		# `## Downsides` are the DEFAULT shapes a model emits — the pinned scorecard schema itself
		# writes `## Downsides` — and matching only a bare `Falsifier:` at line start meant a bolded
		# header was not seen as a boundary at all. The next section then got absorbed into this
		# one's body, inflating a genuinely-null block past the reason bar and silencing the hook:
		# the module's own motivating example (`Downsides: none that matter`) walked straight back in
		# through a formatting variant. Structural checks have to survive the formatting the model
		# actually produces, not the formatting the example was written in.
		if not line.strip() or boundary.match(line):
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
	if _find_section_header(label, msg):
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

	# A REPO ARTIFACT beats every finance signal, cashtag or not — found by dogfooding, not by
	# reasoning: an agent's own report on this very hook was hard-blocked for quoting its fixtures'
	# example vocabulary (a price target, a rating, "overweight", "priced-in"). Those set
	# other_finance_signal, which the cashtag-only suppression above deliberately does not touch.
	#
	# Working on this repository means writing about market vocabulary constantly, AS SUBJECT
	# MATTER. A hook that cannot tell talking about a market from making a market call gets trained
	# away by its own false fires, and this one owns the layer's only hard block — the most
	# expensive thing to have people learn to ignore.
	#
	# The marker is deliberately NARROWER than dev_context above: a literal repository filename or
	# path, not a topic word. "harness" or "refactor" can appear in a real market answer; the string
	# `verdict_gate.py` or `.claude/hooks/` cannot plausibly appear in one. That tightness is what
	# makes this safe to apply against the hard block rather than only the cashtag path — a broad
	# topical guard here would be the semantic judgment the ceiling rule declines, and would punch a
	# hole in the NFI/NFA guarantee. Widen it only with a fixture proving a real verdict still blocks.
	repo_artifact = _has(
		r"\b[\w./-]+\.py\b|\bSKILL\.md\b|\bCLAUDE\.md\b|\bsettings\.json\b|\bharness-spec\.md\b"
		r"|\.claude/|\brun_fixtures\b|\bpytest\b|\bgit (?:commit|diff|status|add)\b",
		msg,
	)
	# A bare `fixtures?/` was here and is deliberately gone: it matched `sessions/990101.hook-fixture/`
	# inside a real `Saved:` mark, so a genuine archived verdict stopped hard-blocking. Caught by the
	# suite on the first run. `.claude/` already covers the real fixture directory, which is the
	# lesson worth keeping — a path fragment general enough to feel safe is general enough to match
	# the archive, and this guard suppresses the layer's only hard block, so it is the one place
	# where over-matching is the expensive direction.
	finance_signal = (other_finance_signal or cashtag_signal) and not repo_artifact

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
		r"|\d[\d,.]*\s?[%TtBbMmKk]?[^/\n]{0,20}\s/\s[^\d$₩€£\n]{0,20}[$₩€£]?\d"
		r"|\d[\d,.]*\s?[%TtBbMmKk]?/[$₩€£]?\d"
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
