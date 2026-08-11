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
    meta = json.loads(_run("sample", "--n", "25", "--seed", "7", "--no-network").stdout)["meta"]
    assert meta["resolution"]["rejected"], "rejections must be reported, not silently absorbed"
    assert {r["ticker"] for r in meta["resolution"]["rejected"]} >= {"SIVE", "XFAB"}
    assert all(r.get("reason") for r in meta["resolution"]["rejected"])


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
    run a driver line on). Collapsing that to 0 manufactures a miss out of a correct answer."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_ev", EVAL)
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)
    assert ev._mechanical_scores({"checks": {"lens_line": None, "downsides": None,
                                             "falsifier": None}}) == {}
    assert ev._mechanical_scores({"checks": {"lens_line": False}}) == {"lens_run": 0}
    assert ev._mechanical_scores({"checks": {"downsides": True, "falsifier": False}}) \
        == {"bear_and_falsifier": 0}


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
    assert "1/3 case(s) carry no judge result" in out
    assert "computed over the remaining 2" in out
    # and the rates really are over 2, not 3
    row = next(l for l in out.splitlines() if l.startswith("| archetype_named"))
    assert "2 / 2" in row, row


def test_a_fully_scored_run_says_nothing_about_missing_judges(tmp_path):
    """The warning has to be absent when it does not apply, or it becomes wallpaper."""
    p = _scored(tmp_path, [_case("AXTI", "chokepoint", dict(_FULL))])
    assert "carry no judge result" not in _run("report", "--results", str(p), "--no-hook").stdout
