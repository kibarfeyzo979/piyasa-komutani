"""opportunity_scanner.py testleri.

Gercek internet baglantisi kullanilmaz: load_cached_prices ve
sync_portfolio_symbols her testte monkeypatch ile degistirilir.
"""

from __future__ import annotations

import pandas as pd
import pytest

from piyasa_komutani import opportunity_scanner
from piyasa_komutani.data import UniverseRow
from piyasa_komutani.opportunity_scanner import (
    DEFAULT_MIN_AVERAGE_VOLUME,
    OpportunityCandidate,
    ScanOutcome,
    _scan_symbol,
    load_min_average_volume,
    scan_universe,
    write_opportunities_csv,
)
from piyasa_komutani.technical_analysis import OpportunityScore, TrendScore


def _make_price_data(rows: int = 250, *, volume: float = 200_000.0, trend: float = 0.1) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.date_range("2023-01-01", periods=rows, freq="D"),
            "Open": 100.0,
            "High": 101.0,
            "Low": 99.0,
            "Close": [100.0 + i * trend for i in range(rows)],
            "Volume": float(volume),
        }
    )


def _no_op_sync(symbols, cache_dir=None):
    return []


# --- _scan_symbol ---


def test_scan_symbol_no_cache_is_error(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(opportunity_scanner, "load_cached_prices", lambda symbol, cache_dir: None)

    outcome, candidate = _scan_symbol("AAA", tmp_path, DEFAULT_MIN_AVERAGE_VOLUME)

    assert outcome == ScanOutcome("AAA", "error", "Piyasa verisi yok.")
    assert candidate is None


def test_scan_symbol_insufficient_history_is_error(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    short_history = _make_price_data(rows=50)
    monkeypatch.setattr(opportunity_scanner, "load_cached_prices", lambda symbol, cache_dir: short_history)

    outcome, candidate = _scan_symbol("AAA", tmp_path, DEFAULT_MIN_AVERAGE_VOLUME)

    assert outcome.symbol == "AAA"
    assert outcome.status == "error"
    assert outcome.message is not None
    assert "50" in outcome.message
    assert candidate is None


def test_scan_symbol_below_volume_threshold_is_ok_without_candidate(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    low_volume = _make_price_data(volume=1_000.0)
    monkeypatch.setattr(opportunity_scanner, "load_cached_prices", lambda symbol, cache_dir: low_volume)

    outcome, candidate = _scan_symbol("AAA", tmp_path, min_average_volume=100_000.0)

    assert outcome == ScanOutcome("AAA", "ok")
    assert candidate is None


def test_scan_symbol_success_produces_candidate(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    prices = _make_price_data(volume=500_000.0)
    monkeypatch.setattr(opportunity_scanner, "load_cached_prices", lambda symbol, cache_dir: prices)

    outcome, candidate = _scan_symbol("AAA", tmp_path, min_average_volume=100_000.0)

    assert outcome == ScanOutcome("AAA", "ok")
    assert candidate is not None
    assert candidate.symbol == "AAA"
    assert candidate.average_volume_20 == pytest.approx(500_000.0)
    assert candidate.trend.score is not None
    assert candidate.opportunity.score is not None


def test_scan_symbol_unexpected_exception_is_caught(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_error(symbol, cache_dir):
        raise RuntimeError("beklenmeyen hata")

    monkeypatch.setattr(opportunity_scanner, "load_cached_prices", raise_error)

    outcome, candidate = _scan_symbol("AAA", tmp_path, DEFAULT_MIN_AVERAGE_VOLUME)

    assert outcome.status == "error"
    assert "beklenmeyen hata" in outcome.message
    assert candidate is None


# --- scan_universe ---


def test_scan_universe_skips_disabled_rows(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(opportunity_scanner, "sync_portfolio_symbols", _no_op_sync)
    monkeypatch.setattr(opportunity_scanner, "load_cached_prices", lambda symbol, cache_dir: _make_price_data())

    rows = [
        UniverseRow("AAA", "A Sirketi", "BIST", True),
        UniverseRow("BBB", "B Sirketi", "BIST", False),
    ]
    report = scan_universe(rows, cache_dir=tmp_path)

    assert [o.symbol for o in report.outcomes] == ["AAA"]


def test_scan_universe_continues_after_one_symbol_fails(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(opportunity_scanner, "sync_portfolio_symbols", _no_op_sync)

    def fake_load(symbol, cache_dir):
        if symbol == "BAD":
            return None
        return _make_price_data()

    monkeypatch.setattr(opportunity_scanner, "load_cached_prices", fake_load)

    rows = [
        UniverseRow("BAD", "Bad Sirketi", "BIST", True),
        UniverseRow("GOOD", "Good Sirketi", "BIST", True),
    ]
    report = scan_universe(rows, cache_dir=tmp_path)

    assert [o.symbol for o in report.outcomes] == ["BAD", "GOOD"]
    assert report.outcomes[0].status == "error"
    assert report.outcomes[1].status == "ok"
    assert [c.symbol for c in report.candidates] == ["GOOD"]


def test_scan_universe_sorts_by_opportunity_then_trend_descending(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(opportunity_scanner, "sync_portfolio_symbols", _no_op_sync)

    def fake_load(symbol, cache_dir):
        # AAA: duz fiyat (dusuk skor), BBB: guclu yukselen trend (yuksek skor)
        trend = 0.0 if symbol == "AAA" else 1.0
        return _make_price_data(trend=trend)

    monkeypatch.setattr(opportunity_scanner, "load_cached_prices", fake_load)

    rows = [
        UniverseRow("AAA", "A", "BIST", True),
        UniverseRow("BBB", "B", "BIST", True),
    ]
    report = scan_universe(rows, cache_dir=tmp_path)

    keys = [(c.opportunity.score, c.trend.score) for c in report.candidates]
    assert keys == sorted(keys, reverse=True)


def test_scan_report_summary_properties(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(opportunity_scanner, "sync_portfolio_symbols", _no_op_sync)

    def fake_load(symbol, cache_dir):
        if symbol == "BAD":
            return None
        return _make_price_data(trend=1.0)  # guclu trend -> HIGH_OPPORTUNITY/INTERESTING olasi

    monkeypatch.setattr(opportunity_scanner, "load_cached_prices", fake_load)

    rows = [
        UniverseRow("BAD", "Bad", "BIST", True),
        UniverseRow("GOOD1", "Good1", "BIST", True),
        UniverseRow("GOOD2", "Good2", "BIST", True),
    ]
    report = scan_universe(rows, cache_dir=tmp_path)

    assert report.scanned == 3
    assert report.successful == 2
    assert report.failed == 1
    assert report.high_opportunity_count + report.interesting_count <= len(report.candidates)


# --- load_min_average_volume ---


def test_load_min_average_volume_reads_config(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("[scanner]\nmin_average_volume = 250000\n", encoding="utf-8")

    assert load_min_average_volume(config_path) == pytest.approx(250_000.0)


def test_load_min_average_volume_falls_back_on_missing_file(tmp_path) -> None:
    missing_path = tmp_path / "does_not_exist.toml"

    assert load_min_average_volume(missing_path) == DEFAULT_MIN_AVERAGE_VOLUME


def test_load_min_average_volume_falls_back_on_missing_section(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("[other]\nvalue = 1\n", encoding="utf-8")

    assert load_min_average_volume(config_path) == DEFAULT_MIN_AVERAGE_VOLUME


def test_load_min_average_volume_falls_back_on_malformed_toml(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("bu gecerli bir TOML degil [[[", encoding="utf-8")

    assert load_min_average_volume(config_path) == DEFAULT_MIN_AVERAGE_VOLUME


# --- write_opportunities_csv ---


def test_write_opportunities_csv_roundtrip(tmp_path) -> None:
    path = tmp_path / "opportunities.csv"
    candidates = [
        OpportunityCandidate(
            symbol="AAA",
            close=110.0,
            ema20=105.0,
            ema50=100.0,
            ema200=90.0,
            rsi=60.0,
            macd_hist=1.5,
            average_volume_20=300_000.0,
            return_20d=8.0,
            distance_ema20_pct=1.2,
            trend=TrendScore(85, "VERY_STRONG_TREND", ("neden",)),
            opportunity=OpportunityScore(90, "HIGH_OPPORTUNITY", ("+ neden",)),
        )
    ]

    write_opportunities_csv(candidates, path)

    result = pd.read_csv(path)
    assert list(result.columns) == [
        "Rank",
        "Symbol",
        "Close",
        "EMA20",
        "EMA50",
        "EMA200",
        "RSI",
        "MACD Histogram",
        "Average Volume 20",
        "Trend Score",
        "Trend Status",
        "Opportunity Score",
        "Opportunity Status",
        "Return 20D",
        "Distance EMA20 %",
    ]
    assert result.loc[0, "Symbol"] == "AAA"
    assert result.loc[0, "Rank"] == 1
    assert result.loc[0, "Trend Status"] == "VERY_STRONG_TREND"
    assert result.loc[0, "Opportunity Status"] == "HIGH_OPPORTUNITY"


def test_write_opportunities_csv_creates_missing_parent_directory(tmp_path) -> None:
    path = tmp_path / "reports" / "nested" / "opportunities.csv"

    write_opportunities_csv([], path)

    assert path.exists()
