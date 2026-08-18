#!/usr/bin/env python3
"""Capture one real response per HTTP-JSON provider, through the adapter itself.

A hand-authored fixture records what its author believed the provider returns,
and stays green forever once that belief is wrong. These payloads are recorded
by running the real provider against the real endpoint with a transport that
delegates to the production default and writes down what came back, so the file
is provably the response to the request the adapter actually makes -- and the
replay test in tests/260817/adapters/test_recorded_payloads.py drives the same
adapter over it.

    python tests/260817/fixtures/recorded/capture_payloads.py --list
    python tests/260817/fixtures/recorded/capture_payloads.py --provider cftc
    python tests/260817/fixtures/recorded/capture_payloads.py --all

Re-capture when a provider changes its response shape, never to make a failing
test pass: a replay failure means the adapter and the provider disagree, and
overwriting the payload hides exactly the drift this suite exists to surface.
Providers needing a credential this machine lacks are reported as skipped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


RECORDED_ROOT = Path(__file__).resolve().parent
REPO_ROOT = RECORDED_ROOT.parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

# One case per provider: the query is stored beside the payload so the replay
# test reads what was captured instead of restating it and drifting.
CASES: dict[str, dict[str, Any]] = {
    "sec": {"case": "resolve-ticker", "query": {"ticker": "SWK"}},
    "openfigi": {"case": "map-ticker", "query": {"ticker": "SWK"}},
    "fred": {"case": "observations", "query": {"series_id": "DGS10", "cutoff": "2026-08-15T00:00:00Z", "observation_start": "2026-07-01", "observation_end": "2026-07-31"}},
    # award_type_codes is not optional: USASpending answers 422 without it.
    "usaspending": {"case": "award-search", "query": {"recipient_search_text": ["Stanley Black"], "award_type_codes": ["A", "B", "C", "D"], "limit": 3}},
    "eia": {"case": "region-data", "query": {"route": "electricity/rto/region-data", "length": 3}},
    "bls": {"case": "series-data", "query": {"series": ["CES0000000001"], "startyear": "2025", "endyear": "2025"}},
    "cftc": {"case": "commitments", "query": {"$limit": 3}},
    "federal-register": {"case": "documents", "query": {"per_page": 2, "order": "newest"}},
}


class RecordingTransport:
    """Delegate to the production transport and keep every call in order."""

    def __init__(self, inner: Callable[..., Any]) -> None:
        self._inner = inner
        self.calls: list[tuple[str, bytes]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        result = self._inner(*args, **kwargs)
        body = result if isinstance(result, bytes) else getattr(result, "body", None)
        if isinstance(body, bytes):
            # The URL only, never the request object: its repr carries the query
            # and body, and a keyed provider puts its credential there.
            self.calls.append((str(getattr(args[0], "url", args[0])), body))
        return result


def _capture_sec(query: dict[str, Any]) -> list[tuple[str, bytes]]:
    from serenity_core.providers.sec import SecIdentityProvider, default_http_get

    transport = RecordingTransport(default_http_get)
    SecIdentityProvider(http_get=transport).resolve(query["ticker"])
    return transport.calls


def _capture_openfigi(query: dict[str, Any]) -> list[tuple[str, bytes]]:
    from serenity_core.providers.openfigi import OpenFigiProvider, default_http_post

    transport = RecordingTransport(default_http_post)
    OpenFigiProvider(http_post=transport).lookup(query["ticker"])
    return transport.calls


def _capture_fred(query: dict[str, Any]) -> list[tuple[str, bytes]]:
    from serenity_core.providers.fred import FredProvider, _default_http_get

    transport = RecordingTransport(_default_http_get)
    FredProvider(http_get=transport).observations(
        query["series_id"],
        cutoff=query["cutoff"],
        observation_start=query.get("observation_start"),
        observation_end=query.get("observation_end"),
    )
    return transport.calls


def _capture_public_data(provider_id: str, query: dict[str, Any]) -> list[tuple[str, bytes]]:
    from serenity_core.providers.public_data import _default_http, public_data_catalog

    transport = RecordingTransport(_default_http)
    adapter = public_data_catalog(http=transport, config=_public_data_config(provider_id))[provider_id]
    if not adapter.configured:
        raise LookupError(adapter.unavailable_reason or f"{provider_id} is not configured on this machine")
    adapter.collect(query)
    return [(call[0].url if hasattr(call[0], "url") else str(call[0]), call[1]) for call in transport.calls]


def _public_data_config(provider_id: str) -> dict[str, str]:
    key = {"eia": ("eia_api_key", "EIA_API_KEY"), "bls": ("bls_registration_key", "BLS_REGISTRATION_KEY"), "bea": ("bea_api_key", "BEA_API_KEY"), "sam": ("sam_api_key", "SAM_API_KEY"), "uspto": ("uspto_api_key", "USPTO_API_KEY")}.get(provider_id)
    if key is None:
        return {}
    # EIA publishes DEMO_KEY for exactly this: a real, rate-limited public path.
    configured = os.environ.get(key[1]) or ("DEMO_KEY" if provider_id == "eia" else "")
    return {key[0]: configured} if configured else {}


def capture(provider_id: str) -> Path:
    definition = CASES[provider_id]
    query = definition["query"]
    if provider_id == "sec":
        calls = _capture_sec(query)
    elif provider_id == "openfigi":
        calls = _capture_openfigi(query)
    elif provider_id == "fred":
        calls = _capture_fred(query)
    else:
        calls = _capture_public_data(provider_id, query)
    if not calls:
        raise LookupError(f"{provider_id} made no recordable call; check credentials and connectivity")

    directory = RECORDED_ROOT / provider_id
    directory.mkdir(parents=True, exist_ok=True)
    recorded = []
    for index, (uri, body) in enumerate(calls):
        payload = f"{definition['case']}-{index}.json"
        (directory / payload).write_bytes(body)
        recorded.append({"uri": uri, "payload": payload, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)})
    meta = {
        "provider_id": provider_id,
        "case": definition["case"],
        "query": query,
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "calls": recorded,
    }
    serialized = json.dumps(meta, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    _refuse_to_write_a_credential(serialized)
    meta_path = directory / f"{definition['case']}.meta.json"
    meta_path.write_text(serialized, encoding="utf-8")
    return meta_path


def _refuse_to_write_a_credential(serialized: str) -> None:
    """Make committing a key impossible rather than merely discouraged.

    Every value this process holds that looks like a credential is checked
    against what is about to be written. DEMO_KEY is exempt because EIA
    publishes it as the public path.
    """

    for name, value in os.environ.items():
        if len(value) < 12 or value == "DEMO_KEY" or not any(marker in name for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            continue
        if value in serialized:
            raise SystemExit(f"refusing to write a recording containing the value of {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="show which providers are recorded and when")
    group.add_argument("--all", action="store_true", help="re-capture every provider reachable from this machine")
    group.add_argument("--provider", choices=sorted(CASES), help="re-capture one provider")
    arguments = parser.parse_args()

    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")

    if arguments.list:
        for provider_id in sorted(CASES):
            meta = RECORDED_ROOT / provider_id / f"{CASES[provider_id]['case']}.meta.json"
            print(f"{provider_id:18} {json.loads(meta.read_text())['captured_at'] if meta.exists() else 'not recorded'}")
        return 0

    failures = 0
    for provider_id in sorted(CASES) if arguments.all else [arguments.provider]:
        try:
            print(f"{provider_id:18} -> {capture(provider_id).relative_to(REPO_ROOT)}")
        except Exception as error:
            failures += 1
            print(f"{provider_id:18} -- skipped: {type(error).__name__}: {error}", file=sys.stderr)
    return 1 if failures and not arguments.all else 0


if __name__ == "__main__":
    raise SystemExit(main())
