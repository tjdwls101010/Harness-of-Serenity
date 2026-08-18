from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from serenity_core.providers.filings import FilingsProvider


FROZEN_NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
FIXTURE = Path(__file__).parents[1] / "fixtures" / "filings" / "nvda_10q.json"
RAW_FIXTURE = Path(__file__).parents[1] / "fixtures" / "filings" / "nvda_10q_submission.txt"
IDENTITY = {"ticker": "NVDA", "cik": "0001045810", "issuer": "NVIDIA CORP"}


class FixtureBackend:
    def __init__(self, response: dict, *, raw_content: bytes | None = None) -> None:
        self.response = dict(response)
        if "raw_content" not in self.response:
            self.response["raw_content"] = RAW_FIXTURE.read_bytes() if raw_content is None else raw_content
        self.requests: list[dict] = []

    def execute(self, request: dict) -> dict:
        self.requests.append(request)
        return self.response


def test_missing_explicit_sec_identity_is_typed_unavailable_before_a_backend_request() -> None:
    backend = FixtureBackend({})

    envelope = FilingsProvider(backend=backend, clock=lambda: FROZEN_NOW).execute(
        {"capability": "filings", "ticker": "NVDA"}, cutoff=None
    ).to_dict()

    assert envelope["status"] == "unavailable"
    assert envelope["error"] == {"reason": "explicit SEC identity requires ticker, cik, and issuer"}
    assert envelope["identity_bindings"] == {"ticker": "NVDA"}
    assert backend.requests == []


def test_filing_list_preserves_sec_identity_and_exact_injected_raw_bytes() -> None:
    response = json.loads(FIXTURE.read_text(encoding="utf-8"))
    backend = FixtureBackend(response)
    request = {"capability": "filings", "identity": IDENTITY, "form": "10-Q", "limit": 1}

    envelope = FilingsProvider(
        backend=backend,
        clock=lambda: FROZEN_NOW,
        provider_version="test-edgartools",
    ).execute(request, cutoff=None).to_dict()

    assert envelope["status"] == "available"
    assert envelope["provider"] == "sec.filings"
    assert envelope["identity_bindings"] == IDENTITY
    assert envelope["data"]["identity"] == IDENTITY
    assert envelope["data"]["capability"] == "filings"
    assert envelope["data"]["requested"] == request
    assert envelope["data"]["filing"] == response["filing"]
    assert envelope["source"]["uri"] == "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000123/nvda-20260727.htm"
    assert envelope["source"]["content_sha256"] == hashlib.sha256(RAW_FIXTURE.read_bytes()).hexdigest()
    assert envelope["parse"] == {"status": "parsed", "transform_version": "filings-provider/1"}
    assert envelope["temporal"] == {
        "effective_at": "2026-07-27",
        "period_start": None,
        "period_end": None,
        "observed_at": "2026-07-27",
        "available_at": FROZEN_NOW.isoformat().replace("+00:00", "Z"),
        "source_version": "0001045810-26-000123",
    }


@pytest.mark.parametrize(
    ("capability", "arguments"),
    [
        ("submissions", {}),
        ("filings", {"form": "10-Q"}),
        ("filing_text", {"accession": "0001045810-26-000123", "format": "text"}),
        ("section", {"form": "10-Q", "item": "Item 2"}),
        ("eightk", {"item": "1.01"}),
        ("8-K", {"item": "1.01"}),
        ("xbrl_facts", {"form": "10-Q", "concept": "Revenue", "axis": "StatementBusinessSegmentsAxis"}),
        ("segments", {"form": "10-Q", "concept": "Revenue", "axis": "StatementBusinessSegmentsAxis"}),
        ("statement", {"form": "10-Q", "statement": "income", "view": "standard"}),
    ],
)
def test_supported_capabilities_remain_provider_neutral_and_preserve_requested_args(capability: str, arguments: dict) -> None:
    backend = FixtureBackend(
        {
            "filing": {
                "form": "10-Q",
                "filing_date": "2026-08-14",
                "report_date": "2026-07-27",
                "accession": "0001045810-26-000123",
            },
            "data": {"raw": "fixture"},
        }
    )
    request = {"capability": capability, "identity": IDENTITY, **arguments}

    envelope = FilingsProvider(backend=backend, clock=lambda: FROZEN_NOW).execute(request, cutoff=None).to_dict()

    assert envelope["status"] == "available"
    assert envelope["data"]["capability"] == capability
    assert envelope["data"]["requested"] == request
    assert envelope["data"]["filing"]["accession"] == "0001045810-26-000123"


def test_cutoff_never_uses_a_filing_that_was_not_yet_available() -> None:
    backend = FixtureBackend(
        {
            "filing": {
                "form": "10-Q",
                "filing_date": "2026-08-18",
                "report_date": "2026-07-27",
                "accession": "0001045810-26-000123",
            },
            "data": {"filings": []},
        }
    )

    envelope = FilingsProvider(backend=backend, clock=lambda: FROZEN_NOW).execute(
        {"capability": "filings", "identity": IDENTITY}, cutoff="2026-08-17T23:59:59Z"
    ).to_dict()

    assert envelope["status"] == "unavailable"
    assert envelope["error"] == {"reason": "filing date is after cutoff"}
    assert envelope["temporal"]["available_at"] is None


def test_actual_filing_availability_timestamp_takes_priority_over_the_filing_date() -> None:
    envelope = FilingsProvider(
        backend=FixtureBackend(
            {
                "filing": {
                    "form": "10-Q",
                    "filing_date": "2026-08-14",
                    "available_at": "2026-08-14T21:30:00Z",
                    "accession": "0001045810-26-000123",
                },
                "data": {"filings": []},
            }
        ),
        clock=lambda: FROZEN_NOW,
    ).execute({"capability": "filings", "identity": IDENTITY}, cutoff="2026-08-14T20:00:00Z").to_dict()

    assert envelope["status"] == "unavailable"
    assert envelope["temporal"]["available_at"] == "2026-08-14T21:30:00Z"


def test_sec_acceptance_datetime_is_used_for_intraday_cutoff() -> None:
    envelope = FilingsProvider(
        backend=FixtureBackend(
            {
                "filing": {
                    "form": "10-Q",
                    "filing_date": "2026-08-14",
                    "acceptance_datetime": "20260814213000",
                    "accession": "0001045810-26-000123",
                },
                "data": {"filings": []},
            }
        ),
        clock=lambda: FROZEN_NOW,
    ).execute({"capability": "filings", "identity": IDENTITY}, cutoff="2026-08-14T20:00:00Z").to_dict()

    assert envelope["status"] == "unavailable"
    assert envelope["temporal"]["available_at"] == "2026-08-14T21:30:00Z"


def test_same_day_intraday_cutoff_requires_an_actual_sec_acceptance_timestamp() -> None:
    envelope = FilingsProvider(
        backend=FixtureBackend(
            {
                "filing": {
                    "form": "10-Q",
                    "filing_date": "2026-08-14",
                    "report_date": "2026-07-27",
                    "accession": "0001045810-26-000123",
                },
                "data": {"filings": []},
            }
        ),
        clock=lambda: FROZEN_NOW,
    ).execute({"capability": "filings", "identity": IDENTITY}, cutoff="2026-08-14T23:59:59Z").to_dict()

    assert envelope["status"] == "unavailable"
    assert envelope["error"] == {"reason": "filing availability is unknown for intraday historical use"}
    assert envelope["temporal"]["available_at"] is None


def test_raw_sec_bytes_are_hashed_exactly_when_the_backend_supplies_them() -> None:
    raw_filing = b'<SEC-DOCUMENT>raw filing bytes</SEC-DOCUMENT>'
    envelope = FilingsProvider(
        backend=FixtureBackend(
            {
                "filing": {
                    "form": "10-Q",
                    "filing_date": "2026-08-14",
                    "available_at": "2026-08-14T21:30:00Z",
                    "accession": "0001045810-26-000123",
                },
                "data": {"filings": []},
                "raw_content": raw_filing,
            }
        ),
        clock=lambda: FROZEN_NOW,
    ).execute({"capability": "filings", "identity": IDENTITY}, cutoff=None).to_dict()

    assert envelope["status"] == "available"
    assert envelope["source"]["content_sha256"] == hashlib.sha256(raw_filing).hexdigest()


def test_backend_without_exact_raw_bytes_is_unavailable_instead_of_hashing_transformed_data() -> None:
    envelope = FilingsProvider(
        backend=FixtureBackend(
            {
                "filing": {
                    "form": "10-Q",
                    "filing_date": "2026-08-14",
                    "acceptance_datetime": "2026-08-14T21:30:00Z",
                    "accession": "0001045810-26-000123",
                },
                "data": {"filings": []},
                "raw_content": None,
            }
        ),
        clock=lambda: FROZEN_NOW,
    ).execute({"capability": "filings", "identity": IDENTITY}, cutoff=None).to_dict()

    assert envelope["status"] == "unavailable"
    assert envelope["error"] == {"reason": "exact SEC raw content is unavailable"}
    assert envelope["source"]["content_sha256"] is None


def test_historical_request_without_actual_filing_availability_is_unavailable() -> None:
    backend = FixtureBackend({"filing": {"form": "10-Q", "accession": "0001045810-26-000123"}, "data": {}})

    envelope = FilingsProvider(backend=backend, clock=lambda: FROZEN_NOW).execute(
        {"capability": "filings", "identity": IDENTITY}, cutoff="2026-08-17"
    ).to_dict()

    assert envelope["status"] == "unavailable"
    assert envelope["error"] == {"reason": "filing availability is unknown for historical use"}


def test_missing_disclosure_is_not_disclosed_and_backend_parse_failure_is_invalid() -> None:
    missing = FilingsProvider(
        backend=FixtureBackend({"filing": {"form": "10-Q", "filing_date": "2026-08-14", "accession": "0001045810-26-000123"}, "status": "not_disclosed"}),
        clock=lambda: FROZEN_NOW,
    ).execute({"capability": "segments", "identity": IDENTITY}, cutoff=None).to_dict()
    invalid = FilingsProvider(
        backend=FixtureBackend({"filing": {"form": "10-Q", "filing_date": "2026-08-14", "accession": "0001045810-26-000123"}, "error": "malformed XBRL", "raw_content": b"<xbrl>broken</xbrl>"}),
        clock=lambda: FROZEN_NOW,
    ).execute({"capability": "xbrl_facts", "identity": IDENTITY}, cutoff=None).to_dict()

    assert missing["status"] == "not_disclosed"
    assert missing["error"] == {"reason": "requested SEC disclosure was not disclosed"}
    assert invalid["status"] == "invalid"
    assert invalid["error"] == {"reason": "SEC filings backend returned invalid data: malformed XBRL"}
    assert invalid["source"]["content_sha256"] == hashlib.sha256(b"<xbrl>broken</xbrl>").hexdigest()


def test_empty_backend_disclosure_is_not_disclosed_instead_of_an_empty_available_fact() -> None:
    envelope = FilingsProvider(
        backend=FixtureBackend(
            {"filing": {"form": "10-Q", "filing_date": "2026-08-14", "accession": "0001045810-26-000123"}, "data": {}}
        ),
        clock=lambda: FROZEN_NOW,
    ).execute({"capability": "segments", "identity": IDENTITY}, cutoff=None).to_dict()

    assert envelope["status"] == "not_disclosed"
    assert envelope["error"] == {"reason": "requested SEC disclosure was not disclosed"}


def test_an_injected_cache_is_reusable_without_a_default_global_cache() -> None:
    response = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cache: dict[str, dict] = {}
    request = {"capability": "filings", "identity": IDENTITY, "form": "10-Q"}
    first = FilingsProvider(backend=FixtureBackend(response), cache=cache, clock=lambda: FROZEN_NOW).execute(request, cutoff=None).to_dict()

    class BrokenBackend:
        def execute(self, request: dict) -> dict:
            raise AssertionError("the injected cache should satisfy this request")

    second = FilingsProvider(backend=BrokenBackend(), cache=cache, clock=lambda: FROZEN_NOW).execute(request, cutoff=None).to_dict()

    assert cache
    assert second["status"] == "available"
    assert second["source"]["content_sha256"] == first["source"]["content_sha256"]


def test_edgar_acceptance_instant_survives_as_the_filing_availability_time() -> None:
    """edgartools hands back a datetime, and only a datetime knows the intraday instant.

    Dropping it left every filing with an unknown availability, which an
    intraday cutoff -- the shape every run derives from --as-of -- then refuses.
    """

    backend = FixtureBackend(
        {
            "filing": {
                "form": "10-K",
                "filing_date": datetime(2026, 2, 26, tzinfo=timezone.utc).date(),
                "report_date": "2025-12-31",
                "accession": "0001437749-26-005875",
                "primary_document": "aaoi20251231_10k.htm",
                "acceptance_datetime": datetime(2026, 2, 26, 21, 24, 24, tzinfo=timezone.utc),
            },
            "data": {"section": "risk_factors", "text": "Vendor concentration."},
        }
    )

    envelope = FilingsProvider(backend=backend, clock=lambda: FROZEN_NOW).execute(
        {"capability": "section", "identity": IDENTITY, "form": "10-K", "named": "risk_factors"},
        cutoff="2026-08-17T23:59:59Z",
    ).to_dict()

    assert envelope["status"] == "available"
    assert envelope["temporal"]["available_at"] == "2026-02-26T21:24:24Z"
