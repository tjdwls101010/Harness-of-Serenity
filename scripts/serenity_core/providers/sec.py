"""SEC identity records with source-pinned provider envelopes."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from serenity_core.providers.base import ProviderEnvelope


COMPANY_TICKERS_URI = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URI = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_HEADERS = {"Accept": "application/json"}

HttpGet = Callable[[str, dict[str, str]], bytes]
Clock = Callable[[], datetime | str]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(value: datetime | str) -> str:
    if isinstance(value, str):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def default_http_get(uri: str, headers: dict[str, str]) -> bytes:
    request = Request(uri, headers=headers)
    with urlopen(request, timeout=30) as response:  # nosec B310 - fixed official SEC endpoints
        return response.read()


MAX_ERROR_BODY_BYTES = 65536
SEC_CONFIGURATION_NOTICE = "undeclared automated tool"
# SEC answers a refused User-Agent and a genuine rate block with the same 403, and www.sec.gov serves
# its rate-limit page for both -- so the notice text alone cannot separate them. Name both causes,
# refused-identity first, because that one never clears by waiting.
SEC_FORBIDDEN_REMEDY = (
    "verify SERENITY_SEC_USER_AGENT declares a contactable address SEC accepts -- a refused email "
    "domain is answered with 403, not an auth error -- then consider SEC rate limiting"
)
_TITLE_PATTERN = re.compile(rb"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _http_status(exc: BaseException) -> int | None:
    return exc.code if isinstance(exc, HTTPError) else None


def _error_body(exc: BaseException) -> bytes | None:
    """SEC states the reason for a refusal in the response body; read it once instead of discarding it."""
    if not isinstance(exc, HTTPError):
        return None
    try:
        return exc.read(MAX_ERROR_BODY_BYTES)
    except Exception:  # a refusal we cannot read is still a refusal
        return None


def _sec_notice(body: bytes | None) -> str | None:
    if not body:
        return None
    match = _TITLE_PATTERN.search(body)
    if match is None:
        return None
    notice = " ".join(match.group(1).decode("utf-8", "replace").split())
    return notice or None


def _identity_rejection(code: str, reason: str) -> dict[str, Any]:
    return {"code": code, "reason": reason, "category": "identity", "retryable": False}


def _unavailable_rejection(code: str, reason: str, detail: str, http_status: int | None, notice: str | None = None) -> dict[str, Any]:
    """Separate a transport outage from an identity conflict so the operator knows whether to retry.

    A refused User-Agent also arrives as HTTP 403, and retrying it never succeeds -- only SEC's own
    notice text separates that configuration failure from a genuine rate-limit block.
    """
    configuration = bool(notice) and SEC_CONFIGURATION_NOTICE in notice.lower()
    rejection: dict[str, Any] = {
        "code": code,
        "reason": reason,
        "category": "configuration" if configuration else "availability",
        "retryable": not configuration,
        "detail": detail,
    }
    if http_status is not None:
        rejection["http_status"] = http_status
    if notice is not None:
        rejection["sec_notice"] = notice
    if http_status == 403:
        rejection["remedy"] = SEC_FORBIDDEN_REMEDY
    return rejection


@dataclass(frozen=True)
class SecLookup:
    ticker: str
    cik: str | None
    official_name: str | None
    exchange: str | None
    envelopes: tuple[dict[str, Any], ...]
    issuer_domains: tuple[str, ...] = ()
    provider_envelopes: tuple[ProviderEnvelope, ...] = ()
    rejection: dict[str, Any] | None = None


class SecIdentityProvider:
    """Resolve a symbol through SEC records with an explicit contact identity.

    Pass ``user_agent``, set ``SERENITY_SEC_USER_AGENT``, or retain the legacy
    ``EDGAR_IDENTITY`` setting with a contactable SEC User-Agent value. Without
    an identity, this provider returns a typed rejection and intentionally makes
    no network call.
    """

    def __init__(
        self,
        *,
        http_get: HttpGet = default_http_get,
        clock: Clock = utc_now,
        user_agent: str | None = None,
    ) -> None:
        self._http_get = http_get
        self._clock = clock
        configured_user_agent = user_agent or os.getenv("SERENITY_SEC_USER_AGENT") or os.getenv("EDGAR_IDENTITY", "")
        self._user_agent = configured_user_agent.strip()

    def _headers(self) -> dict[str, str]:
        return {**SEC_HEADERS, "User-Agent": self._user_agent}

    def resolve(self, ticker: str) -> SecLookup:
        normalized_ticker = ticker.strip().upper()
        request = {"ticker": normalized_ticker}
        fetched_at = self._clock()
        available_at = _utc_iso(fetched_at)
        if not self._user_agent:
            envelope = ProviderEnvelope.unavailable(
                provider="sec.company_tickers",
                provider_version="v1",
                source_uri=COMPANY_TICKERS_URI,
                fetched_at=fetched_at,
                request=request,
                status="unavailable",
                reason="SEC requests require user_agent or SERENITY_SEC_USER_AGENT",
                available_at=available_at,
                parse={"status": "not_parsed", "transform_version": "sec-identity/1"},
            )
            return SecLookup(
                ticker=normalized_ticker,
                cik=None,
                official_name=None,
                exchange=None,
                envelopes=(envelope.to_dict(),),
                provider_envelopes=(envelope,),
                rejection={
                    "code": "sec_user_agent_required",
                    "reason": "SEC requests require user_agent or SERENITY_SEC_USER_AGENT",
                    "category": "configuration",
                    "retryable": False,
                },
            )
        try:
            raw_directory = self._http_get(COMPANY_TICKERS_URI, self._headers())
            directory = json.loads(raw_directory)
        except Exception as exc:  # external provider boundary
            detail = f"SEC company_tickers unavailable: {exc}"
            http_status = _http_status(exc)
            error_body = _error_body(exc)
            notice = _sec_notice(error_body)
            envelope = ProviderEnvelope.unavailable(
                provider="sec.company_tickers",
                provider_version="v1",
                source_uri=COMPANY_TICKERS_URI,
                fetched_at=fetched_at,
                request=request,
                status="unavailable",
                reason=detail,
                available_at=available_at,
                http_status=http_status,
                raw_content=error_body,
                parse={"status": "not_parsed", "transform_version": "sec-identity/1"},
            )
            return SecLookup(
                ticker=normalized_ticker,
                cik=None,
                official_name=None,
                exchange=None,
                envelopes=(envelope.to_dict(),),
                provider_envelopes=(envelope,),
                rejection=_unavailable_rejection("sec_directory_unavailable", "SEC company_tickers could not be loaded", detail, http_status, notice),
            )

        record = self._find_record(directory, normalized_ticker)
        if record is None:
            provider_envelope = ProviderEnvelope.unavailable(
                provider="sec.company_tickers",
                provider_version="v1",
                source_uri=COMPANY_TICKERS_URI,
                fetched_at=fetched_at,
                request=request,
                status="invalid",
                reason="ticker is not present in SEC company_tickers",
                available_at=available_at,
                raw_content=raw_directory,
                parse={"status": "parsed", "transform_version": "sec-identity/1"},
            )
            return SecLookup(
                ticker=normalized_ticker,
                cik=None,
                official_name=None,
                exchange=None,
                envelopes=(provider_envelope.to_dict(),),
                provider_envelopes=(provider_envelope,),
                rejection=_identity_rejection("unresolved_ticker", "ticker is not present in SEC company_tickers"),
            )

        try:
            cik = f"{int(record['cik_str']):010d}"
        except (KeyError, TypeError, ValueError):
            provider_envelope = ProviderEnvelope.available(
                provider="sec.company_tickers",
                provider_version="v1",
                source_uri=COMPANY_TICKERS_URI,
                raw_content=raw_directory,
                data={"ticker": normalized_ticker, "record": record},
                fetched_at=fetched_at,
                request=request,
                available_at=available_at,
                identity_bindings={"ticker": normalized_ticker},
                parse={"status": "parsed", "transform_version": "sec-identity/1"},
            )
            return SecLookup(
                ticker=normalized_ticker,
                cik=None,
                official_name=None,
                exchange=None,
                envelopes=(provider_envelope.to_dict(),),
                provider_envelopes=(provider_envelope,),
                rejection=_identity_rejection("invalid_sec_cik", "SEC company_tickers CIK is invalid"),
            )

        directory_envelope = ProviderEnvelope.available(
            provider="sec.company_tickers",
            provider_version="v1",
            source_uri=COMPANY_TICKERS_URI,
            raw_content=raw_directory,
            data={"ticker": normalized_ticker, "cik": cik, "record": record},
            fetched_at=fetched_at,
            request=request,
            available_at=available_at,
            identity_bindings={"ticker": normalized_ticker, "cik": cik},
            parse={"status": "parsed", "transform_version": "sec-identity/1"},
        )
        submission_uri = SUBMISSIONS_URI.format(cik=cik)
        try:
            raw_submission = self._http_get(submission_uri, self._headers())
            submission = json.loads(raw_submission)
        except Exception as exc:  # external provider boundary
            detail = f"SEC submissions unavailable: {exc}"
            http_status = _http_status(exc)
            error_body = _error_body(exc)
            notice = _sec_notice(error_body)
            submission_envelope = ProviderEnvelope.unavailable(
                provider="sec.submissions",
                provider_version="v1",
                source_uri=submission_uri,
                fetched_at=fetched_at,
                request={"ticker": normalized_ticker, "cik": cik},
                status="unavailable",
                reason=detail,
                available_at=available_at,
                http_status=http_status,
                raw_content=error_body,
                identity_bindings={"ticker": normalized_ticker, "cik": cik},
                parse={"status": "not_parsed", "transform_version": "sec-identity/1"},
            )
            return SecLookup(
                ticker=normalized_ticker,
                cik=cik,
                official_name=None,
                exchange=None,
                envelopes=(directory_envelope.to_dict(), submission_envelope.to_dict()),
                provider_envelopes=(directory_envelope, submission_envelope),
                rejection=_unavailable_rejection("sec_submission_unavailable", "SEC submissions could not be loaded", detail, http_status, notice),
            )

        submission_data = submission if isinstance(submission, dict) else {}
        issuer_domains = self._issuer_domains(submission_data)
        submission_envelope = ProviderEnvelope.available(
            provider="sec.submissions",
            provider_version="v1",
            source_uri=submission_uri,
            raw_content=raw_submission,
            data={
                "ticker": normalized_ticker,
                "cik": cik,
                "record": {
                    "cik": submission_data.get("cik"),
                    "name": submission_data.get("name"),
                    "tickers": submission_data.get("tickers"),
                    "exchanges": submission_data.get("exchanges"),
                    "website": submission_data.get("website"),
                    "investorWebsite": submission_data.get("investorWebsite"),
                },
            },
            fetched_at=fetched_at,
            request={"ticker": normalized_ticker, "cik": cik},
            available_at=available_at,
            identity_bindings={"ticker": normalized_ticker, "cik": cik},
            parse={"status": "parsed", "transform_version": "sec-identity/1"},
        )
        if not isinstance(submission, dict) or self._submission_cik(submission) != cik:
            return SecLookup(
                ticker=normalized_ticker,
                cik=cik,
                official_name=None,
                exchange=None,
                envelopes=(directory_envelope.to_dict(), submission_envelope.to_dict()),
                provider_envelopes=(directory_envelope, submission_envelope),
                rejection=_identity_rejection("sec_submission_cik_conflict", "SEC submissions CIK does not match company_tickers"),
            )
        tickers = submission.get("tickers")
        if not isinstance(tickers, list) or normalized_ticker not in {str(value).upper() for value in tickers}:
            return SecLookup(
                ticker=normalized_ticker,
                cik=cik,
                official_name=None,
                exchange=None,
                envelopes=(directory_envelope.to_dict(), submission_envelope.to_dict()),
                provider_envelopes=(directory_envelope, submission_envelope),
                rejection=_identity_rejection("sec_submission_ticker_conflict", "SEC submissions does not corroborate the requested ticker"),
            )
        name = submission.get("name")
        exchanges = submission.get("exchanges")
        if not isinstance(name, str) or not name.strip() or not isinstance(exchanges, list) or not exchanges or not isinstance(exchanges[0], str):
            return SecLookup(
                ticker=normalized_ticker,
                cik=cik,
                official_name=None,
                exchange=None,
                envelopes=(directory_envelope.to_dict(), submission_envelope.to_dict()),
                provider_envelopes=(directory_envelope, submission_envelope),
                rejection=_identity_rejection("invalid_sec_submission", "SEC submissions lacks name or exchange"),
            )
        return SecLookup(
            ticker=normalized_ticker,
            cik=cik,
            official_name=name,
            exchange=exchanges[0],
            envelopes=(directory_envelope.to_dict(), submission_envelope.to_dict()),
            issuer_domains=issuer_domains,
            provider_envelopes=(directory_envelope, submission_envelope),
        )

    @staticmethod
    def _issuer_domains(submission: dict[str, Any]) -> tuple[str, ...]:
        domains: set[str] = set()
        for key in ("website", "investorWebsite"):
            value = submission.get(key)
            if not isinstance(value, str) or not value.strip():
                continue
            parsed = urlparse(value if "://" in value else f"https://{value}")
            if parsed.scheme in {"http", "https"} and isinstance(parsed.hostname, str):
                domains.add(parsed.hostname.casefold().strip("."))
        return tuple(sorted(domains))

    @staticmethod
    def _find_record(directory: Any, ticker: str) -> dict[str, Any] | None:
        if not isinstance(directory, dict):
            return None
        matches = [record for record in directory.values() if isinstance(record, dict) and str(record.get("ticker", "")).upper() == ticker]
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _submission_cik(submission: dict[str, Any]) -> str | None:
        try:
            return f"{int(submission['cik']):010d}"
        except (KeyError, TypeError, ValueError):
            return None
