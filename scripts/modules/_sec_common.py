#!/usr/bin/env python3
"""Shared SEC EDGAR access helpers for the module scripts.

events.py and filings.py both run as standalone subprocess scripts (see
pipeline/_runner.py launches them with `python modules/<name>.py ...`), so the
interpreter sets __name__ == "__main__" and there is no parent package. That
rules out a package-relative import: there is no modules/__init__.py, and
`from . import ...` raises "attempted relative import with no known parent
package". The scripts must also not borrow a sibling skill's `data_advanced`
package — a skill is only portable if it ships its own dependencies, and
`data_advanced` lives in a different skill that may not be present at all.

So the skill vendors the three helpers it needs right here, and both scripts
import them exactly the way they already import `utils`: the interpreter puts a
script's own directory (modules/) on sys.path[0], so a plain `from _sec_common
import ...` resolves with no path juggling. These are thin, stable wrappers over
the public SEC EDGAR JSON API — vendoring them costs ~25 lines and buys
self-containment.
"""

import requests

# SEC's fair-access policy asks every caller to identify itself in the
# User-Agent; an anonymous request can be throttled or refused. A generic
# descriptive string satisfies the policy without committing a personal address
# to the repo — swap in a real contact if EDGAR ever rate-limits this skill.
SEC_HEADERS = {
	"User-Agent": "Serenity-Pipeline/1.0 (research; contact@example.com)",
	"Accept-Encoding": "gzip, deflate",
}


def get_cik_from_symbol(symbol):
	"""Resolve a ticker to its zero-padded 10-digit CIK via EDGAR's ticker map.

	EDGAR keys every other endpoint by CIK, not ticker, so this lookup is the
	entry point for any filings query. The map stores class-share tickers with a
	hyphen (BRK-B), so dots are normalized to hyphens before matching.
	"""
	url = "https://www.sec.gov/files/company_tickers.json"
	response = requests.get(url, headers=SEC_HEADERS, timeout=30)
	response.raise_for_status()
	data = response.json()

	symbol_upper = symbol.upper().replace(".", "-")
	for entry in data.values():
		if entry.get("ticker", "").upper() == symbol_upper:
			cik = str(entry.get("cik_str", entry.get("cik", "")))
			return cik.zfill(10)

	raise ValueError(f"CIK not found for symbol: {symbol}")


def get_company_info(cik):
	"""Fetch the company submissions blob (the recent-filings index) for a CIK."""
	url = f"https://data.sec.gov/submissions/CIK{cik}.json"
	response = requests.get(url, headers=SEC_HEADERS, timeout=30)
	response.raise_for_status()
	return response.json()
