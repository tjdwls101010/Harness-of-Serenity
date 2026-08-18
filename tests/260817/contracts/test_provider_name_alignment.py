"""The catalog owner of a capability must accept the name its real provider stamps.

A catalog ``provider_id`` is a registry identity (who owns the capability); a
provider envelope's ``provider`` is a source identity (which endpoint produced
the bytes). They are separate names, so this probes every real provider class
with an injected transport and checks the emitted names against what the
catalog declares. One assertion covers every provider, present and future.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json

import pytest

from serenity_core.providers.base import ProviderEnvelope
from serenity_core.providers.filings import FilingsProvider
from serenity_core.providers.fred import FredProvider
from serenity_core.providers.issuer_ir import IssuerIRProvider
from serenity_core.providers.openfigi import OpenFigiProvider
from serenity_core.providers.public_data import public_data_catalog
from serenity_core.providers.rs_rating import RsRatingProvider
from serenity_core.providers.sec import SecIdentityProvider
from serenity_core.providers.yfinance import YFinanceProvider
from serenity_core.research import catalog_source_providers, load_evidence_catalog


FROZEN_NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
IDENTITY = {"ticker": "AAOI", "cik": "0001158114", "issuer": "APPLIED OPTOELECTRONICS, INC."}


def _refuse(*_args: object, **_kwargs: object) -> object:
    raise OSError("structural probe refuses every external call")


def _names(envelopes: object) -> set[str]:
    candidates = envelopes if isinstance(envelopes, (list, tuple)) else [envelopes]
    assert candidates, "a provider probe must produce at least one envelope"
    emitted = set()
    for envelope in candidates:
        assert isinstance(envelope, ProviderEnvelope)
        emitted.add(envelope.to_dict()["provider"])
    return emitted


def _yfinance() -> set[str]:
    return _names(YFinanceProvider(ticker_factory=_refuse, clock=lambda: FROZEN_NOW).fetch("AAOI"))


def _sec_identity() -> set[str]:
    directory = json.dumps({"0": {"cik_str": 1158114, "ticker": "AAOI", "title": IDENTITY["issuer"]}}).encode()

    def http_get(uri: str, _headers: dict[str, str]) -> bytes:
        if uri.endswith("company_tickers.json"):
            return directory
        raise OSError("structural probe refuses the submissions call")

    lookup = SecIdentityProvider(http_get=http_get, clock=lambda: FROZEN_NOW, user_agent="Serenity Probe probe@example.com").resolve("AAOI")
    return _names(list(lookup.provider_envelopes))


def _sec_filings() -> set[str]:
    class RefusingBackend:
        def execute(self, _request: dict[str, object]) -> object:
            raise OSError("structural probe refuses the EDGAR call")

    provider = FilingsProvider(backend=RefusingBackend(), clock=lambda: FROZEN_NOW)
    return _names(provider.execute({"identity": dict(IDENTITY), "capability": "filings"}))


def _openfigi() -> set[str]:
    return _names(OpenFigiProvider(http_post=_refuse, clock=lambda: FROZEN_NOW).lookup("AAOI").provider_envelope)


def _fred() -> set[str]:
    return _names(FredProvider(api_key=None, http_get=_refuse, clock=lambda: FROZEN_NOW).observations("DGS10", cutoff="2026-08-17T23:59:59Z"))


def _rs_rating() -> set[str]:
    class RefusingClient:
        def get(self, _ticker: str, *, date: str | None = None) -> object:
            raise OSError("structural probe refuses the rating call")

    return _names(RsRatingProvider(client=RefusingClient(), clock=lambda: FROZEN_NOW).fetch("AAOI"))


def _issuer_ir() -> set[str]:
    return _names(IssuerIRProvider(http_get=_refuse, clock=lambda: FROZEN_NOW).collect({}))


PUBLIC_DATA_QUERIES = {
    "usaspending": {"recipient_search_text": ["Acme"]},
    "usitc": {"hs_codes": ["854231"], "year": 2025},
    "eia": {"route": "electricity/rto/region-data"},
    "bls": {"series": ["CES0000000001"]},
    "bea": {"method": "GetData", "datasetname": "NIPA"},
    "cftc": {"$limit": 1},
    "federal-register": {"conditions[type][]": "RULE"},
    "bis": {"q": "export control"},
    "sam": {"uei": "ABC123"},
    "uspto": {"patent_number": "12345678"},
}


def _public_data(provider_id: str) -> set[str]:
    adapter = public_data_catalog(http=_refuse, clock=lambda: FROZEN_NOW)[provider_id]
    return _names(adapter.collect(PUBLIC_DATA_QUERIES[provider_id]))


EMITTED_NAME_PROBES = {
    "yfinance": _yfinance,
    "sec": lambda: _sec_identity() | _sec_filings(),
    "openfigi": _openfigi,
    "alfred-fred": _fred,
    "ibd-rs-rating": _rs_rating,
    "issuer-ir": _issuer_ir,
    **{
        provider_id: (lambda provider_id=provider_id: _public_data(provider_id))
        for provider_id in PUBLIC_DATA_QUERIES
    },
}


def test_every_catalog_provider_has_an_emitted_name_probe() -> None:
    declared = {provider["provider_id"] for provider in load_evidence_catalog()["providers"]}

    assert declared == set(EMITTED_NAME_PROBES)


@pytest.mark.parametrize("provider_id", sorted(EMITTED_NAME_PROBES))
def test_capability_owner_accepts_every_name_its_real_provider_emits(provider_id: str) -> None:
    catalog = load_evidence_catalog()
    accepted = catalog_source_providers(catalog)
    capabilities = next(provider["capabilities"] for provider in catalog["providers"] if provider["provider_id"] == provider_id)

    emitted = EMITTED_NAME_PROBES[provider_id]()

    for capability_id in capabilities:
        assert emitted <= accepted[capability_id], (
            f"{provider_id} emits {sorted(emitted - accepted[capability_id])} "
            f"but the catalog owner of {capability_id} accepts {sorted(accepted[capability_id])}"
        )
