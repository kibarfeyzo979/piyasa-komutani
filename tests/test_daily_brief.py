"""daily_brief.py testleri.

Gercek internet baglantisi kullanilmaz: load_cached_prices ve
calculate_technical_indicators (gerektiginde scan_universe de) her
testte monkeypatch ile degistirilir.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from piyasa_komutani import daily_brief
from piyasa_komutani.data import PortfolioRow, UniverseRow
from piyasa_komutani.daily_brief import (
    DEFAULT_DAILY_CSV_PATH,
    TREND_DETERIORATION_LOOKBACK_DAYS,
    TREND_DETERIORATION_THRESHOLD,
    DailyBrief,
    _detect_trend_deterioration,
    build_daily_brief,
    load_trend_deterioration_settings,
    write_daily_brief_csv,
    write_daily_brief_json,
    write_daily_brief_markdown,
)
from piyasa_komutani.opportunity_scanner import OpportunityCandidate
from piyasa_komutani.portfolio_analysis import PortfolioSummary, PositionAnalysis, PositionHealth
from piyasa_komutani.technical_analysis import MIN_ROWS_FOR_SCORE, OpportunityScore, TrendScore


def _make_indicators_df(
    rows: int = MIN_ROWS_FOR_SCORE,
    *,
    close: float = 100.0,
    ema20: float = 100.0,
    ema50: float = 100.0,
    ema200: float = 100.0,
    rsi: float = 50.0,
    macd: float = 0.0,
    macd_signal: float = 0.0,
    return_20d: float = 0.0,
    volume: float = 200_000.0,
) -> pd.DataFrame:
    data = pd.DataFrame(
        {
            "Date": pd.date_range("2020-01-01", periods=rows, freq="D"),
            "Close": 100.0,
            "EMA_20": 100.0,
            "EMA_50": 100.0,
            "EMA_200": 100.0,
            "RSI_14": 50.0,
            "MACD": 0.0,
            "MACD_Signal": 0.0,
            "MACD_Hist": 0.0,
            "Return_5D": 0.0,
            "Return_20D": 0.0,
            "Distance_EMA20_Pct": 0.0,
            "Distance_EMA50_Pct": 0.0,
            "EMA20_Slope": 0.0,
            "EMA50_Slope": 0.0,
            "RSI_Change_3D": 0.0,
            "MACD_Hist_Change_3D": 0.0,
        }
    )
    last = data.index[-1]
    data.loc[last, "Close"] = close
    data.loc[last, "EMA_20"] = ema20
    data.loc[last, "EMA_50"] = ema50
    data.loc[last, "EMA_200"] = ema200
    data.loc[last, "RSI_14"] = rsi
    data.loc[last, "MACD"] = macd
    data.loc[last, "MACD_Signal"] = macd_signal
    data.loc[last, "Return_20D"] = return_20d
    return data


def _dummy_prices(rows: int = MIN_ROWS_FOR_SCORE, *, volume: float = 200_000.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.date_range("2020-01-01", periods=rows, freq="D"),
            "Open": 100.0,
            "High": 101.0,
            "Low": 99.0,
            "Close": 100.0,
            "Volume": float(volume),
        }
    )


def _portfolio_row(symbol: str = "XYZ", quantity: float = 10.0, average_cost: float = 100.0) -> PortfolioRow:
    return PortfolioRow(symbol, "stock", quantity, average_cost, "TRY")


# --- _detect_trend_deterioration ---


def _make_deterioration_indicators(rows: int, lookback_days: int) -> pd.DataFrame:
    """220 satirlik bir DataFrame; (rows-lookback_days-1). satir cok bullish
    (N gun once), son satir cok bearish (bugun) - buyuk bir trend dususu uretir."""
    data = pd.DataFrame(
        {
            "Date": pd.date_range("2020-01-01", periods=rows, freq="D"),
            "Close": 100.0,
            "EMA_20": 100.0,
            "EMA_50": 100.0,
            "EMA_200": 100.0,
            "RSI_14": 50.0,
            "MACD": 0.0,
            "MACD_Signal": 0.0,
            "MACD_Hist": 0.0,
            "Return_5D": 0.0,
            "Return_20D": 0.0,
            "Distance_EMA20_Pct": 0.0,
            "Distance_EMA50_Pct": 0.0,
            "EMA20_Slope": 0.0,
            "EMA50_Slope": 0.0,
            "RSI_Change_3D": 0.0,
            "MACD_Hist_Change_3D": 0.0,
        }
    )
    past_idx = rows - lookback_days - 1
    now_idx = rows - 1

    # N gun once: tam bullish
    data.loc[past_idx, ["Close", "EMA_20", "EMA_50", "EMA_200"]] = [200.0, 190.0, 180.0, 170.0]
    data.loc[past_idx, ["RSI_14", "MACD", "MACD_Signal", "Return_20D"]] = [60.0, 1.0, 0.5, 10.0]

    # bugun: tam bearish
    data.loc[now_idx, ["Close", "EMA_20", "EMA_50", "EMA_200"]] = [50.0, 60.0, 70.0, 80.0]
    data.loc[now_idx, ["RSI_14", "MACD", "MACD_Signal", "Return_20D"]] = [20.0, -1.0, -0.5, -10.0]

    return data


def test_detect_trend_deterioration_flags_large_drop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rows = MIN_ROWS_FOR_SCORE + TREND_DETERIORATION_LOOKBACK_DAYS + 20
    indicators = _make_deterioration_indicators(rows, TREND_DETERIORATION_LOOKBACK_DAYS)
    monkeypatch.setattr(daily_brief, "load_cached_prices", lambda symbol, cache_dir: _dummy_prices(rows))
    monkeypatch.setattr(daily_brief, "calculate_technical_indicators", lambda prices: indicators)

    result = _detect_trend_deterioration(
        "XYZ", tmp_path, TREND_DETERIORATION_LOOKBACK_DAYS, TREND_DETERIORATION_THRESHOLD
    )

    assert result is True


def test_detect_trend_deterioration_false_when_stable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rows = MIN_ROWS_FOR_SCORE + TREND_DETERIORATION_LOOKBACK_DAYS + 20
    indicators = _make_indicators_df(rows=rows, close=100.0, ema20=100.0, ema50=100.0, ema200=100.0)
    monkeypatch.setattr(daily_brief, "load_cached_prices", lambda symbol, cache_dir: _dummy_prices(rows))
    monkeypatch.setattr(daily_brief, "calculate_technical_indicators", lambda prices: indicators)

    result = _detect_trend_deterioration(
        "XYZ", tmp_path, TREND_DETERIORATION_LOOKBACK_DAYS, TREND_DETERIORATION_THRESHOLD
    )

    assert result is False


def test_detect_trend_deterioration_false_when_insufficient_history(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    short_prices = _dummy_prices(rows=50)
    monkeypatch.setattr(daily_brief, "load_cached_prices", lambda symbol, cache_dir: short_prices)

    result = _detect_trend_deterioration(
        "XYZ", tmp_path, TREND_DETERIORATION_LOOKBACK_DAYS, TREND_DETERIORATION_THRESHOLD
    )

    assert result is False


def test_detect_trend_deterioration_false_when_no_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(daily_brief, "load_cached_prices", lambda symbol, cache_dir: None)

    result = _detect_trend_deterioration(
        "XYZ", tmp_path, TREND_DETERIORATION_LOOKBACK_DAYS, TREND_DETERIORATION_THRESHOLD
    )

    assert result is False


# --- build_daily_brief senaryolari (madde 8) ---


def test_all_modules_successful(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from piyasa_komutani import portfolio_analysis

    indicators = _make_indicators_df(close=150.0, ema20=140.0, ema50=130.0, ema200=110.0, rsi=60.0, macd=1.0, macd_signal=0.5)
    monkeypatch.setattr(portfolio_analysis, "load_cached_prices", lambda symbol, cache_dir: _dummy_prices())
    monkeypatch.setattr(portfolio_analysis, "calculate_technical_indicators", lambda prices: indicators)
    monkeypatch.setattr(daily_brief, "load_cached_prices", lambda symbol, cache_dir: _dummy_prices())
    monkeypatch.setattr(daily_brief, "calculate_technical_indicators", lambda prices: indicators)

    # universe_rows bos: scan_universe() gercekten calisir (network yok, cunku
    # sync_portfolio_symbols/_scan_symbol bos sembol listesinde hic yfinance
    # cagirmiyor) - scanner_status="OK" dogrulamasi icin yeterli.
    brief = build_daily_brief([_portfolio_row("XYZ")], [], cache_dir=tmp_path)

    assert brief.portfolio_status == "OK"
    assert brief.scanner_status == "OK"
    assert brief.report is not None
    assert brief.scan_report is not None
    assert brief.report.positions[0].health.status == "STRONG"


def test_scanner_partially_failing_symbols_still_reports_ok(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from piyasa_komutani import opportunity_scanner

    good_indicators = _make_indicators_df(close=150.0, ema20=140.0, ema50=130.0, ema200=110.0, rsi=60.0, macd=1.0, macd_signal=0.5)

    def fake_load(symbol: str, cache_dir: Path) -> pd.DataFrame | None:
        if symbol == "BAD":
            return None
        return _dummy_prices()

    def fake_sync(symbols, cache_dir=None):
        return []

    # scan_universe() opportunity_scanner.py icinde calisir - o modulun KENDI
    # namespace'indeki isimler mock'lanmali (daily_brief'inkiler degil),
    # yoksa gercek ag cagrisi (sync_portfolio_symbols) tetiklenir.
    monkeypatch.setattr(opportunity_scanner, "load_cached_prices", fake_load)
    monkeypatch.setattr(opportunity_scanner, "calculate_technical_indicators", lambda prices: good_indicators)
    monkeypatch.setattr(opportunity_scanner, "sync_portfolio_symbols", fake_sync)

    universe_rows = [
        UniverseRow("BAD", "Bad Sirketi", "BIST", True),
        UniverseRow("GOOD", "Good Sirketi", "BIST", True),
    ]
    brief = build_daily_brief([], universe_rows, cache_dir=tmp_path)

    assert brief.scanner_status == "OK"  # scan_universe kendisi cokmedi
    assert brief.scan_report is not None
    assert brief.scan_report.failed == 1
    assert brief.scan_report.successful == 1


def test_scanner_completely_unreachable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def raise_error(rows, *, cache_dir, min_average_volume):
        raise RuntimeError("universe taranamadi")

    monkeypatch.setattr(daily_brief, "scan_universe", raise_error)

    good_indicators = _make_indicators_df(close=150.0, ema20=140.0, ema50=130.0, ema200=110.0, rsi=60.0, macd=1.0, macd_signal=0.5)
    monkeypatch.setattr(daily_brief, "load_cached_prices", lambda symbol, cache_dir: _dummy_prices())
    monkeypatch.setattr(daily_brief, "calculate_technical_indicators", lambda prices: good_indicators)

    brief = build_daily_brief([_portfolio_row()], [UniverseRow("ABC", "A", "BIST", True)], cache_dir=tmp_path)

    assert brief.scanner_status == "FAILED"
    assert brief.scanner_error is not None
    assert brief.scan_report is None
    # portfoy bolumu yine de uretildi
    assert brief.portfolio_status == "OK"
    assert brief.report is not None


def test_missing_market_data_position_goes_to_review(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(daily_brief, "load_cached_prices", lambda symbol, cache_dir: None)

    brief = build_daily_brief([_portfolio_row("XYZ")], [], cache_dir=tmp_path)

    assert brief.portfolio_status == "OK"
    assert len(brief.positions_to_review) == 1
    assert brief.positions_to_review[0].symbol == "XYZ"
    assert brief.positions_to_review[0].trend.score is None


def test_empty_portfolio(tmp_path: Path) -> None:
    brief = build_daily_brief([], [], cache_dir=tmp_path)

    assert brief.portfolio_status == "EMPTY"
    assert brief.report is None
    assert brief.summary.portfolio_condition == "EMPTY"
    assert brief.summary.positions_requiring_review == 0


def test_weak_positions_present(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from piyasa_komutani import portfolio_analysis

    weak_indicators = _make_indicators_df(
        close=50.0, ema20=55.0, ema50=60.0, ema200=70.0, rsi=30.0, macd=-1.0, macd_signal=-0.5, return_20d=-10.0
    )
    # build_portfolio_analysis_report, portfolio_analysis.py'nin KENDI
    # namespace'indeki load_cached_prices/calculate_technical_indicators'i
    # cagirir - daily_brief'inkileri degil.
    monkeypatch.setattr(portfolio_analysis, "load_cached_prices", lambda symbol, cache_dir: _dummy_prices())
    monkeypatch.setattr(portfolio_analysis, "calculate_technical_indicators", lambda prices: weak_indicators)
    monkeypatch.setattr(daily_brief, "load_cached_prices", lambda symbol, cache_dir: _dummy_prices())
    monkeypatch.setattr(daily_brief, "calculate_technical_indicators", lambda prices: weak_indicators)

    brief = build_daily_brief([_portfolio_row("XYZ")], [], cache_dir=tmp_path)

    assert brief.positions_to_review
    assert brief.summary.main_risk in {"WEAK POSITIONS", "HIGH CONCENTRATION"}


def test_no_high_opportunities(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(daily_brief, "load_cached_prices", lambda symbol, cache_dir: None)

    brief = build_daily_brief([_portfolio_row()], [], cache_dir=tmp_path)

    assert brief.top_opportunities == []
    assert brief.summary.high_opportunity_candidates == 0


def test_concentration_risk_high(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from piyasa_komutani import portfolio_analysis

    indicators = _make_indicators_df(close=150.0, ema20=140.0, ema50=130.0, ema200=110.0, rsi=60.0, macd=1.0, macd_signal=0.5)
    monkeypatch.setattr(portfolio_analysis, "load_cached_prices", lambda symbol, cache_dir: _dummy_prices())
    monkeypatch.setattr(portfolio_analysis, "calculate_technical_indicators", lambda prices: indicators)
    monkeypatch.setattr(daily_brief, "load_cached_prices", lambda symbol, cache_dir: _dummy_prices())
    monkeypatch.setattr(daily_brief, "calculate_technical_indicators", lambda prices: indicators)

    # Tek pozisyon -> otomatik olarak %100 agirlik, esik (%25) asilir
    brief = build_daily_brief(
        [_portfolio_row("XYZ")], [], cache_dir=tmp_path, single_position_threshold_pct=25.0
    )

    assert any("HIGH concentration" in alert for alert in brief.risk_alerts)
    assert brief.summary.main_risk == "HIGH CONCENTRATION"


# --- load_trend_deterioration_settings ---


def test_load_trend_deterioration_settings_reads_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "[daily_brief]\ntrend_deterioration_lookback_days = 5\ntrend_deterioration_threshold = 15\n",
        encoding="utf-8",
    )

    lookback, threshold = load_trend_deterioration_settings(config_path)

    assert lookback == 5
    assert threshold == 15


def test_load_trend_deterioration_settings_falls_back_on_missing_file(tmp_path: Path) -> None:
    lookback, threshold = load_trend_deterioration_settings(tmp_path / "does_not_exist.toml")

    assert lookback == TREND_DETERIORATION_LOOKBACK_DAYS
    assert threshold == TREND_DETERIORATION_THRESHOLD


# --- rapor yazicilari ---


def _sample_brief() -> DailyBrief:
    from piyasa_komutani.portfolio_analysis import PortfolioAnalysisReport

    position = PositionAnalysis(
        symbol="XYZ", quantity=10.0, average_cost=100.0, currency="TRY",
        current_price=50.0, market_value=500.0, cost_value=1000.0,
        unrealized_pl=-500.0, unrealized_pl_pct=-50.0, weight_pct=100.0,
        trend=TrendScore(20, "WEAK_TREND", ()),
        opportunity=OpportunityScore(20, "LOW", ()),
        health=PositionHealth(25, "WEAK", ("- Price below EMA20.",)),
        action_hint="REVIEW",
    )
    summary = PortfolioSummary(totals_by_currency=(), strong_count=0, healthy_count=0, caution_count=0, weak_count=1)
    report = PortfolioAnalysisReport(
        positions=[position], summary=summary, weak_positions=[position], high_opportunity_alternatives=[]
    )
    candidate = OpportunityCandidate(
        symbol="ABC", close=1.0, ema20=1.0, ema50=1.0, ema200=1.0, rsi=55.0, macd_hist=1.0,
        average_volume_20=1.0, return_20d=5.0, distance_ema20_pct=1.0,
        trend=TrendScore(72, "STRONG_TREND", ()), opportunity=OpportunityScore(88, "HIGH_OPPORTUNITY", ()),
    )
    from piyasa_komutani.opportunity_scanner import ScanOutcome, ScanReport

    scan_report = ScanReport(outcomes=[ScanOutcome("ABC", "ok")], candidates=[candidate])

    from datetime import datetime

    from piyasa_komutani.daily_brief import DailySummaryText

    return DailyBrief(
        generated_at=datetime(2026, 1, 1, 9, 0, 0),
        portfolio_status="OK",
        portfolio_error=None,
        report=report,
        scanner_status="OK",
        scanner_error=None,
        scan_report=scan_report,
        risk_alerts=("Health Score cok dusuk pozisyon(lar): XYZ.",),
        deteriorating_positions=(),
        positions_to_review=[position],
        strong_positions=[],
        top_opportunities=[candidate],
        summary=DailySummaryText(
            portfolio_condition="AT_RISK",
            main_risk="WEAK POSITIONS",
            positions_requiring_review=1,
            high_opportunity_candidates=1,
        ),
    )


def test_write_daily_brief_json_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "daily_brief.json"

    write_daily_brief_json(_sample_brief(), path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["portfolio_status"] == "OK"
    assert payload["positions_to_review"] == ["XYZ"]
    assert payload["summary"]["portfolio_condition"] == "AT_RISK"


def test_write_daily_brief_csv_has_all_sections(tmp_path: Path) -> None:
    path = tmp_path / "daily_brief.csv"

    write_daily_brief_csv(_sample_brief(), path)

    result = pd.read_csv(path)
    sections = set(result["Section"])
    assert sections == {"POSITION", "OPPORTUNITY", "ALERT", "SUMMARY"}
    assert list(result.columns)[0] == "Section"


def test_write_daily_brief_markdown_has_all_headers(tmp_path: Path) -> None:
    path = tmp_path / "daily_brief.md"

    write_daily_brief_markdown(_sample_brief(), path)

    content = path.read_text(encoding="utf-8")
    for heading in [
        "## A. Portfolio Summary",
        "## B. Risk Alerts",
        "## C. Positions to Review",
        "## D. Strong Portfolio Positions",
        "## E. Top Market Opportunities",
        "## F. Alternative Candidates",
        "## G. Daily Summary",
    ]:
        assert heading in content
    assert "XYZ" in content
    assert "ABC" in content


def test_write_daily_brief_csv_creates_missing_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "daily_brief.csv"

    write_daily_brief_csv(_sample_brief(), path)

    assert path.exists()


def test_default_daily_csv_path_is_under_reports() -> None:
    assert DEFAULT_DAILY_CSV_PATH.parts[-2:] == ("reports", "daily_brief.csv")
