"""Objective market-fact adapter for yfinance.

This adapter preserves provider facts and provenance only.  Quote metadata is
read from ``get_info`` / ``get_fast_info``; financial facts are read only from
the statement tables exposed by yfinance.
"""

from __future__ import annotations

import importlib.metadata
import json
import math
import re
from hashlib import sha256
from collections.abc import Callable, Mapping
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .base import ProviderEnvelope


RawTransport = Callable[[str], Mapping[str, Mapping[str, Any]]]
RawCache = dict[str, bytes]


def _default_ticker_factory(ticker: str) -> Any:
    import yfinance

    return yfinance.Ticker(ticker)


def _installed_provider_version() -> str:
    """Return the installed package version, without inventing one when absent."""
    try:
        return importlib.metadata.version("yfinance")
    except importlib.metadata.PackageNotFoundError:
        return "unavailable:yfinance"


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalise(value: Any) -> Any:
    """Return a JSON-safe value, treating NaN/infinity as unavailable."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    try:
        missing = value != value
    except (TypeError, ValueError):
        missing = False
    if missing is True or str(missing) == "<NA>":
        return None
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, datetime):
        return _utc_iso(value)
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return _normalise(value.item())
        except (TypeError, ValueError):
            pass
    if isinstance(value, Mapping):
        return {str(key): _normalise(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    return str(value)


def _mapping_value(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(key)
    try:
        return getattr(value, key)
    except (AttributeError, KeyError):
        return None


def _epoch_iso(value: Any) -> str | None:
    value = _normalise(value)
    if isinstance(value, (int, float)):
        try:
            return _utc_iso(datetime.fromtimestamp(value, timezone.utc))
        except (OSError, OverflowError, ValueError):
            return None
    if isinstance(value, str):
        return value
    return None


def _period_label(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    try:
        converted = value.to_pydatetime()
    except AttributeError:
        converted = None
    if isinstance(converted, datetime):
        return converted.date().isoformat()
    return str(value)


def _date_label(value: str) -> str:
    """Provider-envelope temporal fields are calendar dates, unlike quote facts."""
    return value[:10]


def _public_uri(uri: str) -> str:
    """Keep endpoint identity without serializing Yahoo's short-lived crumb."""
    parts = urlsplit(uri)
    query = urlencode([(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key.lower() != "crumb"])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


class _RecordingSession:
    def __init__(self, session: Any, raw_cache: RawCache) -> None:
        self._session = session
        self._raw_cache = raw_cache
        self.records: list[dict[str, Any]] = []

    def get(self, *args: Any, **kwargs: Any) -> Any:
        response = self._session.get(*args, **kwargs)
        content = bytes(response.content)
        content_sha256 = sha256(content).hexdigest()
        self._raw_cache[content_sha256] = content
        self.records.append({"uri": _public_uri(str(response.url)), "content": content, "content_sha256": content_sha256})
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._session, name)


class YFinanceRecordingTransport:
    """Record exact bytes emitted through a ticker's existing authenticated session."""

    def __init__(self, client: Any, raw_cache: RawCache) -> None:
        data = getattr(client, "_data", None)
        session = getattr(data, "_session", None)
        if data is None or session is None or not callable(getattr(session, "get", None)):
            raise ValueError("ticker does not expose a recordable yfinance session")
        self._data = data
        self._original_session = session
        self._recording_session = _RecordingSession(session, raw_cache)

    def attach(self) -> None:
        self._data._session = self._recording_session

    def detach(self) -> None:
        self._data._session = self._original_session

    def mark(self) -> int:
        return len(self._recording_session.records)

    def since(self, mark: int) -> list[dict[str, Any]]:
        return self._recording_session.records[mark:]


def _raw_sources(raw_transport: RawTransport, ticker: str) -> dict[str, dict[str, Any]]:
    payloads = raw_transport(ticker)
    sources: dict[str, dict[str, Any]] = {}
    for name in ("quote", "fundamentals"):
        payload = payloads.get(name) if isinstance(payloads, Mapping) else None
        if not isinstance(payload, Mapping):
            raise ValueError(f"raw transport did not provide {name} payload")
        uri = payload.get("uri")
        content = payload.get("content")
        if not isinstance(uri, str) or not uri or not isinstance(content, bytes):
            raise ValueError(f"raw transport {name} payload requires uri and bytes content")
        sources[name] = {"uri": uri, "content": content, "content_sha256": sha256(content).hexdigest()}
    return sources


def _recorded_source(records: list[dict[str, Any]], fragment: str) -> dict[str, Any] | None:
    matches = [record for record in records if fragment in str(record.get("uri", ""))]
    return matches[-1] if matches else None


def _raw_scalar_matches(content: bytes, key: str, value: Any) -> bool:
    try:
        parsed = json.loads(content)
    except (TypeError, ValueError):
        return False
    expected = _normalise(value)
    stack = [parsed]
    while stack:
        current = stack.pop()
        if isinstance(current, Mapping):
            candidate = current.get(key)
            if isinstance(candidate, Mapping) and _normalise(candidate.get("raw")) == expected:
                return True
            if _normalise(candidate) == expected:
                return True
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return False


def _timeseries_raw_path(path_attribute: str, label: str, period: str) -> str:
    prefix = "quarterly" if path_attribute.startswith("quarterly_") else "annual"
    concept = "".join(part[:1].upper() + part[1:] for part in re.findall(r"[A-Za-z0-9]+", label))
    return f"timeseries.result.{prefix}{concept}[asOfDate={period}].reportedValue.raw"


def _timeseries_value_matches(source: Mapping[str, Any], path_attribute: str, label: str, period: str, value: Any) -> bool:
    try:
        parsed = json.loads(source["content"])
    except (KeyError, TypeError, ValueError):
        return False
    prefix = "quarterly" if path_attribute.startswith("quarterly_") else "annual"
    concept = "".join(part[:1].upper() + part[1:] for part in re.findall(r"[A-Za-z0-9]+", label))
    expected = _normalise(value)
    for result in parsed.get("timeseries", {}).get("result", []):
        for item in result.get(f"{prefix}{concept}", []):
            reported = item.get("reportedValue", {})
            if item.get("asOfDate") == period and _normalise(reported.get("raw")) == expected:
                return True
    return False


def _fact(
    value: Any,
    *,
    source_path: str,
    effective_at: str | None,
    observed_at: str | None,
    available_at: str,
    fetched_at: str,
    availability: str | None = None,
    unit: str | None = None,
    source_uri: str | None = None,
    raw_content_sha256: str | None = None,
    raw_source_path: str | None = None,
) -> dict[str, Any]:
    normalised = _normalise(value)
    invalid = value is not None and normalised is None
    resolved_availability = availability or ("invalid" if invalid else ("available" if normalised is not None else "not_disclosed"))
    public_value = normalised if resolved_availability == "available" else None
    fact = {
        "availability": resolved_availability,
        "value": public_value,
        "raw_value": public_value,
        "source_path": source_path,
        "effective_at": effective_at,
        "observed_at": observed_at,
        "available_at": available_at,
        "fetched_at": fetched_at,
    }
    if unit is not None:
        fact["unit"] = unit
    if source_uri is not None:
        fact["source_uri"] = source_uri
    if raw_content_sha256 is not None:
        fact["raw_content_sha256"] = raw_content_sha256
    if raw_source_path is not None:
        fact["raw_source_path"] = raw_source_path
    return fact


def _statement_table(client: Any, attribute: str) -> tuple[Any | None, str | None]:
    try:
        return getattr(client, attribute), None
    except Exception as exc:  # yfinance lazily fetches these properties
        return None, str(exc)


def _statement_columns(table: Any) -> list[Any]:
    columns = getattr(table, "columns", None)
    index = getattr(table, "index", None)
    if columns is None or index is None:
        return []
    values = list(columns)
    return sorted(values, key=_period_label, reverse=True)


def _statement_value(table: Any, labels: tuple[str, ...]) -> tuple[Any, str | None, str | None]:
    index = getattr(table, "index", None)
    if index is None:
        return None, None, None
    rows = {str(row): row for row in index}
    for period in _statement_columns(table):
        for label in labels:
            row = rows.get(label)
            if row is None:
                continue
            try:
                value = table.loc[row, period]
            except (AttributeError, KeyError, TypeError):
                continue
            if _normalise(value) is not None:
                return value, _period_label(period), label
    return None, None, None


def _raw_statement(table: Any) -> dict[str, dict[str, Any]]:
    index = getattr(table, "index", None)
    if index is None:
        return {}
    rows = list(index)
    raw: dict[str, dict[str, Any]] = {}
    for period in _statement_columns(table):
        raw[_period_label(period)] = {}
        for row in rows:
            try:
                raw[_period_label(period)][str(row)] = _normalise(table.loc[row, period])
            except (AttributeError, KeyError, TypeError):
                raw[_period_label(period)][str(row)] = None
    return raw


class YFinanceProvider:
    """Load ungraded market and financial facts through an injected ticker client."""

    def __init__(
        self,
        *,
        ticker_factory: Callable[[str], Any] = _default_ticker_factory,
        raw_transport: RawTransport | None = None,
        raw_cache: RawCache | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        provider_version: str | None = None,
    ) -> None:
        self._ticker_factory = ticker_factory
        self._raw_transport = raw_transport
        self._raw_cache = raw_cache if raw_cache is not None else {}
        self._clock = clock
        self._provider_version = provider_version if provider_version is not None else _installed_provider_version()

    def fetch(self, ticker: str) -> ProviderEnvelope:
        requested_ticker = ticker.upper()
        fetched_at = _utc_iso(self._clock())
        source_uri = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{requested_ticker}"
        request = {"ticker": requested_ticker}
        try:
            client = self._ticker_factory(requested_ticker)
        except Exception as exc:
            return ProviderEnvelope.unavailable(
                provider="yfinance",
                provider_version=self._provider_version,
                source_uri=source_uri,
                fetched_at=fetched_at,
                request=request,
                status="unavailable",
                reason=str(exc),
                available_at=fetched_at,
            )

        recorder: YFinanceRecordingTransport | None = None
        if self._raw_transport is None:
            try:
                recorder = YFinanceRecordingTransport(client, self._raw_cache)
                recorder.attach()
            except Exception as exc:
                return ProviderEnvelope.unavailable(
                    provider="yfinance",
                    provider_version=self._provider_version,
                    source_uri=source_uri,
                    fetched_at=fetched_at,
                    request=request,
                    status="unavailable",
                    reason=f"yfinance raw recording unavailable: {exc}",
                    available_at=fetched_at,
                )
        try:
            info_mark = recorder.mark() if recorder is not None else 0
            info = dict(client.get_info() or {})
            info_records = recorder.since(info_mark) if recorder is not None else []
            try:
                fast_mark = recorder.mark() if recorder is not None else 0
                fast_client = client.get_fast_info() or {}
                fast_info = {
                    key: _mapping_value(fast_client, key)
                    for key in ("market_cap", "last_price", "shares")
                }
                fast_records = recorder.since(fast_mark) if recorder is not None else []
            except Exception:
                fast_info = {}
                fast_records = []
        except Exception as exc:
            if recorder is not None:
                recorder.detach()
            return ProviderEnvelope.unavailable(
                provider="yfinance",
                provider_version=self._provider_version,
                source_uri=source_uri,
                fetched_at=fetched_at,
                request=request,
                status="unavailable",
                reason=str(exc),
                available_at=fetched_at,
            )
        if self._raw_transport is not None:
            try:
                sources = _raw_sources(self._raw_transport, requested_ticker)
            except Exception as exc:
                return ProviderEnvelope.unavailable(
                    provider="yfinance",
                    provider_version=self._provider_version,
                    source_uri=source_uri,
                    fetched_at=fetched_at,
                    request=request,
                    status="unavailable",
                    reason=f"yfinance raw payload unavailable: {exc}",
                    available_at=fetched_at,
                )
            quote_source = sources["quote"]
            fast_source = quote_source
        else:
            quote_source = _recorded_source(info_records, "/quoteSummary/")
            fast_source = _recorded_source(fast_records, "/chart/") or quote_source
            if quote_source is None:
                recorder.detach()
                return ProviderEnvelope.unavailable(
                    provider="yfinance",
                    provider_version=self._provider_version,
                    source_uri=source_uri,
                    fetched_at=fetched_at,
                    request=request,
                    status="unavailable",
                    reason="yfinance recording did not capture quoteSummary response bytes",
                    available_at=fetched_at,
                )

        raw_info = _normalise(info)
        raw_fast_info = _normalise(fast_info)
        quote_at = _epoch_iso(info.get("regularMarketTime")) or fetched_at

        def select(info_key: str, fast_key: str | None = None) -> tuple[Any, str]:
            candidate = info.get(info_key)
            if _normalise(candidate) is not None:
                return candidate, f"info.{info_key}"
            if fast_key is not None:
                fallback = _mapping_value(fast_info, fast_key)
                if _normalise(fallback) is not None:
                    return fallback, f"fast_info.{fast_key}"
            return candidate, f"info.{info_key}"

        quote_fields = {
            "market_cap": ("marketCap", "market_cap"),
            "price": ("currentPrice", "last_price"),
            "shares_outstanding": ("sharesOutstanding", "shares"),
            "trailing_pe": ("trailingPE", None),
            "forward_pe": ("forwardPE", None),
            "peg_ratio": ("pegRatio", None),
            "price_to_sales": ("priceToSalesTrailing12Months", None),
            "enterprise_value": ("enterpriseValue", None),
            "enterprise_to_revenue": ("enterpriseToRevenue", None),
            "enterprise_to_ebitda": ("enterpriseToEbitda", None),
        }
        facts: dict[str, dict[str, Any]] = {}
        for name, (info_key, fast_key) in quote_fields.items():
            value, source_path = select(info_key, fast_key)
            fact_source = fast_source if source_path.startswith("fast_info.") else quote_source
            verified = _normalise(value) is None or _raw_scalar_matches(fact_source["content"], info_key if source_path.startswith("info.") else fast_key or info_key, value)
            facts[name] = _fact(
                value,
                source_path=source_path,
                effective_at=quote_at,
                observed_at=quote_at,
                available_at=fetched_at,
                fetched_at=fetched_at,
                availability="unavailable" if not verified else None,
                source_uri=fact_source["uri"],
                raw_content_sha256=fact_source["content_sha256"],
                raw_source_path=f"response.{info_key if source_path.startswith('info.') else fast_key or info_key}" if recorder is not None else None,
            )

        statement_specs = {
            "income_statement": ("income_stmt", "quarterly_income_stmt"),
            "balance_sheet": ("balance_sheet", "quarterly_balance_sheet"),
            "cash_flow": ("cash_flow", "quarterly_cash_flow"),
        }
        tables: dict[str, Any | None] = {}
        table_errors: dict[str, str | None] = {}
        statement_sources: dict[str, dict[str, Any] | None] = {}
        for annual_attribute, quarterly_attribute in statement_specs.values():
            annual_mark = recorder.mark() if recorder is not None else 0
            tables[annual_attribute], table_errors[annual_attribute] = _statement_table(client, annual_attribute)
            statement_sources[annual_attribute] = _recorded_source(recorder.since(annual_mark), "/fundamentals-timeseries/") if recorder is not None else sources["fundamentals"]
            quarterly_mark = recorder.mark() if recorder is not None else 0
            tables[quarterly_attribute], table_errors[quarterly_attribute] = _statement_table(client, quarterly_attribute)
            statement_sources[quarterly_attribute] = _recorded_source(recorder.since(quarterly_mark), "/fundamentals-timeseries/") if recorder is not None else sources["fundamentals"]

        statement_fields = {
            "total_revenue": ("income_stmt", "quarterly_income_stmt", ("Total Revenue", "Operating Revenue"), "USD"),
            "gross_profit": ("income_stmt", "quarterly_income_stmt", ("Gross Profit",), "USD"),
            "cost_of_revenue": ("income_stmt", "quarterly_income_stmt", ("Cost Of Revenue", "Cost of Revenue"), "USD"),
            "operating_income": ("income_stmt", "quarterly_income_stmt", ("Operating Income", "Operating Income Loss"), "USD"),
            "net_income": ("income_stmt", "quarterly_income_stmt", ("Net Income", "Net Income Common Stockholders"), "USD"),
            "ebitda": ("income_stmt", "quarterly_income_stmt", ("EBITDA", "Normalized EBITDA"), "USD"),
            "diluted_average_shares": ("income_stmt", "quarterly_income_stmt", ("Diluted Average Shares", "Diluted Average Shares Outstanding"), "shares"),
            "cash": ("balance_sheet", "quarterly_balance_sheet", ("Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents", "Cash Financial"), "USD"),
            "debt": ("balance_sheet", "quarterly_balance_sheet", ("Total Debt",), "USD"),
            "total_assets": ("balance_sheet", "quarterly_balance_sheet", ("Total Assets",), "USD"),
            "inventory": ("balance_sheet", "quarterly_balance_sheet", ("Inventory",), "USD"),
            "free_cash_flow": ("cash_flow", "quarterly_cash_flow", ("Free Cash Flow",), "USD"),
            "operating_cash_flow": ("cash_flow", "quarterly_cash_flow", ("Operating Cash Flow", "Total Cash From Operating Activities"), "USD"),
            "capital_expenditure": ("cash_flow", "quarterly_cash_flow", ("Capital Expenditure", "Capital Expenditure Reported"), "USD"),
            "stock_based_compensation": ("cash_flow", "quarterly_cash_flow", ("Stock Based Compensation", "Stock Based Compensation Expense"), "USD"),
        }
        for name, (annual_attribute, quarterly_attribute, labels, unit) in statement_fields.items():
            value, period, label = _statement_value(tables[quarterly_attribute], labels)
            path_attribute = quarterly_attribute
            if label is None:
                value, period, label = _statement_value(tables[annual_attribute], labels)
                path_attribute = annual_attribute
            source_path = f"{path_attribute}.{period}.{label}" if label is not None and period is not None else f"{quarterly_attribute}.{labels[0]}"
            unavailable = tables[annual_attribute] is None and tables[quarterly_attribute] is None and (table_errors[annual_attribute] or table_errors[quarterly_attribute])
            statement_source = statement_sources.get(path_attribute)
            verified = _normalise(value) is None or (
                statement_source is not None and label is not None and period is not None and _timeseries_value_matches(statement_source, path_attribute, label, period, value)
            )
            facts[name] = _fact(
                value,
                source_path=source_path,
                effective_at=period,
                observed_at=period,
                available_at=fetched_at,
                fetched_at=fetched_at,
                availability="unavailable" if unavailable or statement_source is None or not verified else None,
                unit=unit,
                source_uri=statement_source["uri"] if statement_source is not None else None,
                raw_content_sha256=statement_source["content_sha256"] if statement_source is not None else None,
                raw_source_path=_timeseries_raw_path(path_attribute, label, period) if recorder is not None and label is not None and period is not None else None,
            )

        statement_selection: dict[str, dict[str, Any]] = {}
        for name, (annual_attribute, quarterly_attribute) in statement_specs.items():
            quarterly_periods = _statement_columns(tables[quarterly_attribute])
            annual_periods = _statement_columns(tables[annual_attribute])
            winning_attribute = quarterly_attribute if quarterly_periods else (annual_attribute if annual_periods else None)
            periods = quarterly_periods if quarterly_periods else annual_periods
            statement_selection[name] = {
                "winning_path": winning_attribute,
                "period": _period_label(periods[0]) if periods else None,
                "fallback_from": annual_attribute if winning_attribute == quarterly_attribute else None,
                "available_at": fetched_at,
                "fetched_at": fetched_at,
            }

        statement_dates = {
            "last_fiscal_year_end": statement_selection["income_statement"]["period"] if statement_selection["income_statement"]["winning_path"] == "income_stmt" else (_period_label(_statement_columns(tables["income_stmt"])[0]) if _statement_columns(tables["income_stmt"]) else None),
            "most_recent_quarter": _period_label(_statement_columns(tables["quarterly_income_stmt"])[0]) if _statement_columns(tables["quarterly_income_stmt"]) else None,
        }
        if recorder is not None:
            recorded_sources = {record["content_sha256"]: record for record in recorder.since(0)}
            recorder.detach()
            raw_sources = {
                content_sha256: {"uri": record["uri"], "content_sha256": content_sha256}
                for content_sha256, record in recorded_sources.items()
                if content_sha256 in {fact.get("raw_content_sha256") for fact in facts.values()}
            }
            raw_payloads = {
                content_sha256: record["content"]
                for content_sha256, record in recorded_sources.items()
                if content_sha256 != quote_source["content_sha256"] and content_sha256 in raw_sources
            }
        else:
            raw_sources = {name: {"uri": source["uri"], "content_sha256": source["content_sha256"]} for name, source in sources.items()}
            raw_payloads = {
                source["content_sha256"]: source["content"]
                for source in sources.values()
                if source["content_sha256"] != quote_source["content_sha256"]
            }
        data = {
            "identity": {
                "ticker": _normalise(info.get("symbol")) or requested_ticker,
                "name": _normalise(info.get("longName")) or _normalise(info.get("shortName")),
                "exchange": _normalise(info.get("exchange")),
                "quote_type": _normalise(info.get("quoteType")),
            },
            "facts": facts,
            "statement_dates": statement_dates,
            "statement_selection": statement_selection,
            "client_view": {
                "info": raw_info,
                "fast_info": raw_fast_info,
                "statements": {attribute: _raw_statement(table) for attribute, table in tables.items()},
            },
            "raw_sources": raw_sources,
        }
        return ProviderEnvelope.available(
            provider="yfinance",
            provider_version=self._provider_version,
            source_uri=quote_source["uri"],
            raw_content=quote_source["content"],
            data=data,
            fetched_at=fetched_at,
            request=request,
            effective_at=_date_label(quote_at),
            observed_at=_date_label(quote_at),
            available_at=fetched_at,
            source_version=None,
            raw_payloads=raw_payloads,
            source_parameters={"raw_sources": data["raw_sources"]},
            parse={"status": "parsed", "transform_version": "yfinance-adapter/2", "message": "facts selected from yfinance client views"},
        )
