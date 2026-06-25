#!/usr/bin/env python3
"""serenity_tweets.py — deterministic retrieval from the Serenity thesis DB.

The DB holds the analyst's real theses. This tool *loads* them; it never judges.
Per the harness boundary: code returns evidence (the verbatim posts), the agent
forms the read. Output is JSON, content is returned in full (never truncated) so
the agent reasons from the actual words, not a lossy summary.

USAGE DISCIPLINE (non-negotiable). The DB is the ANSWER KEY, not a default source.
Invoke this tool ONLY when the user explicitly asks to cross-validate ("실제로 어떻게
봤어", "트윗 DB 확인", "cross-validate") — never preload it, never in routine analysis.
Even then, complete the independent analysis and form the thesis FIRST; the DB
validates after, it is never a shortcut or a substitute for the harness doing its
own discovery and reasoning. The harness's purpose is to *reproduce the methodology*
independently (and more consistently/broadly), not to look up his conclusions.

DB schema: tweets(id, user, type, created_at, content, tickers, media)
  type ∈ {post, reply, subscriber};  tickers is a JSON array string.

Examples:
  serenity_tweets.py search --ticker AXTI --limit 12
  serenity_tweets.py search --contains "levered IRR" --type subscriber
  serenity_tweets.py search --ticker NBIS --since 2025-11-01 --until 2026-01-01
  serenity_tweets.py get --id 2004936335702753729
  serenity_tweets.py stats --top 25
"""

import argparse
import json
import os
import sqlite3
import sys

DEFAULT_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "analysis_Serenity.db"
)


def _connect(db_path):
    if not os.path.exists(db_path):
        _die(f"DB not found at {db_path} (pass --db to override)")
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def _die(msg):
    json.dump({"error": str(msg)}, sys.stdout, ensure_ascii=False, indent=2)
    print()
    sys.exit(1)


def _row(r):
    """Normalize a DB row to a JSON-friendly dict; parse the tickers array."""
    try:
        tickers = json.loads(r["tickers"]) if r["tickers"] else []
    except (json.JSONDecodeError, TypeError):
        tickers = []
    return {
        "id": r["id"],
        "created_at": r["created_at"],
        "type": r["type"],
        "tickers": tickers,
        "content": r["content"],
    }


def _emit(data):
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    print()


def cmd_search(args):
    where, params = [], []
    if args.ticker:
        # Match the exact JSON array element ("AXT" must not match "AXTI").
        where.append("tickers LIKE ?")
        params.append(f'%"{args.ticker.upper()}"%')
    if args.type:
        where.append("type = ?")
        params.append(args.type)
    if args.contains:
        where.append("content LIKE ?")
        params.append(f"%{args.contains}%")
    if args.since:
        where.append("created_at >= ?")
        params.append(args.since)
    if args.until:
        where.append("created_at < ?")
        params.append(args.until)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    order = "ASC" if args.oldest_first else "DESC"
    sql = f"SELECT id, created_at, type, tickers, content FROM tweets{clause} ORDER BY created_at {order} LIMIT ?"
    params.append(args.limit)

    con = _connect(args.db)
    rows = [_row(r) for r in con.execute(sql, params).fetchall()]
    con.close()
    _emit({
        "query": {k: v for k, v in vars(args).items() if k not in ("func", "db") and v is not None},
        "count": len(rows),
        "results": rows,
    })


def cmd_get(args):
    con = _connect(args.db)
    r = con.execute(
        "SELECT id, created_at, type, tickers, content FROM tweets WHERE id = ?", (args.id,)
    ).fetchone()
    con.close()
    if r is None:
        _die(f"no tweet with id {args.id}")
    _emit(_row(r))


def cmd_stats(args):
    con = _connect(args.db)
    by_type = {r["type"]: r["n"] for r in con.execute(
        "SELECT type, COUNT(*) n FROM tweets GROUP BY type"
    )}
    date_range = con.execute("SELECT MIN(created_at) lo, MAX(created_at) hi FROM tweets").fetchone()
    # Top tickers: expand the JSON arrays in Python (sqlite has no json_each guarantee here).
    counts = {}
    for (tickers,) in con.execute("SELECT tickers FROM tweets WHERE tickers != '[]'"):
        try:
            for t in json.loads(tickers):
                counts[t] = counts.get(t, 0) + 1
        except (json.JSONDecodeError, TypeError):
            continue
    con.close()
    top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[: args.top]
    _emit({
        "total": sum(by_type.values()),
        "by_type": by_type,
        "date_range": {"from": date_range["lo"], "to": date_range["hi"]},
        "top_tickers": [{"ticker": t, "posts": n} for t, n in top],
    })


def main():
    p = argparse.ArgumentParser(description="Deterministic retrieval from the Serenity thesis DB.")
    p.add_argument("--db", default=DEFAULT_DB, help="Path to analysis_Serenity.db")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("search", help="Filter theses by ticker/type/text/date")
    s.add_argument("--ticker", help="Ticker symbol (matches the post's tagged tickers)")
    s.add_argument("--type", choices=["post", "reply", "subscriber"], help="Restrict to one type")
    s.add_argument("--contains", help="Substring that must appear in content (case-insensitive)")
    s.add_argument("--since", help="ISO date/time lower bound (created_at >=)")
    s.add_argument("--until", help="ISO date/time upper bound (created_at <)")
    s.add_argument("--limit", type=int, default=12, help="Max rows (default 12)")
    s.add_argument("--oldest-first", action="store_true", help="Order ascending by date")
    s.set_defaults(func=cmd_search)

    g = sub.add_parser("get", help="Fetch one thesis by id")
    g.add_argument("--id", required=True, help="Tweet id")
    g.set_defaults(func=cmd_get)

    st = sub.add_parser("stats", help="Corpus overview (counts, date range, top tickers)")
    st.add_argument("--top", type=int, default=25, help="How many top tickers (default 25)")
    st.set_defaults(func=cmd_stats)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
