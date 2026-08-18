"""Replay a real captured response through the adapter that will parse it.

A hand-authored fixture encodes its author's belief about a provider's response
shape, so an adapter written against the same belief passes forever while the
capability is structurally dead. These payloads were captured from the live
endpoints by tests/260817/fixtures/recorded/capture_payloads.py, driving each
provider's own request builder, and are replayed here through the same seam.

The suite is data-driven on purpose: capturing a new provider adds coverage
without editing this file, so nothing has to remember to widen a parametrize
list. A payload whose hash no longer matches its record fails before it is
parsed -- a recorded response edited by hand is a hand-authored fixture again.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from serenity_core.providers.fred import FredProvider
from serenity_core.providers.openfigi import OpenFigiProvider
from serenity_core.providers.public_data import HttpResponse, public_data_catalog
from serenity_core.providers.sec import SecIdentityProvider
from serenity_core.schema import validate_document


RECORDED_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "recorded"
FROZEN_NOW = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
RECORDINGS = sorted(RECORDED_ROOT.glob("*/*.meta.json"))


def _identifier(path: Path) -> str:
    return f"{path.parent.name}:{path.stem.removesuffix('.meta')}"


class Replay:
    """Answer each call with the next recorded body, in capture order."""

    def __init__(self, bodies: list[bytes]) -> None:
        self._bodies = list(bodies)
        self.count = 0

    def bytes(self, *_args: Any, **_kwargs: Any) -> bytes:
        body = self._bodies[min(self.count, len(self._bodies) - 1)]
        self.count += 1
        return body

    def http(self, *args: Any, **kwargs: Any) -> HttpResponse:
        return HttpResponse(status=200, body=self.bytes(*args, **kwargs), headers={})


def _load(path: Path) -> tuple[dict[str, Any], Replay]:
    meta = json.loads(path.read_text(encoding="utf-8"))
    bodies = []
    for call in meta["calls"]:
        body = (path.parent / call["payload"]).read_bytes()
        assert hashlib.sha256(body).hexdigest() == call["sha256"], f"{call['payload']} no longer matches its recorded hash"
        bodies.append(body)
    return meta, Replay(bodies)


def _replay(meta: dict[str, Any], replay: Replay) -> list[dict[str, Any]]:
    provider_id, query = meta["provider_id"], meta["query"]
    if provider_id == "sec":
        lookup = SecIdentityProvider(http_get=replay.bytes, clock=lambda: FROZEN_NOW, user_agent="Serenity Test test@example.com").resolve(query["ticker"])
        assert lookup.rejection is None, lookup.rejection
        assert lookup.cik and lookup.official_name
        return [envelope.to_dict() for envelope in lookup.provider_envelopes]
    if provider_id == "openfigi":
        lookup = OpenFigiProvider(http_post=replay.bytes, clock=lambda: FROZEN_NOW).lookup(query["ticker"])
        assert lookup.record, lookup.envelope
        return [lookup.provider_envelope.to_dict()]
    if provider_id == "fred":
        envelopes = FredProvider(api_key="test-key", http_get=replay.bytes, clock=lambda: FROZEN_NOW).observations(
            query["series_id"], cutoff=query["cutoff"], observation_start=query.get("observation_start"), observation_end=query.get("observation_end")
        )
        return [envelope.to_dict() for envelope in envelopes]
    adapter = public_data_catalog(http=replay.http, clock=lambda: FROZEN_NOW, config={f"{provider_id.replace('-', '_')}_api_key": "test-key", "bls_registration_key": "test-key"})[provider_id]
    return [adapter.collect(query).to_dict()]


@pytest.mark.parametrize("path", RECORDINGS, ids=[_identifier(path) for path in RECORDINGS])
def test_a_recorded_response_parses_into_available_evidence(path: Path) -> None:
    meta, replay = _load(path)

    envelopes = _replay(meta, replay)

    assert replay.count == len(meta["calls"]), "the adapter no longer makes the calls that were captured"
    assert any(envelope["status"] == "available" for envelope in envelopes), [envelope.get("error") for envelope in envelopes]
    for envelope in envelopes:
        validate_document(envelope, "urn:serenity:schema:provider-envelope:1")


def test_every_capturable_provider_is_actually_recorded() -> None:
    """Coverage that is silently absent is the failure mode this suite exists for."""

    recorded = {path.parent.name for path in RECORDINGS}

    assert recorded == {"sec", "openfigi", "fred", "usaspending", "eia", "bls", "cftc", "federal-register"}
