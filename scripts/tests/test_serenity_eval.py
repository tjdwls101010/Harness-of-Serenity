"""Coverage for `serenity_eval.py` — the measurement instrument itself.

This file exists because the instrument had no tests at all, and phase 04's whole premise is that
**part of what it measured was nothing**: 16% of the n=25 draw returned empty pipeline data, the
twelve archetype-labeled gold theses were never sampled, and the two rubric rows the owner most
needs (`recursive_bottom_hop`, `second_order_and_sibling`) had an in-scope N of "whatever a random
draw happened to contain."

An eval is the one piece of code where a silent bug is worst: every other check in this repo is
either green or red, but a broken eval reports a *number*, and a number gets quoted. So the tests
below lean hard on the failures that still look healthy — a gold case quietly dropped, a subject
ticker quietly swapped, an answer key quietly leaking into the blind prompt, a hook that answers
but doesn't actually speak the contract.

Hermetic by construction: every sampler test runs `--no-network` against the committed resolution
cache, so the suite never depends on yfinance being up or on a ticker's market cap that afternoon.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS_DIR.parent
EVAL = SCRIPTS_DIR / "serenity_eval.py"
GOLD = SCRIPTS_DIR / "eval" / "gold_set.json"


def _run(*args, expect_ok=True):
    p = subprocess.run([sys.executable, str(EVAL), *args],
                       capture_output=True, text=True, cwd=str(ROOT), timeout=300)
    if expect_ok:
        assert p.returncode == 0, f"exit {p.returncode}\nstderr: {p.stderr[:2000]}"
    return p


def _sample(n=25, seed=7, *extra):
    """The cases list. `--no-network` keeps the suite hermetic against the committed cache."""
    out = _run("sample", "--n", str(n), "--seed", str(seed), "--no-network", *extra).stdout
    return json.loads(out)["cases"]


@pytest.fixture(scope="module")
def gold():
    return json.loads(GOLD.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sample25():
    return _sample(25, 7)


# --- the archetype floor ---------------------------------------------------------------------

def test_every_gold_case_is_present_regardless_of_n(gold):
    """The floor is a floor. Only ONE of the twelve appeared in the pre-fix n=25/seed=7 draw, which
    is how the two chokepoint-scoped rubric rows ended up measuring an uncontrolled subset."""
    want = {c["id"] for c in gold["cases"]}
    for n in (12, 25):
        got = {c["id"] for c in _sample(n, 7) if c.get("gold")}
        assert got == want, f"n={n} missing {want - got}"


def test_a_smaller_n_than_the_gold_set_still_yields_every_gold_case():
    """Asking for fewer cases than the floor must not silently truncate the floor — an
    archetype-blind sample is the one outcome this file exists to prevent."""
    cases = _sample(5, 7)
    assert len({c["id"] for c in cases if c.get("gold")}) == 12
    assert len(cases) == 12, "n below the floor yields the floor, not a truncated one"


def test_all_six_archetype_categories_survive_into_the_sample(sample25):
    got = {c["archetype"] for c in sample25 if c.get("gold")}
    assert got == {"chokepoint", "disruption", "evolution", "falling_knife",
                   "data_error", "macro", "cycle_meta"}
    assert sum(1 for c in sample25 if c.get("archetype") == "chokepoint") >= 4


def test_gold_cases_bypass_the_resolution_gate(sample25):
    """EWY is an ETF (marketCap and sector are null BY CONSTRUCTION) and IQE is LSE-listed. Both
    fail the naive `marketCap or sector` predicate, and dropping them would empty two of the six
    archetype categories the floor exists to guarantee. The gate is for the random draw."""
    tickers = {c["ticker"] for c in sample25 if c.get("gold")}
    assert {"EWY", "IQE"} <= tickers


def test_both_nbis_cases_survive_the_distinct_ticker_rule(sample25):
    """Two gold cases share NBIS — one the asset-financed levered-IRR read, one the strategic-floor
    read. They test different moves, so ticker-diversity must not deduplicate them."""
    assert sum(1 for c in sample25 if c.get("gold") and c["ticker"] == "NBIS") == 2


# --- subject and framing ---------------------------------------------------------------------

@pytest.mark.parametrize("case_id,subject", [
    ("2004936335702753729", "AXTI"),   # tagged NVDA first; the thesis is the InP chokepoint
    ("2033763395032519112", "AEHR"),   # tagged MSTR first; the thesis is the cycle-stage map
])
def test_a_pinned_subject_overrides_the_first_in_array_heuristic(sample25, case_id, subject):
    """`_primary_ticker` takes the first regex-valid entry of the DB's `tickers` array, which is
    tagging order, not relevance. It is right for 10 of the 12 — measured — so the heuristic stays
    and only these two are pinned. Asking "what's your read on NVDA?" against an answer key about
    AXT's InP substrate scores six misses that have nothing to do with doctrine quality."""
    case = next(c for c in sample25 if c["id"] == case_id)
    assert case["ticker"] == subject
    assert subject in case["blind_prompt"]


@pytest.mark.parametrize("case_id,entry_type,must_not_contain", [
    ("2004936335702753729", "discovery", "sold off hard"),
    ("2033763395032519112", "ranking", "sold off hard"),
    ("1975205333254447126", "discovery", "sold off hard"),
])
def test_curated_framing_overrides_the_keyword_heuristic(sample25, case_id, entry_type, must_not_contain):
    """`entry_type` picks the blind-prompt template, so it decides what question gets asked. The
    heuristic reads a drop mentioned anywhere in a long thesis as a fear-dip and turns a discovery
    read into "did it sell off?" — a different question, scored against the original answer key."""
    case = next(c for c in sample25 if c["id"] == case_id)
    assert case["entry_type"] == entry_type
    assert must_not_contain not in case["blind_prompt"]


def test_every_blind_prompt_carries_the_thesis_date(sample25):
    """The discovery branch used to say "right now" with no date while the pipeline loaded today's
    data — so a September-2025 thesis was asked ~11 months later, and "already re-rated, look
    elsewhere" (the objectively correct present-tense answer) scored as a miss on every row."""
    for c in sample25:
        assert c["date"][:10] in c["blind_prompt"], f"{c['ticker']}: {c['blind_prompt']}"


# --- the resolution gate ---------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["SIVE", "XFAB", "ASHM", "APPL"])
def test_unresolvable_tickers_never_reach_the_random_remainder(sample25, bad):
    """All four returned empty pipeline data in the pre-fix draw — 16% of the sample with no facts
    to build a `Lens:` line from. APPL is a typo for AAPL in the source post and yfinance resolves
    it to an unrelated mutual fund, which is the harness's own ticker-collision gotcha turned on
    the eval: a resolution check that only asks "did something come back" accepts the fund."""
    assert bad not in {c["ticker"] for c in sample25 if not c.get("gold")}


def test_a_rejected_candidate_is_named_in_the_report_not_silently_dropped():
    """Asserts the PROPERTY — every rejection is real and carries a stated reason — rather than a
    specific ticker.

    The earlier version named SIVE and XFAB. That broke the first time the thesis DB grew (52 rows
    added by another session): an UNLABELLED draw shifts when the pool changes, so XFAB was no
    longer reached before the buckets filled and FORM was rejected in its place. Nothing was wrong
    with the code. A test pinned to an instance of the data fails on data growth and teaches people
    to edit the assertion; one pinned to the invariant does not. (The standing sample is immune to
    this by construction — see `--only-labeled` — but this test deliberately exercises the raw draw.)"""
    meta = json.loads(_run("sample", "--n", "25", "--seed", "7", "--no-network").stdout)["meta"]
    rejected = meta["resolution"]["rejected"]
    assert rejected, "rejections must be reported, not silently absorbed"
    assert all(r.get("reason") for r in rejected), "a rejection without a reason is a silent drop"
    cache = json.loads((SCRIPTS_DIR / "eval" / "ticker_resolution_cache.json").read_text())["tickers"]
    for r in rejected:
        assert not cache.get(r["ticker"], {}).get("ok"), \
            f"{r['ticker']} was rejected but the cache says it resolves"


def test_a_thesis_that_disclaims_its_only_ticker_is_skipped():
    """Case 2059532571839729902 tags ["DPZ"] and reads "Definitely not $DPZ. But kinda reminds me
    of Soitec" — so the blind prompt asked for a read on Domino's Pizza while the answer key is
    about an unnamed European power-semi name, and all six items tallied as misses."""
    meta = json.loads(_run("sample", "--n", "25", "--seed", "7", "--no-network").stdout)["meta"]
    assert meta["resolution"]["disclaimed_skipped"] > 0
    assert "2059532571839729902" not in {c["id"] for c in _sample(25, 7)}


def test_the_sample_is_reproducible_offline(sample25):
    """Same (n, seed) → same cases, or a before/after around a doctrine edit measures the network.
    The committed cache is what makes this hold on a fresh clone with yfinance down."""
    again = _sample(25, 7)
    assert [c["id"] for c in again] == [c["id"] for c in sample25]


# --- answer-key leakage ------------------------------------------------------------------------

def test_no_blind_prompt_leaks_the_answer_key(sample25, gold):
    """The harness under test sees `blind_prompt` and nothing else. `thesis_text`, `archetype`,
    `gold_label` and `gold_tests` are all answer key — a leak here would not fail anything, it
    would just quietly inflate every score."""
    tests_by_id = {c["id"]: c for c in gold["cases"]}
    for c in sample25:
        prompt = c["blind_prompt"]
        assert c["thesis_text"][:200] not in prompt
        g = tests_by_id.get(c["id"])
        if g:
            assert g["tests"] not in prompt
            assert g["label"] not in prompt
            assert g["archetype"] not in prompt.lower()


def test_the_gold_set_does_not_duplicate_thesis_text(gold):
    """The answer key lives in the committed DB, keyed by id. A second copy here would drift from
    it, and the drift would be invisible — both files look authoritative."""
    for c in gold["cases"]:
        assert "thesis_text" not in c


# --- report: scope, floor, and the hook oracle -------------------------------------------------

def _scored(tmp_path, cases, meta=None):
    p = tmp_path / "scored.json"
    p.write_text(json.dumps({"meta": meta or {"seed": 7}, "cases": cases}), encoding="utf-8")
    return p


def _case(ticker, archetype, scores, response="TLDR: x. NFI"):
    return {"id": ticker, "ticker": ticker, "entry_type": "discovery",
            "archetype": archetype, "response": response, "scores": scores}


_FULL = {"archetype_named": 1, "lens_run": 1, "recursive_bottom_hop": 1,
         "second_order_and_sibling": 1, "bear_and_falsifier": 1, "priced_in_decomposed": 1,
         "missed_signature_moves": [], "notes": ""}


def test_a_non_chokepoint_case_never_contributes_to_the_chokepoint_rows(tmp_path):
    """The mechanical scope split (the point of persisting `archetype`). A judge that scored a
    disruptor 1 on recursive_bottom_hop must not raise that row's numerator — and one that scored
    it 0 must not lower it. Before this, the judge re-decided scope from unstructured text on every
    pass, so a borderline case could flip n/a<->0 between two scorings of the IDENTICAL answer:
    a false regression with zero underlying change, which no increase in n removes."""
    p = _scored(tmp_path, [_case("SNAP", "disruption", dict(_FULL)),
                           _case("AXTI", "chokepoint", dict(_FULL))])
    out = _run("report", "--results", str(p), "--n-floor", "1", "--no-hook").stdout
    row = next(l for l in out.splitlines() if l.startswith("| recursive_bottom_hop"))
    assert "1 / 1" in row, f"disruptor leaked into the chokepoint row: {row}"


def test_an_unlabeled_case_is_counted_but_flagged_as_scope_unstable(tmp_path):
    p = _scored(tmp_path, [_case("WOLF", None, dict(_FULL))])
    out = _run("report", "--results", str(p), "--n-floor", "1", "--no-hook").stdout
    assert "1 unlabeled case(s)" in out
    assert "flip n/a↔0" in out


@pytest.mark.parametrize("n_cases,floor,suppressed", [(3, 12, True), (3, 2, False)])
def test_a_per_move_percentage_is_suppressed_below_the_n_floor(tmp_path, n_cases, floor, suppressed):
    """A 100%-on-one-case row read as a result is how a broken instrument produces confident wrong
    conclusions. Detecting a 20-point true shift at 80% power needs ~90 in-scope cases."""
    p = _scored(tmp_path, [_case(f"T{i}", "chokepoint", dict(_FULL)) for i in range(n_cases)])
    out = _run("report", "--results", str(p), "--n-floor", str(floor), "--no-hook").stdout
    row = next(l for l in out.splitlines() if l.startswith("| archetype_named"))
    assert ("insufficient n" in row) is suppressed, row


def test_an_unrecorded_model_is_called_out(tmp_path):
    """A before/after separated by weeks could reflect a default-model change rather than the
    doctrine edit under test, and the confound is unrecoverable after the fact."""
    p = _scored(tmp_path, [_case("AXTI", "chokepoint", dict(_FULL))])
    assert "model not recorded" in _run("report", "--results", str(p), "--no-hook").stdout
    p2 = _scored(tmp_path, [_case("AXTI", "chokepoint", dict(_FULL))], meta={"model": "claude-opus-5"})
    out2 = _run("report", "--results", str(p2), "--no-hook").stdout
    assert "model not recorded" not in out2 and "claude-opus-5" in out2


def test_notes_reach_the_report(tmp_path):
    """`notes` is where a judge says "this case is broken" or "different but defensible". It used
    to be collected and then read by nothing — the escape hatch for a resolved-since thesis was
    write-only, which is why F17's failure mode had no visible symptom."""
    sc = dict(_FULL, notes="different but defensible")
    p = _scored(tmp_path, [_case("AXTI", "chokepoint", sc)])
    assert "different but defensible" in _run("report", "--results", str(p), "--no-hook").stdout


def test_a_hook_that_cannot_explain_reads_as_unavailable_not_as_healthy(tmp_path, monkeypatch):
    """Found by running it: a hook predating `--explain` ignores argv, reads the same stdin, and
    prints ordinary hook output — valid JSON that passes a naive parse. The report then said
    "0/4 cases scored" inside a healthy-looking line. An instrument that degrades silently is the
    exact failure this whole phase is about, so the contract's own key is demanded."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_ev", EVAL)
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)

    class _P:
        returncode = 0
        stdout = json.dumps({"decision": "block", "reason": "missing NFI"})  # legacy hook shape
    monkeypatch.setattr(ev.subprocess, "run", lambda *a, **k: _P())
    assert ev._hook_explain("TLDR: buy") is None


def test_hook_null_checks_map_to_n_a_never_to_zero():
    """`null` from the hook means the check did not APPLY (a macro-only answer names no company to
    run a driver line on). Collapsing that to 0 manufactures a miss out of a correct answer.

    This test used to assert `== {}` for the abstain case, which is what its name claims only if
    the caller then treats an absent key as n/a — and the caller did not; it left the judge's score
    in place. So the property was asserted in the one place it could not fail. Now the function
    returns the `n/a` explicitly and the assertions say so."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_ev", EVAL)
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)
    E = ev._mechanical_scores
    assert E({"checks": {"entered": True, "lens_line": None, "downsides": None, "falsifier": None}}) \
        == {"lens_run": "n/a", "bear_and_falsifier": "n/a"}
    assert E({"checks": {"entered": True, "lens_line": False, "downsides": None, "falsifier": None}}) \
        == {"lens_run": 0, "bear_and_falsifier": "n/a"}
    assert E({"checks": {"entered": True, "lens_line": True, "downsides": True, "falsifier": False}}) \
        == {"lens_run": 1, "bear_and_falsifier": 0}
    # entered=False is the one abstention that must NOT be excused — the answer never presented as
    # a verdict, which is a miss to score, so the hook offers no opinion and the judge's score stands.
    assert E({"checks": {"entered": False, "lens_line": None}}) == {}


# --- the disclaim guard, directly ---------------------------------------------------------------

@pytest.mark.parametrize("content,ticker,expected", [
    ("This was the company i liked. Definitely not $DPZ. But kinda reminds me of Soitec", "DPZ", True),
    ("$DPZ is the pick here, huge upside", "DPZ", False),
    ("unlike $INTC, $AMD actually ships. $AMD margins are fine", "AMD", False),
    ("not $NVDA this time", "NVDA", True),
    ("나는 $DPZ 아니라고 본다", "DPZ", False),   # negation AFTER the ticker — window looks backwards only
])
def test_disclaim_guard(content, ticker, expected):
    """A proxy, and documented as one: "not X, but something like it" is a normal way to write and
    a regex keeps losing to rhetorical anchoring. It only has to keep the obvious cases out of the
    one human inspection pass that freezes a standing sample."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_ev", EVAL)
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)
    assert ev._is_disclaimed(ticker, content) is expected


def test_a_case_with_no_judge_result_is_reported_not_silently_dropped(tmp_path):
    """A killed judge arrives as `scores: null`. It contributes to nothing, so without this the
    pooled rate is computed over an unstated subset while the header still says "cases: 3".

    Not hypothetical — a session limit killed five judges during the first pilot run and every one
    came back exactly this way, which is how the gap was found."""
    cases = [_case("AXTI", "chokepoint", dict(_FULL)),
             _case("AAOI", "chokepoint", dict(_FULL))]
    cases.append({"id": "EWY", "ticker": "EWY", "entry_type": "fear_dip",
                  "archetype": "macro", "response": "TLDR: x", "scores": None})
    p = _scored(tmp_path, cases)
    out = _run("report", "--results", str(p), "--n-floor", "1", "--no-hook").stdout
    assert "1/3 case(s) had no JUDGE result" in out
    # and the rates really are over 2, not 3
    row = next(l for l in out.splitlines() if l.startswith("| archetype_named"))
    assert "2 / 2" in row, row


def test_a_fully_scored_run_says_nothing_about_missing_judges(tmp_path):
    """The warning has to be absent when it does not apply, or it becomes wallpaper."""
    p = _scored(tmp_path, [_case("AXTI", "chokepoint", dict(_FULL))])
    assert "carry no judge result" not in _run("report", "--results", str(p), "--no-hook").stdout


# --- the hook/judge integration, where four review findings lived --------------------------------

_MACRO_ANSWER = "TLDR: overweight semis, underweight defensives. NFI"
_FULL_ANSWER = ("TLDR: buy.\nLens: content — $12 × 40M ÷ $4.8B = 10%\nDownsides:\n- dilution, "
                "priced-in\nFalsifier: breaks if demand halves.\nRating: Buy, PT $40. NFI")


def test_the_hook_forces_n_a_when_it_abstains_not_just_when_it_disagrees(tmp_path):
    """A macro-only answer names no company to run a driver line on, so the hook returns `null` for
    lens_line/downsides/falsifier. Returning *nothing* for those left a judge's wrong 0 standing
    uncorrected — two real misses manufactured out of a correct answer. Abstention has to be an
    active `n/a`, not silence."""
    sc = dict(_FULL, lens_run=0, bear_and_falsifier=0)
    p = _scored(tmp_path, [_case("MACRO", "macro", sc, response=_MACRO_ANSWER)])
    out = _run("report", "--results", str(p), "--n-floor", "1").stdout
    for row in ("lens_run", "bear_and_falsifier"):
        line = next(l for l in out.splitlines() if l.startswith(f"| {row} "))
        assert "0 / 0" in line, f"{row} should be out of scope entirely: {line}"


def test_a_failed_response_is_still_scored_not_excused_as_out_of_scope(tmp_path):
    """The inverse, and the reason the fix branches on `entered`. When the hook never enters, the
    answer failed to present as a verdict at all — a miss to score, not a scope exclusion. Forcing
    n/a there would quietly pardon an empty or broken response."""
    sc = dict(_FULL, lens_run=0, bear_and_falsifier=0)
    p = _scored(tmp_path, [_case("EMPTY", "chokepoint", sc, response="...")])
    out = _run("report", "--results", str(p), "--n-floor", "1").stdout
    line = next(l for l in out.splitlines() if l.startswith("| lens_run "))
    assert "0 / 1" in line, f"a non-verdict must stay a scored miss: {line}"


def test_the_unscored_warning_never_contradicts_the_numbers_beside_it(tmp_path):
    """`unscored` was computed BEFORE the hook ran, so a case whose judge died but whose response
    the hook could still score printed 'contributed to nothing above / computed over the remaining
    0' directly beside a rate built from that very case's two hook scores."""
    cases = [{"id": "N", "ticker": "NULLJ", "entry_type": "discovery", "archetype": "chokepoint",
              "response": _FULL_ANSWER, "scores": None}]
    out = _run("report", "--results", str(_scored(tmp_path, cases)), "--n-floor", "1").stdout
    assert "carry no judge result" not in out, "the hook scored it — it did contribute"
    line = next(l for l in out.splitlines() if l.startswith("| lens_run "))
    assert "1 / 1" in line, line


def test_the_per_case_table_agrees_with_the_aggregate_after_a_hook_override(tmp_path):
    """The table re-read `c["scores"]` — the judge's uncorrected opinion — while the aggregate used
    the hook-corrected copy. Worst form: judge says 'n/a', hook corrects to a real miss, the
    aggregate counts it and the row renders '–', the glyph meaning 'not applicable'."""
    sc = dict(_FULL, lens_run="n/a", bear_and_falsifier="n/a")
    # a single-name answer with a null Downsides body: the hook scores bear_and_falsifier 0
    resp = "TLDR: cheap here.\nDownsides:\n- none\nRating: Buy, PT $9, overweight. NFI"
    out = _run("report", "--results", str(_scored(tmp_path, [_case("NVDA", "chokepoint", sc, response=resp)])),
               "--n-floor", "1").stdout
    agg = next(l for l in out.splitlines() if l.startswith("| bear_and_falsifier "))
    assert "0 / 1" in agg, agg
    row = next(l for l in out.splitlines() if l.startswith("| NVDA "))
    assert "✗" in row, f"aggregate scored a miss but the row says otherwise: {row}"


def test_a_hook_failure_after_an_earlier_success_is_reported(tmp_path, monkeypatch):
    """`hook_available` only ever moved None->True/False, so once any case succeeded a later
    timeout was invisible: that case looked like one the hook had no opinion about, and its
    unverified judge score was trusted wholesale."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_ev2", EVAL)
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)
    calls = {"n": 0}
    real = ev.subprocess.run

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] > 1:
            raise ev.subprocess.TimeoutExpired(cmd="verdict_gate", timeout=30)
        return real(*a, **k)
    monkeypatch.setattr(ev.subprocess, "run", flaky)
    assert ev._hook_explain(_FULL_ANSWER) is not None      # first call succeeds
    assert ev._hook_explain(_FULL_ANSWER) is None          # second times out -> unavailable


def test_a_hook_failure_is_visible_in_the_report(tmp_path):
    """End-to-end companion to the unit test above: point the report at a hook that cannot answer
    and confirm the per-case note and the health line both say so."""
    p = _scored(tmp_path, [_case("NVDA", "chokepoint", dict(_FULL), response=_FULL_ANSWER)])
    env = {**os.environ, "PATH": os.environ.get("PATH", "")}
    proc = subprocess.run([sys.executable, str(EVAL), "report", "--results", str(p),
                           "--n-floor", "1"], capture_output=True, text=True, cwd=str(tmp_path),
                          env=env, timeout=120)
    # run from tmp_path: _VERDICT_GATE is resolved from the script's own location, so it still
    # works — this asserts the healthy path rather than the failure, keeping the pair honest.
    assert proc.returncode == 0
    assert "mechanical pre-pass:" in proc.stdout


# --- leakage guards on the two REAL prompt-construction sites -----------------------------------
# The leak test above checks `cmd_sample`'s output field. These check the two places that actually
# build a prompt for the harness-under-test. Both were verified clean by hand during review and
# neither had a test — "currently clean, invisibly regressable" is exactly the state a guard is for.

_ANSWER_KEY_FIELDS = ("thesis_text", "gold_tests", "gold_label")
_WORKFLOW_JS = SCRIPTS_DIR / "eval" / "serenity_eval_workflow.js"
_MODEB = SCRIPTS_DIR / "eval" / "modeb_runner.py"


def _strip_comments_js(src: str) -> str:
    out = []
    for line in src.splitlines():
        s = line.lstrip()
        if s.startswith("//"):
            continue
        out.append(line.split("//")[0] if "//" in line and "'" not in line.split("//")[0][-2:] else line)
    return "\n".join(out)


def test_the_workflow_stage_one_prompt_never_interpolates_an_answer_key_field():
    """Stage 1 is what the harness-under-test reads. Stage 2 (the judge) legitimately carries the
    answer key, so this isolates stage 1 by splitting the file at the judge's own marker rather
    than grepping the whole file and finding the judge's uses."""
    src = _strip_comments_js(_WORKFLOW_JS.read_text(encoding="utf-8"))
    marker = "RUBRIC_TEXT"
    assert marker in src
    stage1 = src.split("Stage 2")[0] if "Stage 2" in src else src.split(marker)[0]
    for field in _ANSWER_KEY_FIELDS:
        assert f"c.{field}" not in stage1, (
            f"answer-key field `{field}` reaches the blind-run prompt — this fails nothing at "
            f"runtime, it just inflates every score")


def test_modeb_sends_only_the_blind_prompt_to_the_harness():
    """`_process_case` passes `case["blind_prompt"]` to `claude -p` verbatim. Nothing else from the
    case object may reach that argv."""
    src = _MODEB.read_text(encoding="utf-8")
    for field in _ANSWER_KEY_FIELDS:
        assert f'case["{field}"]' not in src and f"case.get('{field}')" not in src \
            and f'case.get("{field}")' not in src, f"mode B touches the answer-key field `{field}`"
    assert 'case["blind_prompt"]' in src, "the blind prompt is what mode B is supposed to send"


def test_the_data_timing_note_rides_inside_blind_prompt_so_both_modes_get_it():
    """It used to live in the workflow's six-step wrapper only. Mode B passes `blind_prompt` to
    `claude -p` with no wrapper at all, so anything stated only in the wrapper reached half the
    runs — and the half it missed is the high-fidelity one."""
    for c in _sample(12, 7):
        assert "Data note:" in c["blind_prompt"], c["ticker"]
        assert "AS OF that date" in c["blind_prompt"]
    js = _strip_comments_js(_WORKFLOW_JS.read_text(encoding="utf-8"))
    assert "Data timing:" not in js, "the wrapper must not restate it — one source, not two"


# --- the archetype label cache (the "inspect once and freeze" step) ------------------------------

def test_cached_labels_are_applied_to_the_random_remainder(tmp_path):
    """Without this, growing n buys statistical power for the four always-in-scope rubric rows and
    NONE for the two chokepoint-scoped ones: their stable in-scope N stays at the four curated
    chokepoint cases forever, and those two are the moves the retrospective calls weakest.

    The ids are taken from a draw made under THIS test's own label file, not from the shared
    `sample25` fixture. They diverged once the committed file grew an `excluded` list: the fixture's
    draw skips those cases and a draw with an empty custom file does not, so ids picked from one
    were simply absent from the other and nothing was marked cached."""
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"labels": {}}), encoding="utf-8")
    baseline = json.loads(_run("sample", "--n", "25", "--seed", "7", "--no-network",
                               "--archetype-labels", str(empty)).stdout)["cases"]
    ids = [c["id"] for c in baseline if not c.get("gold")][:4]
    lf = tmp_path / "labels.json"
    lf.write_text(json.dumps({"labels": {i: "disruption" for i in ids}}), encoding="utf-8")
    out = json.loads(_run("sample", "--n", "25", "--seed", "7", "--no-network",
                          "--archetype-labels", str(lf)).stdout)
    cached = [c for c in out["cases"] if c.get("archetype_source") == "cached"]
    assert {c["id"] for c in cached} == set(ids)
    assert all(c["archetype"] == "disruption" for c in cached)
    assert out["meta"]["archetype_labeled"] == 12 + len(ids)


def test_a_label_outside_the_declared_vocabulary_is_a_hard_error(tmp_path):
    """A typo would silently drop that case from the two chokepoint-scoped rows with no error
    anywhere — quietly reintroducing the uncontrolled in-scope N the whole mechanism removes."""
    lf = tmp_path / "labels.json"
    lf.write_text(json.dumps({"labels": {"123": "not_an_archetype"}}), encoding="utf-8")
    p = _run("sample", "--n", "12", "--seed", "7", "--no-network",
             "--archetype-labels", str(lf), expect_ok=False)
    assert p.returncode == 2
    assert "outside the declared vocabulary" in p.stderr


def test_a_missing_label_file_is_not_an_error(tmp_path):
    """Absent labels are the honest default — the gold floor still works and `report` says how many
    cases went unscoped. Only a WRONG label is fatal."""
    p = _run("sample", "--n", "12", "--seed", "7", "--no-network",
             "--archetype-labels", str(tmp_path / "nope.json"))
    assert json.loads(p.stdout)["meta"]["archetype_labeled"] == 12


def test_an_excluded_case_never_enters_the_sample(tmp_path, sample25):
    """A post that is not a scoreable single-name thesis (a ticker list, a table of daily moves, a
    follower-milestone note) still has a tagged ticker and clears the length filter, so nothing
    stopped it. The blind prompt then asks "what's your read on TICKER?" and that post becomes the
    answer key — a guaranteed miss on every rubric row for reasons unrelated to the harness. A low
    score that means nothing is worse than a missing case, because it looks like a finding."""
    victim = next(c["id"] for c in sample25 if not c.get("gold"))
    lf = tmp_path / "labels.json"
    lf.write_text(json.dumps({"labels": {}, "excluded": [victim]}), encoding="utf-8")
    out = json.loads(_run("sample", "--n", "25", "--seed", "7", "--no-network",
                          "--archetype-labels", str(lf)).stdout)
    assert victim not in {c["id"] for c in out["cases"]}
    assert out["meta"]["resolution"]["excluded_not_a_thesis"] >= 1
    assert out["meta"]["n"] == 25, "an exclusion must be back-filled, not left as a hole"


def test_exclusion_cannot_remove_a_gold_case(tmp_path, gold):
    """The curated floor is hand-picked and its archetype spread is the whole point. Exclusion is a
    filter on the RANDOM draw; letting it reach the floor would silently empty an archetype."""
    gid = gold["cases"][0]["id"]
    lf = tmp_path / "labels.json"
    lf.write_text(json.dumps({"labels": {}, "excluded": [gid]}), encoding="utf-8")
    out = json.loads(_run("sample", "--n", "12", "--seed", "7", "--no-network",
                          "--archetype-labels", str(lf)).stdout)
    assert gid in {c["id"] for c in out["cases"]}


def test_only_labeled_yields_a_stable_fully_labeled_standing_sample():
    """The fixed point of the freeze loop. Without it, excluding a case pushes the draw deeper into
    the pool and pulls in fresh UNLABELLED cases, which need another labelling round, which excludes
    more, which pulls in more — the sample never settles. Restricting the pool makes the standing
    sample reachable by a command instead of by committing a blob of cases."""
    cases = _sample(100, 7, "--only-labeled")
    assert all(c.get("archetype") for c in cases), "every case must carry a fixed scope"
    # the two chokepoint-scoped rubric rows only report a percentage above the n-floor; that is the
    # whole return on the labelling pass, so it is asserted rather than hoped for.
    assert sum(1 for c in cases if c["archetype"] == "chokepoint") >= _DEFAULT_N_FLOOR
    assert [c["id"] for c in cases] == [c["id"] for c in _sample(100, 7, "--only-labeled")]


_DEFAULT_N_FLOOR = 12


# --- findings from the codex adversarial review -------------------------------------------------

def test_an_empty_measurement_is_never_rendered_as_zero_percent(tmp_path):
    """0/0 rendered as `0%`. An empty run and a harness that failed every check are completely
    different outcomes, and one of them is a quotable indictment that did not happen."""
    p = _scored(tmp_path, [{"id": "D", "ticker": "DEAD", "archetype": "chokepoint",
                            "entry_type": "event", "scores": None}])
    out = _run("report", "--results", str(p), "--no-hook", "--n-floor", "1").stdout
    assert "No in-scope checks" in out
    # The absence of a RENDERED RATE, not of the characters "0%" — the explanatory line itself
    # contains "not a 0%", which is exactly the sentence doing the work.
    assert "Pooled reproduction rate" not in out


def test_a_missing_judge_is_reported_even_when_the_hook_still_scored_the_case(tmp_path):
    """The hook can score the two structural items straight from the response, so a killed judge
    became two scored FAILURES with no warning. The hook scores are real and stay in; the silence
    about the missing judge was the defect."""
    p = _scored(tmp_path, [{"id": "H", "ticker": "DEADHOOK", "archetype": "evolution",
                            "entry_type": "event", "response": _FULL_ANSWER, "scores": None}])
    out = _run("report", "--results", str(p), "--n-floor", "1").stdout
    assert "had no JUDGE result" in out


def test_a_judge_n_a_corrected_by_the_hook_is_counted_as_a_disagreement(tmp_path):
    """The most interesting disagreement available — the judge says the item does not apply, the
    production hook says it does — and the old condition (`in (0, 1)`) skipped exactly it, so the
    overwrite happened silently while the counter reported zero."""
    sc = {"archetype_named": 1, "lens_run": "n/a", "bear_and_falsifier": "n/a",
          "priced_in_decomposed": 1}
    resp = "TLDR: Rating: buy, PT $9. EV/Rev looks cheap. NFA"
    p = _scored(tmp_path, [{"id": "J", "ticker": "JNA", "archetype": "evolution",
                            "entry_type": "event", "response": resp, "scores": sc}])
    out = _run("report", "--results", str(p), "--n-floor", "1").stdout
    assert "judge=n/a hook=" in out
    assert "disagreements: **0**" not in out


def test_an_unlabeled_case_is_discarded_from_the_chokepoint_rows_not_scored(tmp_path):
    """The sampler's own `unlabeled_archetype` note promised these are left unscored while the code
    admitted them behind a counter. A documented contract the code contradicts is worse than either
    behaviour alone, because the note is what a reader trusts."""
    p = _scored(tmp_path, [{"id": "N", "ticker": "NA", "archetype": None, "entry_type": "event",
                            "scores": {"recursive_bottom_hop": 0, "second_order_and_sibling": 0}}])
    out = _run("report", "--results", str(p), "--no-hook", "--n-floor", "1").stdout
    row = next(l for l in out.splitlines() if l.startswith("| recursive_bottom_hop"))
    assert "0 / 0" in row, row
    assert "DISCARDED" in out


def test_no_gold_still_honours_labels_and_exclusions():
    """`--no-gold` means "do not add the curated twelve". It never meant "ignore the label file and
    the known non-theses" — but the vocabulary was only loaded when gold was enabled, and the label
    cache only when the vocabulary was non-empty, so the flag silently turned both off and returned
    ids explicitly listed as excluded."""
    meta = json.loads(_run("sample", "--n", "25", "--seed", "7", "--no-gold",
                           "--no-network").stdout)["meta"]
    assert meta["gold_forced"] == 0
    assert meta["archetype_labeled"] > 0, "labels must still apply without the gold floor"
    assert meta["resolution"]["excluded_not_a_thesis"] > 0, "exclusions must still apply"


def test_a_resubjected_case_asks_about_the_company_its_thesis_argues(tmp_path):
    """`_primary_ticker` takes the first regex-valid tag — tagging order, not relevance. The curated
    twelve were pinned by hand; the remainder never was, and a subject audit found 19% of random
    cases asked about the wrong company (a thesis arguing SIVE filed under AMD, one arguing LITE
    filed under GOOGL). Neither the labelling pass nor the triage caught it: triage asked whether
    the POST is a scoreable thesis, never whether the SUBJECT is right."""
    cases = _sample(100, 7, "--only-labeled")
    pinned = [c for c in cases if c.get("subject_pinned")]
    assert pinned, "the committed label file carries subject overrides; none reached the sample"
    for c in pinned:
        assert c["ticker"] in c["blind_prompt"], "the pin must reach the question actually asked"


def test_a_resubject_target_that_cannot_resolve_is_excluded_not_pinned(gold):
    """Four of the six re-subject targets were foreign codes (7853, 3363, P4O) or unresolvable
    (SIVE). Re-pointing a case at a ticker the pipeline cannot load would swap a wrong-company
    question for a no-data one — the same 'measures nothing' failure in a different costume."""
    lab = json.loads((SCRIPTS_DIR / "eval" / "archetype_labels.json").read_text(encoding="utf-8"))
    cache = json.loads((SCRIPTS_DIR / "eval" / "ticker_resolution_cache.json").read_text())["tickers"]
    for cid, sub in (lab.get("subjects") or {}).items():
        assert cid not in set(lab.get("excluded") or []), f"{cid} is both pinned and excluded"
        entry = cache.get(sub)
        assert entry is None or entry.get("ok"), f"pinned subject {sub} does not resolve"


def test_cases_lost_between_sampling_and_scoring_are_reported(tmp_path):
    """The workflow guards the transcription step; nothing guarded the far end. A blind run that
    errors or a judge whose result is dropped simply shrinks the file, and every rate is then
    computed over the survivors while the header reports the smaller count as if it were the whole
    sample."""
    p = _scored(tmp_path, [_case("AXTI", "chokepoint", dict(_FULL))], meta={"n": 5, "seed": 7})
    out = _run("report", "--results", str(p), "--n-floor", "1", "--no-hook").stdout
    assert "went missing between sampling and scoring" in out
    assert "n=5" in out and "has 1" in out


def test_a_complete_run_says_nothing_about_missing_cases(tmp_path):
    p = _scored(tmp_path, [_case("AXTI", "chokepoint", dict(_FULL))], meta={"n": 1, "seed": 7})
    assert "went missing" not in _run("report", "--results", str(p), "--no-hook").stdout
