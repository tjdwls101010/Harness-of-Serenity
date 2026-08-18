from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from serenity_core.providers.base import ProviderEnvelope
from serenity_core.providers.issuer_ir import VerifiedIssuerOrigin
from serenity_core.providers.registry import _SNAPSHOT_CAPABILITIES, EvidenceProviderRegistry, ProviderRegistryValidationError
from serenity_core.research import load_evidence_catalog
from serenity_core.schema import validate_document


FROZEN_NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)


def request_for(
    capability_id: str,
    provider: str,
    *,
    parameters: dict[str, object] | None = None,
    allow_network: bool = True,
    cutoff: str | None = None,
) -> dict[str, object]:
    policy: dict[str, object] = {"providers": [provider], "allow_network": allow_network}
    if cutoff is not None:
        policy["historical_cutoff"] = cutoff
    return {
        "schema_id": "urn:serenity:schema:evidence-request:1",
        "request_id": "evidence-request-registry-test",
        "run_id": "run-registry-test",
        "hypothesis_ids": ["hyp-registry-test"],
        "capability_id": capability_id,
        "question": "What evidence resolves the live hypothesis?",
        "evidence_type": "external-fact",
        "provider_policy": policy,
        "acceptance_criteria": ["Return source-backed evidence."],
        "requested_at": "2026-08-17T00:00:00Z",
        "provider_parameters": parameters or {},
        "content_hash": "a" * 64,
    }


def available_envelope(*, provider: str, source_version: str, available_at: str) -> ProviderEnvelope:
    return ProviderEnvelope.available(
        provider=provider,
        provider_version="fixture/1",
        source_uri="https://fixtures.serenity.test/evidence",
        raw_content=source_version.encode(),
        data={"source_version": source_version},
        fetched_at=FROZEN_NOW,
        request={"fixture": source_version},
        available_at=available_at,
        source_version=source_version,
    )


def test_fred_dispatch_preserves_multiple_vintages_in_deterministic_order() -> None:
    calls: list[tuple[str, str]] = []

    class FredFixture:
        def observations(
            self,
            series_id: str,
            *,
            cutoff: str,
            observation_start: str | None = None,
            observation_end: str | None = None,
            vintages: str = "active",
        ) -> list[ProviderEnvelope]:
            calls.append((series_id, cutoff, observation_start, observation_end))
            return [
                available_envelope(provider="fred", source_version="2026-06-15", available_at="2026-06-15T00:00:00Z"),
                available_envelope(provider="fred", source_version="2026-05-15", available_at="2026-05-15T00:00:00Z"),
            ]

    registry = EvidenceProviderRegistry(
        provider_factories={"alfred-fred": lambda **_kwargs: FredFixture()},
        clock=lambda: FROZEN_NOW,
    )

    envelopes = registry.collect(
        request_for(
            "alfred-fred.vintage-series",
            "alfred-fred",
            parameters={"series_id": "DGS10", "observation_start": "2026-01-01"},
            cutoff="2026-07-01T00:00:00Z",
        )
    )

    assert calls == [("DGS10", "2026-07-01T00:00:00Z", "2026-01-01", None)]
    assert [envelope.to_dict()["temporal"]["source_version"] for envelope in envelopes] == ["2026-05-15", "2026-06-15"]
    for envelope in envelopes:
        validate_document(envelope.to_dict(), "urn:serenity:schema:provider-envelope:1")


def test_an_alfred_fred_observation_window_reaches_the_provider() -> None:
    calls: list[tuple[str | None, str | None]] = []

    class FredFixture:
        def observations(
            self,
            _series_id: str,
            *,
            cutoff: str,
            observation_start: str | None = None,
            observation_end: str | None = None,
            vintages: str = "active",
        ) -> list[ProviderEnvelope]:
            calls.append((observation_start, observation_end))
            return [available_envelope(provider="fred", source_version="2026-06-15", available_at="2026-06-15T00:00:00Z")]

    EvidenceProviderRegistry(
        provider_factories={"alfred-fred": lambda **_kwargs: FredFixture()}, clock=lambda: FROZEN_NOW
    ).collect(
        request_for(
            "alfred-fred.macro-series",
            "alfred-fred",
            parameters={"series_id": "DGS10", "observation_start": "2026-06-01", "observation_end": "2026-06-30"},
            cutoff="2026-07-01T00:00:00Z",
        )
    )

    assert calls == [("2026-06-01", "2026-06-30")]


def test_offline_policy_returns_a_nonempty_typed_envelope_without_constructing_provider() -> None:
    constructed = False

    def factory(**_kwargs: object) -> object:
        nonlocal constructed
        constructed = True
        raise AssertionError("offline policy must not construct a provider")

    envelopes = EvidenceProviderRegistry(
        provider_factories={"alfred-fred": factory}, clock=lambda: FROZEN_NOW
    ).collect(
        request_for("alfred-fred.macro-series", "alfred-fred", parameters={"series_id": "DFF"}, allow_network=False)
    )

    assert constructed is False
    assert len(envelopes) == 1
    assert envelopes[0].to_dict()["status"] == "not_requested"
    assert envelopes[0].to_dict()["error"] == {"reason": "network access is disabled by provider_policy"}


def test_historical_cutoff_excludes_later_provider_evidence_without_returning_an_empty_list() -> None:
    class PublicFixture:
        def collect(self, _parameters: dict[str, object]) -> ProviderEnvelope:
            return available_envelope(provider="bls", source_version="late", available_at="2026-08-17T12:00:00Z")

    envelopes = EvidenceProviderRegistry(
        provider_factories={"bls": lambda **_kwargs: PublicFixture()}, clock=lambda: FROZEN_NOW
    ).collect(
        request_for("bls.labor-data", "bls", parameters={"series": ["CES0000000001"]}, cutoff="2026-08-01T00:00:00Z")
    )

    assert len(envelopes) == 1
    assert envelopes[0].to_dict()["status"] == "unavailable"
    assert envelopes[0].to_dict()["error"] == {"reason": "provider evidence was not available by historical cutoff"}


@pytest.mark.parametrize(
    ("capability_id", "provider", "message"),
    [
        ("alfred-fred.macro-series", "sec", "provider_policy does not allow capability owner"),
        ("alfred-fred.macro-series", "not-catalog", "provider_policy has unknown providers"),
        ("made-up.provider", "alfred-fred", "capability_id is not declared by the evidence catalog"),
    ],
)
def test_invalid_capability_or_provider_policy_fails_before_provider_construction(
    capability_id: str, provider: str, message: str
) -> None:
    def factory(**_kwargs: object) -> object:
        raise AssertionError("invalid request must not construct a provider")

    registry = EvidenceProviderRegistry(provider_factories={"alfred-fred": factory, "sec": factory})

    with pytest.raises(ProviderRegistryValidationError, match=message):
        registry.collect(request_for(capability_id, provider, parameters={"series_id": "DFF"}))


def test_public_data_capability_dispatches_to_its_catalog_aligned_adapter() -> None:
    received: list[dict[str, object]] = []
    factory_config: list[dict[str, object]] = []

    class PublicFixture:
        def collect(self, parameters: dict[str, object]) -> ProviderEnvelope:
            received.append(parameters)
            return ProviderEnvelope.available(
                provider="usaspending",
                provider_version="fixture/1",
                source_uri="https://fixtures.serenity.test/evidence",
                raw_content=b"award-1",
                data={"source_version": "award-1"},
                fetched_at=FROZEN_NOW,
                request={"fixture": "award-1"},
                available_at="2026-08-01T00:00:00Z",
                source_version="award-1",
                source_parameters={"api_key": "provider-secret"},
            )

    def factory(**kwargs: object) -> PublicFixture:
        factory_config.append(kwargs["config"])
        return PublicFixture()

    envelopes = EvidenceProviderRegistry(
        provider_factories={"usaspending": factory},
        config={"usaspending": {"api_key": "provider-secret"}},
        clock=lambda: FROZEN_NOW,
    ).collect(
        request_for("usaspending.federal-awards", "usaspending", parameters={"recipient_search_text": ["Acme"], "award_type_codes": ["A", "B", "C", "D"]})
    )

    assert received == [{"recipient_search_text": ["Acme"], "award_type_codes": ["A", "B", "C", "D"]}]
    assert factory_config == [{"api_key": "provider-secret"}]
    assert [envelope.to_dict()["provider"] for envelope in envelopes] == ["usaspending"]
    assert envelopes[0].to_dict()["source"]["parameters"] == {"api_key": "[REDACTED]"}


@pytest.mark.parametrize(
    ("provider_id", "capability_id", "config", "parameters", "source_parameters", "secret"),
    [
        (
            "bls",
            "bls.labor-data",
            {"bls_registration_key": "bls-registration-secret"},
            {"series": ["CES0000000001"], "registrationkey": "bls-registration-secret"},
            {"body": {"registrationkey": "bls-registration-secret"}},
            "bls-registration-secret",
        ),
        (
            "sam",
            "sam.procurement-opportunities",
            {"sam_api_key": "sam-api-secret"},
            {"uei": "ABC123"},
            {"query": {"api_key": "sam-api-secret"}},
            "sam-api-secret",
        ),
        (
            "uspto",
            "uspto.patent-records",
            {"uspto_api_key": "uspto-api-secret"},
            {"q": "semiconductor"},
            {"headers": {"X-API-KEY": "uspto-api-secret"}},
            "uspto-api-secret",
        ),
    ],
)
def test_public_collect_redacts_recursive_provider_credentials_but_keeps_factory_config_live(
    provider_id: str,
    capability_id: str,
    config: dict[str, str],
    parameters: dict[str, object],
    source_parameters: dict[str, object],
    secret: str,
) -> None:
    received_config: list[dict[str, str]] = []
    received_parameters: list[dict[str, object]] = []

    class PublicFixture:
        def collect(self, query: dict[str, object]) -> ProviderEnvelope:
            received_parameters.append(query)
            return ProviderEnvelope.available(
                provider=provider_id,
                provider_version="fixture/1",
                source_uri="https://fixtures.serenity.test/evidence",
                raw_content=b"public-response",
                data={"fact": "public response"},
                fetched_at=FROZEN_NOW,
                request={"fixture": provider_id},
                available_at="2026-08-01T00:00:00Z",
                source_version="fixture-source",
                source_parameters=source_parameters,
            )

    def factory(**kwargs: object) -> PublicFixture:
        received_config.append(kwargs["config"])
        return PublicFixture()

    envelopes = EvidenceProviderRegistry(
        provider_factories={provider_id: factory}, config={provider_id: config}, clock=lambda: FROZEN_NOW
    ).collect(request_for(capability_id, provider_id, parameters=parameters))

    document = envelopes[0].to_dict()
    assert received_config == [config]
    assert received_parameters == [parameters]
    assert secret not in json.dumps(document)
    validate_document(document, "urn:serenity:schema:provider-envelope:1")


def test_sec_filings_capability_dispatches_through_filings_provider_with_identity_and_cutoff() -> None:
    received: list[tuple[dict[str, object], str | None]] = []

    class FilingsFixture:
        def execute(self, request: dict[str, object], cutoff: str | None) -> ProviderEnvelope:
            received.append((request, cutoff))
            return available_envelope(provider="sec.filings", source_version="0001045810-26-000123", available_at="2026-08-14T00:00:00Z")

    envelopes = EvidenceProviderRegistry(
        provider_factories={"sec": lambda **_kwargs: FilingsFixture()}, clock=lambda: FROZEN_NOW
    ).collect(
        request_for(
            "sec.filings",
            "sec",
            parameters={"identity": {"ticker": "NVDA", "cik": "0001045810", "issuer": "NVIDIA CORP"}, "form": "10-Q"},
            cutoff="2026-08-17T00:00:00Z",
        )
    )

    assert received == [
        (
            {"identity": {"ticker": "NVDA", "cik": "0001045810", "issuer": "NVIDIA CORP"}, "form": "10-Q", "capability": "filings"},
            "2026-08-17T00:00:00Z",
        )
    ]
    assert [envelope.to_dict()["provider"] for envelope in envelopes] == ["sec.filings"]


def test_issuer_ir_document_dispatches_the_resolved_official_url_with_cutoff() -> None:
    received: list[tuple[dict[str, object], str | None, VerifiedIssuerOrigin | None]] = []

    class IssuerIRFixture:
        def collect(
            self,
            parameters: dict[str, object],
            cutoff: str | None = None,
            *,
            verified_origin: VerifiedIssuerOrigin | None = None,
        ) -> ProviderEnvelope:
            received.append((parameters, cutoff, verified_origin))
            return available_envelope(
                provider="issuer-ir",
                source_version="official-ir-document",
                available_at="2026-08-14T20:00:00Z",
            )

    parameters = {
        "identity": {"ticker": "NVDA", "cik": "0001045810", "issuer": "NVIDIA CORP"},
        "document": {
            "url": "https://investor.nvidia.com/events-and-presentations/example",
            "kind": "presentation",
        },
        "origin_binding": {
            "issuer_domain": "nvidia.com",
            "binding_source_ref": "snapshot-nvda-binding",
        },
    }
    verified = VerifiedIssuerOrigin(
        ticker="NVDA",
        cik="0001045810",
        issuer="NVIDIA CORP",
        issuer_domain="nvidia.com",
        binding_source_ref="snapshot-nvda-binding",
        binding_content_hash="b" * 64,
    )
    envelopes = EvidenceProviderRegistry(
        provider_factories={"issuer-ir": lambda **_kwargs: IssuerIRFixture()}, clock=lambda: FROZEN_NOW
    ).collect(
        request_for(
            "issuer-ir.document",
            "issuer-ir",
            parameters=parameters,
            cutoff="2026-08-17T00:00:00Z",
        ),
        issuer_origin_binding=verified,
    )

    assert received == [(parameters, "2026-08-17T00:00:00Z", verified)]
    assert [envelope.to_dict()["provider"] for envelope in envelopes] == ["issuer-ir"]


def test_snapshot_owned_baseline_capability_is_explicitly_not_applicable() -> None:
    envelopes = EvidenceProviderRegistry(clock=lambda: FROZEN_NOW).collect(
        request_for("openfigi.security-identity", "openfigi", parameters={"ticker": "NVDA"})
    )

    assert len(envelopes) == 1
    assert envelopes[0].to_dict()["status"] == "not_applicable"
    assert envelopes[0].to_dict()["error"] == {"reason": "baseline snapshot capability is owned by the snapshot service"}


@pytest.mark.parametrize(
    ("capability_id", "backend_verb", "parameters"),
    [
        ("sec.submissions", "submissions", {}),
        ("sec.filings", "filings", {"form": "10-Q"}),
        ("sec.filing-text", "filing_text", {"accession": "0001158114-26-000012", "format": "markdown"}),
        ("sec.filing-section", "section", {"form": "10-K", "named": "risk_factors"}),
        ("sec.xbrl-facts", "xbrl_facts", {"form": "10-K", "concept": "Revenues"}),
        ("sec.segments", "segments", {"form": "10-K", "axis": "ProductOrServiceAxis"}),
        ("sec.statement", "statement", {"form": "10-K", "statement": "income"}),
        ("sec.eightk", "eightk", {"item": "2.02"}),
    ],
)
def test_every_catalog_sec_capability_dispatches_to_its_declared_backend_verb(
    capability_id: str, backend_verb: str, parameters: dict[str, object]
) -> None:
    received: list[dict[str, object]] = []

    class FilingsFixture:
        def execute(self, request: dict[str, object], cutoff: str | None) -> ProviderEnvelope:
            received.append(request)
            return available_envelope(provider="sec.filings", source_version="0001158114-26-000012", available_at="2026-08-14T00:00:00Z")

    identity = {"ticker": "AAOI", "cik": "0001158114", "issuer": "APPLIED OPTOELECTRONICS, INC."}
    envelopes = EvidenceProviderRegistry(
        provider_factories={"sec": lambda **_kwargs: FilingsFixture()}, clock=lambda: FROZEN_NOW
    ).collect(
        request_for(capability_id, "sec", parameters={"identity": identity, **parameters}, cutoff="2026-08-17T00:00:00Z")
    )

    assert received == [{"identity": identity, **parameters, "capability": backend_verb}]
    assert [envelope.to_dict()["status"] for envelope in envelopes] == ["available"]


def test_no_catalog_sec_capability_is_left_without_a_real_filings_verb() -> None:
    from serenity_core.providers.filings import _CAPABILITIES
    from serenity_core.providers.registry import SEC_FILING_VERBS
    from serenity_core.research import load_evidence_catalog

    declared = next(provider["capabilities"] for provider in load_evidence_catalog()["providers"] if provider["provider_id"] == "sec")

    assert set(SEC_FILING_VERBS.values()) <= set(_CAPABILITIES)
    assert set(declared) - {"sec.identity"} == set(SEC_FILING_VERBS)


def test_the_two_alfred_fred_capabilities_ask_the_provider_for_different_vintages() -> None:
    """Two catalog IDs that dispatch identically are one capability wearing two
    names; the catalog would be advertising a read the runtime cannot perform."""

    modes: list[str] = []

    class FredFixture:
        def observations(
            self,
            _series_id: str,
            *,
            cutoff: str,
            observation_start: str | None = None,
            observation_end: str | None = None,
            vintages: str = "active",
        ) -> list[ProviderEnvelope]:
            modes.append(vintages)
            return [available_envelope(provider="fred", source_version="2026-06-15", available_at="2026-06-15T00:00:00Z")]

    registry = EvidenceProviderRegistry(
        provider_factories={"alfred-fred": lambda **_kwargs: FredFixture()}, clock=lambda: FROZEN_NOW
    )
    for capability_id in ("alfred-fred.macro-series", "alfred-fred.vintage-series"):
        registry.collect(
            request_for(capability_id, "alfred-fred", parameters={"series_id": "DGS10", "observation_start": "2026-01-01"}, cutoff="2026-07-01T00:00:00Z")
        )

    assert modes == ["active", "history"]


@pytest.mark.parametrize(
    ("capability_id", "provider_id", "parameters", "expected"),
    [
        ("sec.filing-section", "sec", {"identity": {"ticker": "NVDA", "cik": "0001045810", "issuer": "NVIDIA CORP"}}, "named"),
        ("sec.filing-section", "sec", {"identity": {"ticker": "NVDA", "cik": "0001045810", "issuer": "NVIDIA CORP"}, "named": "liquidity"}, "risk_factors"),
        ("sec.filings", "sec", {"identity": {"ticker": "NVDA", "cik": "0001045810"}}, "issuer"),
        ("alfred-fred.macro-series", "alfred-fred", {}, "series_id"),
        ("eia.energy-data", "eia", {"length": 5}, "route"),
        ("bls.labor-data", "bls", {"startyear": "2025"}, "series"),
        ("usaspending.federal-awards", "usaspending", {"recipient_search_text": ["Acme"]}, "award_type_codes"),
    ],
)
def test_a_provider_parameter_shape_the_capability_cannot_serve_names_what_is_missing(
    capability_id: str, provider_id: str, parameters: dict, expected: str
) -> None:
    """A model that guesses the shape wrong currently gets a typed-but-uninformative
    `unavailable` envelope after a real request went out. Naming the field in the
    refusal is what lets the next attempt be right rather than another guess."""

    def factory(**_kwargs: object) -> object:
        raise AssertionError("an invalid parameter shape must not reach a provider")

    registry = EvidenceProviderRegistry(provider_factories={provider_id: factory}, clock=lambda: FROZEN_NOW)

    with pytest.raises(ProviderRegistryValidationError) as failure:
        registry.collect(request_for(capability_id, provider_id, parameters=parameters, cutoff="2026-07-01T00:00:00Z"))

    assert expected in str(failure.value)
    assert capability_id in str(failure.value)


def test_a_valid_parameter_shape_still_reaches_the_provider() -> None:
    reached: list[dict] = []

    class SecFixture:
        def execute(self, request: dict, cutoff: str | None = None) -> ProviderEnvelope:
            reached.append(request)
            return available_envelope(provider="sec.filings", source_version="0001045810-26-000021", available_at="2026-06-15T00:00:00Z")

    EvidenceProviderRegistry(provider_factories={"sec": lambda **_kwargs: SecFixture()}, clock=lambda: FROZEN_NOW).collect(
        request_for(
            "sec.filing-section",
            "sec",
            parameters={"identity": {"ticker": "NVDA", "cik": "0001045810", "issuer": "NVIDIA CORP"}, "named": "risk_factors", "form": "10-K"},
            cutoff="2026-07-01T00:00:00Z",
        )
    )

    assert reached and reached[0]["named"] == "risk_factors"


def test_every_dispatchable_capability_declares_a_parameter_contract() -> None:
    """A partial map is a trap: a model that finds no entry for its capability
    cannot tell "anything goes" from "nobody wrote this one down yet"."""

    catalog = load_evidence_catalog()
    declared = {capability_id for provider in catalog["providers"] for capability_id in provider.get("capability_parameters", {})}
    dispatchable = {
        capability_id
        for provider in catalog["providers"]
        for capability_id in provider["capabilities"]
        if capability_id not in _SNAPSHOT_CAPABILITIES
    }

    assert dispatchable - declared == set()
