"""Tests for serenity_scrape.py — the thesis-DB refresh CLI.

These run under `scripts/.venv/bin/python -m pytest`, which has NO twikit. That is
deliberate and it constrains the design: serenity_scrape.py must keep `import twikit`
behind the default client factory, so importing the module here stays free. If a test
ever fails with ImportError on twikit, the import leaked out of that factory.
"""

import asyncio
import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import serenity_scrape  # noqa: E402


# --- The ticker regex is FROZEN -------------------------------------------------
#
# `tickers` is a column derived from `content`, and 1,792 rows were already written
# with this exact extraction. Changing it without re-deriving every row would make
# `serenity_tweets.py search --ticker X` have recall that depends on WHEN a row was
# written — a silent bias in the answer key serenity_eval.py scores against.
#
# So these are characterization tests, not specification tests. The expected values
# are not what the regex "should" do in the abstract; they are what is ALREADY in
# data/analysis_Serenity.db, read straight out of the `tickers` column. If one of
# these goes red, the corpus and the code have diverged — that is the alarm, and the
# fix is a deliberate one-shot re-extraction over all rows, not an edit here.

CORPUS_PAIRS = [
	pytest.param(
		"Changed my mind on $ALAB, took profit at $217 so exited long and opened up "
		"short with $CREDO as a hedge.\n\nALAB feels a bit overbought after going up "
		"14%.\n\n$CREDO should play catchup soon though. https://t.co/oDIuqi0mFn",
		["ALAB", "CREDO"],
		id="dedupes-repeats-skips-dollar-amounts-and-bare-symbols",
	),
	pytest.param(
		"And $TSSI up 5.2% 2 hours later after I posted. \n\nIt’s almost free money "
		"playing follow the leader on stocks that are down a ton like $MRVL, $SMCI. "
		"\n\nLot of room to run given that it dropped from the $30s. "
		"https://t.co/Ud9FgrAbz8",
		["TSSI", "MRVL", "SMCI"],
		id="skips-dollar-30s-keeps-first-appearance-order",
	),
	pytest.param(
		"I don’t know how to reiterate this enough for $HIMS\n\n42% short interest "
		"on a 11B, profitable, and fast growing company… has the potential to make "
		"history on a short squeeze like $OPEN or $GME.\n\nThe risk reward is worth it.",
		["HIMS", "OPEN", "GME"],
		id="three-distinct-symbols",
	),
	pytest.param(
		"$AMD is actually insane wtf.\n\nMarkets are repricing it as the next $NVDA "
		"I guess. https://t.co/cuH0dEjd0n",
		["AMD", "NVDA"],
		id="two-symbols",
	),
]


@pytest.mark.parametrize("content,expected", CORPUS_PAIRS)
def test_extract_tickers_reproduces_the_committed_corpus(content, expected):
	assert serenity_scrape._extract_tickers(content) == expected


def test_extract_tickers_uppercases_without_reordering():
	# $sive / $SIVE / $Sive all fold to one symbol, at the position of the first hit.
	assert serenity_scrape._extract_tickers("$sive then $NVDA then $Sive") == ["SIVE", "NVDA"]


def test_extract_tickers_returns_empty_list_for_untagged_prose():
	assert serenity_scrape._extract_tickers("no symbols here, just $5B of capex") == []


# --- created_at is stored as KST, and the corpus is ordered lexicographically on it ---
#
# `serenity_tweets.py` compares created_at as a STRING (`created_at >= ?`), so the
# offset has to be a fixed `+09:00` on every row or ordering silently breaks. The
# worked example below is independent of the implementation: X's wire format is UTC,
# and 16:43:54Z on Sep 8 is 01:43:54 KST on Sep 9. That output is a real row in
# data/analysis_Serenity.db.

def test_to_kst_converts_x_wire_format_and_crosses_the_date_line():
	assert serenity_scrape._to_kst("Mon Sep 08 16:43:54 +0000 2025") == "2025-09-09T01:43:54+09:00"


def test_to_kst_always_emits_the_plus_nine_offset_never_the_source_offset():
	# Same instant, already expressed in KST on the wire. Must not double-shift.
	assert serenity_scrape._to_kst("Tue Sep 09 01:43:54 +0900 2025") == "2025-09-09T01:43:54+09:00"


def test_to_kst_raises_on_an_unrecognised_format():
	# X changing its timestamp format must be a loud failure, never a silently
	# skipped tweet — a swallowed parse error drops data with no trace.
	with pytest.raises(ValueError):
		serenity_scrape._to_kst("2025-09-08T16:43:54Z")


# --- A fake X client -------------------------------------------------------------
#
# The seam is `client_factory`. Everything below stands in for twikit WITHOUT
# importing it, which is what lets these tests run under scripts/.venv.

class FakeUser:
	def __init__(self, screen_name="aleabitoreddit"):
		self.screen_name = screen_name


class FakeTweet:
	"""Just the attributes serenity_scrape reads off a twikit Tweet."""

	def __init__(self, id, text, created_at="Mon Sep 08 16:43:54 +0000 2025",
	             screen_name="aleabitoreddit", note_text=None, exclusive=False,
	             in_reply_to=None, media_urls=()):
		self.id = id
		self.full_text = text
		self.created_at = created_at
		self.user = FakeUser(screen_name)
		self.in_reply_to = in_reply_to
		self.media = [type("M", (), {"media_url": u})() for u in media_urls]
		self._data = {}
		if exclusive:
			self._data["exclusivityInfo"] = {"conversation_control": True}
		if note_text is not None:
			self._data["note_tweet"] = {
				"note_tweet_results": {"result": {"text": note_text}}
			}


class FakePage(list):
	"""A twikit Result stand-in: list-like, with an async next()."""

	def __init__(self, tweets, following=None):
		super().__init__(tweets)
		self._following = following

	async def next(self):
		return self._following


class FakeClient:
	"""Stands in for both twikit's Client and the User it hands back.

	twikit's get_user_by_screen_name returns a User carrying the profile fields
	below, and `get_tweets` is a method on that User — returning self keeps the
	two-hop shape without a second class.
	"""

	name = "Serenity"
	screen_name = "aleabitoreddit"
	followers_count = 12345
	statuses_count = 4567

	def __init__(self, pages, user_error=None, page_errors=()):
		self._pages = pages
		self._user_error = user_error
		self._page_errors = list(page_errors)
		self.requests = 0          # every network-ish call the script made
		self.cookies = None

	def set_cookies(self, cookies, clear_cookies=False):
		self.cookies = cookies

	async def get_user_by_screen_name(self, handle):
		self.requests += 1
		if self._user_error:
			raise self._user_error
		return self

	async def get_tweets(self, tab, count=20):
		self.requests += 1
		if self._page_errors:
			raise self._page_errors.pop(0)
		return self._pages


@pytest.fixture
def cookies(monkeypatch):
	monkeypatch.setenv("X_AUTH_TOKEN", "t")
	monkeypatch.setenv("X_CT0", "c")
	monkeypatch.setenv("X_TWID", "w")


@pytest.fixture(autouse=True)
def instant_backoff(monkeypatch):
	"""Real backoff is 2s/4s/8s. Waiting for it here would buy nothing — the thing
	under test is how many attempts happen and what is reported, not the clock."""
	async def instant(_seconds):
		return None

	monkeypatch.setattr(asyncio, "sleep", instant)


def run(tmp_path, client, argv=(), capsys=None):
	"""Drive the CLI the way the workflow does, and return (exit_code, result_doc)."""
	db = tmp_path / "analysis_Serenity.db"
	code = serenity_scrape.main(
		["--db", str(db), *argv], client_factory=lambda: client
	)
	doc = json.loads(capsys.readouterr().out)
	return code, doc, db


# --- The DB row contract ---------------------------------------------------------

def test_a_run_writes_every_field_the_reader_depends_on(tmp_path, cookies, capsys):
	client = FakeClient(FakePage([
		FakeTweet("1", "short post about $NVDA", media_urls=["https://pbs.x/a.jpg"]),
		FakeTweet("2", "truncated…", note_text="the full long-form body about $AMD"),
		FakeTweet("3", "subscriber only", exclusive=True),
		FakeTweet("4", "a reply", in_reply_to="999"),
	]))
	code, doc, db = run(tmp_path, client, capsys=capsys)

	assert code == 0
	assert doc["new_rows"] == 4

	rows = {r[0]: r for r in sqlite3.connect(db).execute(
		"select id, user, type, created_at, content, tickers, media from tweets"
	)}

	# Long-form notes must win over full_text, or every long thesis is cut at 280.
	assert rows["2"][4] == "the full long-form body about $AMD"
	assert json.loads(rows["2"][5]) == ["AMD"]

	assert rows["1"][1] == "aleabitoreddit"
	assert rows["1"][3] == "2025-09-09T01:43:54+09:00"
	assert json.loads(rows["1"][6]) == ["https://pbs.x/a.jpg"]

	assert rows["1"][2] == "post"
	assert rows["3"][2] == "subscriber"
	assert rows["4"][2] == "reply"


def test_exclusivity_beats_in_reply_to_when_a_subscriber_post_is_also_a_reply(tmp_path, cookies, capsys):
	# Order matters: a paid post inside a thread must not be filed as a plain reply,
	# or it drops out of any subscriber-only slice of the corpus.
	client = FakeClient(FakePage([
		FakeTweet("1", "paid thread continuation", exclusive=True, in_reply_to="998"),
	]))
	_, _, db = run(tmp_path, client, capsys=capsys)

	assert sqlite3.connect(db).execute("select type from tweets").fetchone()[0] == "subscriber"


def test_tweets_from_other_users_are_not_written(tmp_path, cookies, capsys):
	client = FakeClient(FakePage([
		FakeTweet("1", "mine"),
		FakeTweet("2", "someone else's", screen_name="notserenity"),
	]))
	code, doc, db = run(tmp_path, client, capsys=capsys)

	assert doc["new_rows"] == 1
	assert doc["tabs"][0]["skipped_other_users"] == 1

	assert [r[0] for r in sqlite3.connect(db).execute("select id from tweets")] == ["1"]


# --- "caught_up" is the whole invariant -------------------------------------------
#
# The design is incremental: each run starts at the newest tweet and stops once it has
# seen N consecutive ids it already had. That makes ONE failure mode irreversible — if
# a run dies mid-walk, the next run sees page 1 as all duplicates, stops, and the pages
# it never reached are never fetched again. X does not paginate backwards forever, so
# an unrepaired gap eventually becomes unrepairable.
#
# Which is why the health signal is WHY the walk stopped, not how many rows it got.
# `new_rows > 0` proves nothing; `new_rows == 0` proves nothing either.

def _pages(*groups):
	"""Chain groups of tweets into a linked list of pages, newest page first."""
	page = None
	for group in reversed(groups):
		page = FakePage(group, following=page)
	return page


def _seed(db, ids):
	conn = sqlite3.connect(db)
	serenity_scrape._init_db(conn)
	for i in ids:
		conn.execute(
			"INSERT INTO tweets (id, user, type, created_at, content) VALUES (?,?,?,?,?)",
			(i, "aleabitoreddit", "post", "2025-09-09T01:43:54+09:00", "seeded"),
		)
	conn.commit()
	conn.close()


def test_stopping_on_consecutive_duplicates_proves_the_corpus_is_current(tmp_path, cookies, capsys):
	db = tmp_path / "analysis_Serenity.db"
	_seed(db, [str(i) for i in range(100, 104)])
	client = FakeClient(_pages(
		[FakeTweet("1", "new")],
		[FakeTweet(str(i), "known") for i in range(100, 104)],   # 4 consecutive dups
		[FakeTweet("2", "never reached")],
	))
	code = serenity_scrape.main(
		["--db", str(db), "--max-dups", "4"], client_factory=lambda: client
	)
	doc = json.loads(capsys.readouterr().out)

	assert code == 0
	assert doc["tabs"][0]["stopped_reason"] == "duplicate_threshold"
	assert doc["tabs"][0]["caught_up"] is True
	assert doc["invariants_ok"] is True
	assert doc["new_rows"] == 1
	# It stopped early — the third page was never requested.
	assert [r[0] for r in sqlite3.connect(db).execute("select id from tweets where content != 'seeded'")] == ["1"]


def test_a_new_tweet_between_duplicates_resets_the_run_of_consecutive_dups(tmp_path, cookies, capsys):
	# CONSECUTIVE is the point. A stray already-known id in the middle of a burst of
	# new ones must not be read as "we are caught up" and end the walk early.
	db = tmp_path / "analysis_Serenity.db"
	_seed(db, ["100", "101"])
	client = FakeClient(_pages(
		[FakeTweet("100", "known"), FakeTweet("1", "new"), FakeTweet("101", "known")],
		[FakeTweet("2", "still reachable")],
	))
	code = serenity_scrape.main(
		["--db", str(db), "--max-dups", "2"], client_factory=lambda: client
	)
	doc = json.loads(capsys.readouterr().out)

	assert code == 0
	assert doc["new_rows"] == 2
	assert doc["tabs"][0]["stopped_reason"] == "timeline_exhausted"


def test_max_dups_zero_walks_the_whole_timeline_for_gap_repair(tmp_path, cookies, capsys):
	db = tmp_path / "analysis_Serenity.db"
	_seed(db, [str(i) for i in range(100, 120)])
	client = FakeClient(_pages(
		[FakeTweet(str(i), "known") for i in range(100, 120)],
		[FakeTweet("1", "the row an earlier gap left behind")],
	))
	code = serenity_scrape.main(
		["--db", str(db), "--max-dups", "0"], client_factory=lambda: client
	)
	doc = json.loads(capsys.readouterr().out)

	assert code == 0
	assert doc["tabs"][0]["stopped_reason"] == "timeline_exhausted"
	assert doc["new_rows"] == 1


def test_new_rows_equals_the_actual_row_delta(tmp_path, cookies, capsys):
	"""Acceptance test for the notebook's `conn.total_changes` bug.

	That counter is cumulative over the connection, so it is permanently truthy after
	the first insert and "saved N" degenerated into "rows attempted". new_rows is now
	the workflow's commit gate, so an inflated count would push a 2 MB binary commit
	on days nothing was collected.
	"""
	db = tmp_path / "analysis_Serenity.db"
	_seed(db, ["100", "101", "102"])
	before = sqlite3.connect(db).execute("select count(*) from tweets").fetchone()[0]

	client = FakeClient(_pages([
		FakeTweet("100", "known"), FakeTweet("1", "new"),
		FakeTweet("101", "known"), FakeTweet("2", "new"), FakeTweet("102", "known"),
	]))
	_, doc, _ = None, None, None
	serenity_scrape.main(["--db", str(db), "--max-dups", "0"], client_factory=lambda: client)
	doc = json.loads(capsys.readouterr().out)

	after = sqlite3.connect(db).execute("select count(*) from tweets").fetchone()[0]
	assert doc["new_rows"] == after - before == 2
	assert doc["db_before"] == before
	assert doc["db_totals"]["total"] == after


def test_a_second_run_over_unchanged_data_is_green_with_nothing_written(tmp_path, cookies, capsys):
	# The normal outcome on a quiet day. It must not be an error, and it must not
	# produce a commit.
	page_source = lambda: FakeClient(_pages([FakeTweet("1", "a"), FakeTweet("2", "b")]))
	db = tmp_path / "analysis_Serenity.db"

	serenity_scrape.main(["--db", str(db), "--max-dups", "2"], client_factory=page_source)
	capsys.readouterr()

	code = serenity_scrape.main(["--db", str(db), "--max-dups", "2"], client_factory=page_source)
	doc = json.loads(capsys.readouterr().out)

	assert code == 0
	assert doc["new_rows"] == 0
	assert doc["invariants_ok"] is True
	assert doc["tabs"][0]["duplicates"] == 2
	assert doc["db_totals"]["total"] == 2


# --- The gap cases: a run that did NOT prove currency must be red ------------------

# twikit's error classes, reproduced by NAME only. serenity_scrape classifies on the
# class name precisely so it never has to import twikit — see _is_retryable.
class Unauthorized(Exception): pass
class Forbidden(Exception): pass
class NotFound(Exception): pass
class UserNotFound(Exception): pass
class AccountLocked(Exception): pass
class TooManyRequests(Exception): pass
class ServerError(Exception): pass


def test_dying_mid_walk_is_red_because_the_gap_can_never_be_refetched(tmp_path, cookies, capsys):
	db = tmp_path / "analysis_Serenity.db"
	client = FakeClient(_pages([FakeTweet("1", "page one landed")]))
	# The first get_tweets succeeds; the follow-on page blows up for good.
	client._pages = FakePage([FakeTweet("1", "page one landed")], following=_Exploding())

	code = serenity_scrape.main(["--db", str(db)], client_factory=lambda: client)
	doc = json.loads(capsys.readouterr().out)

	assert code == 1
	assert doc["tabs"][0]["caught_up"] is False
	assert doc["tabs"][0]["stopped_reason"] == "fetch_failed"
	assert doc["invariants_ok"] is False
	# ...but page one is still committed. A crash must not throw away what landed.
	assert doc["new_rows"] == 1
	assert sqlite3.connect(db).execute("select count(*) from tweets").fetchone()[0] == 1


def test_an_empty_first_page_is_red_not_a_quiet_day(tmp_path, cookies, capsys):
	"""The silent-green killer.

	A shadow-limited or partly-invalidated session returns 200 with an empty timeline
	and no exception. Treated as "timeline exhausted" it would go green having
	fetched nothing, indefinitely, and look exactly like "he didn't post".
	"""
	client = FakeClient(FakePage([]))
	code, doc, _ = run(tmp_path, client, capsys=capsys)

	assert code == 1
	assert doc["error"] == "empty_timeline"
	assert doc["invariants_ok"] is False
	assert "cookie" in doc["detail"].lower() or "session" in doc["detail"].lower()


def test_hitting_the_page_cap_is_red_because_the_walk_was_truncated(tmp_path, cookies, capsys):
	db = tmp_path / "analysis_Serenity.db"
	client = FakeClient(_pages(
		[FakeTweet("1", "a")], [FakeTweet("2", "b")], [FakeTweet("3", "c")],
	))
	code = serenity_scrape.main(
		["--db", str(db), "--max-dups", "0", "--max-pages", "2"],
		client_factory=lambda: client,
	)
	doc = json.loads(capsys.readouterr().out)

	assert code == 1
	assert doc["tabs"][0]["stopped_reason"] == "page_cap"
	assert doc["tabs"][0]["caught_up"] is False
	assert doc["new_rows"] == 2


# --- Cookie and account failures carry a remedy, and never get retried -------------

def test_missing_cookies_fail_before_any_network_call(tmp_path, monkeypatch, capsys):
	for key in ("X_AUTH_TOKEN", "X_CT0", "X_TWID"):
		monkeypatch.delenv(key, raising=False)
	client = FakeClient(FakePage([FakeTweet("1", "a")]))
	code, doc, _ = run(tmp_path, client, argv=["--env-file", os.devnull], capsys=capsys)

	assert code == 1
	assert doc["error"] == "cookies_missing"
	assert client.requests == 0
	# The remedy must name all three keys — this is the message read at 3am.
	assert all(k in doc["detail"] for k in ("X_AUTH_TOKEN", "X_CT0", "X_TWID"))


def test_rejected_cookies_are_reported_once_and_never_retried(tmp_path, cookies, capsys):
	client = FakeClient(FakePage([]), user_error=Unauthorized("401"))
	code, doc, _ = run(tmp_path, client, capsys=capsys)

	assert code == 1
	assert doc["error"] == "cookies_rejected"
	# The notebook retried EVERY exception, so the dominant failure mode burned
	# three requests and six seconds before reporting. One request, then stop.
	assert client.requests == 1
	assert ".env" in doc["detail"]


def test_a_locked_account_is_distinct_from_expired_cookies(tmp_path, cookies, capsys):
	# Different remedy: clear the challenge at x.com FIRST, then re-copy cookies.
	# Generic "replace your cookies" advice does not work here.
	client = FakeClient(FakePage([]), user_error=AccountLocked("challenge"))
	code, doc, _ = run(tmp_path, client, capsys=capsys)

	assert code == 1
	assert doc["error"] == "account_locked"
	assert client.requests == 1


def test_a_renamed_or_suspended_handle_names_the_user_flag(tmp_path, cookies, capsys):
	client = FakeClient(FakePage([]), user_error=UserNotFound("gone"))
	code, doc, _ = run(tmp_path, client, capsys=capsys)

	assert code == 1
	assert doc["error"] == "user_not_found"
	assert "--user" in doc["detail"]


def test_rate_limits_are_retried_then_reported(tmp_path, cookies, capsys):
	client = FakeClient(FakePage([]), page_errors=[TooManyRequests("429")] * 4)
	code, doc, _ = run(tmp_path, client, capsys=capsys)

	assert code == 1
	assert doc["error"] == "rate_limited"
	# 1 user lookup + 1 initial attempt + 3 retries.
	assert client.requests == 5
	assert doc["tabs"][0]["retries"] == 3


def test_a_retryable_error_that_clears_lets_the_run_finish_green(tmp_path, cookies, capsys):
	client = FakeClient(FakePage([FakeTweet("1", "a")]), page_errors=[ServerError("503")])
	code, doc, _ = run(tmp_path, client, capsys=capsys)

	assert code == 0
	assert doc["new_rows"] == 1
	assert doc["tabs"][0]["retries"] == 1


@pytest.mark.parametrize("exc", [NotFound("404"), Forbidden("403")],
                         ids=["not-found", "forbidden"])
def test_permanent_errors_are_not_retried(tmp_path, cookies, capsys, exc):
	client = FakeClient(FakePage([]), page_errors=[exc] * 4)
	code, doc, _ = run(tmp_path, client, capsys=capsys)

	assert code == 1
	assert doc["tabs"][0]["retries"] == 0
	assert client.requests == 2      # user lookup + one doomed attempt


# --- --dry-run is the only way to exercise the live path safely --------------------

def test_dry_run_reports_what_it_would_write_and_writes_nothing(tmp_path, cookies, capsys):
	db = tmp_path / "analysis_Serenity.db"
	client = FakeClient(FakePage([FakeTweet("1", "a $NVDA"), FakeTweet("2", "b")]))
	code = serenity_scrape.main(
		["--db", str(db), "--dry-run"], client_factory=lambda: client
	)
	doc = json.loads(capsys.readouterr().out)

	assert code == 0
	assert doc["dry_run"] is True
	assert doc["new_rows"] == 2                      # would-be inserts
	assert doc["db_totals"]["total"] == 0            # ...but the corpus is untouched
	assert sqlite3.connect(db).execute("select count(*) from tweets").fetchone()[0] == 0


def test_dry_run_still_recognises_existing_rows_as_duplicates(tmp_path, cookies, capsys):
	# Without the preloaded id set, a dry run could not tell new from known at all —
	# it never inserts, so it can never learn from a rowcount.
	db = tmp_path / "analysis_Serenity.db"
	_seed(db, ["1"])
	client = FakeClient(FakePage([FakeTweet("1", "known"), FakeTweet("2", "new")]))
	code = serenity_scrape.main(
		["--db", str(db), "--dry-run", "--max-dups", "0"], client_factory=lambda: client
	)
	doc = json.loads(capsys.readouterr().out)

	assert code == 0
	assert doc["new_rows"] == 1
	assert doc["tabs"][0]["duplicates"] == 1
	assert sqlite3.connect(db).execute("select count(*) from tweets").fetchone()[0] == 1


# --- Bad arguments stay inside the JSON contract ----------------------------------

def test_a_bad_argument_exits_two_with_json_not_a_usage_traceback(tmp_path, capsys):
	# The workflow reads stdout as JSON unconditionally. argparse's default is to
	# print usage to stderr and SystemExit(2), which would leave stdout empty and
	# the Summary step guessing.
	code = serenity_scrape.main(["--max-dups", "not-a-number"])
	doc = json.loads(capsys.readouterr().out)

	assert code == 2
	assert doc["error"] == "invalid_arguments"
	assert doc["invariants_ok"] is False


# --- Reaching X at all: the client-transaction id ---------------------------------
#
# twikit signs every GraphQL call with an `x-client-transaction-id` derived from a
# hash it scrapes out of X's own web bundle. In August 2026 X migrated the ROOT page
# (https://x.com) to a new "x-web" shell that carries no module map at all, so
# twikit 2.3.3 dies at startup with `Couldn't get KEY_BYTE indices` before it makes a
# single API call. https://x.com/home still serves the old shell, manifest and all.
#
# The snippets below are captured verbatim from a live x.com/home and the ondemand.s
# bundle it points at. They are the only cheap regression signal we have: if X moves
# this again, these go red without needing cookies or a network round trip.

HOME_SNIPPET = (
	'<html><head><script>'
	'...59707:"ondemand.countries-ro",59862:"ondemand.LottieWeb",59924:"ondemand.s",'
	'60041:"i18n/emoji-gu",60227:"ondemand.countries-ur"...'
	'...59707:"62b6416",59862:"684ba55",59924:"048b040",60018:"4224b9c"...'
	'</script></head></html>'
)

# One contiguous slice of the live bundle, spanning all four index sites.
ONDEMAND_SNIPPET = (
	'(r[0],16),u[t(867,931,"4^#@",782,728)](u[a(1331,1240,"!TSQ",1387,1256)]'
	'(u[t(787,666,"kdrs",634,737)](r[34],16),u[t(577,736,e,669,582)](r[37],16)),'
	'u[o(1067,1143,1093,1202,"$Kbj")](r[12],16)'
)


def test_the_ondemand_bundle_hash_is_found_in_a_real_home_page():
	assert serenity_scrape._ondemand_filename(HOME_SNIPPET) == "048b040"


def test_no_module_map_reads_as_a_dead_page_not_a_silent_none():
	# What https://x.com now returns: the new x-web shell, zero module map.
	dead = '<html><head><script src="https://abs.twimg.com/x-web/x-web/entry-client-logged-out-DmJDcwRM.js"></script></head></html>'
	assert serenity_scrape._ondemand_filename(dead) is None


def test_key_byte_indices_are_read_from_the_real_ondemand_bundle():
	assert serenity_scrape._key_byte_indices(ONDEMAND_SNIPPET) == [0, 34, 37, 12]


def test_detail_is_a_single_line_so_the_job_summary_renders(tmp_path, cookies, capsys):
	"""X's 401 body carries embedded newlines.

	`detail` is rendered into a markdown blockquote and passed through a GitHub
	step output; a raw newline breaks both — the quote silently ends mid-sentence
	and the remedy is the part that gets cut.
	"""
	client = FakeClient(FakePage([]), user_error=Unauthorized(
		'status: 401, message: "{"errors":[{"message":"Could not authenticate you"}]}\n"'
	))
	_, doc, _ = run(tmp_path, client, capsys=capsys)

	assert "\n" not in doc["detail"]
	assert "\r" not in doc["detail"]


def test_detail_truncates_a_hostile_exception_body(tmp_path, cookies, capsys):
	# The Actions log is PUBLIC and twikit can echo a request back at us. Cap it.
	client = FakeClient(FakePage([]), user_error=Unauthorized("x" * 5000))
	_, doc, _ = run(tmp_path, client, capsys=capsys)

	assert len(doc["detail"]) < 800


def test_a_dead_session_names_both_of_its_two_causes(tmp_path, cookies, capsys):
	"""The remedy has to cover both, because the symptom is identical.

	Stale cookies and an X bundle change both surface as "twikit cannot build a
	transaction id", and guessing wrong costs a cookie rotation or a dependency
	upgrade you didn't need.
	"""
	client = FakeClient(FakePage([]), user_error=serenity_scrape.SessionInitError(
		"Couldn't get KEY_BYTE indices"))
	code, doc, _ = run(tmp_path, client, capsys=capsys)

	assert code == 1
	assert doc["error"] == "session_init_failed"
	assert client.requests == 1                      # never retried
	assert "X_AUTH_TOKEN" in doc["detail"]           # cause 1: stale cookies
	assert "twikit" in doc["detail"]                 # cause 2: X moved the bundle


class _Exploding:
	"""A page whose next() always fails — an unrecoverable mid-walk death."""

	def __bool__(self):
		return True

	def __iter__(self):
		return iter(())

	async def next(self):
		raise ServerError("gone")
