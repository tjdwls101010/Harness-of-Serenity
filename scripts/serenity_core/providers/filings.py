"""Typed SEC filing facts with injectable retrieval and time boundaries.

The adapter only transports SEC records.  It deliberately does not decide
whether text is relevant, classify a disclosure, or turn a filing fact into a
signal.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, MutableMapping
from datetime import date, datetime, timezone
from typing import Any, Protocol

from .base import ProviderEnvelope


SEC_ARCHIVES_ROOT = "https://www.sec.gov/Archives/edgar/data"
SEC_SUBMISSIONS_ROOT = "https://data.sec.gov/submissions"
FILINGS_PROVIDER_VERSION = "edgartools-adapter/1"
FILINGS_TRANSFORM_VERSION = "filings-provider/1"
_CAPABILITY_ALIASES = {"8-K": "eightk", "8k": "eightk"}
_CAPABILITIES = frozenset({"submissions", "filings", "filing_text", "section", "eightk", "xbrl_facts", "segments", "statement", *_CAPABILITY_ALIASES})


class FilingsBackend(Protocol):
    """Boundary implemented by edgartools or a deterministic fixture client."""

    def execute(self, request: dict[str, Any]) -> Mapping[str, Any] | None: ...


Clock = Callable[[], datetime | str]
IdentityParser = Callable[[Mapping[str, Any]], tuple[dict[str, str] | None, dict[str, str]]]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_iso(value: datetime | str) -> str:
    if isinstance(value, str):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalise_cik(value: object) -> str | None:
    if isinstance(value, int):
        return f"{value:010d}"
    if isinstance(value, str) and value.strip().isdigit():
        return f"{int(value.strip()):010d}"
    return None


def _identity(request: Mapping[str, Any]) -> tuple[dict[str, str] | None, dict[str, str]]:
    candidate = request.get("identity")
    source = candidate if isinstance(candidate, Mapping) else request
    raw_ticker = source.get("ticker")
    raw_issuer = source.get("issuer")
    ticker = raw_ticker.strip().upper() if isinstance(raw_ticker, str) and raw_ticker.strip() else None
    issuer = raw_issuer.strip() if isinstance(raw_issuer, str) and raw_issuer.strip() else None
    cik = _normalise_cik(source.get("cik"))
    partial = {key: value for key, value in (("ticker", ticker), ("cik", cik), ("issuer", issuer)) if value is not None}
    if ticker is None or cik is None or issuer is None:
        return None, partial
    return {"ticker": ticker, "cik": cik, "issuer": issuer}, partial


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _date_string(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10]).isoformat()
        except ValueError:
            return None
    return None


def _instant(value: str) -> datetime | None:
    try:
        if len(value) == 14 and value.isdigit():
            return datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        if "T" not in value:
            return datetime.combine(date.fromisoformat(value), datetime.min.time(), tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _filing_available_at(filing: Mapping[str, Any]) -> str | None:
    for key in ("available_at", "acceptance_at", "acceptance_datetime", "acceptanceDateTime"):
        available_at = filing.get(key)
        if isinstance(available_at, str) and (instant := _instant(available_at)) is not None:
            return _as_iso(instant)
    return None


def _at_or_before_cutoff(available_at: str, cutoff: str) -> bool:
    available = _instant(available_at)
    if available is None:
        return False
    if "T" not in cutoff:
        cutoff_date = _date_string(cutoff)
        return cutoff_date is not None and available.date() <= date.fromisoformat(cutoff_date)
    cutoff_instant = _instant(cutoff)
    return cutoff_instant is not None and available <= cutoff_instant


def _filing_date_is_after_cutoff(filing: Mapping[str, Any], cutoff: str) -> bool:
    filing_date = _date_string(filing.get("filing_date"))
    cutoff_date = _date_string(cutoff)
    return filing_date is not None and cutoff_date is not None and filing_date > cutoff_date


def _can_select_filing_at_cutoff(filing: Mapping[str, Any], cutoff: str) -> bool:
    available_at = _filing_available_at(filing)
    if available_at is not None:
        return _at_or_before_cutoff(available_at, cutoff)
    filing_date = _date_string(filing.get("filing_date"))
    cutoff_date = _date_string(cutoff)
    if filing_date is None or cutoff_date is None:
        return False
    return filing_date <= cutoff_date if "T" not in cutoff else filing_date < cutoff_date


def _filing_url(identity: Mapping[str, str], filing: Mapping[str, Any], capability: str) -> str:
    accession = filing.get("accession") or filing.get("accession_no")
    if capability == "submissions" and not accession:
        return f"{SEC_SUBMISSIONS_ROOT}/CIK{identity['cik']}.json"
    if isinstance(accession, str) and accession:
        accession_compact = accession.replace("-", "")
        base = f"{SEC_ARCHIVES_ROOT}/{int(identity['cik'])}/{accession_compact}"
        document = filing.get("primary_document")
        return f"{base}/{document}" if isinstance(document, str) and document else f"{base}/"
    return f"{SEC_ARCHIVES_ROOT}/{int(identity['cik'])}/"


def _filing_metadata(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    accession = source.get("accession") or source.get("accession_no")
    metadata: dict[str, Any] = {
        "form": source.get("form") if isinstance(source.get("form"), str) else None,
        "filing_date": _date_string(source.get("filing_date")),
        "report_date": _date_string(source.get("report_date")),
        "accession": accession if isinstance(accession, str) and accession else None,
        "primary_document": source.get("primary_document") if isinstance(source.get("primary_document"), str) else None,
    }
    for key in ("available_at", "acceptance_at", "acceptance_datetime", "acceptanceDateTime"):
        if isinstance(source.get(key), str):
            metadata["available_at"] = source[key]
            break
    return metadata


def _source_parameters(request: Mapping[str, Any]) -> dict[str, Any]:
    keys = ("capability", "form", "accession", "format", "item", "named", "concept", "axis", "statement", "view", "limit", "since", "between", "detail")
    return {key: request[key] for key in keys if key in request}


def _parse(status: str, message: str | None = None) -> dict[str, str]:
    parse: dict[str, str] = {"status": status, "transform_version": FILINGS_TRANSFORM_VERSION}
    if message is not None:
        parse["message"] = message
    return parse


def _unavailable(
    *,
    provider_version: str,
    source_uri: str,
    fetched_at: str,
    request: dict[str, Any],
    identity: Mapping[str, str],
    status: str,
    reason: str,
    parse_status: str,
    message: str | None = None,
    effective_at: str | None = None,
    observed_at: str | None = None,
    available_at: str | None = None,
    source_version: str | None = None,
    raw_content: bytes | None = None,
    http_status: int | None = None,
) -> ProviderEnvelope:
    return ProviderEnvelope.unavailable(
        provider="sec.filings",
        provider_version=provider_version,
        source_uri=source_uri,
        fetched_at=fetched_at,
        request=request,
        status=status,
        reason=reason,
        effective_at=effective_at,
        observed_at=observed_at,
        available_at=available_at,
        source_version=source_version,
        raw_content=raw_content,
        source_parameters=_source_parameters(request),
        http_status=http_status,
        identity_bindings=identity,
        parse=_parse(parse_status, message),
    )


class EdgarToolsBackend:
    """Thin edgartools adapter with no identity or local-cache side effects."""

    def execute(self, request: dict[str, Any]) -> Mapping[str, Any] | None:
        from edgar import Company, get_by_accession_number

        identity = request["identity"]
        capability = request["capability"]
        company = Company(identity["cik"])
        if capability == "submissions":
            return {"data": {"submissions": {"cik": str(getattr(company, "cik", "")), "name": getattr(company, "name", None), "tickers": getattr(company, "tickers", None), "exchanges": self._call(company, "get_exchanges")}}}
        if capability == "filing_text":
            filing = get_by_accession_number(request["accession"])
        else:
            filing = self._select_filing(company, request)
        if filing is None:
            return None
        if capability == "filings":
            filings = self._filings(company, request)
            return self._result(filing, {"filings": [self._metadata(item) for item in filings]})
        if capability == "filing_text":
            text = filing.markdown(include_page_breaks=True) if request.get("format") == "markdown" and hasattr(filing, "markdown") else filing.text()
            return self._result(filing, {"text": str(text), "format": request.get("format", "text")})
        if capability == "section":
            obj = filing.obj()
            named = request.get("named")
            item = request.get("item")
            if named:
                names = {"business": "business", "risk_factors": "risk_factors", "mda": "management_discussion"}
                text = getattr(obj, names.get(named, ""), None)
            else:
                text = obj[item] if isinstance(item, str) else None
            return None if text is None else self._result(filing, {"section": named or item, "text": str(text)})
        if capability == "eightk":
            filings = self._filings(company, {**request, "form": "8-K"})
            source_filing = filings[0] if filings else filing
            return self._result(source_filing, {"events": [self._eightk(item, request.get("item")) for item in filings]})
        xbrl = filing.xbrl()
        if xbrl is None:
            return None
        if capability in {"xbrl_facts", "segments"}:
            query = xbrl.query(include_dimensions=bool(request.get("axis")))
            if request.get("concept"):
                query = query.by_concept(request["concept"])
            if request.get("axis"):
                query = query.by_dimension(request["axis"])
            if request.get("statement"):
                query = query.by_statement_type(request["statement"])
            rows = self._records(query.to_dataframe())
            if request.get("limit"):
                rows = rows[: int(request["limit"])]
            key = "segments" if capability == "segments" else "facts"
            return self._result(filing, {key: rows})
        statements = xbrl.statements
        names = {"income": ("income_statement",), "balance": ("balance_sheet", "balance_statement"), "cashflow": ("cashflow_statement", "cash_flow_statement", "cashflow")}[request.get("statement", "income")]
        statement = next((getattr(statements, name)() for name in names if callable(getattr(statements, name, None))), None)
        return None if statement is None else self._result(filing, {"rows": self._records(statement.to_dataframe(view=request.get("view")))})

    def _filings(self, company: Any, request: Mapping[str, Any]) -> list[Any]:
        kwargs = {"form": request["form"]} if isinstance(request.get("form"), str) else {}
        filings = company.get_filings(**kwargs)
        records = list(filings)
        cutoff = request.get("_cutoff")
        if isinstance(cutoff, str):
            records = [record for record in records if _can_select_filing_at_cutoff(self._metadata(record), cutoff)]
        limit = request.get("limit")
        return records[: int(limit)] if isinstance(limit, int) else records

    def _select_filing(self, company: Any, request: Mapping[str, Any]) -> Any:
        accession = request.get("accession")
        if isinstance(accession, str):
            return next((filing for filing in self._filings(company, request) if self._metadata(filing)["accession"] == accession), None)
        filings = self._filings(company, request)
        return filings[0] if filings else None

    @staticmethod
    def _call(value: Any, name: str) -> Any:
        attribute = getattr(value, name, None)
        return attribute() if callable(attribute) else attribute

    @classmethod
    def _metadata(cls, filing: Any) -> dict[str, Any]:
        return _filing_metadata({key: cls._call(filing, key) for key in ("form", "filing_date", "report_date", "accession_no", "primary_document", "acceptance_datetime", "acceptanceDateTime")})

    def _result(self, filing: Any, data: dict[str, Any]) -> dict[str, Any]:
        return {"filing": self._metadata(filing), "data": data, "raw_content": self._raw_content(filing)}

    def _raw_content(self, filing: Any) -> bytes | None:
        for name in ("full_text_submission", "html"):
            try:
                content = self._call(filing, name)
            except Exception:
                continue
            if isinstance(content, bytes):
                return content
            if isinstance(content, str):
                return content.encode("utf-8")
        return None

    @staticmethod
    def _records(value: Any) -> list[dict[str, Any]]:
        if value is None:
            return []
        if hasattr(value, "reset_index") and hasattr(value, "to_dict"):
            return value.reset_index().to_dict(orient="records")
        return value if isinstance(value, list) else []

    def _eightk(self, filing: Any, item: Any) -> dict[str, Any]:
        event = self._metadata(filing)
        obj = filing.obj()
        event["items"] = list(getattr(obj, "items", []) or [])
        if isinstance(item, str):
            key = item if item.startswith("Item ") else f"Item {item}"
            event["body"] = obj[item] if key in event["items"] else None
        return event


class FilingsProvider:
    """Return typed, identity-bound SEC filing records through one public seam."""

    def __init__(
        self,
        *,
        backend: FilingsBackend | None = None,
        clock: Clock = _utc_now,
        identity_parser: IdentityParser = _identity,
        cache: MutableMapping[str, Mapping[str, Any] | None] | None = None,
        provider_version: str = FILINGS_PROVIDER_VERSION,
    ) -> None:
        self._backend = backend or EdgarToolsBackend()
        self._clock = clock
        self._identity_parser = identity_parser
        self._cache = cache
        self._provider_version = provider_version

    def execute(self, request: dict[str, Any], cutoff: str | None = None) -> ProviderEnvelope:
        requested = json.loads(json.dumps(request, ensure_ascii=False, default=str))
        fetched_at = _as_iso(self._clock())
        identity, partial_identity = self._identity_parser(requested)
        capability = requested.get("capability")
        fallback_uri = f"{SEC_ARCHIVES_ROOT}/"
        if identity is None:
            return _unavailable(provider_version=self._provider_version, source_uri=fallback_uri, fetched_at=fetched_at, request=requested, identity=partial_identity, status="unavailable", reason="explicit SEC identity requires ticker, cik, and issuer", parse_status="not_parsed")
        if not isinstance(capability, str) or capability not in _CAPABILITIES:
            return _unavailable(provider_version=self._provider_version, source_uri=fallback_uri, fetched_at=fetched_at, request=requested, identity=identity, status="invalid", reason="unsupported SEC filing capability", parse_status="not_parsed")
        backend_request = {**requested, "identity": identity, "capability": _CAPABILITY_ALIASES.get(capability, capability)}
        if cutoff is not None:
            backend_request["_cutoff"] = cutoff
        cache_key = hashlib.sha256(_canonical_json({"provider": "sec.filings", "request": backend_request})).hexdigest()
        try:
            if self._cache is not None and cache_key in self._cache:
                response = self._cache[cache_key]
            else:
                response = self._backend.execute(backend_request)
                if self._cache is not None:
                    self._cache[cache_key] = response
        except Exception as exc:
            return _unavailable(provider_version=self._provider_version, source_uri=fallback_uri, fetched_at=fetched_at, request=requested, identity=identity, status="unavailable", reason=f"SEC filings backend unavailable: {exc}", parse_status="failed", message=str(exc))
        if response is None:
            return _unavailable(provider_version=self._provider_version, source_uri=fallback_uri, fetched_at=fetched_at, request=requested, identity=identity, status="not_disclosed", reason="requested SEC disclosure was not returned", parse_status="parsed")
        if not isinstance(response, Mapping):
            return _unavailable(provider_version=self._provider_version, source_uri=fallback_uri, fetched_at=fetched_at, request=requested, identity=identity, status="invalid", reason="SEC filings backend returned an invalid response", parse_status="failed")
        filing = _filing_metadata(response.get("filing"))
        available_at = _filing_available_at(filing)
        source_uri = response.get("source_uri") if isinstance(response.get("source_uri"), str) else _filing_url(identity, filing, capability)
        response_raw_content = response.get("raw_content") if isinstance(response.get("raw_content"), bytes) else None
        response_http_status = response.get("http_status") if isinstance(response.get("http_status"), int) else None
        backend_error = response.get("error")
        if isinstance(backend_error, str) and backend_error:
            return _unavailable(provider_version=self._provider_version, source_uri=source_uri, fetched_at=fetched_at, request=requested, identity=identity, status="invalid", reason=f"SEC filings backend returned invalid data: {backend_error}", parse_status="failed", message=backend_error, effective_at=filing["report_date"], observed_at=filing["report_date"], available_at=available_at, source_version=filing["accession"], raw_content=response_raw_content, http_status=response_http_status)
        backend_status = response.get("status")
        if backend_status in {"not_disclosed", "not_applicable", "unavailable", "invalid"}:
            reason = response.get("reason") if isinstance(response.get("reason"), str) else "requested SEC disclosure was not disclosed"
            return _unavailable(provider_version=self._provider_version, source_uri=source_uri, fetched_at=fetched_at, request=requested, identity=identity, status=backend_status, reason=reason, parse_status="failed" if backend_status == "invalid" else "parsed", effective_at=filing["report_date"], observed_at=filing["report_date"], available_at=available_at, source_version=filing["accession"], raw_content=response_raw_content, http_status=response_http_status)
        if cutoff is not None and available_at is None and _filing_date_is_after_cutoff(filing, cutoff):
            return _unavailable(provider_version=self._provider_version, source_uri=source_uri, fetched_at=fetched_at, request=requested, identity=identity, status="unavailable", reason="filing date is after cutoff", parse_status="parsed", effective_at=filing["report_date"], observed_at=filing["report_date"], source_version=filing["accession"], raw_content=response_raw_content, http_status=response_http_status)
        if cutoff is not None and available_at is None and "T" in cutoff:
            return _unavailable(provider_version=self._provider_version, source_uri=source_uri, fetched_at=fetched_at, request=requested, identity=identity, status="unavailable", reason="filing availability is unknown for intraday historical use", parse_status="parsed", effective_at=filing["report_date"], observed_at=filing["report_date"], source_version=filing["accession"], raw_content=response_raw_content, http_status=response_http_status)
        if cutoff is not None and available_at is None and _date_string(filing.get("filing_date")) is None:
            return _unavailable(provider_version=self._provider_version, source_uri=source_uri, fetched_at=fetched_at, request=requested, identity=identity, status="unavailable", reason="filing availability is unknown for historical use", parse_status="parsed", effective_at=filing["report_date"], observed_at=filing["report_date"], source_version=filing["accession"], raw_content=response_raw_content, http_status=response_http_status)
        if cutoff is not None and available_at is not None and not _at_or_before_cutoff(available_at, cutoff):
            return _unavailable(provider_version=self._provider_version, source_uri=source_uri, fetched_at=fetched_at, request=requested, identity=identity, status="unavailable", reason="filing was not available by cutoff", parse_status="parsed", effective_at=filing["report_date"], observed_at=filing["report_date"], available_at=available_at, source_version=filing["accession"], raw_content=response_raw_content, http_status=response_http_status)
        payload = response.get("data")
        if payload is None or (isinstance(payload, Mapping) and not payload):
            return _unavailable(provider_version=self._provider_version, source_uri=source_uri, fetched_at=fetched_at, request=requested, identity=identity, status="not_disclosed", reason="requested SEC disclosure was not disclosed", parse_status="parsed", effective_at=filing["report_date"], observed_at=filing["report_date"], available_at=available_at, source_version=filing["accession"], raw_content=response_raw_content, http_status=response_http_status)
        if response_raw_content is None:
            return _unavailable(provider_version=self._provider_version, source_uri=source_uri, fetched_at=fetched_at, request=requested, identity=identity, status="unavailable", reason="exact SEC raw content is unavailable", parse_status="parsed", effective_at=filing["report_date"], observed_at=filing["report_date"], available_at=available_at, source_version=filing["accession"], http_status=response_http_status)
        data = {"identity": identity, "capability": capability, "requested": requested, "filing": filing, "query": _source_parameters(requested), "result": payload}
        return ProviderEnvelope.available(provider="sec.filings", provider_version=self._provider_version, source_uri=source_uri, raw_content=response_raw_content, data=data, fetched_at=fetched_at, request=requested, effective_at=filing["report_date"], observed_at=filing["report_date"], available_at=available_at, source_version=filing["accession"], source_parameters=_source_parameters(requested), http_status=response_http_status, identity_bindings=identity, parse=_parse("parsed"))
