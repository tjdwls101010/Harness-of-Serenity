"""Free public-data adapters that return evidence, never investment judgments."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from serenity_v2.providers.base import ProviderEnvelope


Clock = Callable[[], datetime]
PUBLIC_DATA_TRANSFORM_VERSION = "public-data/1"


@dataclass(frozen=True)
class HttpRequest:
    method: str
    url: str
    query: dict[str, Any]
    body: dict[str, Any] | None = None
    headers: dict[str, str] | None = None


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes
    headers: Mapping[str, str] | None = None


HttpClient = Callable[[HttpRequest], HttpResponse]


@dataclass(frozen=True)
class EvidenceProvider:
    """The typed catalog entry shared by numeric and narrative evidence sources."""

    provider_id: str
    title: str
    priority: str
    capability: str
    capabilities: tuple[str, ...]
    secret_parameter_names: tuple[str, ...]
    configured: bool


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _default_http(request: HttpRequest) -> HttpResponse:
    url = request.url
    if request.query:
        url = f"{url}?{urlencode(request.query)}"
    headers = {"Accept": "application/json", **(request.headers or {})}
    body = None
    if request.body is not None:
        body = json.dumps(request.body, separators=(",", ":")).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    with urlopen(Request(url, data=body, headers=headers, method=request.method), timeout=30) as response:  # noqa: S310
        return HttpResponse(status=response.status, body=response.read(), headers=dict(response.headers.items()))


def _json(raw: bytes) -> Any:
    return json.loads(raw.decode("utf-8"))


def _first_date(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


class ResponseShapeError(ValueError):
    pass


def _collection_at(payload: Any, *path: str) -> list[Any]:
    current = payload
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            raise ResponseShapeError(f"expected response collection at {'.'.join(path)}")
        current = current[key]
    if not isinstance(current, list):
        raise ResponseShapeError(f"expected response collection at {'.'.join(path)} to be a list")
    return current


class PublicDataAdapter(EvidenceProvider):
    """One external provider boundary; callers can inject HTTP and clock for repeatable runs."""

    provider_version = "public-v1"
    source_uri = ""
    unavailable_reason: str | None = None
    capabilities: tuple[str, ...] = ()
    secret_parameter_names: tuple[str, ...] = ()

    def __init__(self, *, http: HttpClient | None, clock: Clock, config: Mapping[str, str]) -> None:
        configured = self.unavailable_reason is None
        super().__init__(
            provider_id=self.provider_id,
            title=self.title,
            priority=self.priority,
            capability=self.capability,
            capabilities=self.capabilities,
            secret_parameter_names=self.secret_parameter_names,
            configured=configured,
        )
        object.__setattr__(self, "_http", http or _default_http)
        object.__setattr__(self, "_clock", clock)
        object.__setattr__(self, "_config", config)

    def build_request(self, query: Mapping[str, Any]) -> HttpRequest:
        raise NotImplementedError

    def parse(self, response: HttpResponse, request: HttpRequest) -> ProviderEnvelope:
        fetched_at = self._clock()
        request_record = self._request_record(request)
        if not 200 <= response.status < 300:
            return ProviderEnvelope.unavailable(
                provider=self.provider_id,
                provider_version=self.provider_version,
                source_uri=request.url,
                fetched_at=fetched_at,
                request=request_record,
                status="unavailable",
                reason=f"HTTP {response.status}",
                available_at=_iso(fetched_at),
                raw_content=response.body,
                source_parameters=self._source_parameters(request),
                http_status=response.status,
                parse=self._parse_metadata("not_parsed", f"HTTP {response.status}"),
            )
        try:
            data, temporal = self._parse_available(_json(response.body))
        except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            return ProviderEnvelope.unavailable(
                provider=self.provider_id,
                provider_version=self.provider_version,
                source_uri=request.url,
                fetched_at=fetched_at,
                request=request_record,
                status="invalid",
                reason=f"invalid response: {error}",
                available_at=_iso(fetched_at),
                raw_content=response.body,
                source_parameters=self._source_parameters(request),
                http_status=response.status,
                parse=self._parse_metadata("failed", str(error)),
            )
        return ProviderEnvelope.available(
            provider=self.provider_id,
            provider_version=self.provider_version,
            source_uri=request.url,
            raw_content=response.body,
            data=data,
            fetched_at=fetched_at,
            request=request_record,
            effective_at=temporal.get("effective_at"),
            period_start=temporal.get("period_start"),
            period_end=temporal.get("period_end"),
            observed_at=temporal.get("observed_at"),
            available_at=temporal.get("available_at") or _iso(fetched_at),
            source_version=(response.headers or {}).get("ETag"),
            source_parameters=self._source_parameters(request),
            http_status=response.status,
            parse=self._parse_metadata("parsed"),
        )

    def collect(self, query: Mapping[str, Any]) -> ProviderEnvelope:
        fetched_at = self._clock()
        if self.unavailable_reason is not None:
            return ProviderEnvelope.unavailable(
                provider=self.provider_id,
                provider_version=self.provider_version,
                source_uri=self.source_uri,
                fetched_at=fetched_at,
                request={"query": self._redact(dict(query))},
                status="not_requested",
                reason=self.unavailable_reason,
                available_at=_iso(fetched_at),
                source_parameters={"query": self._redact(dict(query))},
                parse=self._parse_metadata("not_parsed", self.unavailable_reason),
            )
        request = self.build_request(query)
        try:
            return self.parse(self._http(request), request)
        except OSError as error:
            return ProviderEnvelope.unavailable(
                provider=self.provider_id,
                provider_version=self.provider_version,
                source_uri=request.url,
                fetched_at=fetched_at,
                request=self._request_record(request),
                status="unavailable",
                reason=f"transport error: {error}",
                available_at=_iso(fetched_at),
                source_parameters=self._source_parameters(request),
                parse=self._parse_metadata("not_parsed", f"transport error: {error}"),
            )

    def _request_record(self, request: HttpRequest) -> dict[str, Any]:
        return {"method": request.method, "url": request.url, "query": self._redact(request.query), "body": self._redact(request.body or {})}

    def _source_parameters(self, request: HttpRequest) -> dict[str, Any]:
        return {"method": request.method, "query": self._redact(request.query), "body": self._redact(request.body or {})}

    def _redact(self, value: Any) -> Any:
        secret_names = {name.casefold() for name in self.secret_parameter_names}
        if isinstance(value, Mapping):
            return {
                str(key): "[REDACTED]" if str(key).casefold() in secret_names else self._redact(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        return value

    @staticmethod
    def _parse_metadata(status: str, message: str | None = None) -> dict[str, str]:
        value = {"status": status, "transform_version": PUBLIC_DATA_TRANSFORM_VERSION}
        if message is not None:
            value["message"] = message
        return value

    def _parse_available(self, payload: Any) -> tuple[dict[str, Any], dict[str, str | None]]:
        raise NotImplementedError


class USASpendingAdapter(PublicDataAdapter):
    provider_id = "usaspending"
    title = "USASpending award search"
    priority = "high"
    capability = "numeric"
    capabilities = ("usaspending.federal-awards", "usaspending.contract-obligations")
    source_uri = "https://api.usaspending.gov/api/v2/search/spending_by_award/"

    def build_request(self, query: Mapping[str, Any]) -> HttpRequest:
        filters = {key: value for key, value in query.items() if key not in {"limit", "page"}}
        return HttpRequest(
            method="POST",
            url=self.source_uri,
            query={},
            body={
                "filters": filters,
                "fields": ["Award ID", "Recipient Name", "Award Amount", "Start Date", "End Date"],
                "limit": int(query.get("limit", 100)),
                "page": int(query.get("page", 1)),
                "subawards": False,
            },
        )

    def _parse_available(self, payload: Any) -> tuple[dict[str, Any], dict[str, str | None]]:
        rows = _collection_at(payload, "results")
        awards = [
            {
                "award_id": row.get("Award ID"),
                "recipient_name": row.get("Recipient Name"),
                "award_amount": row.get("Award Amount"),
                "period_start": row.get("Start Date"),
                "period_end": row.get("End Date"),
            }
            for row in rows
            if isinstance(row, dict)
        ]
        starts = sorted(value for value in (row["period_start"] for row in awards) if _first_date(value))
        ends = sorted(value for value in (row["period_end"] for row in awards) if _first_date(value))
        return {"awards": awards}, {
            "period_start": starts[0] if starts else None,
            "period_end": ends[-1] if ends else None,
            "observed_at": ends[-1] if ends else None,
        }


class USITCDataWebAdapter(PublicDataAdapter):
    provider_id = "usitc"
    title = "USITC DataWeb trade data"
    priority = "high"
    capability = "numeric"
    capabilities = ("usitc.trade-data", "usitc.tariff-data")
    source_uri = "https://dataweb.usitc.gov/api/data"

    def build_request(self, query: Mapping[str, Any]) -> HttpRequest:
        return HttpRequest(method="POST", url=self.source_uri, query={}, body=dict(query))

    def _parse_available(self, payload: Any) -> tuple[dict[str, Any], dict[str, str | None]]:
        source_rows = _collection_at(payload, "data")
        rows = [
            {
                "year": row.get("year"),
                "hs_code": row.get("hts10") or row.get("hs_code"),
                "customs_value": row.get("customs_value"),
                "quantity": row.get("quantity"),
            }
            for row in source_rows
            if isinstance(row, dict)
        ]
        years = [row["year"] for row in rows if isinstance(row["year"], int)]
        observed_at = f"{max(years)}-12-31" if years else None
        return {"rows": rows}, {"observed_at": observed_at, "effective_at": observed_at}


class EIAAdapter(PublicDataAdapter):
    provider_id = "eia"
    title = "US Energy Information Administration v2"
    priority = "high"
    capability = "numeric"
    capabilities = ("eia.energy-data",)
    secret_parameter_names = ("api_key",)
    source_uri = "https://api.eia.gov/v2/"

    def build_request(self, query: Mapping[str, Any]) -> HttpRequest:
        route = str(query["route"]).strip("/")
        parameters = {"api_key": self._config.get("eia_api_key", "DEMO_KEY"), "data[0]": "value", "length": query.get("length", 5000)}
        facets = query.get("facets", {})
        if isinstance(facets, Mapping):
            for key, values in facets.items():
                for value in values if isinstance(values, list) else [values]:
                    parameters[f"facets[{key}][]"] = str(value)
        return HttpRequest(method="GET", url=f"{self.source_uri}{route}/data/", query=parameters)

    def _parse_available(self, payload: Any) -> tuple[dict[str, Any], dict[str, str | None]]:
        source_rows = _collection_at(payload, "response", "data")
        rows = [
            {
                "period": row.get("period"),
                "respondent": row.get("respondent"),
                "value": row.get("value"),
                "unit": row.get("value-units") or row.get("unit"),
            }
            for row in source_rows
            if isinstance(row, dict)
        ]
        periods = sorted(value for value in (row["period"] for row in rows) if _first_date(value))
        observed_at = periods[-1] if periods else None
        return {"rows": rows}, {"observed_at": observed_at, "effective_at": observed_at}


class BLSAdapter(PublicDataAdapter):
    provider_id = "bls"
    title = "Bureau of Labor Statistics time series"
    priority = "medium"
    capability = "numeric"
    capabilities = ("bls.labor-data", "bls.price-data")
    secret_parameter_names = ("registrationkey",)
    source_uri = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

    def build_request(self, query: Mapping[str, Any]) -> HttpRequest:
        body: dict[str, Any] = {"seriesid": list(query["series"])}
        for key in ("startyear", "endyear"):
            if key in query:
                body[key] = str(query[key])
        registration_key = self._config.get("bls_registration_key") or query.get("registrationkey")
        if registration_key:
            body["registrationkey"] = str(registration_key)
        return HttpRequest(method="POST", url=self.source_uri, query={}, body=body)

    def _parse_available(self, payload: Any) -> tuple[dict[str, Any], dict[str, str | None]]:
        series = _collection_at(payload, "Results", "series")
        rows = [item for entry in series if isinstance(entry, dict) for item in entry.get("data", []) if isinstance(item, dict)]
        observed_at = None
        if rows and isinstance(rows[0].get("year"), str) and isinstance(rows[0].get("period"), str):
            observed_at = f"{rows[0]['year']}-{rows[0]['period'][1:]}-01"
        return {"series": series, "rows": rows}, {"observed_at": observed_at}


class BEAAdapter(PublicDataAdapter):
    provider_id = "bea"
    title = "Bureau of Economic Analysis API"
    priority = "medium"
    capability = "numeric"
    capabilities = ("bea.national-accounts", "bea.industry-data")
    secret_parameter_names = ("UserID",)
    source_uri = "https://apps.bea.gov/api/data/"

    def __init__(self, *, http: HttpClient | None, clock: Clock, config: Mapping[str, str]) -> None:
        self.unavailable_reason = None if config.get("bea_api_key") else "BEA API key is not configured"
        super().__init__(http=http, clock=clock, config=config)

    def build_request(self, query: Mapping[str, Any]) -> HttpRequest:
        parameters = {"UserID": self._config["bea_api_key"], "ResultFormat": "JSON", **{key: str(value) for key, value in query.items()}}
        return HttpRequest(method="GET", url=self.source_uri, query=parameters)

    def _parse_available(self, payload: Any) -> tuple[dict[str, Any], dict[str, str | None]]:
        rows = _collection_at(payload, "BEAAPI", "Results", "Data")
        return {"rows": rows}, {"observed_at": _first_date(rows[0].get("TimePeriod")) if rows and isinstance(rows[0], dict) else None}


class CFTCAdapter(PublicDataAdapter):
    provider_id = "cftc"
    title = "CFTC public reporting"
    priority = "medium"
    capability = "numeric"
    capabilities = ("cftc.commitments-of-traders",)
    source_uri = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"

    def build_request(self, query: Mapping[str, Any]) -> HttpRequest:
        return HttpRequest(method="GET", url=self.source_uri, query={key: str(value) for key, value in query.items()})

    def _parse_available(self, payload: Any) -> tuple[dict[str, Any], dict[str, str | None]]:
        if not isinstance(payload, list):
            raise ResponseShapeError("expected CFTC response to be a list")
        rows = payload
        observed_at = _first_date(rows[0].get("report_date_as_yyyy_mm_dd")) if rows and isinstance(rows[0], dict) else None
        return {"rows": rows}, {"observed_at": observed_at, "effective_at": observed_at}


class OptionalAPIAdapter(PublicDataAdapter):
    capability = "numeric"

    def __init__(self, *, http: HttpClient | None, clock: Clock, config: Mapping[str, str]) -> None:
        self.unavailable_reason = f"{self.title} API key is not configured" if not config.get(self.config_key) else None
        super().__init__(http=http, clock=clock, config=config)

    def build_request(self, query: Mapping[str, Any]) -> HttpRequest:
        return HttpRequest(method="GET", url=self.source_uri, query={key: str(value) for key, value in query.items()})

    def _parse_available(self, payload: Any) -> tuple[dict[str, Any], dict[str, str | None]]:
        return {"raw": payload}, {}


class SAMAdapter(OptionalAPIAdapter):
    provider_id = "sam"
    title = "SAM.gov"
    priority = "optional"
    capabilities = ("sam.procurement-opportunities",)
    source_uri = "https://api.sam.gov/entity-information/v3/entities"
    config_key = "sam_api_key"
    secret_parameter_names = ("api_key",)

    def build_request(self, query: Mapping[str, Any]) -> HttpRequest:
        return HttpRequest(
            method="GET",
            url=self.source_uri,
            query={**{key: str(value) for key, value in query.items()}, "api_key": self._config[self.config_key]},
        )

    def _parse_available(self, payload: Any) -> tuple[dict[str, Any], dict[str, str | None]]:
        return {"entities": _collection_at(payload, "entityData")}, {}


class USPTOAdapter(OptionalAPIAdapter):
    provider_id = "uspto"
    title = "USPTO"
    priority = "optional"
    capabilities = ("uspto.patent-records",)
    source_uri = "https://api.uspto.gov/api/v1/patent/"
    config_key = "uspto_api_key"
    secret_parameter_names = ("X-API-KEY",)

    def build_request(self, query: Mapping[str, Any]) -> HttpRequest:
        return HttpRequest(
            method="GET",
            url=self.source_uri,
            query={key: str(value) for key, value in query.items()},
            headers={"X-API-KEY": self._config[self.config_key]},
        )

    def _parse_available(self, payload: Any) -> tuple[dict[str, Any], dict[str, str | None]]:
        return {"patents": _collection_at(payload, "patentDataBag")}, {}


class NarrativeLinkProvider(PublicDataAdapter):
    priority = "narrative"
    capability = "narrative_link"
    unavailable_reason = "narrative links are evidence references, not numeric source substitution"

    def build_request(self, query: Mapping[str, Any]) -> HttpRequest:
        return HttpRequest(method="GET", url=self.source_uri, query={key: str(value) for key, value in query.items()})

    def _parse_available(self, payload: Any) -> tuple[dict[str, Any], dict[str, str | None]]:
        return {"links": _collection_at(payload, "results")}, {}


class FederalRegisterProvider(NarrativeLinkProvider):
    provider_id = "federal-register"
    title = "Federal Register"
    capabilities = ("federal-register.rulemaking", "federal-register.notices")
    source_uri = "https://www.federalregister.gov/api/v1/documents.json"


class BISProvider(NarrativeLinkProvider):
    provider_id = "bis"
    title = "Bureau of Industry and Security"
    capabilities = ("bis.export-controls", "bis.entity-lists")
    source_uri = "https://www.bis.gov/"


class InvestorRelationsProvider(NarrativeLinkProvider):
    provider_id = "issuer-ir"
    title = "Issuer investor relations"
    capabilities = ("issuer-ir.announcements", "issuer-ir.presentations")
    source_uri = "https://www.sec.gov/edgar/browse/"


def public_data_catalog(
    *,
    http: HttpClient | None = None,
    clock: Clock = _utc_now,
    config: Mapping[str, str] | None = None,
) -> dict[str, PublicDataAdapter]:
    """Build the free-data capability catalog with injectable external boundaries."""

    resolved_config = config or {}
    adapters = (
        USASpendingAdapter(http=http, clock=clock, config=resolved_config),
        USITCDataWebAdapter(http=http, clock=clock, config=resolved_config),
        EIAAdapter(http=http, clock=clock, config=resolved_config),
        BLSAdapter(http=http, clock=clock, config=resolved_config),
        BEAAdapter(http=http, clock=clock, config=resolved_config),
        CFTCAdapter(http=http, clock=clock, config=resolved_config),
        SAMAdapter(http=http, clock=clock, config=resolved_config),
        USPTOAdapter(http=http, clock=clock, config=resolved_config),
        FederalRegisterProvider(http=http, clock=clock, config=resolved_config),
        BISProvider(http=http, clock=clock, config=resolved_config),
        InvestorRelationsProvider(http=http, clock=clock, config=resolved_config),
    )
    return {adapter.provider_id: adapter for adapter in adapters}
