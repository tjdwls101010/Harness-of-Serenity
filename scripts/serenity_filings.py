#!/usr/bin/env python3
"""Serenity SEC filings CLI — a thin, deterministic edgartools wrapper.

This is the SEC half of "code loads, the agent judges." It pulls the filing's own
NUMBERS (XBRL: segment/geographic revenue, customer concentration, inventory, purchase
obligations) and TEXT (sections, 8-K bodies) straight from EDGAR. It contains NO LLM,
no extraction schema, and no judgment — every value is reproduced verbatim from the
filing or emitted as null. A relationship, share, or contract the filing does not state
is absent here; the agent never fills it from memory.

	NUMBERS (pipeline-grade, byte-stable):
	  company TICKER
	  financials TICKER [--offset N]
	  xbrl-facts TICKER [--form 10-K] [--concept REGEX] [--dimension AXIS] [--statement TYPE] [--limit N]
	  segments TICKER [--axis AXIS] [--concept REGEX] [--form 10-K]
	  statement TICKER [--which income|balance|cashflow] [--view standard|detailed|summary] [--form 10-K]

	TEXT (for the serenity-filings subagent to read):
	  filings TICKER [--form 10-K] [--since YYYY-MM-DD] [--between A:B] [--limit N]
	  section TICKER [--form 10-K] [--item "Item 1A" | --named business|risk_factors|mda]
	  eightk TICKER [--limit N] [--item 1.01]
	  text ACCESSION [--format text|markdown]
	  context ACCESSION [--detail minimal|standard|full]

Identity (SEC requires it) from --identity, else $EDGAR_IDENTITY, else .env, else a
neutral fallback. All output is JSON; nulls are preserved; nothing is truncated. On a
network/parse failure the command emits {"error": "data_unavailable", ...} and exits 0,
so a caller always gets JSON, never a traceback.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_SCRIPTS, "modules"))

try:
	from utils import normalize as _normalize  # numpy/NaN/Timestamp -> JSON-safe
except Exception:  # noqa: BLE001 — utils is best-effort; fall back to a minimal normalizer
	def _normalize(obj):
		return obj

_DEFAULT_IDENTITY = "Harness Research chunghun1@naver.com"


# ---------------------------------------------------------------------------
# Setup / output helpers
# ---------------------------------------------------------------------------

def _setup_identity(args) -> None:
	identity = getattr(args, "identity", None) or os.environ.get("EDGAR_IDENTITY")
	if not identity:
		try:
			from dotenv import load_dotenv
			load_dotenv(os.path.join(os.path.dirname(_SCRIPTS), ".env"))
			identity = os.environ.get("EDGAR_IDENTITY")
		except Exception:  # noqa: BLE001
			pass
	identity = identity or _DEFAULT_IDENTITY
	from edgar import set_identity
	set_identity(identity)
	try:
		from edgar import use_local_storage
		use_local_storage(True)
	except Exception:  # noqa: BLE001 — caching is an optimization, never required
		pass


def _emit(obj) -> None:
	json.dump(_normalize(obj), sys.stdout, ensure_ascii=False, indent=2, default=str)
	print()


def _error(detail: str, **ctx):
	return {"error": "data_unavailable", "detail": str(detail), **ctx}


def _records(df):
	"""DataFrame -> list-of-dict records, JSON-safe. None/empty -> []."""
	if df is None:
		return []
	try:
		if hasattr(df, "empty") and df.empty:
			return []
		if hasattr(df, "to_dict"):
			return df.reset_index().to_dict(orient="records") if hasattr(df, "reset_index") else df.to_dict(orient="records")
	except Exception:  # noqa: BLE001
		pass
	return df if isinstance(df, list) else []


def _retry(fn, tries: int = 2):
	"""Run fn, retrying once on any exception (transient SEC throttling). Re-raises last."""
	last = None
	for _ in range(max(1, tries)):
		try:
			return fn()
		except Exception as e:  # noqa: BLE001
			last = e
	raise last


def _company(ticker: str):
	from edgar import Company
	from edgar.entity.core import CompanyNotFoundError  # type: ignore
	c = _retry(lambda: Company(ticker.upper()))
	if getattr(c, "not_found", False):
		raise CompanyNotFoundError(ticker)
	# Touch .cik to force the submissions load now (so failures surface as our error JSON).
	_ = c.cik
	return c


# ---------------------------------------------------------------------------
# NUMBERS
# ---------------------------------------------------------------------------

def cmd_company(args):
	try:
		c = _company(args.ticker)
	except Exception as e:  # noqa: BLE001
		return _error(e, ticker=args.ticker.upper())
	out = {"ticker": args.ticker.upper()}
	for attr in ("cik", "name", "tickers", "industry", "public_float", "shares_outstanding"):
		out[attr] = _safe_attr(c, attr)
	out["exchanges"] = _safe_call(c, "get_exchanges")
	return out


def cmd_financials(args):
	try:
		c = _company(args.ticker)
		fin = _retry(c.get_financials)
	except Exception as e:  # noqa: BLE001
		return _error(e, ticker=args.ticker.upper())
	if fin is None:
		return _error("no financials", ticker=args.ticker.upper())
	offset = getattr(args, "offset", 0) or 0
	metrics = (
		"get_revenue", "get_net_income", "get_operating_income", "get_free_cash_flow",
		"get_operating_cash_flow", "get_capital_expenditures", "get_total_assets",
		"get_total_liabilities", "get_stockholders_equity",
	)
	out = {"ticker": args.ticker.upper(), "offset": offset}
	for m in metrics:
		key = m[len("get_"):]
		fn = getattr(fin, m, None)
		if not callable(fn):
			out[key] = None
			continue
		try:
			out[key] = fn(offset=offset)
		except TypeError:
			try:
				out[key] = fn()
			except Exception:  # noqa: BLE001
				out[key] = None
		except Exception:  # noqa: BLE001
			out[key] = None
	return out


def cmd_xbrl_facts(args):
	try:
		c = _company(args.ticker)
		filing = _retry(lambda: c.latest(args.form))
		xb = filing.xbrl() if filing is not None else None
	except Exception as e:  # noqa: BLE001
		return _error(e, ticker=args.ticker.upper(), form=args.form)
	if xb is None:
		return _error("no XBRL in latest filing", ticker=args.ticker.upper(), form=args.form)
	try:
		q = xb.query(include_dimensions=bool(args.dimension))
		if args.concept:
			q = q.by_concept(args.concept)
		if args.dimension:
			q = q.by_dimension(args.dimension)
		if args.statement:
			q = q.by_statement_type(args.statement)
		df = q.to_dataframe()
	except Exception as e:  # noqa: BLE001
		return _error(e, ticker=args.ticker.upper(), form=args.form)
	rows = _records(df)
	if args.limit:
		rows = rows[: args.limit]
	return {"ticker": args.ticker.upper(), "form": args.form, "count": len(rows), "facts": rows}


def cmd_segments(args):
	try:
		c = _company(args.ticker)
		filing = _retry(lambda: c.latest(args.form))
		xb = filing.xbrl() if filing is not None else None
	except Exception as e:  # noqa: BLE001
		return _error(e, ticker=args.ticker.upper(), form=args.form)
	if xb is None:
		return _error("no XBRL in latest filing", ticker=args.ticker.upper(), form=args.form)
	try:
		q = xb.query(include_dimensions=True).by_concept(args.concept).by_dimension(args.axis)
		df = q.to_dataframe()
	except Exception as e:  # noqa: BLE001
		return _error(e, ticker=args.ticker.upper(), form=args.form, axis=args.axis)
	return {"ticker": args.ticker.upper(), "form": args.form, "axis": args.axis,
			"concept": args.concept, "segments": _records(df)}


def cmd_statement(args):
	try:
		c = _company(args.ticker)
		filing = _retry(lambda: c.latest(args.form))
		xb = filing.xbrl() if filing is not None else None
	except Exception as e:  # noqa: BLE001
		return _error(e, ticker=args.ticker.upper(), form=args.form)
	if xb is None:
		return _error("no XBRL in latest filing", ticker=args.ticker.upper(), form=args.form)
	method = {
		"income": ("income_statement",),
		"balance": ("balance_sheet", "balance_statement"),
		"cashflow": ("cashflow_statement", "cash_flow_statement", "cashflow"),
	}.get(args.which, ("income_statement",))
	stmts = getattr(xb, "statements", None)
	stmt_obj = None
	for name in method:
		fn = getattr(stmts, name, None)
		if callable(fn):
			try:
				stmt_obj = fn()
				break
			except Exception:  # noqa: BLE001
				continue
	if stmt_obj is None:
		return _error(f"statement '{args.which}' unavailable", ticker=args.ticker.upper(), form=args.form)
	try:
		df = stmt_obj.to_dataframe(view=args.view) if args.view else stmt_obj.to_dataframe()
	except TypeError:
		df = stmt_obj.to_dataframe()
	except Exception as e:  # noqa: BLE001
		return _error(e, ticker=args.ticker.upper(), form=args.form)
	return {"ticker": args.ticker.upper(), "form": args.form, "which": args.which,
			"view": args.view, "rows": _records(df)}


# ---------------------------------------------------------------------------
# TEXT
# ---------------------------------------------------------------------------

def cmd_filings(args):
	try:
		c = _company(args.ticker)
		kwargs = {}
		if args.form:
			kwargs["form"] = args.form
		if args.between:
			kwargs["filing_date"] = args.between
		elif args.since:
			kwargs["filing_date"] = f"{args.since}:"
		fs = _retry(lambda: c.get_filings(**kwargs))
		if hasattr(fs, "head"):
			fs = fs.head(args.limit)
	except Exception as e:  # noqa: BLE001
		return _error(e, ticker=args.ticker.upper(), form=args.form)
	out = []
	try:
		for f in fs:
			out.append({
				"form": _safe_attr(f, "form"),
				"filing_date": _safe_attr(f, "filing_date"),
				"accession_no": _safe_attr(f, "accession_no"),
				"report_date": _safe_attr(f, "report_date"),
				"primary_document": _safe_attr(f, "primary_document"),
			})
	except Exception as e:  # noqa: BLE001
		return _error(e, ticker=args.ticker.upper())
	return {"ticker": args.ticker.upper(), "form": args.form, "count": len(out), "filings": out}


_NAMED_SECTION = {
	"business": "business",
	"risk_factors": "risk_factors",
	"mda": "management_discussion",
}


def cmd_section(args):
	try:
		c = _company(args.ticker)
		filing = _retry(lambda: c.latest(args.form))
		obj = filing.obj() if filing is not None else None
	except Exception as e:  # noqa: BLE001
		return _error(e, ticker=args.ticker.upper(), form=args.form)
	if obj is None:
		return _error("filing object unavailable", ticker=args.ticker.upper(), form=args.form)
	text = None
	used = None
	if args.named:
		prop = _NAMED_SECTION.get(args.named)
		if prop and hasattr(obj, prop):
			try:
				text = getattr(obj, prop)
				used = f"named:{args.named}"
			except Exception:  # noqa: BLE001
				text = None
	elif args.item:
		try:
			text = obj[args.item]
			used = f"item:{args.item}"
		except Exception:  # noqa: BLE001
			text = None
	if text is None:
		return _error(
			"section unavailable (TenQ lacks named sections — use --item 'Item 2' / 'Item 1A')",
			ticker=args.ticker.upper(), form=args.form,
			requested=args.named or args.item,
		)
	return {"ticker": args.ticker.upper(), "form": args.form, "section": used, "text": str(text)}


def cmd_eightk(args):
	try:
		c = _company(args.ticker)
		fs = _retry(lambda: c.get_filings(form="8-K"))
		if hasattr(fs, "head"):
			fs = fs.head(args.limit)
	except Exception as e:  # noqa: BLE001
		return _error(e, ticker=args.ticker.upper())
	out = []
	try:
		for f in fs:
			rec = {
				"filing_date": _safe_attr(f, "filing_date"),
				"accession_no": _safe_attr(f, "accession_no"),
			}
			try:
				ek = f.obj()
				rec["items"] = list(getattr(ek, "items", []) or [])
				if args.item:
					key = args.item if str(args.item).startswith("Item") else f"Item {args.item}"
					code = key.replace("Item ", "")
					rec["body"] = ek[code] if key in rec["items"] else None  # NO EightK.get()
				if getattr(ek, "has_press_release", False):
					prs = getattr(ek, "press_releases", None)
					if prs:
						rec["press_release"] = prs[0].to_markdown()
			except Exception as e:  # noqa: BLE001
				rec["parse_error"] = str(e)
			out.append(rec)
	except Exception as e:  # noqa: BLE001
		return _error(e, ticker=args.ticker.upper())
	return {"ticker": args.ticker.upper(), "count": len(out), "events": out}


def cmd_text(args):
	try:
		from edgar import get_by_accession_number
		filing = _retry(lambda: get_by_accession_number(args.accession))
	except Exception as e:  # noqa: BLE001
		return _error(e, accession=args.accession)
	if filing is None:
		return _error("filing not found", accession=args.accession)
	try:
		if args.format == "markdown":
			body = filing.markdown(include_page_breaks=True) if hasattr(filing, "markdown") else filing.text()
		else:
			body = filing.text()
	except Exception as e:  # noqa: BLE001
		return _error(e, accession=args.accession)
	return {"accession": args.accession, "format": args.format,
			"form": _safe_attr(filing, "form"), "text": str(body)}


def cmd_context(args):
	try:
		from edgar import get_by_accession_number
		filing = _retry(lambda: get_by_accession_number(args.accession))
		obj = filing.obj() if filing is not None else None
	except Exception as e:  # noqa: BLE001
		return _error(e, accession=args.accession)
	if obj is None or not hasattr(obj, "to_context"):
		return _error("to_context unavailable for this filing", accession=args.accession)
	try:
		ctx = obj.to_context(detail=args.detail)
	except Exception as e:  # noqa: BLE001
		return _error(e, accession=args.accession)
	return {"accession": args.accession, "detail": args.detail, "context": str(ctx)}


# ---------------------------------------------------------------------------
# small reflective helpers
# ---------------------------------------------------------------------------

def _safe_attr(obj, name):
	try:
		val = getattr(obj, name, None)
		return val() if callable(val) else val
	except Exception:  # noqa: BLE001
		return None


def _safe_call(obj, name):
	try:
		fn = getattr(obj, name, None)
		return fn() if callable(fn) else None
	except Exception:  # noqa: BLE001
		return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
	p = argparse.ArgumentParser(prog="serenity_filings.py",
		description="Thin deterministic edgartools CLI (SEC numbers + text; no LLM, no judgment).")
	p.add_argument("--identity", default=None, help="SEC EDGAR identity 'Name email@x' (else $EDGAR_IDENTITY/.env)")
	sub = p.add_subparsers(dest="command", required=True)

	def add_ticker(sp):
		sp.add_argument("ticker", help="Ticker symbol")

	sp = sub.add_parser("company", help="Company identity facts"); add_ticker(sp); sp.set_defaults(func=cmd_company)

	sp = sub.add_parser("financials", help="Standardized financial metrics"); add_ticker(sp)
	sp.add_argument("--offset", type=int, default=0, help="Periods back (0 = latest)"); sp.set_defaults(func=cmd_financials)

	sp = sub.add_parser("xbrl-facts", help="Query raw XBRL facts"); add_ticker(sp)
	sp.add_argument("--form", default="10-K"); sp.add_argument("--concept", default=None, help="Concept name regex")
	sp.add_argument("--dimension", default=None, help="Dimension axis (implies include_dimensions)")
	sp.add_argument("--statement", default=None, help="Statement type filter")
	sp.add_argument("--limit", type=int, default=None); sp.set_defaults(func=cmd_xbrl_facts)

	sp = sub.add_parser("segments", help="Segment/geographic revenue concentration"); add_ticker(sp)
	sp.add_argument("--form", default="10-K")
	sp.add_argument("--axis", default="StatementBusinessSegmentsAxis", help="Dimension axis")
	sp.add_argument("--concept", default="RevenueFromContractWithCustomer"); sp.set_defaults(func=cmd_segments)

	sp = sub.add_parser("statement", help="A full financial statement as rows"); add_ticker(sp)
	sp.add_argument("--which", choices=["income", "balance", "cashflow"], default="income")
	sp.add_argument("--view", choices=["standard", "detailed", "summary"], default=None)
	sp.add_argument("--form", default="10-K"); sp.set_defaults(func=cmd_statement)

	sp = sub.add_parser("filings", help="Enumerate filings"); add_ticker(sp)
	sp.add_argument("--form", default=None); sp.add_argument("--since", default=None, help="YYYY-MM-DD (from)")
	sp.add_argument("--between", default=None, help="YYYY-MM-DD:YYYY-MM-DD")
	sp.add_argument("--limit", type=int, default=10); sp.set_defaults(func=cmd_filings)

	sp = sub.add_parser("section", help="A named section or item of a filing"); add_ticker(sp)
	sp.add_argument("--form", default="10-K")
	sp.add_argument("--named", choices=["business", "risk_factors", "mda"], default=None)
	sp.add_argument("--item", default=None, help="e.g. 'Item 1A' (10-K/Q) or 'Item 1.01' (8-K)")
	sp.set_defaults(func=cmd_section)

	sp = sub.add_parser("eightk", help="Recent 8-K events (+ optional item body)"); add_ticker(sp)
	sp.add_argument("--limit", type=int, default=5); sp.add_argument("--item", default=None, help="e.g. 1.01")
	sp.set_defaults(func=cmd_eightk)

	sp = sub.add_parser("text", help="Full filing text by accession number")
	sp.add_argument("accession", help="e.g. 0000320193-23-000106")
	sp.add_argument("--format", choices=["text", "markdown"], default="text"); sp.set_defaults(func=cmd_text)

	sp = sub.add_parser("context", help="Routing summary by accession number (NOT full text)")
	sp.add_argument("accession")
	sp.add_argument("--detail", choices=["minimal", "standard", "full"], default="standard")
	sp.set_defaults(func=cmd_context)

	return p


def main():
	args = build_parser().parse_args()
	_setup_identity(args)
	try:
		result = args.func(args)
	except Exception as e:  # noqa: BLE001 — last-resort guard: always emit JSON, never a traceback
		result = _error(f"{type(e).__name__}: {e}", command=getattr(args, "command", None))
	_emit(result)


if __name__ == "__main__":
	main()
