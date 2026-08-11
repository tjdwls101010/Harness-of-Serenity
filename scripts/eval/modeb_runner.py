#!/usr/bin/env python3
"""modeb_runner.py — blind-runs eval cases as REAL top-level `claude -p` sessions, isolated from
the live session archive (design-review plan §4.6).

Mode B exists to measure the harness WITH hooks firing (SessionStart/UserPromptSubmit/PostToolUse/
Stop) — the fidelity a workflow `agent()` subagent (mode A) cannot give, since a subagent never
fires them. The cost of that fidelity: each case is a REAL top-level session, and CLAUDE.md's
archive rule + verdict_gate's `Saved:` nudge push every one of them toward writing into the real
`sessions/` and appending to the real `INDEX.md`. Run cases in parallel (the natural move once
mode A's speed is off the table) and two processes interleave on the same index.

	modeb_runner.py --cases cases.json --out answers.json [--model ID] [--limit N] [--dry-run] [--keep]

WORKTREE STRATEGY — one throwaway `git worktree` PER CASE, torn down after (unless --keep), never
one worktree reused across cases. Two reasons, in priority order:

  1. Case independence. This is a MEASUREMENT instrument — case N's blind run must not be able to
     see case N-1's leftover archive state (a stray sessions/ folder from the prior case changes
     what a Read/Glob over sessions/ turns up, and what the archive-nudge hook sees as "already
     non-empty"). A single reused worktree accumulates exactly that contamination across a run.
     Per-case isolation removes the question rather than hoping no case's answer depends on it.
  2. It is what makes parallelism SAFE rather than merely fast. Every case gets a distinct
     directory and its own private sessions/ tree, so nothing shared exists for two cases to race
     on. This script itself still runs cases sequentially (see below) — but because isolation is
     per-case, running N *instances* of this script over disjoint case slices is safe with zero
     additional locking. Wall-clock parallelism is achieved that way, not with an internal thread
     pool: adding one here would buy speed this script doesn't need to own, at the cost of
     interleaved progress output and one more thing to get right around git's own worktree
     locking. Add it later if a real N=25 run needs it; nothing here forecloses that.

TWO PLAN DEFECTS, BOTH WORKED AROUND BELOW (see `_link_shared_deps`):

  - scripts/.venv is gitignored with ZERO tracked files (`git ls-files scripts/.venv` → empty), so
    a bare `git worktree add` produces a tree with no Python interpreter at all — every pipeline
    call inside it would fail outright. FLAGGED IN THE BRIEF, confirmed here, fixed by symlinking
    the venv directory into the worktree rather than copying it (477MB/case copied, 409MB of that
    the venv, vs. near-zero for a symlink).
  - .env is ALSO gitignored and untracked, and holds FRED_API_KEY. This one was NOT flagged going
    in. It does not crash the pipeline — scripts/pipeline/_runner.py's `_run_script` catches a
    child script's failure into a per-gauge `{"error": ...}`, so a worktree with no .env would
    silently degrade every macro-touching case (the fear_dip/event branches, and any discovery
    case that loads serenity-macro first per CLAUDE.md's routing) rather than fail loudly. That is
    the EXACT "part of what the instrument measures is nothing" failure §4.1 opens with — just
    reintroduced by the isolation meant to fix a different instance of it. Symlinked for the same
    reason as the venv (read-only, never written to by a run). EDGAR_IDENTITY, the other credential
    read from .env, already falls back to a hardcoded default in serenity_filings.py, so it was
    never silent — FRED_API_KEY specifically is what made this worth fixing.

PERMISSIONS — every claude -p call is run with --permission-mode bypassPermissions. A non-
interactive `-p` session cannot answer a permission prompt; without this, a case whose blind run
needs a Bash or Write call (i.e. nearly every real case) would hang until the timeout, which is
the same "measures nothing" failure again, just as a hang instead of empty data. This is judged
safe specifically BECAUSE each case runs in a disposable, isolated worktree — bypassing permissions
in the live project directory would be a materially different call. Verified end-to-end manually
(a throwaway worktree, a prompt that forces a Bash tool call, CLAUDE_PROJECT_DIR pointed at the
worktree): the tool call ran without a permission prompt, hooks fired, stdout stayed clean JSON.

ARCHIVE GUARD — exit criterion 4 ("a mode-B run touches no file under the real sessions/") is
MACHINE-CHECKED here, not assumed: `_snapshot_sessions` hashes every path under <repo-root>/sessions/
before any worktree work and again after, and `_diff_sessions` reports every ADDED/REMOVED/MODIFIED
path by name. Any violation fails the run loudly (stderr + nonzero exit + an `archive_guard` block
in --out, so it is visible even to a caller that only inspects the JSON). "A guard nobody has seen
fire is not a guard" — so the failure path is exercised for real, not just written: --repo-root
lets the test suite redirect BOTH the worktree source and the guarded sessions/ tree at a disposable
sandbox repo, and --simulate-rogue-write (gated on --repo-root being given explicitly, so it can
never fire against the real archive by accident) injects a canary write into that sandbox's
sessions/ mid-run so a test can assert the guard actually catches it. scripts/tests/test_modeb_runner.py
exercises both the clean path and the tripped path through the real CLI, not a mocked stand-in.

--dry-run runs this exact code path minus the `claude -p` call itself: real worktree, real symlinks,
a real `<worktree>/scripts/.venv/bin/python -c "import yfinance"` smoke test (proving the symlink
resolves to a WORKING interpreter, not just that the link exists), the real archive guard, real
teardown. That is how the isolation gets verified without spending eval tokens.

Exit codes: 0 clean; 1 the archive guard tripped (treated as the most severe outcome regardless of
per-case results); 2 a usage/setup error (bad args, missing `claude` on PATH, the rogue-write
interlock refusing); 3 one or more cases errored but the archive guard stayed clean.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_REPO_ROOT = os.path.dirname(os.path.dirname(_HERE))  # scripts/eval -> scripts -> repo root

# Reference cost (plan §4.8): 2-6 min/case measured live. 900s leaves headroom for a slower case
# (a deep chokepoint chain needing more tool calls) without letting one hung case stall a batch
# forever.
_CASE_TIMEOUT_SECONDS = 900
_SMOKE_TIMEOUT_SECONDS = 60
_MAX_SESSION_FILE_BYTES = 500_000  # per captured sessions/ file; generous for a markdown scorecard


# ---------------------------------------------------------------------------------------------
# Archive guard — pure, independently-testable functions. Exit criterion 4, machine-checked.
# ---------------------------------------------------------------------------------------------

def _snapshot_sessions(sessions_root: str) -> dict:
	"""relpath -> a description of that path under sessions_root. Files carry size/mtime_ns/sha256
	(any one changing is a real change); dirs are recorded too, so an added *empty* directory is
	still caught. A missing root snapshots as {} — sessions/ not existing is not this guard's job
	to flag."""
	snap: dict = {}
	if not os.path.isdir(sessions_root):
		return snap
	for dirpath, _dirnames, filenames in os.walk(sessions_root):
		rel_dir = os.path.relpath(dirpath, sessions_root)
		if rel_dir != ".":
			snap[rel_dir] = {"type": "dir"}
		for fn in filenames:
			full = os.path.join(dirpath, fn)
			rel = fn if rel_dir == "." else os.path.join(rel_dir, fn)
			try:
				st = os.stat(full)
				h = hashlib.sha256()
				with open(full, "rb") as fh:
					for chunk in iter(lambda: fh.read(1 << 16), b""):
						h.update(chunk)
				snap[rel] = {"type": "file", "size": st.st_size, "mtime_ns": st.st_mtime_ns,
				             "sha256": h.hexdigest()}
			except OSError as e:
				snap[rel] = {"type": "file", "stat_error": str(e)}
	return snap


def _diff_sessions(before: dict, after: dict) -> list:
	"""Every path whose presence or content changed, named individually — "fail loudly and say
	exactly which path", not a bare boolean."""
	violations = []
	for path in sorted(set(before) | set(after)):
		b, a = before.get(path), after.get(path)
		if b is None:
			violations.append(f"ADDED {path}")
		elif a is None:
			violations.append(f"REMOVED {path}")
		elif b != a:
			violations.append(f"MODIFIED {path} (before={b}, after={a})")
	return violations


def _inject_simulated_rogue_write(repo_root: str) -> None:
	"""TESTING ONLY — writes a canary file straight into <repo_root>/sessions/, standing in for
	what a broken isolation would produce, so the guard's FAILURE path is exercised for real
	rather than trusted on paper. Never called in a normal run: gated in main() behind
	--simulate-rogue-write, which itself refuses to fire unless --repo-root was given explicitly
	(see main()) — this function has no independent safety check of its own, by design, so that
	responsibility lives in exactly one place."""
	target = os.path.join(repo_root, "sessions", "990199.simulated-rogue-write")
	os.makedirs(target, exist_ok=True)
	with open(os.path.join(target, "ROGUE.md"), "w", encoding="utf-8") as fh:
		fh.write("# injected by --simulate-rogue-write to prove the archive guard fires\n")


# ---------------------------------------------------------------------------------------------
# Worktree lifecycle
# ---------------------------------------------------------------------------------------------

def _git(args: list, cwd: str, timeout: int = 60) -> subprocess.CompletedProcess:
	return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=timeout)


def _git_ok(args: list, cwd: str, timeout: int = 60) -> subprocess.CompletedProcess:
	p = _git(args, cwd, timeout=timeout)
	if p.returncode != 0:
		raise RuntimeError(f"git {' '.join(args)} failed (exit {p.returncode}): {p.stderr.strip()}")
	return p


def _slug(text, max_len: int = 40) -> str:
	s = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text or "case")).strip("_")
	return (s or "case")[:max_len]


def _link_shared_deps(repo_root: str, worktree: str) -> list:
	"""Symlink the two gitignored-but-required trees a bare worktree checkout has zero of (see the
	module docstring for why each matters). Both are best-effort: a missing source is recorded as a
	warning, not a hard failure, so a worktree degrades the same way the real repo would if IT had
	no .env — never worse, and never silently different."""
	warnings = []
	venv_src = os.path.join(repo_root, "scripts", ".venv")
	if os.path.isdir(venv_src):
		os.symlink(venv_src, os.path.join(worktree, "scripts", ".venv"), target_is_directory=True)
	else:
		warnings.append(f"no scripts/.venv at {venv_src} — pipeline calls inside the worktree will fail")
	env_src = os.path.join(repo_root, ".env")
	if os.path.isfile(env_src):
		os.symlink(env_src, os.path.join(worktree, ".env"))
	else:
		warnings.append(f"no .env at {env_src} — FRED-gated macro gauges will degrade to per-gauge errors")
	return warnings


def _remove_worktree(repo_root: str, worktree: str) -> None:
	"""--force is required, not a safety compromise: a worktree that actually did its job has the
	.venv/.env symlinks (untracked) and, hopefully, new files under sessions/ (untracked) — a plain
	`git worktree remove` refuses on both. Verified live: it fails with 'contains modified or
	untracked files' without --force, and cleans up completely with it."""
	p = _git(["worktree", "remove", "--force", worktree], repo_root)
	if p.returncode != 0:
		# Best-effort fallback so a wedged worktree never survives the run silently.
		_git(["worktree", "prune"], repo_root)
		shutil.rmtree(worktree, ignore_errors=True)


def _sessions_written(sessions_dir: str, baseline: dict) -> list:
	"""What THIS RUN wrote under sessions/ — the diff against the worktree's own starting state.

	A worktree is created from HEAD, so its `sessions/` already contains the committed archive. A
	plain walk therefore reports every archived scorecard in the repo as though the run had produced
	it: the real signal ("did the archive step happen?") gets buried under a verbatim copy of the
	archive, once per case. Content is captured only for paths that actually changed, and it is
	captured HERE because the worktree is deleted at teardown — after that, the answer is gone."""
	entries = []
	after = _snapshot_sessions(sessions_dir)
	for rel in sorted(set(after) - set(baseline)) + sorted(
			r for r in set(after) & set(baseline) if after[r] != baseline[r]):
		meta = after[rel]
		entry = {"path": rel, "change": "added" if rel not in baseline else "modified",
		         "size": meta.get("size")}
		if meta.get("type") == "dir":
			entry["type"] = "dir"
			entries.append(entry)
			continue
		try:
			with open(os.path.join(sessions_dir, rel), "rb") as fh:
				raw = fh.read(_MAX_SESSION_FILE_BYTES + 1)
			if len(raw) > _MAX_SESSION_FILE_BYTES:
				entry["truncated"] = True
				raw = raw[:_MAX_SESSION_FILE_BYTES]
			entry["content"] = raw.decode("utf-8", errors="replace")
		except OSError as e:
			entry["read_error"] = str(e)
		entries.append(entry)
	return entries


def _process_case(case: dict, index: int, *, repo_root: str, run_dir: str, model, dry_run: bool,
                   keep: bool) -> dict:
	"""Everything for ONE case: worktree -> symlinks -> interpreter smoke-test -> (dry-run: stop
	here) claude -p -> capture worktree sessions/ -> teardown. Shared verbatim by --dry-run and a
	real run (see module docstring) — the only branch between them is whether `claude -p` is
	actually invoked."""
	ticker = case.get("ticker") or case.get("id") or f"case{index}"
	worktree = os.path.join(run_dir, f"case-{index:03d}-{_slug(ticker)}")
	result = {
		"index": index, "id": case.get("id"), "ticker": case.get("ticker"),
		"date": case.get("date"), "entry_type": case.get("entry_type"), "worktree": worktree,
	}
	created = False
	try:
		_git_ok(["worktree", "add", "--detach", "--quiet", worktree, "HEAD"], repo_root)
		created = True

		warnings = _link_shared_deps(repo_root, worktree)
		if warnings:
			result["warnings"] = warnings

		py = os.path.join(worktree, "scripts", ".venv", "bin", "python")
		smoke = subprocess.run([py, "-c", "import yfinance"], capture_output=True, text=True,
		                        timeout=_SMOKE_TIMEOUT_SECONDS)
		if smoke.returncode != 0:
			result["error"] = (
				"interpreter smoke-test failed inside the worktree (`python -c 'import yfinance'`, "
				f"exit {smoke.returncode}): {(smoke.stderr or smoke.stdout or '').strip()[-2000:]}"
			)
			return result
		result["interpreter_smoke_test"] = "ok"
		# Baseline BEFORE the run, taken from the worktree's own starting state — that is what makes
		# "what did THIS run archive?" answerable at all.
		sessions_dir = os.path.join(worktree, "sessions")
		sessions_baseline = _snapshot_sessions(sessions_dir)

		if dry_run:
			result["dry_run"] = True
		else:
			env = {**os.environ, "CLAUDE_PROJECT_DIR": worktree}
			argv = ["claude", "-p", case["blind_prompt"], "--output-format", "json",
			        "--permission-mode", "bypassPermissions"]
			if model:
				argv += ["--model", model]
			proc = subprocess.run(argv, cwd=worktree, env=env, capture_output=True, text=True,
			                       timeout=_CASE_TIMEOUT_SECONDS)
			result["returncode"] = proc.returncode
			try:
				payload = json.loads(proc.stdout)
			except json.JSONDecodeError:
				result["error"] = (
					f"claude -p produced non-JSON stdout (exit {proc.returncode}): "
					f"{(proc.stderr or proc.stdout or '').strip()[-2000:]}"
				)
				return result
			result["answer"] = payload.get("result")
			result["session_id"] = payload.get("session_id")
			result["is_error"] = payload.get("is_error")
			result["total_cost_usd"] = payload.get("total_cost_usd")
			result["num_turns"] = payload.get("num_turns")
			# The resolved model, read back from claude's OWN accounting rather than echoing the
			# --model flag: an alias ("sonnet") is not an identity, and this flag is never trusted
			# as the record of what actually ran (§4.7).
			model_usage = payload.get("modelUsage") or {}
			result["resolved_models"] = sorted(model_usage.keys())
			result["canonical_models"] = sorted({
				v.get("canonicalModel") for v in model_usage.values() if v.get("canonicalModel")
			})

		result["sessions_written"] = _sessions_written(sessions_dir, sessions_baseline)
	except subprocess.TimeoutExpired as e:
		result["error"] = f"timed out: {e}"
	except Exception as e:  # noqa: BLE001 — one bad case must never sink the whole batch
		result["error"] = f"{type(e).__name__}: {e}"
	finally:
		if created and not keep:
			_remove_worktree(repo_root, worktree)
	return result


def _load_cases(path: str) -> list:
	with open(path, encoding="utf-8") as fh:
		data = json.load(fh)
	cases = data.get("cases") if isinstance(data, dict) else data
	if not isinstance(cases, list) or not cases:
		print(f"error: {path} has no `cases` list", file=sys.stderr)
		sys.exit(2)
	return cases


def main(argv=None) -> int:
	parser = argparse.ArgumentParser(
		prog="modeb_runner.py",
		description=__doc__,
		formatter_class=argparse.RawDescriptionHelpFormatter,
	)
	parser.add_argument("--cases", required=True,
	                     help="Cases JSON — serenity_eval.py sample's {meta, cases} shape, or a bare list.")
	parser.add_argument("--out", required=True, help="Where to write the answers JSON.")
	parser.add_argument("--model", default=None,
	                     help="Model id/alias pinned for every claude -p call (passed through as "
	                          "--model). The RESOLVED model is read back from claude's own JSON "
	                          "output (modelUsage) and recorded regardless (§4.7) — this flag alone "
	                          "is never trusted as the record of what actually ran.")
	parser.add_argument("--limit", type=int, default=None, help="Process at most N cases.")
	parser.add_argument("--dry-run", action="store_true",
	                     help="Do everything except invoke `claude -p`: worktree, symlinks, "
	                          "interpreter smoke-test, archive guard, teardown.")
	parser.add_argument("--keep", action="store_true",
	                     help="Do not remove worktrees afterward (debugging; each case's `worktree` "
	                          "path is in --out).")
	parser.add_argument("--repo-root", default=None,
	                     help="Override the source/archive root (default: this repo, auto-detected). "
	                          "For the test suite to point at a disposable sandbox — do not pass this "
	                          "in real usage.")
	parser.add_argument("--simulate-rogue-write", action="store_true",
	                     help="TESTING ONLY. Injects a canary file into <repo-root>/sessions/ to prove "
	                          "the archive guard fires. Refuses to run unless --repo-root is also given "
	                          "explicitly, so this can never fire against the real archive by accident.")
	args = parser.parse_args(argv)

	if args.simulate_rogue_write and args.repo_root is None:
		print("error: --simulate-rogue-write refuses to run without an explicit --repo-root — it "
		      "writes into <repo-root>/sessions/ ON PURPOSE, and the default repo-root is this real "
		      "repository. Point --repo-root at a disposable sandbox (see test_modeb_runner.py).",
		      file=sys.stderr)
		return 2

	repo_root = os.path.abspath(args.repo_root) if args.repo_root else _DEFAULT_REPO_ROOT
	if not os.path.exists(os.path.join(repo_root, ".git")):
		print(f"error: {repo_root} does not look like a git repo (no .git)", file=sys.stderr)
		return 2
	if not args.dry_run and shutil.which("claude") is None:
		print("error: `claude` not found on PATH (needed for a real, non-dry-run mode-B pass)",
		      file=sys.stderr)
		return 2

	cases = _load_cases(args.cases)
	if args.limit is not None:
		cases = cases[: args.limit]

	sessions_root = os.path.join(repo_root, "sessions")
	before = _snapshot_sessions(sessions_root)

	if args.simulate_rogue_write:
		_inject_simulated_rogue_write(repo_root)

	_git(["worktree", "prune"], repo_root)  # best-effort hygiene; a stale entry must never block a fresh add

	run_id = uuid.uuid4().hex[:12]
	run_dir = os.path.join(repo_root, ".tmp", "modeb_runs", run_id)
	os.makedirs(run_dir, exist_ok=True)

	results = []
	for i, case in enumerate(cases):
		if not case.get("blind_prompt"):
			results.append({"index": i, "id": case.get("id"), "ticker": case.get("ticker"),
			                 "error": "case has no blind_prompt — skipped before any worktree was created"})
			continue
		print(f"[modeb_runner] case {i + 1}/{len(cases)}: {case.get('ticker') or case.get('id')}",
		      file=sys.stderr)
		try:
			result = _process_case(case, i, repo_root=repo_root, run_dir=run_dir, model=args.model,
			                        dry_run=args.dry_run, keep=args.keep)
		except Exception as e:  # noqa: BLE001 — one bad case must never sink the batch
			result = {"index": i, "id": case.get("id"), "ticker": case.get("ticker"),
			          "error": f"unhandled {type(e).__name__}: {e}"}
		results.append(result)

	if not args.keep:
		try:
			os.rmdir(run_dir)  # only succeeds if empty — every case tore its own worktree down already
		except OSError:
			pass  # non-empty (a case's teardown failed, or --keep was used per-case some other way)

	after = _snapshot_sessions(sessions_root)
	violations = _diff_sessions(before, after)

	all_resolved = sorted({m for r in results for m in (r.get("resolved_models") or [])})
	all_canonical = sorted({m for r in results for m in (r.get("canonical_models") or [])})
	n_errors = sum(1 for r in results if r.get("error"))

	output = {
		"meta": {
			"requested_model": args.model,
			"resolved_models": all_resolved,
			"canonical_models": all_canonical,
			"n_cases": len(results),
			"n_errors": n_errors,
			"dry_run": args.dry_run,
			"kept_worktrees": args.keep,
			"repo_root": repo_root,
			"run_id": run_id,
		},
		"archive_guard": {
			"ok": not violations,
			"sessions_root": sessions_root,
			"violations": violations,
		},
		"cases": results,
	}
	with open(args.out, "w", encoding="utf-8") as fh:
		json.dump(output, fh, indent=2, ensure_ascii=False)

	if violations:
		print("ARCHIVE GUARD TRIPPED — a mode-B run touched the real sessions/ tree at "
		      f"{sessions_root}:\n  " + "\n  ".join(violations), file=sys.stderr)
		return 1
	if n_errors:
		print(f"[modeb_runner] {n_errors}/{len(results)} case(s) errored — see {args.out}", file=sys.stderr)
		return 3
	return 0


if __name__ == "__main__":
	sys.exit(main())
