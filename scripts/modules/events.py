#!/usr/bin/env python3
"""SEC 8-K supply chain event extraction.

Extracts supply-chain-related events from recent 8-K filings using
SEC EDGAR API and regex pattern matching. No LLM required.

Commands:
	events: Extract supply-chain-related events from recent 8-K filings

Args:
	symbol (str): Stock ticker symbol (e.g., "AAPL", "NVDA")
	--limit (int): Max 8-K filings to check (default: 10)
	--days (int): Lookback window in days (default: 180)

Returns:
	cmd_events:
	dict: {
		"data": [{
			"filing_date": str,
			"accession_number": str,
			"filing_url": str,
			"event_type": str,
			"supply_chain_relevance": str,
			"context": str,
			"confidence": str
		}],
		"metadata": {
			"symbol": str,
			"cik": str,
			"company_name": str,
			"filings_checked": int,
			"supply_chain_events_found": int
		}
	}
"""

import argparse
import os
import re
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from utils import output_json, safe_run

# Vendored SEC helpers live alongside this script in modules/; the interpreter
# puts that dir on sys.path[0] whether we run as a script or get imported, so a
# plain import resolves either way (see modules/_sec_common.py for why).
from _sec_common import SEC_HEADERS, get_cik_from_symbol, get_company_info


def _strip_html_tags(text):
	"""Remove HTML tags and normalize whitespace."""
	text = re.sub(r"<[^>]+>", " ", text)
	text = re.sub(r"&nbsp;", " ", text)
	text = re.sub(r"&amp;", "&", text)
	text = re.sub(r"&lt;", "<", text)
	text = re.sub(r"&gt;", ">", text)
	text = re.sub(r"&#\d+;", " ", text)
	text = re.sub(r"\s+", " ", text).strip()
	return text


_8K_ITEM_TYPES = {
	"1.01": "Material Agreement",
	"1.02": "Termination of Material Agreement",
	"2.01": "Completion of Acquisition/Disposition",
	"2.05": "Costs of Exit/Disposal",
	"2.06": "Material Impairments",
	"7.01": "Regulation FD Disclosure",
	"8.01": "Other Events",
}

_8K_SC_PATTERNS = [
	r"(?:supply|supplier|vendor|procurement)",
	r"(?:material\s+agreement|definitive\s+agreement|purchase\s+agreement)",
	r"(?:acquisition|merger|joint\s+venture|partnership)",
	r"(?:manufacturing|production|capacity|facility)",
	r"(?:tariff|trade|export|import|sanction)",
	r"(?:shortage|disruption|force\s+majeure|allocation)",
	r"(?:contract|offtake|supply\s+agreement|purchase\s+order)",
]


@safe_run
def cmd_events(args):
	"""Extract supply-chain-related events from recent 8-K filings."""
	symbol = args.symbol.upper()
	limit = args.limit
	days = args.days

	cik = get_cik_from_symbol(symbol)
	data = get_company_info(cik)
	company_name = data.get("name", "")

	filings = data.get("filings", {}).get("recent", {})
	if not filings:
		output_json({
			"data": [],
			"metadata": {"symbol": symbol, "cik": cik, "company_name": company_name,
						"filings_checked": 0, "supply_chain_events_found": 0},
		})
		return

	from datetime import datetime, timedelta
	cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

	forms = filings.get("form", [])
	filing_dates = filings.get("filingDate", [])
	accession_numbers = filings.get("accessionNumber", [])
	primary_documents = filings.get("primaryDocument", [])

	eight_k_filings = []
	for i in range(len(forms)):
		if forms[i] == "8-K" and i < len(filing_dates):
			if filing_dates[i] >= cutoff_date:
				accession = accession_numbers[i] if i < len(accession_numbers) else ""
				primary_doc = primary_documents[i] if i < len(primary_documents) else ""
				cik_int = int(cik)
				filing_url = (
					f"https://www.sec.gov/Archives/edgar/data/{cik_int}/"
					f"{accession.replace('-', '')}/{primary_doc}"
				)
				eight_k_filings.append({
					"filing_date": filing_dates[i],
					"accession_number": accession,
					"filing_url": filing_url,
				})
				if len(eight_k_filings) >= limit:
					break

	sc_events = []
	for filing in eight_k_filings:
		time.sleep(0.15)
		try:
			resp = requests.get(
				filing["filing_url"], headers=SEC_HEADERS, timeout=30,
			)
			resp.raise_for_status()
			content = _strip_html_tags(resp.text)

			relevance_matches = []
			for pattern in _8K_SC_PATTERNS:
				if re.search(pattern, content, re.IGNORECASE):
					relevance_matches.append(pattern.replace(r"(?:", "").replace(")", "").replace("|", "/"))

			if relevance_matches:
				event_type = "Other"
				for item_num, item_name in _8K_ITEM_TYPES.items():
					if re.search(rf"Item\s+{re.escape(item_num)}", content, re.IGNORECASE):
						event_type = f"{item_num}: {item_name}"
						break

				for pattern in _8K_SC_PATTERNS:
					m = re.search(pattern, content, re.IGNORECASE)
					if m:
						start = max(0, m.start() - 200)
						end = min(len(content), m.end() + 200)
						context = content[start:end].strip()[:400]
						break
				else:
					context = content[:400]

				confidence = "high" if len(relevance_matches) >= 3 else "medium" if len(relevance_matches) >= 2 else "low"

				sc_events.append({
					"filing_date": filing["filing_date"],
					"accession_number": filing["accession_number"],
					"filing_url": filing["filing_url"],
					"event_type": event_type,
					"supply_chain_relevance": ", ".join(relevance_matches[:5]),
					"context": context,
					"confidence": confidence,
				})

		except Exception:
			continue

	output_json({
		"data": sc_events,
		"metadata": {
			"symbol": symbol,
			"cik": cik,
			"company_name": company_name,
			"filings_checked": len(eight_k_filings),
			"supply_chain_events_found": len(sc_events),
		},
	})


def main():
	parser = argparse.ArgumentParser(description="SEC 8-K supply chain events")
	sub = parser.add_subparsers(dest="command", required=True)

	sp = sub.add_parser("events", help="Extract supply chain events from 8-K filings")
	sp.add_argument("symbol", help="Ticker symbol")
	sp.add_argument("--limit", type=int, default=10, help="Max 8-K filings to check")
	sp.add_argument("--days", type=int, default=180, help="Lookback window in days")
	sp.set_defaults(func=cmd_events)

	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
