from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from serenity_v2.providers.issuer_ir import IssuerIRHttpResponse, IssuerIRProvider, VerifiedIssuerOrigin
from serenity_v2.raw_cache import RawPayloadStore
from serenity_v2.schema import validate_document


FROZEN_NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)


def request(*, url: str = "https://investors.acme.test/news/q2-results", published_at_claim: str = "2026-08-14T20:05:00Z") -> dict:
    return {
        "identity": {"ticker": "ACME", "cik": "0000123456", "issuer": "Acme Corp."},
        "document": {
            "url": url,
            "kind": "prepared_remarks",
            "published_at_claim": published_at_claim,
            "title_claim": "Caller-supplied title must not become evidence",
        },
        "origin_binding": {
            "issuer_domain": "investors.acme.test",
            "binding_source_ref": "snapshot-acme-binding",
        },
    }


def verified_origin() -> VerifiedIssuerOrigin:
    return VerifiedIssuerOrigin(
        ticker="ACME",
        cik="0000123456",
        issuer="Acme Corp.",
        issuer_domain="investors.acme.test",
        binding_source_ref="snapshot-acme-binding",
        binding_content_hash="c" * 64,
    )


def response(*, published_at: str = "2026-08-14T20:05:00Z") -> IssuerIRHttpResponse:
    body = (
        '<html><head><meta property="article:published_time" content="'
        + published_at
        + '"><title>Official Q2 2026 prepared remarks</title></head><body><article><p>Customer qualification is complete.</p><p>Volume production begins in 2027.</p></article></body></html>'
    ).encode()
    return IssuerIRHttpResponse(
        status=200,
        body=body,
        headers={
            "Content-Type": "text/html; charset=utf-8",
            "ETag": '"q2-v1"',
            "Last-Modified": "Fri, 14 Aug 2026 20:05:00 GMT",
        },
        final_url="https://investors.acme.test/news/q2-results.html",
        redirect_chain=(
            "https://investors.acme.test/news/q2-results",
            "https://investors.acme.test/news/q2-results.html",
        ),
    )


def test_issuer_ir_document_preserves_exact_bytes_origin_time_and_extracted_text(tmp_path: Path) -> None:
    raw = response()
    provider = IssuerIRProvider(http_get=lambda _url: raw, clock=lambda: FROZEN_NOW)

    envelope = provider.collect(request(), cutoff="2026-08-17T00:00:00Z", verified_origin=verified_origin())
    document = envelope.to_dict()

    assert document["status"] == "available"
    assert document["provider"] == "issuer-ir"
    assert document["identity_bindings"] == {"ticker": "ACME", "cik": "0000123456", "issuer": "Acme Corp."}
    assert document["source"]["uri"] == raw.final_url
    assert document["source"]["content_sha256"] == hashlib.sha256(raw.body).hexdigest()
    assert document["source"]["http_status"] == 200
    assert document["source"]["parameters"] == {
        "binding_content_hash": "c" * 64,
        "binding_source_ref": "snapshot-acme-binding",
        "content_type": "text/html; charset=utf-8",
        "document_kind": "prepared_remarks",
        "etag": '"q2-v1"',
        "final_url": raw.final_url,
        "issuer_domain": "investors.acme.test",
        "last_modified": "Fri, 14 Aug 2026 20:05:00 GMT",
        "redirect_chain": list(raw.redirect_chain),
        "requested_url": "https://investors.acme.test/news/q2-results",
    }
    assert document["temporal"]["available_at"] == "2026-08-14T20:05:00Z"
    assert document["temporal"]["source_version"] == '"q2-v1"'
    assert document["data"] == {
        "document_kind": "prepared_remarks",
        "publication_time_source": "html:article:published_time",
        "text": "Customer qualification is complete. Volume production begins in 2027.",
        "title": "Official Q2 2026 prepared remarks",
    }
    assert document["parse"] == {"status": "parsed", "transform_version": "issuer-ir-document/1"}
    cached = RawPayloadStore(tmp_path / "raw-cache").cache(envelope)
    assert cached.content_sha256 == hashlib.sha256(raw.body).hexdigest()
    assert cached.path is not None and cached.path.read_bytes() == raw.body
    validate_document(document, "urn:serenity:schema:provider-envelope:1")


def test_issuer_ir_rejects_nonissuer_origin_before_network() -> None:
    called = False

    def http_get(_url: str) -> IssuerIRHttpResponse:
        nonlocal called
        called = True
        raise AssertionError("origin mismatch must stop before network")

    provider = IssuerIRProvider(http_get=http_get, clock=lambda: FROZEN_NOW)

    document = provider.collect(request(url="https://news.example.test/acme-ceo"), verified_origin=verified_origin()).to_dict()

    assert called is False
    assert document["status"] == "conflict"
    assert document["error"] == {"reason": "document URL is not bound to the resolved issuer domain"}
    assert document["source"]["content_sha256"] is None
    validate_document(document, "urn:serenity:schema:provider-envelope:1")


def test_issuer_ir_rejects_an_offdomain_intermediate_redirect() -> None:
    raw = response()
    redirected = IssuerIRHttpResponse(
        status=raw.status,
        body=raw.body,
        headers=raw.headers,
        final_url=raw.final_url,
        redirect_chain=(
            "https://investors.acme.test/news/q2-results",
            "https://tracking.example.test/issuer-hop",
            raw.final_url,
        ),
    )

    document = IssuerIRProvider(http_get=lambda _url: redirected, clock=lambda: FROZEN_NOW).collect(
        request(), verified_origin=verified_origin()
    ).to_dict()

    assert document["status"] == "conflict"
    assert document["error"] == {"reason": "redirect chain left the resolved issuer domain"}


def test_issuer_ir_rejects_caller_supplied_identity_and_domain_without_a_runtime_verified_binding() -> None:
    called = False

    def http_get(_url: str) -> IssuerIRHttpResponse:
        nonlocal called
        called = True
        return response()

    document = IssuerIRProvider(http_get=http_get, clock=lambda: FROZEN_NOW).collect(request()).to_dict()

    assert called is False
    assert document["status"] == "conflict"
    assert document["error"] == {"reason": "issuer origin binding was not verified by the active run"}


def test_issuer_ir_historical_cutoff_never_uses_fetch_time_or_a_postcutoff_document() -> None:
    provider = IssuerIRProvider(http_get=lambda _url: response(published_at="2026-08-18T00:00:00Z"), clock=lambda: FROZEN_NOW)

    postcutoff = provider.collect(
        request(published_at_claim="2026-08-18T00:00:00Z"),
        cutoff="2026-08-17T23:59:59Z",
        verified_origin=verified_origin(),
    ).to_dict()

    assert postcutoff["status"] == "unavailable"
    assert postcutoff["error"] == {"reason": "issuer document was not available by historical cutoff"}
    assert postcutoff["temporal"]["available_at"] == "2026-08-18T00:00:00Z"

    missing_time = IssuerIRHttpResponse(
        status=200,
        body=b"<html><body>Prepared remarks without publication metadata.</body></html>",
        headers={"Content-Type": "text/html"},
        final_url="https://investors.acme.test/news/q2-results",
        redirect_chain=(),
    )
    unknown = IssuerIRProvider(http_get=lambda _url: missing_time, clock=lambda: FROZEN_NOW).collect(
        request(published_at_claim=""),
        cutoff="2026-08-17T23:59:59Z",
        verified_origin=verified_origin(),
    ).to_dict()

    assert unknown["status"] == "unavailable"
    assert unknown["error"] == {"reason": "issuer publication time is unknown for historical use"}
    assert unknown["temporal"]["available_at"] is None
    assert unknown["fetched_at"] == "2026-08-17T12:00:00Z"
    validate_document(postcutoff, "urn:serenity:schema:provider-envelope:1")
    validate_document(unknown, "urn:serenity:schema:provider-envelope:1")


def test_issuer_ir_failures_retain_received_bytes_without_fabricating_content() -> None:
    raw = b"upstream unavailable"
    provider = IssuerIRProvider(
        http_get=lambda _url: IssuerIRHttpResponse(
            status=503,
            body=raw,
            headers={"Content-Type": "text/plain"},
            final_url="https://investors.acme.test/news/q2-results",
            redirect_chain=(),
        ),
        clock=lambda: FROZEN_NOW,
    )

    document = provider.collect(request(), verified_origin=verified_origin()).to_dict()

    assert document["status"] == "unavailable"
    assert document["data"] is None
    assert document["source"]["content_sha256"] == hashlib.sha256(raw).hexdigest()
    assert document["source"]["http_status"] == 503
    assert document["parse"] == {
        "status": "not_parsed",
        "transform_version": "issuer-ir-document/1",
        "message": "HTTP 503",
    }
    validate_document(document, "urn:serenity:schema:provider-envelope:1")
