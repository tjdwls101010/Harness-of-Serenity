#!/usr/bin/env python3
"""SEC company filings access and Management Discussion & Analysis (MD&A) extraction.

Provides access to SEC EDGAR filings including 10-K, 10-Q, 8-K, and other form types.
Includes MD&A section extraction from 10-K and 10-Q filings for fundamental analysis.
Uses SEC's official EDGAR API with company ticker to CIK mapping.

Args:
	symbol (str): Stock ticker symbol (e.g., "AAPL", "MSFT", "TSLA")
	--form (str): SEC form type filter (e.g., "10-K", "10-Q", "8-K", "all") (optional)
	--limit (int): Maximum number of filings to return, most recent first (optional)

Returns:
	cmd_filings:
	dict: {
		"data": [
			{
				"form": str,                     # SEC form type (e.g., "10-K", "10-Q")
				"filing_date": str,              # Date filed with SEC (YYYY-MM-DD)
				"report_date": str,              # Period end date (YYYY-MM-DD)
				"accession_number": str,         # SEC accession number (unique ID)
				"description": str,              # Primary document description
				"filing_url": str                # Direct URL to SEC EDGAR document
			},
			...
		],
		"metadata": {
			"symbol": str,                       # Ticker symbol
			"cik": str,                          # SEC Central Index Key
			"company_name": str,                 # Official company name
			"form_filter": str,                  # Applied form filter
			"total_results": int                 # Number of filings returned
		}
	}

	cmd_mda:
	dict: {
		"data": {
			"filing": {
				"form": str,                     # Form type (10-K or 10-Q)
				"filing_date": str,
				"report_date": str,
				"accession_number": str,
				"filing_url": str
			},
			"mda_content": str                   # Extracted MD&A section (plain text)
		},
		"metadata": {
			"symbol": str,
			"cik": str,
			"company_name": str,
			"form": str
		}
	}

Example:
	>>> python filings.py AAPL --form 10-K --limit 5
	{
		"data": [
			{
				"form": "10-K",
				"filing_date": "2025-10-31",
				"report_date": "2025-09-27",
				"accession_number": "0000320193-25-000106",
				"description": "10-K Annual Report",
				"filing_url": "https://www.sec.gov/Archives/edgar/data/320193/..."
			}
		],
		"metadata": {
			"symbol": "AAPL",
			"cik": "0000320193",
			"company_name": "Apple Inc.",
			"total_results": 5
		}
	}

	>>> python filings.py mda TSLA --form 10-Q
	>>> python filings.py MSFT --form 8-K --limit 20

Use Cases:
	- Track quarterly and annual filing dates for earnings analysis
	- Extract MD&A sections for NLP sentiment analysis and risk factor detection
	- Monitor 8-K filings for material events and corporate actions
	- Build fundamental datasets from structured 10-K/10-Q disclosures
	- Analyze filing lag between report date and filing date for quality screening
	- Download complete filing documents for detailed financial statement analysis

Notes:
	- No API key required (public SEC EDGAR access)
	- Rate limits: 10 requests per second per IP address (SEC enforced)
	- Data delays: Filings appear on EDGAR within minutes of submission
	- Form types: 10-K (annual), 10-Q (quarterly), 8-K (current events), 4 (insider trading)
	- MD&A extraction: Automated text extraction may miss edge cases (manual review recommended)
	- Filing URL: Direct link to primary document (HTML format)
	- CIK mapping: Automatic conversion from ticker symbol to SEC Central Index Key
	- Accession numbers: Unique SEC document identifiers (format: ####-##-######)
	- Empty results exit with code 1 and error JSON when no filings match the filter

See Also:
	- sec/insider.py: Form 4 insider trading filings
	- sec/institutions.py: Form 13F institutional holdings
	- sec/ftd.py: Failures to deliver data
	- analysis/sentiment.py: NLP sentiment analysis on MD&A text
"""

import argparse
import os
import re
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from utils import error_json, output_json, safe_run

# Vendored SEC helpers — same-dir import, resolves whether run as a script or
# imported (modules/ lands on sys.path[0]); see modules/_sec_common.py.
from _sec_common import SEC_HEADERS, get_cik_from_symbol, get_company_info


@safe_run
def cmd_filings(args):
	"""Get company SEC filings."""
	cik = get_cik_from_symbol(args.symbol)
	data = get_company_info(cik)

	filings = data.get("filings", {}).get("recent", {})
	if not filings:
		error_json(f"No filings found for {args.symbol} (CIK: {cik})")

	# Build list of filings
	results = []
	forms = filings.get("form", [])
	filing_dates = filings.get("filingDate", [])
	accession_numbers = filings.get("accessionNumber", [])
	primary_documents = filings.get("primaryDocument", [])
	report_dates = filings.get("reportDate", [])
	descriptions = filings.get("primaryDocDescription", [])

	form_filter = args.form.upper() if args.form else None

	for i in range(len(forms)):
		form_type = forms[i] if i < len(forms) else ""
		if form_filter and form_filter not in form_type.upper():
			continue

		accession = accession_numbers[i] if i < len(accession_numbers) else ""
		primary_doc = primary_documents[i] if i < len(primary_documents) else ""
		cik_int = int(cik)

		filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession.replace('-', '')}/{primary_doc}"

		results.append(
			{
				"form": form_type,
				"filing_date": filing_dates[i] if i < len(filing_dates) else None,
				"report_date": report_dates[i] if i < len(report_dates) else None,
				"accession_number": accession,
				"description": descriptions[i] if i < len(descriptions) else None,
				"filing_url": filing_url,
			}
		)

		if args.limit and len(results) >= args.limit:
			break

	if not results:
		if form_filter:
			error_json(f"No filings found for {args.symbol} matching filter '{form_filter}'")
		else:
			error_json(f"No filings found for {args.symbol}")

	output_json(
		{
			"data": results,
			"metadata": {
				"symbol": args.symbol,
				"cik": cik,
				"company_name": data.get("name", ""),
				"form_filter": form_filter,
				"total_results": len(results),
			},
		}
	)


@safe_run
def cmd_mda(args):
	"""Get Management Discussion and Analysis from 10-K or 10-Q filing."""
	cik = get_cik_from_symbol(args.symbol)
	data = get_company_info(cik)

	filings = data.get("filings", {}).get("recent", {})
	if not filings:
		output_json({"data": None, "metadata": {"symbol": args.symbol, "cik": cik, "error": "No filings found"}})
		return

	# Find the most recent 10-K or 10-Q filing
	target_form = args.form.upper() if args.form else "10-K"
	forms = filings.get("form", [])
	filing_dates = filings.get("filingDate", [])
	accession_numbers = filings.get("accessionNumber", [])
	primary_documents = filings.get("primaryDocument", [])
	report_dates = filings.get("reportDate", [])

	target_filing = None
	for i in range(len(forms)):
		form_type = forms[i] if i < len(forms) else ""
		if form_type == target_form:
			accession = accession_numbers[i] if i < len(accession_numbers) else ""
			primary_doc = primary_documents[i] if i < len(primary_documents) else ""
			cik_int = int(cik)

			filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession.replace('-', '')}/{primary_doc}"

			target_filing = {
				"form": form_type,
				"filing_date": filing_dates[i] if i < len(filing_dates) else None,
				"report_date": report_dates[i] if i < len(report_dates) else None,
				"accession_number": accession,
				"filing_url": filing_url,
			}
			break

	if not target_filing:
		output_json(
			{
				"data": None,
				"metadata": {
					"symbol": args.symbol,
					"cik": cik,
					"form": target_form,
					"error": f"No {target_form} filing found",
				},
			}
		)
		return

	# Fetch the filing document
	try:
		doc_response = requests.get(target_filing["filing_url"], headers=SEC_HEADERS, timeout=60)
		doc_response.raise_for_status()
		content = doc_response.text

		# Extract MD&A section (simplified extraction)
		# Look for common MD&A section markers
		mda_patterns = [
			r"MANAGEMENT['']?S DISCUSSION AND ANALYSIS",
			r"Item 7\.\s*Management",
			r"Item 2\.\s*Management",
			r"MD&A",
		]

		mda_start = None
		for pattern in mda_patterns:
			match = re.search(pattern, content, re.IGNORECASE)
			if match:
				mda_start = match.start()
				break

		# Find the end of MD&A (next Item section)
		mda_end = None
		if mda_start:
			end_patterns = [
				r"Item 8\.",
				r"Item 3\.",
				r"Item 6\.",
				r"PART IV",
				r"SIGNATURES",
			]
			for pattern in end_patterns:
				match = re.search(pattern, content[mda_start + 100 :], re.IGNORECASE)
				if match:
					mda_end = mda_start + 100 + match.start()
					break

		if mda_start and mda_end:
			mda_content = content[mda_start:mda_end]
			# Clean HTML tags (basic cleaning)
			mda_content = re.sub(r"<[^>]+>", " ", mda_content)
			mda_content = re.sub(r"\s+", " ", mda_content).strip()
			# Truncate to reasonable length
			if len(mda_content) > 50000:
				mda_content = mda_content[:50000] + "... [truncated]"
		else:
			mda_content = "MD&A section could not be automatically extracted. Please view the filing directly."

	except Exception as e:
		mda_content = f"Error fetching filing: {str(e)}"

	output_json(
		{
			"data": {
				"filing": target_filing,
				"mda_content": mda_content,
			},
			"metadata": {
				"symbol": args.symbol,
				"cik": cik,
				"company_name": data.get("name", ""),
				"form": target_form,
			},
		}
	)


def main():
	# The pipeline calls this script as `filings.py <ticker> --form S-3 ...` —
	# a flat call with no subcommand — so the parser is flat too. --mda flips
	# the mode from "list filings" to "extract MD&A from the latest filing".
	parser = argparse.ArgumentParser(description="SEC EDGAR filings retrieval")
	parser.add_argument("symbol", help="Ticker symbol")
	parser.add_argument("--form", default=None,
		help="Filter by form type (e.g. 10-K, 10-Q, 8-K, S-3)")
	parser.add_argument("--limit", type=int, default=20,
		help="Maximum number of filings to return")
	parser.add_argument("--mda", action="store_true", default=False,
		help="Extract MD&A from the latest --form filing (default 10-K) instead of listing")
	args = parser.parse_args()
	if args.mda:
		if not args.form:
			args.form = "10-K"
		cmd_mda(args)
	else:
		cmd_filings(args)


if __name__ == "__main__":
	main()
