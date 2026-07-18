"""market_data.py testleri.

Gercek internet baglantisi kullanilmaz: _download_history her testte
monkeypatch ile sahte bir fonksiyonla degistirilir.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from piyasa_komutani import market_data
from piyasa_komutani.market_data import (
    SymbolSyncResult,
    _last_expected_trading_day,
    sync_portfolio_symbols,
    sync_symbol,
)

MONDAY = date(2024, 1, 8)
WEDNESDAY = date(2024, 1, 3)
THURSDAY = date(2024, 1, 4)
SATURDAY = date(2024, 1, 6)
SUNDAY = date(2024, 1, 7)


def _bars(*iso_dates: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(list(iso_dates)),
            "Open": [10.0] * len(iso_dates),
            "High": [11.0] * len(iso_dates),
            "Low": [9.0] * len(iso_dates),
            "Close": [10.5] * len(iso_dates),
            "Volume": [1000] * len(iso_dates),
        }
    )


def _write_cache_csv(cache_dir, symbol: str, *iso_dates: str) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    _bars(*iso_dates).to_csv(cache_dir / f"{symbol}.csv", index=False)


def test_last_expected_trading_day_handles_weekend_and_monday() -> None:
    assert _last_expected_trading_day(MONDAY) == date(2024, 1, 5)  # onceki Cuma
    assert _last_expected_trading_day(WEDNESDAY) == date(2024, 1, 2)  # dun
    assert _last_expected_trading_day(SATURDAY) == date(2024, 1, 5)  # Cuma
    assert _last_expected_trading_day(SUNDAY) == date(2024, 1, 5)  # Cuma


def test_full_fetch_when_no_cache_exists(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake(symbol: str, start: date, end: date) -> pd.DataFrame:
        calls.append((symbol, start, end))
        return _bars("2024-01-08", "2024-01-09")

    monkeypatch.setattr(market_data, "_download_history", fake)

    result = sync_symbol("AAA", tmp_path, today=MONDAY)

    assert result == SymbolSyncResult("AAA", "updated", "2 yeni gun")
    assert len(calls) == 1
    _, start, end = calls[0]
    assert start == MONDAY - timedelta(days=market_data.LOOKBACK_DAYS)
    assert end == MONDAY + timedelta(days=1)

    cached = pd.read_csv(tmp_path / "AAA.csv", parse_dates=["Date"])
    assert list(cached["Date"].dt.date) == [date(2024, 1, 8), date(2024, 1, 9)]


def test_skips_download_when_cache_is_fresh(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_cache_csv(tmp_path, "AAA", "2024-01-05")  # Monday'in beklenen son is gunu

    def fail_if_called(*_args: object, **_kwargs: object) -> pd.DataFrame:
        raise AssertionError("guncel cache icin indirme yapilmamali")

    monkeypatch.setattr(market_data, "_download_history", fail_if_called)

    result = sync_symbol("AAA", tmp_path, today=MONDAY)

    assert result.status == "fresh"


def test_incremental_update_fetches_only_missing_days(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_cache_csv(tmp_path, "AAA", "2024-01-01")  # eski (Pazartesi), guncel degil
    calls = []

    def fake(symbol: str, start: date, end: date) -> pd.DataFrame:
        calls.append((symbol, start, end))
        return _bars("2024-01-02")

    monkeypatch.setattr(market_data, "_download_history", fake)

    result = sync_symbol("AAA", tmp_path, today=WEDNESDAY)  # beklenen son is gunu = Sali (01-02)

    assert result.status == "updated"
    _, start, _end = calls[0]
    assert start == date(2024, 1, 2)  # son cache + 1 gun

    cached = pd.read_csv(tmp_path / "AAA.csv", parse_dates=["Date"])
    assert list(cached["Date"].dt.date) == [date(2024, 1, 1), date(2024, 1, 2)]


def test_merge_deduplicates_overlapping_dates(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_cache_csv(tmp_path, "AAA", "2024-01-01", "2024-01-02")  # guncel degil (bkz. asagida)

    def fake(symbol: str, start: date, end: date) -> pd.DataFrame:
        # Ayni tarihi (2024-01-02) tekrar donduruyor, ustune bir de yeni gun ekliyor.
        return _bars("2024-01-02", "2024-01-03")

    monkeypatch.setattr(market_data, "_download_history", fake)

    sync_symbol("AAA", tmp_path, today=THURSDAY)  # beklenen son is gunu = Carsamba (01-03)

    cached = pd.read_csv(tmp_path / "AAA.csv", parse_dates=["Date"])
    assert list(cached["Date"].dt.date) == [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)]


def test_download_failure_is_reported_not_raised(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(symbol: str, start: date, end: date) -> pd.DataFrame:
        raise ConnectionError("ag hatasi")

    monkeypatch.setattr(market_data, "_download_history", fake)

    result = sync_symbol("AAA", tmp_path, today=MONDAY)

    assert result.status == "failed"
    assert result.message is not None
    assert "ag hatasi" in result.message
    assert not (tmp_path / "AAA.csv").exists()


def test_empty_result_without_cache_is_failure(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(symbol: str, start: date, end: date) -> pd.DataFrame:
        return pd.DataFrame(columns=["Date", *market_data.OHLCV_COLUMNS])

    monkeypatch.setattr(market_data, "_download_history", fake)

    result = sync_symbol("BILINMEYEN", tmp_path, today=MONDAY)

    assert result.status == "failed"


def test_empty_incremental_result_is_not_a_failure(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_cache_csv(tmp_path, "AAA", "2024-01-02")

    def fake(symbol: str, start: date, end: date) -> pd.DataFrame:
        return pd.DataFrame(columns=["Date", *market_data.OHLCV_COLUMNS])

    monkeypatch.setattr(market_data, "_download_history", fake)

    result = sync_symbol("AAA", tmp_path, today=WEDNESDAY)

    assert result.status == "fresh"


def test_sync_portfolio_symbols_continues_after_one_symbol_fails(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(symbol: str, start: date, end: date) -> pd.DataFrame:
        if symbol == "BAD":
            raise ConnectionError("ag hatasi")
        return _bars("2024-01-08")

    monkeypatch.setattr(market_data, "_download_history", fake)

    results = sync_portfolio_symbols(["BAD", "GOOD"], cache_dir=tmp_path)

    assert [r.symbol for r in results] == ["BAD", "GOOD"]
    assert results[0].status == "failed"
    assert results[1].status == "updated"
    assert not (tmp_path / "BAD.csv").exists()
    assert (tmp_path / "GOOD.csv").exists()


def test_sync_portfolio_symbols_deduplicates_preserving_order(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def fake(symbol: str, start: date, end: date) -> pd.DataFrame:
        calls.append(symbol)
        return _bars("2024-01-08")

    monkeypatch.setattr(market_data, "_download_history", fake)

    results = sync_portfolio_symbols(["AAA", "BBB", "AAA"], cache_dir=tmp_path)

    assert [r.symbol for r in results] == ["AAA", "BBB"]
    assert calls == ["AAA", "BBB"]
