"""Probe the real provider interfaces the adapters parse.

edgartools and yfinance hand back Python objects, not JSON, so no recorded
payload can pin ``EntityFiling.acceptance_datetime`` being a ``datetime`` or
``TenQ`` lacking ``.risk_factors``. Those facts live in a pinned library
release, and the only thing that notices when a release moves them is a probe
that builds the real object and reads the attribute the adapter reads.

Every probe here goes through the adapter's own seam rather than calling the
library directly: a probe that reproduces the adapter's parsing in test code
passes while the adapter is broken, which is the defect class this file exists
to end.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from serenity_core.providers.filings import EdgarToolsBackend, FilingsProvider
from serenity_core.providers.public_data import public_data_catalog


pytestmark = pytest.mark.live

IDENTITY = {"ticker": "NVDA", "cik": "0001045810", "issuer": "NVIDIA CORP"}


def _backend(capability: str, **arguments: object) -> dict:
    result = EdgarToolsBackend().execute({"identity": IDENTITY, "capability": capability, **arguments})
    assert result is not None, f"{capability} returned no record for a filer that files it"
    return dict(result)


def _is_instant(value: object) -> bool:
    return isinstance(value, str) and datetime.fromisoformat(value.replace("Z", "+00:00")) is not None


def test_submissions_carries_a_filing_anchor_and_exact_raw_bytes() -> None:
    result = _backend("submissions")

    assert isinstance(result["raw_content"], bytes)
    assert _is_instant(result["filing"]["available_at"])
    assert result["filing"]["accession"]
    assert result["data"]["submissions"]["cik"]


def test_submissions_is_consumable_evidence_through_the_provider() -> None:
    """The measure of done for the capability, not for the backend method."""

    envelope = FilingsProvider().execute({"identity": IDENTITY, "capability": "submissions"}, cutoff=None).to_dict()

    assert envelope["status"] == "available", envelope.get("error")
    assert envelope["temporal"]["available_at"] is not None
    assert envelope["source"]["uri"] == "https://data.sec.gov/submissions/CIK0001045810.json"


def test_entity_filing_still_exposes_acceptance_as_an_instant() -> None:
    """``EntityFiling.acceptance_datetime`` is a ``datetime``; a str would silently
    reach ``_filing_metadata``'s string branch and skip UTC normalisation."""

    result = _backend("filings", form="10-K", limit=1)

    assert _is_instant(result["filing"]["available_at"])
    assert result["data"]["filings"][0]["form"] == "10-K"


def test_filing_text_by_accession_keeps_its_acceptance_instant() -> None:
    """``get_by_accession_number`` returns a bare ``Filing`` with no acceptance
    attribute at all, so availability has to come from the entity path."""

    accession = _backend("filings", form="10-Q", limit=1)["data"]["filings"][0]["accession"]

    result = _backend("filing_text", accession=accession, format="text")

    assert _is_instant(result["filing"]["available_at"])
    assert result["data"]["text"]


def test_named_sections_resolve_on_a_ten_k() -> None:
    for named in ("business", "risk_factors", "mda"):
        result = _backend("section", form="10-K", named=named, limit=1)
        assert result["data"]["text"], f"10-K {named} came back empty"


def test_named_sections_resolve_on_a_ten_q_through_part_qualified_keys() -> None:
    """``TenQ`` exposes no ``.risk_factors`` property, and bare ``tenq['Item 1']``
    silently resolves to Part I, so the resolver has to be part-qualified."""

    result = _backend("section", form="10-Q", named="risk_factors", limit=1)

    assert result["data"]["text"]
    assert result["data"]["section"] == "risk_factors"


def test_a_section_a_form_does_not_define_is_invalid_not_undisclosed() -> None:
    """A 10-Q has no Business section. Answering ``not_disclosed`` would make an
    absence of adapter support indistinguishable from an absence of disclosure."""

    result = _backend("section", form="10-Q", named="business", limit=1)

    assert result["status"] == "invalid"
    assert "10-Q" in result["reason"] and "business" in result["reason"]


def test_xbrl_rows_carry_the_columns_a_derived_fact_selects_on() -> None:
    result = _backend("xbrl_facts", form="10-Q", concept="Revenues", limit=5)

    row = result["data"]["facts"][0]
    assert {"concept", "value", "period_end", "unit_ref"} <= set(row)


def test_eightk_events_carry_dotted_item_labels() -> None:
    result = _backend("eightk", limit=1)

    assert all(item.startswith("Item ") for item in result["data"]["events"][0]["items"])


def test_yfinance_fast_info_is_read_by_attribute_rather_than_as_a_mapping() -> None:
    """Trap: ``FastInfo.keys()`` and ``.get()`` are camelCase, so ``.get("market_cap")``
    answers None while ``fast.market_cap`` answers the number. ``_mapping_value``
    reaches the correct value only because ``FastInfo`` is not a ``Mapping`` and it
    falls through to ``getattr``. Were yfinance ever to register it as one, market
    cap and last price would silently read None with every offline test still green.
    """

    from collections.abc import Mapping

    import yfinance

    client = yfinance.Ticker("NVDA")
    fast = client.get_fast_info()

    assert not isinstance(fast, Mapping)
    assert all(isinstance(getattr(fast, key), (int, float)) for key in ("market_cap", "last_price", "shares"))
    assert client.get_info().get("shortName")
    assert "Total Revenue" in set(client.income_stmt.index)


def test_usitc_dataweb_still_answers_html_rather_than_json() -> None:
    """This probe asserts a disabling reason is still true, so re-enabling the
    adapter becomes a test failure rather than something nobody notices."""

    from urllib.request import Request, urlopen

    request = Request("https://dataweb.usitc.gov/api/data", data=b"{}", headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
    with urlopen(request, timeout=30) as response:  # noqa: S310
        body = response.read()

    with pytest.raises(json.JSONDecodeError):
        json.loads(body)

    assert public_data_catalog()["usitc"].configured is False


def test_uspto_bound_path_answers_as_a_json_api_that_requires_a_key() -> None:
    """Bounded probe: without a key a 200 is unreachable, so this pins only that
    the bound path is a resource that authenticates, unlike USITC's SPA shell."""

    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    request = Request("https://api.uspto.gov/api/v1/patent/applications/search?q=test", headers={"Accept": "application/json"})
    with pytest.raises(HTTPError) as failure:
        urlopen(request, timeout=30)  # noqa: S310

    assert failure.value.code in {401, 403}
    assert isinstance(json.loads(failure.value.read()), dict)
