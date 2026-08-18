from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from serenity_core.providers.public_data import HttpResponse, public_data_catalog
from serenity_core.schema import validate_document


FROZEN_NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
REPO_ROOT = Path(__file__).resolve().parents[3]


def test_catalog_declares_typed_priority_and_narrative_capabilities() -> None:
    catalog = public_data_catalog(clock=lambda: FROZEN_NOW)

    assert catalog["usaspending"].capability == "numeric"
    assert catalog["usaspending"].priority == "high"
    assert catalog["usitc"].priority == "high"
    assert catalog["eia"].priority == "high"
    assert {catalog[key].priority for key in ("bls", "bea", "cftc")} == {"medium"}
    assert catalog["sam"].configured is False
    assert catalog["uspto"].configured is False
    assert {catalog[key].capability for key in ("federal-register", "bis")} == {"narrative_link"}
    assert "issuer-ir" not in catalog


def test_every_public_adapter_is_losslessly_declared_in_the_evidence_catalog() -> None:
    catalog_document = json.loads((REPO_ROOT / "config" / "evidence-catalog.v1.json").read_text())
    declared = {entry["provider_id"]: set(entry["capabilities"]) for entry in catalog_document["providers"]}

    adapters = public_data_catalog(clock=lambda: FROZEN_NOW)

    assert set(adapters).issubset(declared)
    assert {provider_id: set(adapter.capabilities) for provider_id, adapter in adapters.items()} == {
        provider_id: declared[provider_id] for provider_id in adapters
    }


def test_usaspending_builds_documented_award_search_and_preserves_raw_response() -> None:
    catalog = public_data_catalog(clock=lambda: FROZEN_NOW)
    provider = catalog["usaspending"]
    request = provider.build_request(
        {
            "recipient_search_text": ["Acme Robotics"],
            "time_period": [{"start_date": "2025-01-01", "end_date": "2025-12-31"}],
        }
    )
    raw = json.dumps(
        {
            "results": [
                {
                    "Award ID": "FA1234-25-C-0001",
                    "Recipient Name": "Acme Robotics, Inc.",
                    "Award Amount": 1250000,
                    "Start Date": "2025-02-01",
                    "End Date": "2026-01-31",
                }
            ]
        }
    ).encode()

    envelope = provider.parse(HttpResponse(status=200, body=raw), request).to_dict()

    assert request.method == "POST"
    assert request.url == "https://api.usaspending.gov/api/v2/search/spending_by_award/"
    assert request.body == {
        "filters": {
            "recipient_search_text": ["Acme Robotics"],
            "time_period": [{"start_date": "2025-01-01", "end_date": "2025-12-31"}],
        },
        "fields": ["Award ID", "Recipient Name", "Award Amount", "Start Date", "End Date"],
        "limit": 100,
        "page": 1,
        "subawards": False,
    }
    assert envelope["status"] == "available"
    assert envelope["data"] == {
        "awards": [
            {
                "award_id": "FA1234-25-C-0001",
                "recipient_name": "Acme Robotics, Inc.",
                "award_amount": 1250000,
                "period_start": "2025-02-01",
                "period_end": "2026-01-31",
            }
        ]
    }
    assert envelope["source"]["content_sha256"] == hashlib.sha256(raw).hexdigest()
    assert envelope["temporal"]["available_at"] == "2026-08-17T12:00:00Z"


def test_usitc_dataweb_builds_trade_query_and_parses_returned_rows() -> None:
    catalog = public_data_catalog(clock=lambda: FROZEN_NOW)
    provider = catalog["usitc"]
    request = provider.build_request({"hs_codes": ["854231"], "year": 2025, "trade_flow": "imports"})
    raw = json.dumps(
        {
            "data": [
                {"year": 2025, "hts10": "8542310000", "customs_value": 2800000000, "quantity": 8100000}
            ]
        }
    ).encode()

    envelope = provider.parse(HttpResponse(status=200, body=raw), request).to_dict()

    assert request.method == "POST"
    assert request.url == "https://dataweb.usitc.gov/api/data"
    assert request.body == {"hs_codes": ["854231"], "year": 2025, "trade_flow": "imports"}
    assert envelope["status"] == "available"
    assert envelope["data"]["rows"] == [
        {"year": 2025, "hs_code": "8542310000", "customs_value": 2800000000, "quantity": 8100000}
    ]
    assert envelope["temporal"]["observed_at"] == "2025-12-31"


def test_eia_builds_v2_route_and_parses_series_rows() -> None:
    catalog = public_data_catalog(clock=lambda: FROZEN_NOW, config={"eia_api_key": "demo-key"})
    provider = catalog["eia"]
    request = provider.build_request({"route": "electricity/rto/region-data", "facets": {"respondent": ["PJM"]}})
    raw = json.dumps(
        {
            "response": {
                "data": [
                    {"period": "2026-08-15", "respondent": "PJM", "value": "152345", "value-units": "megawatthours"}
                ]
            }
        }
    ).encode()

    envelope = provider.parse(HttpResponse(status=200, body=raw), request).to_dict()

    assert request.method == "GET"
    assert request.url == "https://api.eia.gov/v2/electricity/rto/region-data/data/"
    assert request.query == {
        "api_key": "demo-key",
        "data[0]": "value",
        "facets[respondent][]": "PJM",
        "length": 5000,
    }
    assert envelope["status"] == "available"
    assert envelope["data"]["rows"] == [
        {"period": "2026-08-15", "respondent": "PJM", "value": "152345", "unit": "megawatthours"}
    ]
    assert envelope["temporal"]["observed_at"] == "2026-08-15"


def test_response_failures_preserve_raw_evidence_and_parse_provenance() -> None:
    raw_http_failure = b'{"detail":"maintenance"}'
    catalog = public_data_catalog(
        clock=lambda: FROZEN_NOW,
        http=lambda _request: HttpResponse(status=503, body=raw_http_failure),
    )

    unavailable = catalog["bls"].collect({"series": ["CES0000000001"]}).to_dict()

    assert unavailable["status"] == "unavailable"
    assert unavailable["error"] == {"reason": "HTTP 503"}
    assert unavailable["source"]["content_sha256"] == hashlib.sha256(raw_http_failure).hexdigest()
    assert unavailable["source"]["http_status"] == 503
    assert unavailable["source"]["parameters"] == {"method": "POST", "query": {}, "body": {"seriesid": ["CES0000000001"]}}
    assert unavailable["parse"] == {"status": "not_parsed", "transform_version": "public-data/1", "message": "HTTP 503"}
    assert unavailable["temporal"]["available_at"] == "2026-08-17T12:00:00Z"
    validate_document(unavailable, "urn:serenity:schema:provider-envelope:1")


def test_parse_failure_preserves_raw_evidence_and_transform_metadata() -> None:
    raw_parse_failure = b"not JSON"
    catalog = public_data_catalog(clock=lambda: FROZEN_NOW)
    request = catalog["eia"].build_request({"route": "electricity/rto/region-data"})

    invalid = catalog["eia"].parse(HttpResponse(status=200, body=raw_parse_failure), request).to_dict()

    assert invalid["status"] == "invalid"
    assert invalid["source"]["content_sha256"] == hashlib.sha256(raw_parse_failure).hexdigest()
    assert invalid["source"]["http_status"] == 200
    assert invalid["source"]["parameters"] == {
        "method": "GET",
        "query": {"api_key": "[REDACTED]", "data[0]": "value", "length": 5000},
        "body": {},
    }
    assert invalid["parse"]["status"] == "failed"
    assert invalid["parse"]["transform_version"] == "public-data/1"
    validate_document(invalid, "urn:serenity:schema:provider-envelope:1")


def test_unconfigured_optional_source_is_a_schema_valid_typed_state() -> None:
    not_requested = public_data_catalog(clock=lambda: FROZEN_NOW)["sam"].collect({"uei": "ABC123"}).to_dict()

    assert not_requested["status"] == "not_requested"
    assert not_requested["error"] == {"reason": "SAM.gov API key is not configured"}
    validate_document(not_requested, "urn:serenity:schema:provider-envelope:1")


def test_configured_credentials_reach_required_auth_surfaces_but_never_serialized_provenance() -> None:
    requests = []
    responses = iter(
        [
            HttpResponse(status=200, body=b'{"Results":{"series":[]}}'),
            HttpResponse(status=200, body=b'{"entityData":[]}'),
            HttpResponse(status=200, body=b'{"patentDataBag":[]}'),
        ]
    )
    catalog = public_data_catalog(
        clock=lambda: FROZEN_NOW,
        config={"bls_registration_key": "bls-secret", "sam_api_key": "sam-secret", "uspto_api_key": "uspto-secret"},
        http=lambda request: (requests.append(request), next(responses))[1],
    )

    envelopes = [
        catalog["bls"].collect({"series": ["CES0000000001"]}).to_dict(),
        catalog["sam"].collect({"uei": "ABC123"}).to_dict(),
        catalog["uspto"].collect({"patent_number": "12345678"}).to_dict(),
    ]

    assert requests[0].body == {"seriesid": ["CES0000000001"], "registrationkey": "bls-secret"}
    assert requests[1].query["api_key"] == "sam-secret"
    assert requests[2].headers == {"X-API-KEY": "uspto-secret"}
    assert catalog["bls"].secret_parameter_names == ("registrationkey",)
    assert catalog["sam"].secret_parameter_names == ("api_key",)
    assert catalog["uspto"].secret_parameter_names == ("X-API-KEY",)
    for envelope in envelopes:
        serialized = json.dumps(envelope)
        assert "secret" not in serialized
        validate_document(envelope, "urn:serenity:schema:provider-envelope:1")


@pytest.mark.parametrize(
    ("provider_id", "config", "query", "validated_empty"),
    [
        ("usaspending", {}, {"recipient_search_text": ["Acme"]}, {"results": []}),
        ("usitc", {}, {"hs_codes": ["854231"], "year": 2025}, {"data": []}),
        ("eia", {}, {"route": "electricity/rto/region-data"}, {"response": {"data": []}}),
        ("bls", {}, {"series": ["CES0000000001"]}, {"Results": {"series": []}}),
        ("bea", {"bea_api_key": "bea-key"}, {"method": "GetData", "datasetname": "NIPA"}, {"BEAAPI": {"Results": {"Data": []}}}),
        ("cftc", {}, {"$limit": 1}, []),
        ("sam", {"sam_api_key": "sam-key"}, {"uei": "ABC123"}, {"entityData": []}),
        ("uspto", {"uspto_api_key": "uspto-key"}, {"patent_number": "12345678"}, {"patentDataBag": []}),
        ("federal-register", {}, {"conditions[type][]": "RULE"}, {"results": []}),
        ("bis", {}, {"q": "export control"}, {"results": []}),
    ],
)
def test_each_adapter_distinguishes_an_unexpected_2xx_shape_from_a_valid_empty_collection(
    provider_id: str, config: dict[str, str], query: dict[str, object], validated_empty: object
) -> None:
    provider = public_data_catalog(clock=lambda: FROZEN_NOW, config=config)[provider_id]
    request = provider.build_request(query)

    invalid = provider.parse(HttpResponse(status=200, body=b"{}"), request).to_dict()
    empty = provider.parse(HttpResponse(status=200, body=json.dumps(validated_empty).encode()), request).to_dict()

    assert invalid["status"] == "invalid"
    assert invalid["parse"]["status"] == "failed"
    assert empty["status"] == "available"
    assert empty["parse"] == {"status": "parsed", "transform_version": "public-data/1"}
    validate_document(invalid, "urn:serenity:schema:provider-envelope:1")
    validate_document(empty, "urn:serenity:schema:provider-envelope:1")


def test_federal_register_is_bound_to_its_real_documents_endpoint() -> None:
    provider = public_data_catalog(clock=lambda: FROZEN_NOW)["federal-register"]

    assert provider.configured is True
    assert provider.build_request({"conditions[type][]": "RULE"}).url == "https://www.federalregister.gov/api/v1/documents.json"


def test_bis_stays_disabled_for_the_true_reason_that_no_api_endpoint_is_bound() -> None:
    provider = public_data_catalog(clock=lambda: FROZEN_NOW)["bis"]

    envelope = provider.collect({"q": "export control"}).to_dict()

    assert provider.configured is False
    assert envelope["status"] == "not_requested"
    assert envelope["error"] == {"reason": "no BIS API endpoint is bound; https://www.bis.gov/ is a homepage, not a query API"}
    validate_document(envelope, "urn:serenity:schema:provider-envelope:1")


def test_usitc_stays_disabled_because_its_bound_path_answers_html_with_http_200() -> None:
    provider = public_data_catalog(clock=lambda: FROZEN_NOW)["usitc"]

    envelope = provider.collect({"hs_codes": ["854231"], "year": 2025}).to_dict()

    assert provider.configured is False
    assert envelope["status"] == "not_requested"
    assert envelope["error"] == {
        "reason": "no USITC API endpoint is bound; https://dataweb.usitc.gov/api/data answers the DataWeb app's HTML with HTTP 200 for every request, and the queryable host datawebws.usitc.gov is token-gated"
    }
    validate_document(envelope, "urn:serenity:schema:provider-envelope:1")


def test_uspto_is_bound_to_a_resource_path_rather_than_the_api_root() -> None:
    """The bare ``/api/v1/patent/`` base answers 403 and is not a queryable
    resource; ``applications/search`` answers 401, which is what an unkeyed
    request to a real resource returns."""

    provider = public_data_catalog(clock=lambda: FROZEN_NOW, config={"uspto_api_key": "uspto-secret"})["uspto"]

    assert provider.build_request({"q": "patent"}).url == "https://api.uspto.gov/api/v1/patent/applications/search"
