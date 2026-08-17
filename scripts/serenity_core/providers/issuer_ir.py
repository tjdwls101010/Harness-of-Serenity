"""Identity-bound issuer narrative documents with exact raw-byte provenance."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any, Callable, Mapping
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from serenity_core.providers.base import ProviderEnvelope


PROVIDER_VERSION = "issuer-ir-document/1"
TRANSFORM_VERSION = "issuer-ir-document/1"
DOCUMENT_KINDS = frozenset({"press_release", "presentation", "prepared_remarks", "call_transcript", "other"})
HttpGet = Callable[[str], "IssuerIRHttpResponse"]


@dataclass(frozen=True)
class IssuerIRHttpResponse:
    status: int
    body: bytes
    headers: Mapping[str, str]
    final_url: str
    redirect_chain: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerifiedIssuerOrigin:
    """Runtime-verified snapshot binding; never reconstructed from request JSON."""

    ticker: str
    cik: str
    issuer: str
    issuer_domain: str
    binding_source_ref: str
    binding_content_hash: str


class _IssuerHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.title: list[str] = []
        self.publication_times: list[tuple[str, str]] = []
        self._ignored_depth = 0
        self._title_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._ignored_depth += 1
        if tag == "title":
            self._title_depth += 1
        if tag != "meta":
            return
        values = {key.casefold(): value for key, value in attrs if value is not None}
        marker = (values.get("property") or values.get("name") or values.get("itemprop") or "").casefold()
        content = values.get("content")
        if content and marker in {"article:published_time", "datepublished", "publishdate", "parsely-pub-date"}:
            self.publication_times.append((f"html:{marker}", content))

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1
        if tag == "title" and self._title_depth:
            self._title_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._title_depth and data.strip():
            self.title.append(data.strip())
        elif not self._ignored_depth and data.strip():
            self.text.append(data.strip())


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | str) -> str:
    if isinstance(value, str):
        parsed = _parse_instant(value)
    else:
        parsed = value
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class _RecordingRedirectHandler(HTTPRedirectHandler):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any:
        self.urls.append(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _redirect_chain(requested_url: str, final_url: str, redirected_urls: list[str]) -> tuple[str, ...]:
    if not redirected_urls and final_url == requested_url:
        return ()
    chain = [requested_url, *redirected_urls]
    if chain[-1] != final_url:
        chain.append(final_url)
    return tuple(chain)


def _default_http_get(url: str) -> IssuerIRHttpResponse:
    request = Request(
        url,
        headers={"Accept": "text/html,application/pdf,text/plain", "User-Agent": "Harness-of-Serenity/2 issuer-evidence"},
        method="GET",
    )
    redirect_handler = _RecordingRedirectHandler()
    opener = build_opener(redirect_handler)
    try:
        with opener.open(request, timeout=30) as response:  # noqa: S310
            final_url = response.geturl()
            return IssuerIRHttpResponse(
                status=response.status,
                body=response.read(),
                headers=dict(response.headers.items()),
                final_url=final_url,
                redirect_chain=_redirect_chain(url, final_url, redirect_handler.urls),
            )
    except HTTPError as error:
        final_url = error.geturl() or url
        return IssuerIRHttpResponse(
            status=error.code,
            body=error.read(),
            headers=dict(error.headers.items()) if error.headers is not None else {},
            final_url=final_url,
            redirect_chain=_redirect_chain(url, final_url, redirect_handler.urls),
        )


def _header(headers: Mapping[str, str], name: str) -> str | None:
    target = name.casefold()
    return next((value for key, value in headers.items() if key.casefold() == target), None)


def _host_matches(host: str | None, issuer_domain: str) -> bool:
    return isinstance(host, str) and (host == issuer_domain or host.endswith(f".{issuer_domain}"))


def _url_matches_origin(url: str, issuer_domain: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and _host_matches(parsed.hostname, issuer_domain)


def _identity(value: Any) -> dict[str, str] | None:
    if not isinstance(value, Mapping):
        return None
    ticker = value.get("ticker")
    cik = value.get("cik")
    issuer = value.get("issuer")
    if not all(isinstance(item, str) and item.strip() for item in (ticker, cik, issuer)):
        return None
    normalized_cik = cik.strip()
    if not normalized_cik.isdigit():
        return None
    return {"ticker": ticker.strip().upper(), "cik": f"{int(normalized_cik):010d}", "issuer": issuer.strip()}


def _parse_html(raw: bytes) -> tuple[str, str | None, str | None, str | None]:
    text = raw.decode("utf-8")
    parser = _IssuerHTMLParser()
    parser.feed(text)
    publication_source: str | None = None
    publication_time: str | None = None
    for source, candidate in parser.publication_times:
        try:
            publication_time = _iso(candidate)
        except ValueError:
            continue
        publication_source = source
        break
    if publication_time is None:
        match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', text, flags=re.IGNORECASE)
        if match is not None:
            try:
                publication_time = _iso(match.group(1))
                publication_source = "html:json-ld:datePublished"
            except ValueError:
                pass
    extracted = " ".join(" ".join(parser.text).split())
    title = " ".join(" ".join(parser.title).split()) or None
    return extracted, publication_time, publication_source, title


def _http_last_modified(headers: Mapping[str, str]) -> str | None:
    value = _header(headers, "Last-Modified")
    if value is None:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return _iso(parsed)


def _parse_metadata(status: str, message: str | None = None) -> dict[str, str]:
    result = {"status": status, "transform_version": TRANSFORM_VERSION}
    if message is not None:
        result["message"] = message
    return result


class IssuerIRProvider:
    """Fetch one already-resolved official issuer document; never crawl or judge it."""

    provider_id = "issuer-ir"
    capabilities = ("issuer-ir.document",)
    secret_parameter_names: tuple[str, ...] = ()

    def __init__(self, *, http_get: HttpGet | None = None, clock: Callable[[], datetime] = _utc_now) -> None:
        self._http_get = http_get or _default_http_get
        self._clock = clock

    def collect(
        self,
        parameters: Mapping[str, Any],
        cutoff: str | None = None,
        *,
        verified_origin: VerifiedIssuerOrigin | None = None,
    ) -> ProviderEnvelope:
        fetched_at = _iso(self._clock())
        request = dict(parameters) if isinstance(parameters, Mapping) else {}
        identity = _identity(request.get("identity"))
        document = request.get("document")
        origin = request.get("origin_binding")
        url = document.get("url") if isinstance(document, Mapping) else None
        source_uri = url if isinstance(url, str) and urlparse(url).scheme in {"http", "https"} else "https://invalid.invalid/issuer-ir"
        if identity is None or not isinstance(document, Mapping) or not isinstance(origin, Mapping):
            return self._unavailable(source_uri, fetched_at, request, identity or {}, "invalid", "issuer-ir.document requires identity, document, and origin_binding", parse_status="not_parsed")
        kind = document.get("kind")
        issuer_domain = origin.get("issuer_domain")
        binding_source_ref = origin.get("binding_source_ref")
        if not isinstance(url, str) or urlparse(url).scheme != "https" or kind not in DOCUMENT_KINDS or not isinstance(issuer_domain, str) or not issuer_domain or not isinstance(binding_source_ref, str) or not binding_source_ref:
            return self._unavailable(source_uri, fetched_at, request, identity, "invalid", "issuer-ir.document parameters are invalid", parse_status="not_parsed")
        issuer_domain = issuer_domain.casefold().strip(".")
        if verified_origin is None:
            return self._unavailable(source_uri, fetched_at, request, identity, "conflict", "issuer origin binding was not verified by the active run", parse_status="not_parsed")
        expected_binding = (
            verified_origin.ticker,
            verified_origin.cik,
            verified_origin.issuer,
            verified_origin.issuer_domain.casefold().strip("."),
            verified_origin.binding_source_ref,
        )
        supplied_binding = (identity["ticker"], identity["cik"], identity["issuer"], issuer_domain, binding_source_ref)
        if supplied_binding != expected_binding or not re.fullmatch(r"[a-f0-9]{64}", verified_origin.binding_content_hash):
            return self._unavailable(source_uri, fetched_at, request, identity, "conflict", "issuer origin binding does not match the active run", parse_status="not_parsed")
        if not _url_matches_origin(url, issuer_domain):
            return self._unavailable(source_uri, fetched_at, request, identity, "conflict", "document URL is not bound to the resolved issuer domain", parse_status="not_parsed")
        try:
            cutoff_at = _parse_instant(cutoff) if cutoff is not None else None
        except ValueError:
            return self._unavailable(source_uri, fetched_at, request, identity, "invalid", "historical cutoff is invalid", parse_status="not_parsed")
        try:
            response = self._http_get(url)
        except OSError as error:
            return self._unavailable(source_uri, fetched_at, request, identity, "unavailable", f"transport error: {error}", parse_status="not_parsed", message=f"transport error: {error}")
        final_url = response.final_url or url
        source_parameters = self._source_parameters(
            requested_url=url,
            final_url=final_url,
            response=response,
            document_kind=kind,
            issuer_domain=issuer_domain,
            binding_source_ref=binding_source_ref,
            binding_content_hash=verified_origin.binding_content_hash,
        )
        if any(not _url_matches_origin(hop, issuer_domain) for hop in response.redirect_chain):
            return self._unavailable(final_url, fetched_at, request, identity, "conflict", "redirect chain left the resolved issuer domain", parse_status="not_parsed", raw_content=response.body, http_status=response.status, source_parameters=source_parameters)
        if not _url_matches_origin(final_url, issuer_domain):
            return self._unavailable(final_url, fetched_at, request, identity, "conflict", "redirect left the resolved issuer domain", parse_status="not_parsed", raw_content=response.body, http_status=response.status, source_parameters=source_parameters)
        if not 200 <= response.status < 300:
            return self._unavailable(final_url, fetched_at, request, identity, "unavailable", f"HTTP {response.status}", parse_status="not_parsed", message=f"HTTP {response.status}", raw_content=response.body, http_status=response.status, source_parameters=source_parameters)
        content_type = (_header(response.headers, "Content-Type") or "").casefold()
        try:
            if content_type.startswith("text/html"):
                text, available_at, time_source, title = _parse_html(response.body)
            elif content_type.startswith("text/plain"):
                text = " ".join(response.body.decode("utf-8").split())
                available_at, time_source, title = None, None, None
            elif content_type.startswith("application/pdf"):
                text, available_at, time_source, title = "", None, None, None
            else:
                return self._unavailable(final_url, fetched_at, request, identity, "invalid", "issuer document content type is unsupported", parse_status="failed", message="unsupported content type", raw_content=response.body, http_status=response.status, source_parameters=source_parameters)
        except (UnicodeDecodeError, ValueError) as error:
            return self._unavailable(final_url, fetched_at, request, identity, "invalid", "issuer document extraction failed", parse_status="failed", message=str(error), raw_content=response.body, http_status=response.status, source_parameters=source_parameters)
        if available_at is None:
            available_at = _http_last_modified(response.headers)
            time_source = "http:last-modified" if available_at is not None else None
        claim = document.get("published_at_claim")
        if isinstance(claim, str) and claim:
            try:
                normalized_claim = _iso(claim)
            except ValueError:
                return self._unavailable(final_url, fetched_at, request, identity, "invalid", "published_at_claim is invalid", parse_status="failed", raw_content=response.body, http_status=response.status, source_parameters=source_parameters)
            if available_at is not None and normalized_claim != available_at:
                return self._unavailable(final_url, fetched_at, request, identity, "conflict", "published_at_claim does not match issuer document metadata", parse_status="parsed", raw_content=response.body, http_status=response.status, source_parameters=source_parameters, available_at=available_at)
        if cutoff_at is not None and available_at is None:
            return self._unavailable(final_url, fetched_at, request, identity, "unavailable", "issuer publication time is unknown for historical use", parse_status="not_parsed", raw_content=response.body, http_status=response.status, source_parameters=source_parameters)
        if cutoff_at is not None and _parse_instant(available_at) > cutoff_at:
            return self._unavailable(final_url, fetched_at, request, identity, "unavailable", "issuer document was not available by historical cutoff", parse_status="parsed", raw_content=response.body, http_status=response.status, source_parameters=source_parameters, available_at=available_at)
        observed_available_at = available_at or fetched_at
        parse_status = "parsed" if text else "not_parsed"
        data = {
            "document_kind": kind,
            "publication_time_source": time_source or "fetch-observed",
            "text": text or None,
            "title": title,
        }
        return ProviderEnvelope.available(
            provider=self.provider_id,
            provider_version=PROVIDER_VERSION,
            source_uri=final_url,
            raw_content=response.body,
            data=data,
            fetched_at=fetched_at,
            request=request,
            effective_at=observed_available_at[:10],
            observed_at=observed_available_at,
            available_at=observed_available_at,
            source_version=_header(response.headers, "ETag") or _header(response.headers, "Last-Modified"),
            source_parameters=source_parameters,
            http_status=response.status,
            identity_bindings=identity,
            parse=_parse_metadata(parse_status),
        )

    @staticmethod
    def _source_parameters(
        *, requested_url: str, final_url: str, response: IssuerIRHttpResponse, document_kind: str, issuer_domain: str, binding_source_ref: str, binding_content_hash: str
    ) -> dict[str, Any]:
        return {
            "binding_content_hash": binding_content_hash,
            "binding_source_ref": binding_source_ref,
            "content_type": _header(response.headers, "Content-Type"),
            "document_kind": document_kind,
            "etag": _header(response.headers, "ETag"),
            "final_url": final_url,
            "issuer_domain": issuer_domain,
            "last_modified": _header(response.headers, "Last-Modified"),
            "redirect_chain": list(response.redirect_chain),
            "requested_url": requested_url,
        }

    @staticmethod
    def _unavailable(
        source_uri: str,
        fetched_at: str,
        request: dict[str, Any],
        identity: Mapping[str, str],
        status: str,
        reason: str,
        *,
        parse_status: str,
        message: str | None = None,
        raw_content: bytes | None = None,
        http_status: int | None = None,
        source_parameters: Mapping[str, Any] | None = None,
        available_at: str | None = None,
    ) -> ProviderEnvelope:
        return ProviderEnvelope.unavailable(
            provider="issuer-ir",
            provider_version=PROVIDER_VERSION,
            source_uri=source_uri,
            fetched_at=fetched_at,
            request=request,
            status=status,
            reason=reason,
            available_at=available_at,
            source_version=None,
            raw_content=raw_content,
            source_parameters=source_parameters,
            http_status=http_status,
            identity_bindings=identity,
            parse=_parse_metadata(parse_status, message),
        )
