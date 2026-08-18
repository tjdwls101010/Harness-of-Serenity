"""Pin EdgarToolsBackend's own decisions with edgartools stubbed at the seam.

Every other SEC test injects a FixtureBackend, which stands *in front of* this
class, so the only code that ever touched real edgar objects had no test seat at
all. The stubs here stand in for the external library rather than for an
internal collaborator: what they encode -- TenQ having no ``.risk_factors``, a
bare ``Filing`` having no ``acceptance_datetime`` -- is asserted against the real
releases by tests/260817/live/test_provider_interfaces.py. This file owns the
decisions; that file owns the shapes.
"""

from __future__ import annotations

import json
import sys
import types
from datetime import date, datetime, timezone
from typing import Any

import pytest

from serenity_core.providers.filings import EdgarToolsBackend


IDENTITY = {"ticker": "SWK", "cik": "0000093556", "issuer": "STANLEY BLACK & DECKER, INC."}
ACCEPTED_AT = datetime(2026, 5, 20, 20, 35, 52, tzinfo=timezone.utc)


class FakeSections:
    """Item lookup that answers None for an absent key, as TenK/TenQ do."""

    def __init__(self, sections: dict[str, str]) -> None:
        self.sections = sections
        self.requested: list[str] = []

    def __getitem__(self, key: str) -> str | None:
        self.requested.append(key)
        return self.sections.get(key)


class FakeFiling:
    def __init__(self, *, form: str, accession: str, sections: dict[str, str] | None = None, acceptance: datetime | None = ACCEPTED_AT) -> None:
        self.form = form
        self.filing_date = date(2026, 5, 20)
        self.report_date = "2026-04-26"
        self.accession_no = accession
        self.primary_document = "swk-20260426.htm"
        self.acceptance_datetime = acceptance
        self.full_text_submission = b"<SEC-DOCUMENT>raw</SEC-DOCUMENT>"
        self._sections = FakeSections(sections or {})

    def obj(self) -> FakeSections:
        return self._sections

    def text(self) -> str:
        return "filing body"


class FakeCompany:
    def __init__(self, filings: list[FakeFiling]) -> None:
        self._filings = filings

    def get_filings(self, **kwargs: Any) -> list[FakeFiling]:
        form = kwargs.get("form")
        return [filing for filing in self._filings if form is None or filing.form == form]


@pytest.fixture
def edgar_stub(monkeypatch: pytest.MonkeyPatch):
    state: dict[str, Any] = {"filings": [], "by_accession": None, "submissions": "{}"}

    module = types.ModuleType("edgar")
    module.Company = lambda _cik: FakeCompany(state["filings"])  # type: ignore[attr-defined]
    module.get_by_accession_number = lambda accession: state["by_accession"]  # type: ignore[attr-defined]
    requests = types.ModuleType("edgar.httprequests")
    requests.download_text = lambda _uri: state["submissions"]  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "edgar", module)
    monkeypatch.setitem(sys.modules, "edgar.httprequests", requests)
    return state


def _execute(capability: str, **arguments: Any) -> Any:
    return EdgarToolsBackend().execute({"identity": IDENTITY, "capability": capability, **arguments})


def test_a_ten_q_named_section_resolves_through_its_part_qualified_key(edgar_stub) -> None:
    """``tenq["Item 1A"]`` happens to work today, but ``tenq["Item 1"]`` silently
    answers Part I, so the resolver commits to the part qualifier everywhere."""

    filing = FakeFiling(form="10-Q", accession="0000093556-26-000012", sections={"Part II, Item 1A": "quarterly risk factors"})
    edgar_stub["filings"] = [filing]

    result = _execute("section", form="10-Q", named="risk_factors")

    assert result["data"] == {"section": "risk_factors", "text": "quarterly risk factors"}
    assert filing.obj().requested == ["Part II, Item 1A"]


def test_a_ten_k_named_section_resolves_through_its_bare_item_key(edgar_stub) -> None:
    filing = FakeFiling(form="10-K", accession="0000093556-26-000003", sections={"Item 1A": "annual risk factors"})
    edgar_stub["filings"] = [filing]

    assert _execute("section", form="10-K", named="risk_factors")["data"]["text"] == "annual risk factors"
    assert filing.obj().requested == ["Item 1A"]


def test_an_amendment_resolves_as_the_form_it_amends(edgar_stub) -> None:
    filing = FakeFiling(form="10-K/A", accession="0000093556-26-000004", sections={"Item 7": "restated MD&A"})
    edgar_stub["filings"] = [filing]

    assert _execute("section", form="10-K/A", named="mda")["data"]["text"] == "restated MD&A"


@pytest.mark.parametrize(
    ("form", "named", "expected"),
    [
        ("10-Q", "business", "form 10-Q does not define the named section business; it defines mda, risk_factors"),
        ("8-K", "risk_factors", "form 8-K defines no named sections"),
    ],
)
def test_a_section_a_form_does_not_define_is_invalid_rather_than_undisclosed(edgar_stub, form: str, named: str, expected: str) -> None:
    """An absence of adapter support must never be reportable as an absence of
    disclosure: that is the one failure a source-provenance harness cannot survive."""

    edgar_stub["filings"] = [FakeFiling(form=form, accession="0000093556-26-000005", sections={})]

    result = _execute("section", form=form, named=named)

    assert result["status"] == "invalid"
    assert result["reason"].startswith(expected)
    assert result["filing"]["form"] == form


def test_an_unsupported_pair_still_points_at_the_interface_that_can_serve_it(edgar_stub) -> None:
    edgar_stub["filings"] = [FakeFiling(form="10-Q", accession="0000093556-26-000006", sections={})]

    reason = _execute("section", form="10-Q", named="business")["reason"]

    assert "item=" in reason and "Part II, Item 1A" in reason


def test_a_genuinely_absent_section_is_still_reported_as_no_record(edgar_stub) -> None:
    edgar_stub["filings"] = [FakeFiling(form="10-K", accession="0000093556-26-000007", sections={})]

    assert _execute("section", form="10-K", named="risk_factors") is None


def test_filing_text_by_accession_prefers_the_entity_path_that_carries_acceptance(edgar_stub) -> None:
    """``get_by_accession_number`` returns a bare ``Filing`` with no acceptance
    attribute, so preferring it would lose availability on every accession read."""

    edgar_stub["filings"] = [FakeFiling(form="10-Q", accession="0000093556-26-000012")]
    edgar_stub["by_accession"] = FakeFiling(form="10-Q", accession="0000093556-26-000012", acceptance=None)

    result = _execute("filing_text", accession="0000093556-26-000012", format="text")

    assert result["filing"]["available_at"] == "2026-05-20T20:35:52Z"


def test_an_accession_outside_the_entity_index_still_falls_back(edgar_stub) -> None:
    edgar_stub["filings"] = []
    edgar_stub["by_accession"] = FakeFiling(form="10-Q", accession="0000093556-26-000099", acceptance=None)

    result = _execute("filing_text", accession="0000093556-26-000099", format="text")

    assert result["data"]["text"] == "filing body"
    assert result["filing"]["available_at"] is None


def test_a_limit_cannot_hide_the_accession_being_searched_for(edgar_stub) -> None:
    """``limit`` bounds how many filings a list returns; applying it to a search
    would make an accession resolvable only when it happens to be recent."""

    edgar_stub["filings"] = [
        FakeFiling(form="10-Q", accession="0000093556-26-000012"),
        FakeFiling(form="10-Q", accession="0000093556-25-000044"),
    ]

    result = _execute("filing_text", accession="0000093556-25-000044", limit=1, format="text")

    assert result["filing"]["accession"] == "0000093556-25-000044"


def test_submissions_returns_the_index_anchored_to_its_newest_filing(edgar_stub) -> None:
    edgar_stub["submissions"] = json.dumps(
        {
            "cik": "0000093556",
            "name": "STANLEY BLACK & DECKER, INC.",
            "tickers": ["SWK"],
            "exchanges": ["NYSE"],
            "filings": {
                "recent": {
                    "acceptanceDateTime": ["2026-05-20T20:35:52.000Z", "2026-08-01T18:00:00.000Z"],
                    "accessionNumber": ["0000093556-26-000012", "0000093556-26-000030"],
                    "form": ["10-Q", "8-K"],
                    "filingDate": ["2026-05-20", "2026-08-01"],
                    "reportDate": ["2026-04-26", ""],
                    "primaryDocument": ["swk-20260426.htm", "swk-20260801.htm"],
                }
            },
        }
    )

    result = _execute("submissions")

    assert result["source_uri"] == "https://data.sec.gov/submissions/CIK0000093556.json"
    assert result["filing"]["accession"] == "0000093556-26-000030"
    assert result["filing"]["available_at"] == "2026-08-01T18:00:00.000Z"
    assert result["filing"]["report_date"] is None
    assert result["data"]["submissions"] == {"cik": "0000093556", "name": "STANLEY BLACK & DECKER, INC.", "tickers": ["SWK"], "exchanges": ["NYSE"]}
    assert json.loads(result["raw_content"]) == json.loads(edgar_stub["submissions"])


def test_a_filer_with_no_filings_yet_yields_no_availability_rather_than_a_crash(edgar_stub) -> None:
    edgar_stub["submissions"] = json.dumps({"cik": "0000093556", "name": "NEW FILER", "filings": {"recent": {}}})

    result = _execute("submissions")

    assert result["filing"]["available_at"] is None
    assert result["filing"]["accession"] is None
