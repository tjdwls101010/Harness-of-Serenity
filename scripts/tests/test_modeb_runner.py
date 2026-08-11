"""Coverage for scripts/eval/modeb_runner.py — mode-B isolation (plan §4.6).

The file this tests exists to guarantee ONE thing above everything else: a mode-B blind-run must
never write into this repo's real `sessions/`. Exit criterion 4 says that guard has to be
MACHINE-CHECKED, and separately that a check nobody has seen fire is not a check — so this suite
does two things most test files here don't need to: it constructs a disposable sandbox git repo
per test (never the real one) to safely exercise `git worktree` end to end, and it deliberately
trips the guard on purpose (`--simulate-rogue-write`) to prove the failure path actually fires
rather than just reads well.

Every test that runs the real CLI uses --dry-run — it exercises the exact same code path as a real
run (worktree, symlinks, the interpreter smoke-test, the archive guard, teardown) minus the `claude
-p` call itself, so this suite proves the isolation without spending eval tokens or wall-clock.

Two independent trust boundaries, deliberately not merged:
  - `sandbox_repo` (a throwaway `git init`) is what most tests point `--repo-root` at, so a bug in
    the code under test cannot reach the real archive no matter what it does.
  - Where a test's whole point is a guarantee ABOUT the real repo (the --simulate-rogue-write
    interlock; the real-repo-default smoke test), it additionally snapshots the REAL project's
    `sessions/` before and after and asserts no diff, INSIDE the test — so a bug in the interlock
    itself fails the test loudly instead of silently writing into the real archive.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "eval" / "modeb_runner.py"
REAL_VENV = ROOT / "scripts" / ".venv"


def _load_module():
	"""Direct-import for the pure archive-guard helpers (_snapshot_sessions/_diff_sessions/_slug) —
	everything else here drives the CLI as a subprocess, matching test_serenity_lens.py's split."""
	spec = importlib.util.spec_from_file_location("modeb_runner_test", SCRIPT)
	assert spec is not None and spec.loader is not None
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


MOD = _load_module()

_NEEDS_REAL_VENV = pytest.mark.skipif(
	not REAL_VENV.is_dir(),
	reason="scripts/.venv is not installed — cannot smoke-test a real interpreter",
)


def _case(ticker: str, **kw) -> dict:
	c = {
		"id": f"id-{ticker}", "ticker": ticker, "date": "2025-01-01T00:00:00Z",
		"entry_type": "discovery", "blind_prompt": f"What's your read on {ticker}? (test fixture)",
	}
	c.update(kw)
	return c


def _run_cli(*args, env=None, timeout=120) -> subprocess.CompletedProcess:
	full_env = {**os.environ}
	if env:
		full_env.update(env)
	return subprocess.run([sys.executable, str(SCRIPT), *args], env=full_env,
	                       capture_output=True, text=True, timeout=timeout)


def _path_without_claude() -> str:
	"""The real PATH minus EVERY directory that would resolve `claude` — used to prove --dry-run
	does NOT require the claude binary, without nuking git/python along with it (a blunt PATH="" or
	a guessed minimal PATH would be both less portable and less precise about what's being tested).

	Drops any PATH entry containing a `claude` executable, not just `shutil.which`'s first hit —
	this machine has it installed twice (~/.local/bin AND /opt/homebrew/bin), and stripping only
	the first meant the real binary was still found and a live `claude -p` call actually ran during
	what was supposed to be a blocked-before-any-worktree-work test. Caught by the "no worktree
	was created" assertion in the test that uses this, not by a token bill — but the closer miss
	either way is exactly why that assertion exists."""
	kept = []
	for p in os.environ.get("PATH", "").split(os.pathsep):
		if p and not (os.path.isfile(os.path.join(p, "claude")) and os.access(os.path.join(p, "claude"), os.X_OK)):
			kept.append(p)
	return os.pathsep.join(kept)


@pytest.fixture
def sandbox_repo(tmp_path):
	"""A minimal, throwaway git repo — never the real one — that `--repo-root` can point at so
	`git worktree add` has something real to work against. scripts/.venv is a symlink CHAIN to the
	real project's already-installed venv (worktree/scripts/.venv -> sandbox/scripts/.venv ->
	real-repo/scripts/.venv) so the interpreter smoke-test this script performs is a genuine check
	against a real yfinance-capable Python, at zero extra disk cost — not a fake pass."""
	repo = tmp_path / "sandbox_repo"
	repo.mkdir()
	subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
	subprocess.run(["git", "config", "user.email", "modeb-test@example.com"], cwd=repo, check=True)
	subprocess.run(["git", "config", "user.name", "modeb-test"], cwd=repo, check=True)
	(repo / "sessions").mkdir()
	(repo / "sessions" / "INDEX.md").write_text("# index\n<!-- entries below -->\n", encoding="utf-8")
	(repo / "scripts").mkdir()
	# A real, TRACKED file, not a bare mkdir — git records trees, not empty directories, so an
	# empty scripts/ would vanish from `git worktree add`'s checkout entirely and _link_shared_deps
	# would fail creating scripts/.venv with ENOENT on the missing parent (hit while writing this
	# fixture). The real repo never has this problem: scripts/ holds dozens of tracked .py files.
	(repo / "scripts" / "placeholder.py").write_text("# keeps scripts/ tracked\n", encoding="utf-8")
	(repo / "README.md").write_text("sandbox repo for modeb_runner tests\n", encoding="utf-8")
	subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
	subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
	# Linked AFTER the commit, deliberately: the real repo's scripts/.venv is gitignored and
	# untracked, so a fresh `git worktree add` never checks it out. If this were linked BEFORE the
	# commit, it would become a TRACKED symlink and every per-case worktree would already have it
	# at checkout time — masking the exact collision _link_shared_deps must not hit in production
	# (it did, the first time this fixture was written: FileExistsError creating the case worktree's
	# own symlink on top of the one git had just checked out).
	if REAL_VENV.is_dir():
		os.symlink(REAL_VENV, repo / "scripts" / ".venv", target_is_directory=True)
	return repo


# --- pure archive-guard helpers -------------------------------------------------------------------

def test_diff_sessions_reports_added_modified_and_leaves_unchanged_alone():
	before = {
		"a.md": {"type": "file", "size": 1, "mtime_ns": 1, "sha256": "x"},
		"b.md": {"type": "file", "size": 2, "mtime_ns": 2, "sha256": "y"},
	}
	after = {
		"a.md": {"type": "file", "size": 1, "mtime_ns": 1, "sha256": "x"},        # unchanged
		"b.md": {"type": "file", "size": 3, "mtime_ns": 3, "sha256": "z"},        # modified
		"c.md": {"type": "file", "size": 4, "mtime_ns": 4, "sha256": "w"},        # added
	}
	violations = MOD._diff_sessions(before, after)
	assert any(v.startswith("MODIFIED b.md") for v in violations)
	assert any(v.startswith("ADDED c.md") for v in violations)
	assert not any(v.split()[1].startswith("a.md") for v in violations)


def test_diff_sessions_reports_removed():
	before = {"a.md": {"type": "file", "size": 1, "mtime_ns": 1, "sha256": "x"}}
	assert MOD._diff_sessions(before, {}) == ["REMOVED a.md"]


def test_diff_sessions_is_empty_for_two_identical_snapshots():
	snap = {"a.md": {"type": "file", "size": 1, "mtime_ns": 1, "sha256": "x"}}
	assert MOD._diff_sessions(snap, dict(snap)) == []


def test_snapshot_sessions_detects_a_real_content_change_on_disk(tmp_path):
	sroot = tmp_path / "sessions"
	sroot.mkdir()
	(sroot / "INDEX.md").write_text("hello\n", encoding="utf-8")
	before = MOD._snapshot_sessions(str(sroot))
	assert MOD._diff_sessions(before, MOD._snapshot_sessions(str(sroot))) == [], \
		"re-snapshotting an untouched tree must be a no-op diff"
	(sroot / "INDEX.md").write_text("hello world\n", encoding="utf-8")
	after = MOD._snapshot_sessions(str(sroot))
	violations = MOD._diff_sessions(before, after)
	assert len(violations) == 1 and violations[0].startswith("MODIFIED INDEX.md")


def test_snapshot_sessions_on_a_missing_root_is_empty_not_an_error(tmp_path):
	assert MOD._snapshot_sessions(str(tmp_path / "does-not-exist")) == {}


def test_slug_is_filesystem_safe_nonempty_and_bounded():
	assert re.fullmatch(r"[A-Za-z0-9_.-]+", MOD._slug("weird/ticker with spaces!"))
	assert MOD._slug("") == "case"
	assert MOD._slug(None) == "case"
	assert len(MOD._slug("x" * 100)) <= 40


# --- _ensure_linked: idempotent link/skip/replace, unit-level -------------------------------------

def test_ensure_linked_creates_a_fresh_symlink_when_nothing_is_there(tmp_path):
	src = tmp_path / "src.env"
	src.write_text("FRED_API_KEY=x\n", encoding="utf-8")
	dst = tmp_path / "dst.env"
	MOD._ensure_linked(str(dst), str(src), is_dir=False)
	assert dst.is_symlink()
	assert dst.read_text(encoding="utf-8") == "FRED_API_KEY=x\n"


def test_ensure_linked_leaves_an_already_working_target_alone(tmp_path):
	"""The exact scenario a repo that tracks scripts/.venv produces: `git worktree add` checks out
	a REAL directory (not a symlink) at dst before this function ever runs."""
	src = tmp_path / "src_venv"
	(src / "bin").mkdir(parents=True)
	(src / "bin" / "python").write_text("#!/bin/sh\necho fake\n", encoding="utf-8")
	dst = tmp_path / "dst_venv"
	shutil.copytree(src, dst)
	MOD._ensure_linked(str(dst), str(src), is_dir=True)
	assert not dst.is_symlink(), "an already-usable target must be left exactly as it was found"
	assert (dst / "bin" / "python").read_text(encoding="utf-8") == "#!/bin/sh\necho fake\n"


def test_ensure_linked_replaces_a_broken_dangling_symlink(tmp_path):
	src = tmp_path / "src_venv"
	(src / "bin").mkdir(parents=True)
	(src / "bin" / "python").write_text("#!/bin/sh\necho fake\n", encoding="utf-8")
	dst = tmp_path / "dst_venv"
	os.symlink(tmp_path / "nowhere", dst, target_is_directory=True)  # dangling: points nowhere
	assert not os.path.exists(dst)  # sanity: a dangling symlink reports False for exists()

	MOD._ensure_linked(str(dst), str(src), is_dir=True)
	assert dst.is_symlink()
	assert os.path.realpath(str(dst)) == os.path.realpath(str(src))
	assert (dst / "bin" / "python").exists()


@pytest.fixture
def sandbox_repo_with_tracked_venv(tmp_path):
	"""The scenario `sandbox_repo` deliberately avoids (see its docstring), built on purpose here:
	a repo that does NOT gitignore scripts/.venv, so `git worktree add` checks out a real, working
	symlink at that path before `_link_shared_deps` ever runs. Proves `_ensure_linked` is idempotent
	rather than relying on every caller's repo to keep .venv untracked the way this one does — a
	real robustness gap a hand-built repro outside this fixture caught (FileExistsError creating a
	symlink on top of one git had already checked out)."""
	if not REAL_VENV.is_dir():
		pytest.skip("scripts/.venv is not installed — cannot smoke-test a real interpreter")
	repo = tmp_path / "sandbox_repo_tracked_venv"
	repo.mkdir()
	subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
	subprocess.run(["git", "config", "user.email", "modeb-test@example.com"], cwd=repo, check=True)
	subprocess.run(["git", "config", "user.name", "modeb-test"], cwd=repo, check=True)
	(repo / "sessions").mkdir()
	(repo / "sessions" / "INDEX.md").write_text("# index\n<!-- entries below -->\n", encoding="utf-8")
	(repo / "scripts").mkdir()
	os.symlink(REAL_VENV, repo / "scripts" / ".venv", target_is_directory=True)  # linked BEFORE commit
	subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
	subprocess.run(["git", "commit", "-q", "-m", "init, venv tracked on purpose"], cwd=repo, check=True)
	return repo


def test_a_tracked_already_checked_out_venv_is_left_alone_not_collided_with(sandbox_repo_with_tracked_venv):
	sandbox = sandbox_repo_with_tracked_venv
	cases_path = sandbox / "cases.json"
	cases_path.write_text(json.dumps({"cases": [_case("NVDA")]}), encoding="utf-8")
	out_path = sandbox / "answers.json"

	proc = _run_cli("--cases", str(cases_path), "--out", str(out_path), "--dry-run",
	                 "--repo-root", str(sandbox))
	assert proc.returncode == 0, f"stderr: {proc.stderr}"
	out = json.loads(out_path.read_text(encoding="utf-8"))
	case0 = out["cases"][0]
	assert case0.get("error") is None, "a tracked venv must be reused, not collided with"
	assert case0["interpreter_smoke_test"] == "ok"


# --- CLI: clean dry-run against a sandbox ---------------------------------------------------------

@_NEEDS_REAL_VENV
def test_dry_run_clean_sandbox_reports_ok_and_leaves_no_trace(sandbox_repo):
	cases_path = sandbox_repo / "cases.json"
	cases_path.write_text(json.dumps({"cases": [_case("NVDA")]}), encoding="utf-8")
	out_path = sandbox_repo / "answers.json"
	before = MOD._snapshot_sessions(str(sandbox_repo / "sessions"))

	proc = _run_cli("--cases", str(cases_path), "--out", str(out_path), "--dry-run",
	                 "--repo-root", str(sandbox_repo))
	assert proc.returncode == 0, f"stderr: {proc.stderr}"

	out = json.loads(out_path.read_text(encoding="utf-8"))
	assert out["archive_guard"] == {
		"ok": True, "sessions_root": str(sandbox_repo / "sessions"), "violations": [],
	}
	case0 = out["cases"][0]
	assert case0["dry_run"] is True
	assert case0["interpreter_smoke_test"] == "ok"
	assert case0.get("error") is None
	assert out["meta"]["n_errors"] == 0
	assert out["meta"]["dry_run"] is True
	assert out["meta"]["resolved_models"] == []  # no claude -p call was made

	after = MOD._snapshot_sessions(str(sandbox_repo / "sessions"))
	assert MOD._diff_sessions(before, after) == []

	# Default (no --keep): the worktree and its now-empty run directory must both be gone.
	run_id = out["meta"]["run_id"]
	assert not (sandbox_repo / ".tmp" / "modeb_runs" / run_id).exists()
	wt_list = subprocess.run(["git", "-C", str(sandbox_repo), "worktree", "list"],
	                          capture_output=True, text=True, check=True).stdout
	assert wt_list.count("\n") == 1, f"a worktree was left registered:\n{wt_list}"


@_NEEDS_REAL_VENV
def test_keep_retains_the_worktree_with_a_working_symlink(sandbox_repo):
	cases_path = sandbox_repo / "cases.json"
	cases_path.write_text(json.dumps({"cases": [_case("NVDA")]}), encoding="utf-8")
	out_path = sandbox_repo / "answers.json"

	proc = _run_cli("--cases", str(cases_path), "--out", str(out_path), "--dry-run", "--keep",
	                 "--repo-root", str(sandbox_repo))
	assert proc.returncode == 0, f"stderr: {proc.stderr}"
	out = json.loads(out_path.read_text(encoding="utf-8"))
	wt = Path(out["cases"][0]["worktree"])
	try:
		assert wt.is_dir()
		venv_link = wt / "scripts" / ".venv"
		assert venv_link.is_symlink()
		assert (venv_link / "bin" / "python").exists()
	finally:
		subprocess.run(["git", "-C", str(sandbox_repo), "worktree", "remove", "--force", str(wt)],
		                check=True)


def test_a_case_without_blind_prompt_errors_before_any_worktree_is_created(sandbox_repo):
	cases_path = sandbox_repo / "cases.json"
	cases_path.write_text(json.dumps({"cases": [{"id": "bad", "ticker": "ZZZ"}]}), encoding="utf-8")
	out_path = sandbox_repo / "answers.json"

	proc = _run_cli("--cases", str(cases_path), "--out", str(out_path), "--dry-run",
	                 "--repo-root", str(sandbox_repo))
	assert proc.returncode == 3  # cases errored, but the archive guard itself stayed clean
	out = json.loads(out_path.read_text(encoding="utf-8"))
	assert out["cases"][0]["error"] == \
		"case has no blind_prompt — skipped before any worktree was created"
	assert out["meta"]["n_errors"] == 1
	assert out["archive_guard"]["ok"] is True
	wt_list = subprocess.run(["git", "-C", str(sandbox_repo), "worktree", "list"],
	                          capture_output=True, text=True, check=True).stdout
	assert wt_list.count("\n") == 1, "no worktree should have been created for the bad case"


@_NEEDS_REAL_VENV
def test_limit_caps_the_number_of_cases_processed(sandbox_repo):
	cases_path = sandbox_repo / "cases.json"
	cases_path.write_text(json.dumps({"cases": [_case("A"), _case("B"), _case("C")]}), encoding="utf-8")
	out_path = sandbox_repo / "answers.json"

	proc = _run_cli("--cases", str(cases_path), "--out", str(out_path), "--dry-run", "--limit", "2",
	                 "--repo-root", str(sandbox_repo))
	assert proc.returncode == 0, f"stderr: {proc.stderr}"
	out = json.loads(out_path.read_text(encoding="utf-8"))
	assert out["meta"]["n_cases"] == 2
	assert [c["ticker"] for c in out["cases"]] == ["A", "B"]


def test_a_bad_repo_root_is_rejected_before_touching_anything(tmp_path):
	not_a_repo = tmp_path / "not_a_repo"
	not_a_repo.mkdir()
	cases_path = tmp_path / "cases.json"
	cases_path.write_text(json.dumps({"cases": [_case("X")]}), encoding="utf-8")
	out_path = tmp_path / "out.json"

	proc = _run_cli("--cases", str(cases_path), "--out", str(out_path), "--dry-run",
	                 "--repo-root", str(not_a_repo))
	assert proc.returncode == 2
	assert "does not look like a git repo" in proc.stderr
	assert not out_path.exists()


def test_missing_claude_binary_blocks_a_real_run_before_any_worktree_work(sandbox_repo):
	cases_path = sandbox_repo / "cases.json"
	cases_path.write_text(json.dumps({"cases": [_case("NVDA")]}), encoding="utf-8")
	out_path = sandbox_repo / "out.json"

	proc = _run_cli("--cases", str(cases_path), "--out", str(out_path),
	                 "--repo-root", str(sandbox_repo), env={"PATH": _path_without_claude()})
	assert proc.returncode == 2
	assert "claude" in proc.stderr.lower()
	assert not out_path.exists()
	wt_list = subprocess.run(["git", "-C", str(sandbox_repo), "worktree", "list"],
	                          capture_output=True, text=True, check=True).stdout
	assert wt_list.count("\n") == 1, "must exit before any worktree is created"


@_NEEDS_REAL_VENV
def test_dry_run_does_not_require_the_claude_binary_on_path(sandbox_repo):
	cases_path = sandbox_repo / "cases.json"
	cases_path.write_text(json.dumps({"cases": [_case("NVDA")]}), encoding="utf-8")
	out_path = sandbox_repo / "out.json"

	proc = _run_cli("--cases", str(cases_path), "--out", str(out_path), "--dry-run",
	                 "--repo-root", str(sandbox_repo), env={"PATH": _path_without_claude()})
	assert proc.returncode == 0, f"stderr: {proc.stderr}"


# --- the archive guard actually firing -------------------------------------------------------------

def test_simulate_rogue_write_refuses_without_an_explicit_repo_root(tmp_path):
	"""The interlock, proven against the REAL repo. If it were broken, this test would not just
	assert-fail — it would leave a canary file in this project's real sessions/, which is exactly
	why the diff-against-the-real-tree check below is inside the test, not trusted to the interlock
	alone."""
	cases_path = tmp_path / "cases.json"
	cases_path.write_text(json.dumps({"cases": [_case("NVDA")]}), encoding="utf-8")
	real_sessions = str(ROOT / "sessions")
	before = MOD._snapshot_sessions(real_sessions)

	proc = _run_cli("--cases", str(cases_path), "--out", str(tmp_path / "out.json"),
	                 "--dry-run", "--simulate-rogue-write")

	after = MOD._snapshot_sessions(real_sessions)
	assert proc.returncode == 2, f"stderr: {proc.stderr}"
	assert "--repo-root" in proc.stderr
	assert not (tmp_path / "out.json").exists()
	assert MOD._diff_sessions(before, after) == [], (
		"the interlock must refuse BEFORE touching anything — the real project's sessions/ changed!"
	)


@_NEEDS_REAL_VENV
def test_simulate_rogue_write_with_explicit_repo_root_trips_the_guard(sandbox_repo):
	"""The guard's failure path, exercised for real: inject a canary write into the SANDBOX's
	sessions/ (never the real one — --repo-root points this whole run at sandbox_repo) and confirm
	modeb_runner both detects it and fails loudly, naming the exact path."""
	cases_path = sandbox_repo / "cases.json"
	cases_path.write_text(json.dumps({"cases": [_case("NVDA")]}), encoding="utf-8")
	out_path = sandbox_repo / "answers.json"

	proc = _run_cli("--cases", str(cases_path), "--out", str(out_path), "--dry-run",
	                 "--repo-root", str(sandbox_repo), "--simulate-rogue-write")

	assert proc.returncode == 1, f"stderr: {proc.stderr}"
	assert "ARCHIVE GUARD TRIPPED" in proc.stderr
	assert "990199.simulated-rogue-write" in proc.stderr

	out = json.loads(out_path.read_text(encoding="utf-8"))
	assert out["archive_guard"]["ok"] is False
	joined = " ".join(out["archive_guard"]["violations"])
	assert "990199.simulated-rogue-write" in joined and "ROGUE.md" in joined

	# The injection genuinely happened — this isn't the guard flagging its own absence.
	assert (sandbox_repo / "sessions" / "990199.simulated-rogue-write" / "ROGUE.md").is_file()


# --- against the real repo's default --repo-root (no override) ------------------------------------

@_NEEDS_REAL_VENV
def test_dry_run_against_the_real_repo_default_leaves_it_untouched(tmp_path):
	"""No --repo-root: exercises the actual default path a real invocation would use (this repo,
	its actual 409MB scripts/.venv) — closest automated equivalent of the manual verify command."""
	cases_path = tmp_path / "cases.json"
	cases_path.write_text(json.dumps({"cases": [_case("NVDA")]}), encoding="utf-8")
	out_path = tmp_path / "answers.json"
	real_sessions = str(ROOT / "sessions")
	before = MOD._snapshot_sessions(real_sessions)

	proc = _run_cli("--cases", str(cases_path), "--out", str(out_path), "--dry-run")

	after = MOD._snapshot_sessions(real_sessions)
	assert proc.returncode == 0, f"stderr: {proc.stderr}"
	assert MOD._diff_sessions(before, after) == []

	out = json.loads(out_path.read_text(encoding="utf-8"))
	assert out["meta"]["repo_root"] == str(ROOT)
	assert out["archive_guard"]["ok"] is True
	assert out["cases"][0]["interpreter_smoke_test"] == "ok"
	assert out["cases"][0].get("error") is None
