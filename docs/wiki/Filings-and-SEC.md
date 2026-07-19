# Filings and SEC

`scripts/serenity_filings.py` — the deterministic SEC surface. Every command, plus the design
reasoning for why filings are handled differently from market data.

## Why filings are a separate layer

Market data is structurally uniform. Every company reports a market cap in the same place, so a
fixed fetch-and-pick pipeline works.

Filing content is not. Customer concentration might live in a revenue note, a risk factor, or a
segment footnote. Different filers tag it differently, and the same filer changes across years.
Any fixed parser eventually hits a filing shaped differently than it expects — and its failure mode
is the worst one available: it returns nothing, which is indistinguishable from "the company does
not disclose this."

So the work is split:

| Job | Handled by | Why |
| --- | --- | --- |
| **Finding** the disclosure — which section, which concept, which cross-reference | The [`serenity-filings` subagent](Agent-Harness.md#serenity-filings) | Adaptive; requires reading and judgment about *where* to look |
| **Extracting** the number | `scripts/serenity_filings.py` → edgartools XBRL | Deterministic; the concept is cited so the figure is reproducible |

The number stays reproducible even though an agent orchestrated the lookup. That is the point of
the split — adaptive navigation, deterministic extraction.

An earlier design put an XBRL parser inside the pipeline. It was retired for exactly the silent-null
failure above; its code survives as a frozen reference at `scripts/pipeline/legacy/_sec_xbrl.py`
and the validator asserts it stays unimported.

## Configuration

SEC EDGAR policy requires a contact string in the User-Agent on every request. Resolution order:

1. `--identity "Your Name you@example.com"` on the command line
2. `EDGAR_IDENTITY` in the environment
3. `EDGAR_IDENTITY` from `.env` — this CLI *does* load `.env`, unlike the macro modules
4. A built-in default identity

Set your own. Requests are attributed to whatever identity is sent, and the default carries the
maintainer's contact.

```bash
# In .env
EDGAR_IDENTITY="Jane Doe jane@example.com"
```

**Caching** is enabled through edgartools local storage when available, and treated as an
optimization — a failure to enable it is swallowed rather than raised. **Retries**: each EDGAR
call retries once on any exception, to absorb transient throttling. There is no rate limiter
beyond that; pacing is delegated to edgartools.

## The error contract

Every command **always exits 0**. A failure returns structured JSON:

```json
{
  "error": "data_unavailable",
  "detail": "HTTPError: 403 Client Error: Forbidden",
  "command": "segments",
  "ticker": "TSM"
}
```

A caller always gets parseable JSON, never a traceback. This matters because the subagent calling
these commands has to distinguish "the filing is silent on this" from "the fetch failed" — and a
crash would collapse both into the same nothing.

**Nulls are preserved.** A field the filing did not disclose comes back `null`, never `0` and
never omitted.

---

## Commands — numbers

These produce pipeline-grade, byte-stable figures with the XBRL concept identified.

### `company`

Identity and basic facts.

```bash
$PY scripts/serenity_filings.py company TSM
```

Returns CIK, name, tickers, industry, public float, shares outstanding, and exchanges.

### `financials`

Nine standardized metrics from the latest filing.

```bash
$PY scripts/serenity_filings.py financials TSM
$PY scripts/serenity_filings.py financials TSM --offset 1   # one period back
```

| Flag | Default | Effect |
| --- | --- | --- |
| `--offset` | `0` | Periods back; `0` is the latest |

Covers revenue, net income, operating income, free cash flow, operating cash flow, capital
expenditures, total assets, total liabilities, stockholders' equity.

### `xbrl-facts`

The general-purpose XBRL query — the workhorse for disclosures the income statement does not
carry.

```bash
# Customer concentration
$PY scripts/serenity_filings.py xbrl-facts TSM \
    --concept "Concentration" --dimension MajorCustomersAxis

# Inventory composition
$PY scripts/serenity_filings.py xbrl-facts TSM --concept "InventoryNet" --limit 20

# Purchase obligations
$PY scripts/serenity_filings.py xbrl-facts TSM --concept "PurchaseObligation"
```

| Flag | Default | Effect |
| --- | --- | --- |
| `--form` | `10-K` | Filing form to query |
| `--concept` | — | Concept-name regex |
| `--dimension` | — | Dimension axis; implies dimensional facts are included |
| `--statement` | — | Statement-type filter |
| `--limit` | — | Cap on rows returned |

### `segments`

Revenue by business segment or geography — the disclosure most often needed and least often
present in a summary.

```bash
# By geography
$PY scripts/serenity_filings.py segments TSM --axis StatementGeographicalAxis

# By business segment (default)
$PY scripts/serenity_filings.py segments TSM --axis StatementBusinessSegmentsAxis
```

| Flag | Default |
| --- | --- |
| `--form` | `10-K` |
| `--axis` | `StatementBusinessSegmentsAxis` |
| `--concept` | `RevenueFromContractWithCustomer` |

### `statement`

A full financial statement as structured rows.

```bash
$PY scripts/serenity_filings.py statement TSM --which balance
$PY scripts/serenity_filings.py statement TSM --which cashflow --view detailed
```

| Flag | Options | Default |
| --- | --- | --- |
| `--which` | `income`, `balance`, `cashflow` | `income` |
| `--view` | `standard`, `detailed`, `summary` | library default |
| `--form` | any form | `10-K` |

---

## Commands — text

For narrative content: relationships, critical inputs, financing structure, material events.

### `filings`

The filing index.

```bash
$PY scripts/serenity_filings.py filings TSM --form 10-K --limit 3
$PY scripts/serenity_filings.py filings TSM --form 8-K --since 2026-01-01
$PY scripts/serenity_filings.py filings TSM --between 2025-01-01:2025-12-31
```

| Flag | Default | Effect |
| --- | --- | --- |
| `--form` | all | Form type filter |
| `--since` | — | Lower bound, `YYYY-MM-DD` |
| `--between` | — | `YYYY-MM-DD:YYYY-MM-DD`. Takes precedence over `--since`. |
| `--limit` | `10` | Maximum filings |

Returns form, filing date, accession number, report date, and primary document per filing.

### `section`

A named section or numbered item from the latest filing of a form.

```bash
$PY scripts/serenity_filings.py section TSM --form 10-K --named business
$PY scripts/serenity_filings.py section TSM --form 10-K --named risk_factors
$PY scripts/serenity_filings.py section TSM --form 10-K --item "Item 1A"
```

| Flag | Options |
| --- | --- |
| `--form` | Default `10-K` |
| `--named` | `business`, `risk_factors`, `mda` |
| `--item` | e.g. `Item 1A` for 10-K/10-Q, `Item 1.01` for 8-K |

Note that `--named mda` maps to edgartools' `management_discussion` attribute, and **10-Q objects
do not expose it** — use `--item` on a quarterly filing.

### `eightk`

Recent 8-K filings with their item codes, and press releases where attached.

```bash
$PY scripts/serenity_filings.py eightk TSM --limit 5
$PY scripts/serenity_filings.py eightk TSM --item 1.01     # material agreements
```

| Flag | Default |
| --- | --- |
| `--limit` | `5` |
| `--item` | — |

Item codes worth knowing: **1.01** material definitive agreement, **2.02** results of operations,
**5.02** officer departure or appointment, **8.01** other material events.

### `text`

Full text of one filing by accession number.

```bash
$PY scripts/serenity_filings.py text 0000320193-23-000106
$PY scripts/serenity_filings.py text 0000320193-23-000106 --format markdown
```

| Flag | Options | Default |
| --- | --- | --- |
| `--format` | `text`, `markdown` | `text` |

Markdown preserves structure and page breaks, which makes locating a section easier.

### `context`

A routing summary of a filing — what is in it and where, without pulling the full text.

```bash
$PY scripts/serenity_filings.py context 0000320193-23-000106 --detail standard
```

| Flag | Options | Default |
| --- | --- | --- |
| `--detail` | `minimal`, `standard`, `full` | `standard` |

Use this before `text` on a large filing.

---

## What the subagent brings back

When invoked through the agent harness, `serenity-filings` returns five buckets, each with the
*degree* attached — a name without a percentage or a contract term is not usable evidence:

| Bucket | Contains |
| --- | --- |
| `company_relationships` | Named customers, suppliers, partners with % of revenue, dollar value, or contract term |
| `country_exposure` | Where the company manufactures, sells, and sources, with percentages, plus export-control / tariff / sanction flags |
| `critical_inputs` | Sole-source and dual-source dependencies, lead times, named sources |
| `financing_facts` | ATM programs and equity raises (size, and size relative to market cap), convertibles (coupon, size, maturity), debt terms, customer prepayments, offtake agreements, buybacks |
| `recent_material_events` | 8-K items with date and item code |

Two rules govern the output:

- **Quote and cite.** Every fact carries its form and item, or its XBRL concept.
- **Silence is `null`.** Never `0`, never an inferred value. A filing that does not address
  something produces an explicit empty bucket, not a guess.

Financing facts in particular are reported **exactly and neutrally** — size, coupon, maturity, and
size relative to market cap — with no "dilutive" label attached. Whether an ATM program de-risks
the business or merely transfers risk to new shareholders is the
[funded-versus-self-minted](Concepts.md#funded-versus-self-minted) judgment, and it belongs to the
analyst.

## Known edgartools traps

Pinned against edgartools 5.35.1 and worth knowing if you extend this CLI — the type annotations
do not reflect these:

- There is no `EightK.get()`. Access items by subscript, and only after confirming the item is
  present in `.items`.
- `FactQuery.by_value` takes a callable, not a value.
- There is no top-level `get_company`.
- MD&A is `.management_discussion`, not `.mda`, and 10-Q objects do not have it.

## Rate limits and etiquette

SEC EDGAR is a free public service with a fair-use policy. Send a real identity, do not
parallelize aggressively, and expect throttling under load. A `403` usually means the identity
string is missing or malformed rather than that you are blocked.

If EDGAR blocks or throttles you mid-analysis, the resulting nulls are indistinguishable from
genuine non-disclosure. The method's response is explicit: a nulled line **blocks** the analysis
until it is reconciled through a successful read, rather than proceeding on the assumption that
silence means absence.

---

**Next:** [Agent Harness](Agent-Harness.md) for how the subagent is invoked. ·
[Back to index](README.md)
