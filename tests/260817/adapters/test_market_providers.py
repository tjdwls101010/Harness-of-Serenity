from __future__ import annotations

import math
import json
from hashlib import sha256
from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd

import serenity_core.providers.yfinance as yfinance_provider
from serenity_core.providers.rs_rating import RsRatingProvider
from serenity_core.providers.yfinance import YFinanceProvider
from serenity_core.raw_cache import cache_provider_raw_payloads
from serenity_core.schema import validate_document


FROZEN_NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
QUOTE_RAW = json.dumps(
    {
        "quoteSummary": {
            "result": [
                {
                    "marketCap": {"raw": 4_200_000_000_000},
                    "currentPrice": {"raw": 174.55},
                    "sharesOutstanding": {"raw": 24_000_000_000},
                    "trailingPE": {"raw": 53.2},
                    "forwardPE": {"raw": 31.4},
                    "pegRatio": {"raw": 1.0},
                    "priceToSalesTrailing12Months": {"raw": 2.0},
                    "enterpriseValue": {"raw": 4_000_000_000_000},
                    "enterpriseToRevenue": {"raw": 3.0},
                    "enterpriseToEbitda": {"raw": 4.0},
                    "market_cap": {"raw": 4_200_000_000_000},
                    "last_price": {"raw": 174.55},
                }
            ]
        }
    },
    separators=(",", ":"),
).encode()


def _raw_series(name: str, period: str, value: int) -> tuple[str, list[dict]]:
    return name, [{"asOfDate": period, "reportedValue": {"raw": value}}]


FUNDAMENTALS_RAW = json.dumps(
    {
        "timeseries": {
            "result": [
                dict(
                    [
                        _raw_series("quarterlyTotalRevenue", "2026-07-31", 50_000_000_000),
                        _raw_series("quarterlyGrossProfit", "2026-07-31", 35_000_000_000),
                        _raw_series("quarterlyCostOfRevenue", "2026-07-31", 15_000_000_000),
                        _raw_series("quarterlyOperatingIncome", "2026-07-31", 25_000_000_000),
                        _raw_series("quarterlyNetIncome", "2026-07-31", 20_000_000_000),
                        _raw_series("quarterlyEBITDA", "2026-07-31", 26_000_000_000),
                        _raw_series("quarterlyDilutedAverageShares", "2026-07-31", 24_500_000_000),
                        _raw_series("quarterlyCashCashEquivalentsAndShortTermInvestments", "2026-07-31", 52_000_000_000),
                        _raw_series("quarterlyTotalDebt", "2026-07-31", 12_000_000_000),
                        _raw_series("quarterlyTotalAssets", "2026-07-31", 140_000_000_000),
                        _raw_series("quarterlyInventory", "2026-07-31", 11_000_000_000),
                        _raw_series("quarterlyFreeCashFlow", "2026-07-31", 24_000_000_000),
                        _raw_series("quarterlyOperatingCashFlow", "2026-07-31", 26_000_000_000),
                        _raw_series("quarterlyCapitalExpenditure", "2026-07-31", -2_000_000_000),
                        _raw_series("quarterlyStockBasedCompensation", "2026-07-31", 1_500_000_000),
                        _raw_series("annualTotalRevenue", "2025-01-31", 130_000_000_000),
                        _raw_series("annualEBITDA", "2025-01-31", 68_000_000_000),
                    ]
                )
            ]
        }
    },
    separators=(",", ":"),
).encode()
RS_RAW = b'[{"ticker":"NVDA","date":"2026-08-14","rs_raw":1.2345,"rs_rating":93}]'


def raw_yfinance_payloads(ticker: str) -> dict[str, dict[str, str | bytes]]:
    assert ticker == "NVDA"
    return {
        "quote": {
            "uri": "https://query1.finance.yahoo.com/v10/finance/quoteSummary/NVDA",
            "content": QUOTE_RAW,
        },
        "fundamentals": {
            "uri": "https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/NVDA",
            "content": FUNDAMENTALS_RAW,
        },
    }


def raw_rs_response(ticker: str, as_of: str | None) -> bytes:
    assert ticker == "NVDA"
    assert as_of is None
    return RS_RAW


RECORDED_QUOTE_URI = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/NVDA?crumb=secret"
RECORDED_INCOME_QUARTER_URI = "https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/NVDA?type=quarterly"
RECORDED_INCOME_ANNUAL_URI = "https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/NVDA?type=annual"
RECORDED_BALANCE_ANNUAL_URI = "https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/NVDA?type=annual-balance"
RECORDED_BALANCE_QUARTER_URI = "https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/NVDA?type=quarterly-balance"
RECORDED_CASH_ANNUAL_URI = "https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/NVDA?type=annual-cash"
RECORDED_CASH_QUARTER_URI = "https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/NVDA?type=quarterly-cash"
RECORDED_CHART_URI = "https://query2.finance.yahoo.com/v8/finance/chart/NVDA?range=1d"
RECORDED_QUOTE_RAW = b'{"quoteSummary":{"result":[{"marketCap":{"raw":4200000000000},"currentPrice":{"raw":174.55}}]}}'
RECORDED_CHART_RAW = b'{"chart":{"result":[{"last_price":174.55}]}}'
RECORDED_INCOME_QUARTER_RAW = b'{"timeseries":{"result":[{"quarterlyTotalRevenue":[{"asOfDate":"2026-07-31","reportedValue":{"raw":50000000000}}]}]}}'
RECORDED_EMPTY_RAW = b'{"timeseries":{"result":[]}}'


class RecordingSession:
    def __init__(self, payloads: dict[str, bytes]) -> None:
        self.payloads = payloads

    def get(self, uri: str, *args, **kwargs):
        return SimpleNamespace(url=uri, content=self.payloads[uri])


class SessionBackedTicker:
    def __init__(self) -> None:
        self._data = SimpleNamespace(
            _session=RecordingSession(
                {
                    RECORDED_QUOTE_URI: RECORDED_QUOTE_RAW,
                    RECORDED_INCOME_ANNUAL_URI: RECORDED_EMPTY_RAW,
                    RECORDED_INCOME_QUARTER_URI: RECORDED_INCOME_QUARTER_RAW,
                    RECORDED_BALANCE_ANNUAL_URI: RECORDED_EMPTY_RAW,
                    RECORDED_BALANCE_QUARTER_URI: RECORDED_EMPTY_RAW,
                    RECORDED_CASH_ANNUAL_URI: RECORDED_EMPTY_RAW,
                    RECORDED_CASH_QUARTER_URI: RECORDED_EMPTY_RAW,
                }
            )
        )

    def get_info(self) -> dict:
        self._data._session.get(RECORDED_QUOTE_URI)
        return {**FakeTicker().get_info(), "marketCap": 4_200_000_000_000, "currentPrice": 174.55}

    def get_fast_info(self) -> dict:
        return FakeTicker().get_fast_info()

    @property
    def income_stmt(self):
        self._data._session.get(RECORDED_INCOME_ANNUAL_URI)
        return FakeTicker.income_stmt

    @property
    def quarterly_income_stmt(self):
        self._data._session.get(RECORDED_INCOME_QUARTER_URI)
        return FakeTicker.quarterly_income_stmt

    @property
    def balance_sheet(self):
        self._data._session.get(RECORDED_BALANCE_ANNUAL_URI)
        return FakeTicker.balance_sheet

    @property
    def quarterly_balance_sheet(self):
        self._data._session.get(RECORDED_BALANCE_QUARTER_URI)
        return FakeTicker.quarterly_balance_sheet

    @property
    def cash_flow(self):
        self._data._session.get(RECORDED_CASH_ANNUAL_URI)
        return FakeTicker.cash_flow

    @property
    def quarterly_cash_flow(self):
        self._data._session.get(RECORDED_CASH_QUARTER_URI)
        return FakeTicker.quarterly_cash_flow


class LazyFastInfo:
    def __init__(self, ticker: "LazyFastTicker") -> None:
        self._ticker = ticker

    def __getattr__(self, key: str):
        if key == "last_price":
            self._ticker._data._session.get(RECORDED_CHART_URI)
            return 174.55
        return None


class LazyFastTicker(SessionBackedTicker):
    def __init__(self) -> None:
        super().__init__()
        self._data._session.payloads[RECORDED_CHART_URI] = RECORDED_CHART_RAW

    def get_info(self) -> dict:
        info = super().get_info()
        info["currentPrice"] = None
        return info

    def get_fast_info(self) -> LazyFastInfo:
        return LazyFastInfo(self)


class FakeTicker:
    income_stmt = pd.DataFrame(
        {
            pd.Timestamp("2025-01-31"): {
                "Total Revenue": 130_000_000_000,
                "Gross Profit": 91_000_000_000,
                "Cost Of Revenue": 39_000_000_000,
                "Operating Income": 65_000_000_000,
                "Net Income": 52_000_000_000,
                "EBITDA": 68_000_000_000,
            },
        }
    )
    quarterly_income_stmt = pd.DataFrame(
        {
            pd.Timestamp("2026-04-30"): {
                "Total Revenue": 44_000_000_000,
                "Gross Profit": 30_000_000_000,
                "Cost Of Revenue": 14_000_000_000,
                "Operating Income": 21_000_000_000,
                "Net Income": 18_000_000_000,
                "EBITDA": 22_000_000_000,
            },
            pd.Timestamp("2026-07-31"): {
                "Total Revenue": 50_000_000_000,
                "Gross Profit": 35_000_000_000,
                "Cost Of Revenue": 15_000_000_000,
                "Operating Income": 25_000_000_000,
                "Net Income": 20_000_000_000,
                "EBITDA": 26_000_000_000,
                "Diluted Average Shares": 24_500_000_000,
            },
        }
    )
    balance_sheet = pd.DataFrame(
        {
            pd.Timestamp("2025-01-31"): {
                "Cash Cash Equivalents And Short Term Investments": 45_000_000_000,
                "Total Debt": 10_000_000_000,
                "Total Assets": 120_000_000_000,
                "Inventory": 9_000_000_000,
            },
        }
    )
    quarterly_balance_sheet = pd.DataFrame(
        {
            pd.Timestamp("2026-07-31"): {
                "Cash Cash Equivalents And Short Term Investments": 52_000_000_000,
                "Total Debt": 12_000_000_000,
                "Total Assets": 140_000_000_000,
                "Inventory": 11_000_000_000,
            },
        }
    )
    cash_flow = pd.DataFrame(
        {
            pd.Timestamp("2025-01-31"): {
                "Operating Cash Flow": 70_000_000_000,
                "Capital Expenditure": -4_000_000_000,
                "Free Cash Flow": 66_000_000_000,
            },
        }
    )
    quarterly_cash_flow = pd.DataFrame(
        {
            pd.Timestamp("2026-07-31"): {
                "Operating Cash Flow": 26_000_000_000,
                "Capital Expenditure": -2_000_000_000,
                "Free Cash Flow": 24_000_000_000,
                "Stock Based Compensation": 1_500_000_000,
            },
        }
    )

    def get_info(self) -> dict:
        return {
            "symbol": "NVDA",
            "longName": "NVIDIA Corporation",
            "exchange": "NMS",
            "quoteType": "EQUITY",
            "marketCap": math.nan,
            "currentPrice": None,
            "sharesOutstanding": 24_000_000_000,
            "trailingPE": 53.2,
            "forwardPE": 31.4,
            "grossMargins": 0.75,
            "operatingMargins": 0.62,
            "revenueGrowth": 1.22,
            "freeCashflow": 60_000_000_000,
            "totalCash": 45_000_000_000,
            "totalDebt": 10_000_000_000,
            "totalAssets": 120_000_000_000,
            "inventory": 9_000_000_000,
            "lastFiscalYearEnd": 1767225600,
            "mostRecentQuarter": 1780185600,
            "regularMarketTime": 1786968000,
            "unserializable": math.inf,
        }

    def get_fast_info(self) -> dict:
        return {"market_cap": 4_200_000_000_000, "last_price": 174.55}


class FakeRsClient:
    def get(self, ticker: str, date: str | None = None) -> dict:
        assert ticker == "NVDA"
        assert date is None
        return {
            "ticker": "NVDA",
            "date": "2026-08-14",
            "rs_raw": 1.2345,
            "rs_rating": 93,
            "provider_note": pd.NA,
        }


def test_yfinance_provider_preserves_objective_fields_with_per_fact_provenance() -> None:
    envelope = YFinanceProvider(
        ticker_factory=lambda ticker: FakeTicker(),
        raw_transport=raw_yfinance_payloads,
        clock=lambda: FROZEN_NOW,
        provider_version="test-yf",
    ).fetch("nvda").to_dict()

    validate_document(envelope, "urn:serenity:schema:provider-envelope:1")
    assert envelope["schema_id"] == "urn:serenity:schema:provider-envelope:1"
    assert envelope["provider"] == "yfinance"
    assert envelope["status"] == "available"
    assert envelope["fetched_at"] == "2026-08-17T12:00:00Z"
    assert envelope["data"]["identity"] == {
        "ticker": "NVDA",
        "name": "NVIDIA Corporation",
        "exchange": "NMS",
        "quote_type": "EQUITY",
    }
    assert envelope["data"]["facts"]["market_cap"] == {
        "availability": "available",
        "value": 4_200_000_000_000,
        "raw_value": 4_200_000_000_000,
        "source_path": "fast_info.market_cap",
        "effective_at": "2026-08-17T12:00:00Z",
        "observed_at": "2026-08-17T12:00:00Z",
        "available_at": "2026-08-17T12:00:00Z",
        "fetched_at": "2026-08-17T12:00:00Z",
        "source_uri": "https://query1.finance.yahoo.com/v10/finance/quoteSummary/NVDA",
        "raw_content_sha256": sha256(QUOTE_RAW).hexdigest(),
    }
    assert envelope["data"]["facts"]["price"]["value"] == 174.55
    assert envelope["data"]["facts"]["price"]["source_path"] == "fast_info.last_price"
    assert envelope["data"]["facts"]["total_revenue"] == {
        "availability": "available",
        "value": 50_000_000_000,
        "raw_value": 50_000_000_000,
        "source_path": "quarterly_income_stmt.2026-07-31.Total Revenue",
        "effective_at": "2026-07-31",
        "observed_at": "2026-07-31",
        "available_at": "2026-08-17T12:00:00Z",
        "fetched_at": "2026-08-17T12:00:00Z",
        "unit": "USD",
        "source_uri": "https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/NVDA",
        "raw_content_sha256": sha256(FUNDAMENTALS_RAW).hexdigest(),
    }
    assert envelope["data"]["facts"]["free_cash_flow"]["value"] == 24_000_000_000
    assert envelope["data"]["facts"]["free_cash_flow"]["source_path"] == "quarterly_cash_flow.2026-07-31.Free Cash Flow"
    assert envelope["data"]["facts"]["operating_cash_flow"]["value"] == 26_000_000_000
    assert envelope["data"]["facts"]["capital_expenditure"]["value"] == -2_000_000_000
    assert envelope["data"]["facts"]["gross_profit"]["value"] == 35_000_000_000
    assert envelope["data"]["facts"]["gross_profit"]["source_path"] == "quarterly_income_stmt.2026-07-31.Gross Profit"
    assert envelope["data"]["facts"]["gross_profit"]["unit"] == "USD"
    assert envelope["data"]["facts"]["cost_of_revenue"]["value"] == 15_000_000_000
    assert envelope["data"]["facts"]["operating_income"]["value"] == 25_000_000_000
    assert envelope["data"]["facts"]["net_income"]["value"] == 20_000_000_000
    assert envelope["data"]["facts"]["ebitda"]["value"] == 26_000_000_000
    assert envelope["data"]["facts"]["stock_based_compensation"]["value"] == 1_500_000_000
    assert envelope["data"]["facts"]["diluted_average_shares"] == {
        "availability": "available",
        "value": 24_500_000_000,
        "raw_value": 24_500_000_000,
        "source_path": "quarterly_income_stmt.2026-07-31.Diluted Average Shares",
        "effective_at": "2026-07-31",
        "observed_at": "2026-07-31",
        "available_at": "2026-08-17T12:00:00Z",
        "fetched_at": "2026-08-17T12:00:00Z",
        "unit": "shares",
        "source_uri": "https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/NVDA",
        "raw_content_sha256": sha256(FUNDAMENTALS_RAW).hexdigest(),
    }
    assert "gross_margin" not in envelope["data"]["facts"]
    assert envelope["data"]["facts"]["cash"]["value"] == 52_000_000_000
    assert envelope["data"]["facts"]["total_assets"]["value"] == 140_000_000_000
    assert envelope["data"]["facts"]["inventory"]["value"] == 11_000_000_000
    assert envelope["data"]["facts"]["total_revenue"]["available_at"] == envelope["fetched_at"]
    assert envelope["data"]["facts"]["total_revenue"]["fetched_at"] == envelope["fetched_at"]
    assert envelope["data"]["facts"]["total_revenue"]["raw_value"] == 50_000_000_000
    assert envelope["data"]["statement_selection"]["income_statement"]["winning_path"] == "quarterly_income_stmt"
    assert envelope["data"]["statement_dates"] == {"last_fiscal_year_end": "2025-01-31", "most_recent_quarter": "2026-07-31"}
    assert envelope["data"]["facts"]["forward_pe"]["availability"] == "available"
    assert envelope["data"]["client_view"]["info"]["marketCap"] is None
    assert envelope["data"]["client_view"]["info"]["unserializable"] is None


def test_yfinance_provider_hashes_injected_endpoint_bytes_and_keeps_statement_provenance_separate() -> None:
    envelope = YFinanceProvider(
        ticker_factory=lambda ticker: FakeTicker(),
        raw_transport=raw_yfinance_payloads,
        clock=lambda: FROZEN_NOW,
        provider_version="test-yf",
    ).fetch("NVDA").to_dict()

    assert envelope["source"] == {
        "uri": "https://query1.finance.yahoo.com/v10/finance/quoteSummary/NVDA",
        "content_sha256": sha256(QUOTE_RAW).hexdigest(),
        "parameters": {"raw_sources": envelope["data"]["raw_sources"]},
    }
    assert envelope["data"]["facts"]["total_revenue"]["source_uri"] == "https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/NVDA"
    assert envelope["data"]["facts"]["total_revenue"]["raw_content_sha256"] == sha256(FUNDAMENTALS_RAW).hexdigest()
    assert envelope["parse"] == {
        "status": "parsed",
        "transform_version": "yfinance-adapter/2",
        "message": "facts selected from yfinance client views",
    }


def test_yfinance_default_recording_transport_uses_the_ticker_session_and_caches_each_cited_payload(tmp_path) -> None:
    raw_cache: dict[str, bytes] = {}
    provider_envelope = YFinanceProvider(
        ticker_factory=lambda ticker: SessionBackedTicker(),
        raw_cache=raw_cache,
        clock=lambda: FROZEN_NOW,
        provider_version="test-yf",
    ).fetch("NVDA")
    envelope = provider_envelope.to_dict()

    market_cap = envelope["data"]["facts"]["market_cap"]
    revenue = envelope["data"]["facts"]["total_revenue"]
    assert market_cap["availability"] == "available"
    assert market_cap["raw_content_sha256"] == sha256(RECORDED_QUOTE_RAW).hexdigest()
    assert "crumb" not in market_cap["source_uri"]
    assert revenue["availability"] == "available"
    assert revenue["source_uri"] == RECORDED_INCOME_QUARTER_URI
    assert revenue["raw_content_sha256"] == sha256(RECORDED_INCOME_QUARTER_RAW).hexdigest()
    assert revenue["raw_source_path"] == "timeseries.result.quarterlyTotalRevenue[asOfDate=2026-07-31].reportedValue.raw"
    assert raw_cache[market_cap["raw_content_sha256"]] == RECORDED_QUOTE_RAW
    assert raw_cache[revenue["raw_content_sha256"]] == RECORDED_INCOME_QUARTER_RAW
    results = cache_provider_raw_payloads([provider_envelope], root=tmp_path)
    cached_hashes = {result.content_sha256 for result in results}
    assert {market_cap["raw_content_sha256"], revenue["raw_content_sha256"]} <= cached_hashes


def test_yfinance_default_recording_transport_materializes_lazy_fast_info_before_selecting_facts() -> None:
    envelope = YFinanceProvider(
        ticker_factory=lambda ticker: LazyFastTicker(),
        raw_cache={},
        clock=lambda: FROZEN_NOW,
        provider_version="test-yf",
    ).fetch("NVDA").to_dict()

    price = envelope["data"]["facts"]["price"]
    assert price["availability"] == "available"
    assert price["value"] == 174.55
    assert price["source_uri"] == RECORDED_CHART_URI
    assert price["raw_content_sha256"] == sha256(RECORDED_CHART_RAW).hexdigest()


def test_yfinance_provider_nulls_a_fact_when_its_declared_raw_source_cannot_verify_the_value() -> None:
    def mismatched_payloads(ticker: str) -> dict[str, dict[str, str | bytes]]:
        payloads = raw_yfinance_payloads(ticker)
        return {
            **payloads,
            "fundamentals": {
                "uri": payloads["fundamentals"]["uri"],
                "content": b'{"timeseries":{"result":[]}}',
            },
        }

    envelope = YFinanceProvider(
        ticker_factory=lambda ticker: FakeTicker(),
        raw_transport=mismatched_payloads,
        clock=lambda: FROZEN_NOW,
        provider_version="test-yf",
    ).fetch("NVDA").to_dict()

    revenue = envelope["data"]["facts"]["total_revenue"]
    assert revenue["availability"] == "unavailable"
    assert revenue["value"] is None
    assert revenue["raw_value"] is None


def test_yfinance_provider_refuses_to_call_transformed_client_views_raw_payloads() -> None:
    envelope = YFinanceProvider(
        ticker_factory=lambda ticker: FakeTicker(),
        clock=lambda: FROZEN_NOW,
        provider_version="test-yf",
    ).fetch("NVDA").to_dict()

    assert envelope["status"] == "unavailable"
    assert envelope["error"] == {"reason": "yfinance raw recording unavailable: ticker does not expose a recordable yfinance session"}


def test_yfinance_provider_returns_typed_unavailable_when_the_client_fails() -> None:
    def broken_ticker_factory(ticker: str) -> object:
        raise RuntimeError("Yahoo is unavailable")

    envelope = YFinanceProvider(
        ticker_factory=broken_ticker_factory,
        clock=lambda: FROZEN_NOW,
        provider_version="test-yf",
    ).fetch("NVDA").to_dict()

    assert envelope["status"] == "unavailable"
    assert envelope["error"] == {"reason": "Yahoo is unavailable"}
    assert envelope["request_id"].startswith("req-")


def test_yfinance_provider_records_the_exact_installed_version_unless_overridden(monkeypatch) -> None:
    monkeypatch.setattr(yfinance_provider.importlib.metadata, "version", lambda distribution: "0.2.66")

    envelope = YFinanceProvider(
        ticker_factory=lambda ticker: FakeTicker(),
        raw_transport=raw_yfinance_payloads,
        clock=lambda: FROZEN_NOW,
    ).fetch("NVDA").to_dict()

    assert envelope["provider_version"] == "0.2.66"


def test_yfinance_provider_marks_a_missing_dependency_version_as_typed_unavailable(monkeypatch) -> None:
    def missing_version(distribution: str) -> str:
        raise yfinance_provider.importlib.metadata.PackageNotFoundError(distribution)

    monkeypatch.setattr(yfinance_provider.importlib.metadata, "version", missing_version)

    envelope = YFinanceProvider(
        ticker_factory=lambda ticker: FakeTicker(),
        raw_transport=raw_yfinance_payloads,
        clock=lambda: FROZEN_NOW,
    ).fetch("NVDA").to_dict()

    assert envelope["provider_version"] == "unavailable:yfinance"


def test_rs_provider_preserves_the_owned_library_record_without_interpretation() -> None:
    envelope = RsRatingProvider(
        client=FakeRsClient(),
        raw_transport=raw_rs_response,
        clock=lambda: FROZEN_NOW,
        provider_version="0.3.0",
    ).fetch("nvda").to_dict()

    assert envelope["provider"] == "ibd-rs-rating"
    assert envelope["status"] == "available"
    assert envelope["data"]["ticker"] == "NVDA"
    assert envelope["data"]["record_date"] == "2026-08-14"
    assert envelope["data"]["rs_raw"] == 1.2345
    assert envelope["data"]["rs_rating"] == 93
    assert envelope["data"]["fields"]["rs_rating"] == {
        "availability": "available",
        "value": 93,
        "raw_value": 93,
        "source_path": "rs.get.rs_rating",
        "effective_at": "2026-08-14",
        "observed_at": "2026-08-14",
        "available_at": "2026-08-17T12:00:00Z",
        "fetched_at": "2026-08-17T12:00:00Z",
        "source_uri": "https://qgoytloruyjtyasypesv.supabase.co/rest/v1/rs",
        "raw_content_sha256": sha256(RS_RAW).hexdigest(),
    }
    assert envelope["data"]["client_view"]["provider_note"] is None
    assert "leadership" not in envelope["data"]
    assert "threshold" not in envelope["data"]


def test_rs_provider_hashes_exact_injected_raw_response_bytes() -> None:
    envelope = RsRatingProvider(
        client=FakeRsClient(),
        raw_transport=raw_rs_response,
        clock=lambda: FROZEN_NOW,
        provider_version="0.3.0",
    ).fetch("NVDA").to_dict()

    assert envelope["source"]["content_sha256"] == sha256(RS_RAW).hexdigest()


def test_rs_provider_refuses_to_hash_a_transformed_client_record_as_raw_payload() -> None:
    envelope = RsRatingProvider(
        client=FakeRsClient(),
        clock=lambda: FROZEN_NOW,
        provider_version="0.3.0",
    ).fetch("NVDA").to_dict()

    assert envelope["status"] == "unavailable"
    assert envelope["error"] == {"reason": "RS client does not expose exact raw response bytes; inject raw_transport"}


def test_rs_provider_keeps_a_missing_record_as_typed_not_disclosed_data() -> None:
    class EmptyRsClient:
        def get(self, ticker: str, date: str | None = None) -> None:
            return None

    envelope = RsRatingProvider(
        client=EmptyRsClient(),
        clock=lambda: FROZEN_NOW,
        provider_version="0.3.0",
    ).fetch("NOPE").to_dict()

    assert envelope["status"] == "not_disclosed"
    assert envelope["error"] == {"reason": "no RS record returned"}


def test_providers_mark_nonfinite_supplied_values_invalid_instead_of_fabricating_a_number() -> None:
    class InvalidRsClient:
        def get(self, ticker: str, date: str | None = None) -> dict:
            return {"ticker": "NVDA", "date": "2026-08-14", "rs_raw": math.inf, "rs_rating": 93}

    envelope = RsRatingProvider(
        client=InvalidRsClient(),
        clock=lambda: FROZEN_NOW,
        provider_version="0.3.0",
    ).fetch("NVDA").to_dict()

    assert envelope["status"] == "invalid"
    assert envelope["error"] == {"reason": "RS record rs_raw is not a finite number"}


def test_yfinance_provider_does_not_substitute_info_financials_when_statements_are_missing() -> None:
    class QuoteOnlyTicker(FakeTicker):
        income_stmt = None
        quarterly_income_stmt = None
        balance_sheet = None
        quarterly_balance_sheet = None
        cash_flow = None
        quarterly_cash_flow = None

    envelope = YFinanceProvider(
        ticker_factory=lambda ticker: QuoteOnlyTicker(),
        raw_transport=raw_yfinance_payloads,
        clock=lambda: FROZEN_NOW,
        provider_version="test-yf",
    ).fetch("NVDA").to_dict()

    assert envelope["status"] == "available"
    assert envelope["data"]["facts"]["total_revenue"]["availability"] == "not_disclosed"
    assert envelope["data"]["facts"]["free_cash_flow"]["availability"] == "not_disclosed"
    assert envelope["data"]["facts"]["gross_profit"]["availability"] == "not_disclosed"
    assert envelope["data"]["facts"]["total_revenue"]["source_path"] == "quarterly_income_stmt.Total Revenue"


def test_yfinance_provider_marks_an_annual_statement_fallback_as_the_winning_path() -> None:
    class AnnualOnlyTicker(FakeTicker):
        quarterly_income_stmt = pd.DataFrame()
        quarterly_balance_sheet = pd.DataFrame()
        quarterly_cash_flow = pd.DataFrame()

    envelope = YFinanceProvider(
        ticker_factory=lambda ticker: AnnualOnlyTicker(),
        raw_transport=raw_yfinance_payloads,
        clock=lambda: FROZEN_NOW,
        provider_version="test-yf",
    ).fetch("NVDA").to_dict()

    assert envelope["data"]["facts"]["total_revenue"]["source_path"] == "income_stmt.2025-01-31.Total Revenue"
    assert envelope["data"]["facts"]["ebitda"]["source_path"] == "income_stmt.2025-01-31.EBITDA"
    assert envelope["data"]["statement_selection"]["income_statement"]["winning_path"] == "income_stmt"


def test_rs_provider_rejects_a_ticker_conflict_without_interpreting_a_rating() -> None:
    class ConflictingRsClient:
        def get(self, ticker: str, date: str | None = None) -> dict:
            return {"ticker": "AMD", "date": "2026-08-14", "rs_raw": 1.2, "rs_rating": 99}

    envelope = RsRatingProvider(
        client=ConflictingRsClient(),
        clock=lambda: FROZEN_NOW,
        provider_version="0.3.0",
    ).fetch("NVDA").to_dict()

    assert envelope["status"] == "conflict"
    assert envelope["error"] == {"reason": "RS record ticker does not match requested ticker"}


def test_rs_provider_marks_a_malformed_raw_record_invalid_without_a_threshold() -> None:
    class MalformedRsClient:
        def get(self, ticker: str, date: str | None = None) -> list[str]:
            return ["not", "a", "record"]

    envelope = RsRatingProvider(
        client=MalformedRsClient(),
        clock=lambda: FROZEN_NOW,
        provider_version="0.3.0",
    ).fetch("NVDA").to_dict()

    assert envelope["status"] == "invalid"
    assert envelope["error"] == {"reason": "RS record is not an object"}
