"""Coverage for `serenity_harness.py`'s CLI surface — `rankdiff`, tier canonicalization, `new-session`.

This file exists because a review found the surface had NONE. `lint_scorecard` gets indirect exercise
through the `scorecard_guard` hook fixtures, but `_canonical_tier`'s agreement-percentage math and
`cmd_new_session`'s slug validation and collision suffix were exercised by nothing at all — so by this
repository's own standard ("every fix needs a check that reddens when the fix is reverted"), that code
had no check to revert against and a regression would have shipped silently.

`rankdiff`'s agreement percentage is the archive's one free reproducibility measurement. A tier
canonicalizer that maps two genuinely different tiers onto one would INFLATE it — the opposite of the
formatting-noise deflation it was built to remove, and worse, because a deflated number looks like
drift while an inflated one looks like agreement.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS_DIR.parent
HARNESS = SCRIPTS_DIR / "serenity_harness.py"


def _run(*args, cwd=None):
    """Invoke the CLI with CLAUDE_PROJECT_DIR pointed at the test's tmp dir.

    `new-session` writes to the project's `sessions/`, so without this every run would create real
    folders in the live archive — which is how these tests were first written, and it did exactly
    that until the fifth polluted folder made the point."""
    env = {**os.environ}
    if cwd is not None:
        env["CLAUDE_PROJECT_DIR"] = str(cwd)
    return subprocess.run([sys.executable, str(HARNESS), *args], env=env,
                          capture_output=True, text=True, cwd=str(cwd or ROOT), timeout=120)


def _ranking(path, rows, tier_cut="Tier 2"):
    body = ["| ticker | tier | rung | gates | why |", "| --- | --- | --- | --- | --- |"]
    body += [f"| {t} | {tier} | 4 | pass | — |" for t, tier in rows]
    body.append("")
    body.append(f"Tier cut: {tier_cut}")
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    return path


# --- tier canonicalization ----------------------------------------------------------------------

@pytest.mark.parametrize("a,b", [
    ("1", "Tier 1"),            # the bug that prompted this: a bare rung vs. the word form
    ("1", "1 (core)"),          # a parenthetical qualifier
    ("1", "**1**"),             # markdown emphasis
    ("EXIT", "exit"),           # case
    ("EXCLUDED", "Excluded"),
])
def test_formatting_variants_of_one_tier_are_treated_as_agreement(tmp_path, a, b):
    """Two spellings of the SAME tier must not read as a change.

    This is the deflation `_canonical_tier` exists to remove: plain string equality scored `Tier 1`
    against `1` as a changed tier, which quietly lowered the one number this command produces."""
    x = _ranking(tmp_path / "a.md", [("NVDA", a)])
    y = _ranking(tmp_path / "b.md", [("NVDA", b)])
    out = json.loads(_run("rankdiff", str(x), str(y)).stdout)
    assert out["agreement_pct"] == 100.0, f"{a!r} vs {b!r} read as a tier change"
    assert out["changed"] == []


@pytest.mark.parametrize("a,b", [
    ("1", "2"), ("2", "3"), ("1", "EXIT"), ("EXIT", "EXCLUDED"), ("3", "UNRESOLVED"),
])
def test_genuinely_different_tiers_never_collapse_into_agreement(tmp_path, a, b):
    """The inverse failure, and the more dangerous one.

    A canonicalizer that over-normalizes would map two real tiers onto one and INFLATE agreement —
    reporting reproducibility that did not happen. Deflation looks like drift and gets investigated;
    inflation looks like success and does not."""
    x = _ranking(tmp_path / "a.md", [("NVDA", a)])
    y = _ranking(tmp_path / "b.md", [("NVDA", b)])
    out = json.loads(_run("rankdiff", str(x), str(y)).stdout)
    assert out["agreement_pct"] == 0.0, f"{a!r} and {b!r} collapsed into agreement"
    assert len(out["changed"]) == 1


def test_a_tier_outside_the_vocabulary_is_reported_and_excluded_not_diffed(tmp_path):
    """Reported, never rejected. Refusing the whole diff over a few rows would destroy the agreement
    percentage for every OTHER row — and the archive legitimately holds rankings written before the
    vocabulary was enforced (the real `_ranking.md` carries `EXIT/TRIM`)."""
    x = _ranking(tmp_path / "a.md", [("NVDA", "1"), ("AMKR", "EXIT/TRIM")])
    y = _ranking(tmp_path / "b.md", [("NVDA", "1"), ("AMKR", "EXIT/TRIM")])
    out = json.loads(_run("rankdiff", str(x), str(y)).stdout)
    assert out["agreement_pct"] == 100.0          # the good row still measures
    assert out["excluded_from_agreement"] == 2    # one per file
    assert [r["tier"] for r in out["unknown_tiers_a"]] == ["EXIT/TRIM"]


def test_rankdiff_reports_a_missing_file_as_json_not_a_traceback(tmp_path):
    p = _run("rankdiff", str(tmp_path / "nope.md"), str(tmp_path / "nope2.md"))
    payload = json.loads(p.stdout)      # raises if a traceback leaked to stdout
    assert payload["error"] == "file_not_found"
    assert "quote the path" in payload["detail"]   # real session paths contain spaces


# --- new-session --------------------------------------------------------------------------------

@pytest.mark.parametrize("slug", [
    "반도체 딥리서치",           # the exact failure: the only real session folder ever produced
    "AI Supply Chain",          # spaces + capitals
    "ai_supply_chain",          # underscores
    "trailing-hyphen-",
    "double--hyphen",
])
def test_a_bad_slug_is_rejected_at_the_argument_boundary(tmp_path, slug):
    """Rejected BEFORE mkdir, not discovered after.

    `verdict_gate`'s `Saved:`-mark regex cannot match a space or non-ASCII after the dot, so a folder
    named this way is unreachable by its own archive check — the repo's one real session folder is
    exactly this and gets nagged to re-archive. A failure detectable only after the fact is one that
    keeps getting committed."""
    p = _run("new-session", "--slug", slug, cwd=tmp_path)
    assert p.returncode == 2
    payload = json.loads(p.stdout)
    assert payload["error"] == "invalid_slug"
    assert not (tmp_path / "sessions").exists() or not list((tmp_path / "sessions").glob("*")), \
        "a rejected slug must not leave a folder behind — the point is rejection BEFORE mkdir"


def test_a_good_slug_creates_the_folder_and_prints_both_paste_ready_lines(tmp_path):
    (tmp_path / "sessions").mkdir()
    p = _run("new-session", "--slug", "semiconductor-deep-research",
             "--type", "ranking", "--tickers", "mu,tsem", cwd=tmp_path)
    assert p.returncode == 0
    out = json.loads(p.stdout)
    assert out["folder"].startswith("sessions/") and out["folder"].endswith(".semiconductor-deep-research/")
    assert out["saved_line"] == f"Saved: {out['folder']}"
    assert "MU TSEM" in out["index_line"]          # uppercased, space-separated
    assert "ranking" in out["index_line"]
    assert (tmp_path / out["folder"]).is_dir()


def test_the_generated_saved_line_satisfies_the_stop_hooks_own_regex(tmp_path):
    """The generator's whole purpose. The hand-made folder in the archive does NOT match this regex;
    anything this command emits must."""
    import re
    (tmp_path / "sessions").mkdir()
    out = json.loads(_run("new-session", "--slug", "a-valid-slug", cwd=tmp_path).stdout)
    rx = re.compile(r"Saved:\s*`?(sessions/\d{6}\.[a-z0-9-]+(?:-\d+)?/?)", re.IGNORECASE)
    assert rx.search(out["saved_line"]), f"{out['saved_line']!r} would be nagged by verdict_gate"


def test_a_name_collision_suffixes_rather_than_writing_into_an_existing_folder(tmp_path):
    """Doctrine: never write into a session folder this session did not create. Silently merging two
    analyses under one date loses one of them."""
    (tmp_path / "sessions").mkdir()
    first = json.loads(_run("new-session", "--slug", "same-topic", cwd=tmp_path).stdout)
    second = json.loads(_run("new-session", "--slug", "same-topic", cwd=tmp_path).stdout)
    assert first["folder"] != second["folder"]
    assert second["folder"].rstrip("/").endswith("-2")
    third = json.loads(_run("new-session", "--slug", "same-topic", cwd=tmp_path).stdout)
    assert third["folder"].rstrip("/").endswith("-3")


# --- scorecard-lint -----------------------------------------------------------------------------

def test_scorecard_lint_names_each_violation_and_exits_nonzero(tmp_path):
    d = tmp_path / "sessions" / "990105.lint-check"
    d.mkdir(parents=True)
    bad = d / "NVDA.md"
    bad.write_text("---\nticker: NVDA\narchetype: Bottleneck\nstage: 3→4\ntier: 1\n"
                   "conviction: medium-high\n---\n## Body\n", encoding="utf-8")
    p = _run("scorecard-lint", str(bad))
    assert p.returncode == 1
    report = json.loads(p.stdout)["reports"][0]
    assert report["conforms"] is False
    joined = " ".join(report["violations"])
    assert "`tier:` is forbidden" in joined
    assert "archetype: Bottleneck" in joined      # enum is lowercase `chokepoint`
    assert "stage: 3→4" in joined                 # must be an int rung 1-5
    assert "missing required field `mc:`" in joined


def test_a_scorecard_predating_the_boundary_date_is_grandfathered(tmp_path):
    """Non-conforming and reported, but not a failure. `date`/`data_as_of`/`mc` cannot be recovered
    without re-running the pipeline, and back-filling them would produce a file that LOOKS current
    while carrying expired numbers — which the spine's numbers-expire rule exists to prevent."""
    d = tmp_path / "sessions" / "260101.legacy-cohort"
    d.mkdir(parents=True)
    old = d / "NVDA.md"
    old.write_text("---\nticker: NVDA\ntier: 1\n---\n## Body\n", encoding="utf-8")
    p = _run("scorecard-lint", str(old))
    assert p.returncode == 0, "a grandfathered file must not fail the command"
    report = json.loads(p.stdout)["reports"][0]
    assert report["grandfathered"] is True
    assert report["conforms"] is False            # still honestly reported as non-conforming
