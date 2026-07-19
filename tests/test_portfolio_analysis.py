"""portfolio_analysis.py testleri.

Gercek internet baglantisi kullanilmaz: load_cached_prices ve
calculate_technical_indicators her testte monkeypatch ile
degistirilir (fake/mock market data).
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

from piyasa_komutani import portfolio_analysis
from piyasa_komutani.data import PortfolioRow
from piyasa_komutani.opportunity_scanner import OpportunityCandidate
from piyasa_komutani.portfolio_analysis import (
    DEFAULT_SINGLE_POSITION_THRESHOLD_PCT,
    PortfolioAnalysisReport,
    PositionAnalysis,
    PositionHealth,
    _analyze_single_position,
    _score_health,
    analyze_portfolio,
    build_portfolio_analysis_report,
    find_high_opportunity_alternatives,
    find_weak_positions,
    load_concentration_thresholds,
    summarize_portfolio,
    write_portfolio_analysis_csv,
    write_portfolio_summary_json,
)
from piyasa_komutani.technical_analysis import MIN_ROWS_FOR_SCORE, OpportunityScore, TrendScore

NAN = math.nan


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
    macd_hist: float = 0.0,
    return_5d: float = 0.0,
    return_20d: float = 0.0,
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
    data.loc[last, "MACD_Hist"] = macd_hist
    data.loc[last, "Return_5D"] = return_5d
    data.loc[last, "Return_20D"] = return_20d
    return data


def _dummy_prices(marker: float = 1.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.date_range("2020-01-01", periods=5, freq="D"),
            "Close": [marker] * 5,
            "Volume": [1000] * 5,
        }
    )


def _portfolio_row(symbol: str = "XYZ", quantity: float = 10.0, average_cost: float = 100.0, currency: str = "TRY") -> PortfolioRow:
    return PortfolioRow(symbol, "stock", quantity, average_cost, currency)


# --- _score_health kural testleri ---


def _health_kwargs(**overrides: float) -> dict[str, float]:
    base = {
        "trend_score": NAN,
        "close": NAN,
        "ema20": NAN,
        "ema50": NAN,
        "ema200": NAN,
        "macd_hist": NAN,
        "rsi": NAN,
        "return_5d": NAN,
        "return_20d": NAN,
    }
    base.update(overrides)
    return base


def test_health_base_score_is_50_when_all_nan() -> None:
    score, reasons = _score_health(**_health_kwargs())

    assert score == 50
    assert reasons == ()


def test_health_trend_score_60_or_above_adds_points() -> None:
    score, reasons = _score_health(**_health_kwargs(trend_score=60))

    assert score == 50 + 15
    assert any("trend strong" in r.lower() for r in reasons)


def test_health_price_above_both_emas_adds_points() -> None:
    score, _ = _score_health(**_health_kwargs(close=110, ema20=100, ema50=100))

    assert score == 50 + 10


def test_health_bullish_alignment_adds_points() -> None:
    score, _ = _score_health(**_health_kwargs(ema20=110, ema50=100, ema200=90))

    assert score == 50 + 15


def test_health_macd_positive_and_negative() -> None:
    positive, _ = _score_health(**_health_kwargs(macd_hist=1.0))
    negative, _ = _score_health(**_health_kwargs(macd_hist=-1.0))

    assert positive == 50 + 10
    assert negative == 50 - 10


def test_health_rsi_healthy_range_and_weak() -> None:
    healthy, _ = _score_health(**_health_kwargs(rsi=50))
    weak, _ = _score_health(**_health_kwargs(rsi=30))
    neutral, _ = _score_health(**_health_kwargs(rsi=42))  # 40-45 arasi notr bosluk

    assert healthy == 50 + 10
    assert weak == 50 - 10
    assert neutral == 50


def test_health_price_below_emas_each_penalized_separately() -> None:
    score, reasons = _score_health(**_health_kwargs(close=90, ema20=100, ema50=100))

    assert score == 50 - 10 - 10  # Close<EMA20 VE Close<EMA50 ayri ayri cezalandirilir
    assert len(reasons) == 2


def test_health_ema20_below_ema50_is_penalized() -> None:
    score, _ = _score_health(**_health_kwargs(ema20=90, ema50=100))

    assert score == 50 - 15


def test_health_sharp_5d_decline_is_penalized() -> None:
    score, _ = _score_health(**_health_kwargs(return_5d=-6.0))
    not_sharp, _ = _score_health(**_health_kwargs(return_5d=-4.0))

    assert score == 50 - 10
    assert not_sharp == 50


def test_health_negative_20d_trend_is_penalized() -> None:
    score, _ = _score_health(**_health_kwargs(return_20d=-1.0))

    assert score == 50 - 10


# --- Senaryo A-E (madde 13) ---


def test_scenario_a_profitable_but_trend_broken(monkeypatch: pytest.MonkeyPatch) -> None:
    """A: Karli ama trendi ciddi bozulan pozisyon - P&L pozitif olsa da health dusuk kalmali."""
    indicators = _make_indicators_df(
        close=150.0, ema20=160.0, ema50=170.0, ema200=140.0,
        rsi=35.0, macd=-1.0, macd_signal=-0.5, macd_hist=-0.5,
        return_5d=-6.0, return_20d=-8.0,
    )
    monkeypatch.setattr(portfolio_analysis, "load_cached_prices", lambda symbol, cache_dir: _dummy_prices())
    monkeypatch.setattr(portfolio_analysis, "calculate_technical_indicators", lambda prices: indicators)

    row = _portfolio_row(average_cost=100.0)  # giris 100, guncel fiyat 150 -> %50 kar
    position = _analyze_single_position(row, Path("."))

    assert position.unrealized_pl_pct == pytest.approx(50.0)
    assert position.health.status in {"WEAK", "CAUTION"}


def test_scenario_b_losing_but_trend_strengthening(monkeypatch: pytest.MonkeyPatch) -> None:
    """B: Zararda ama trendi guclenmeye baslayan pozisyon - health P&L'e ragmen iyilesmeli."""
    indicators = _make_indicators_df(
        close=92.0, ema20=90.0, ema50=88.0, ema200=95.0,
        rsi=55.0, macd=0.3, macd_signal=0.1, macd_hist=0.2,
        return_5d=2.0, return_20d=-1.0,
    )
    monkeypatch.setattr(portfolio_analysis, "load_cached_prices", lambda symbol, cache_dir: _dummy_prices())
    monkeypatch.setattr(portfolio_analysis, "calculate_technical_indicators", lambda prices: indicators)

    row = _portfolio_row(average_cost=120.0)  # giris 120, guncel fiyat 92 -> zarar
    position = _analyze_single_position(row, Path("."))

    assert position.unrealized_pl_pct < 0
    assert position.health.status in {"CAUTION", "HEALTHY"}
    assert position.health.status != "WEAK"


def test_scenario_c_single_position_over_threshold_triggers_risk_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C: Portfoyun buyuk cogunlugunu (>%25 esigi) olusturan tek, zayif trendli pozisyon
    hem concentration uyarisi hem RISK_ALERT tetiklemeli."""
    weak_indicators = _make_indicators_df(
        close=50.0, ema20=55.0, ema50=60.0, ema200=70.0,
        rsi=30.0, macd=-1.0, macd_signal=-0.5, macd_hist=-0.5,
        return_5d=-6.0, return_20d=-10.0,
    )
    strong_indicators = _make_indicators_df(
        close=150.0, ema20=140.0, ema50=130.0, ema200=110.0,
        rsi=60.0, macd=1.0, macd_signal=0.5, macd_hist=0.5,
        return_5d=1.0, return_20d=5.0,
    )

    def fake_load(symbol: str, cache_dir: Path) -> pd.DataFrame:
        return _dummy_prices(marker=1.0 if symbol == "BIG" else 2.0)

    def fake_calculate(prices: pd.DataFrame) -> pd.DataFrame:
        return weak_indicators if prices["Close"].iloc[0] == 1.0 else strong_indicators

    monkeypatch.setattr(portfolio_analysis, "load_cached_prices", fake_load)
    monkeypatch.setattr(portfolio_analysis, "calculate_technical_indicators", fake_calculate)

    rows = [
        _portfolio_row("BIG", quantity=1000.0, average_cost=40.0),
        _portfolio_row("SMALL1", quantity=10.0, average_cost=100.0),
        _portfolio_row("SMALL2", quantity=10.0, average_cost=100.0),
    ]
    positions = analyze_portfolio(rows, Path("."), single_position_threshold_pct=25.0)
    big = next(p for p in positions if p.symbol == "BIG")

    assert big.weight_pct is not None
    assert big.weight_pct > 25.0
    assert big.trend.status == "WEAK_TREND"
    assert big.action_hint == "RISK_ALERT"

    summary = summarize_portfolio(positions, single_position_threshold_pct=25.0, top3_threshold_pct=60.0)
    try_totals = next(t for t in summary.totals_by_currency if t.currency == "TRY")
    assert any("HIGH concentration" in warning for warning in try_totals.warnings)


def test_scenario_d_healthy_strong_trend_position(monkeypatch: pytest.MonkeyPatch) -> None:
    """D: Saglikli ve guclu trendli pozisyon -> HEALTHY/STRONG + HOLD_CANDIDATE."""
    indicators = _make_indicators_df(
        close=150.0, ema20=140.0, ema50=130.0, ema200=110.0,
        rsi=60.0, macd=2.0, macd_signal=1.0, macd_hist=1.0,
        return_5d=3.0, return_20d=10.0,
    )
    monkeypatch.setattr(portfolio_analysis, "load_cached_prices", lambda symbol, cache_dir: _dummy_prices())
    monkeypatch.setattr(portfolio_analysis, "calculate_technical_indicators", lambda prices: indicators)

    positions = analyze_portfolio([_portfolio_row(average_cost=100.0)], Path("."))

    assert positions[0].health.status in {"HEALTHY", "STRONG"}
    assert positions[0].action_hint == "HOLD_CANDIDATE"


def test_scenario_e_weak_position_vs_high_opportunity_alternative() -> None:
    """E: Weak pozisyona karsi yuksek Opportunity Score'lu, portfoyde OLMAYAN bir alternatif
    ayri listelenmeli; portfoyde ZATEN olan bir sembol (HIGH_OPPORTUNITY olsa bile) alternatif
    listesine sizmamali."""
    weak_position = PositionAnalysis(
        symbol="XYZ", quantity=10.0, average_cost=100.0, currency="TRY",
        current_price=50.0, market_value=500.0, cost_value=1000.0,
        unrealized_pl=-500.0, unrealized_pl_pct=-50.0, weight_pct=100.0,
        trend=TrendScore(20, "WEAK_TREND", ()),
        opportunity=OpportunityScore(20, "LOW", ()),
        health=PositionHealth(25, "WEAK", ()),
        action_hint="REVIEW",
    )

    def _candidate(symbol: str, opportunity_status: str = "HIGH_OPPORTUNITY") -> OpportunityCandidate:
        return OpportunityCandidate(
            symbol=symbol, close=1.0, ema20=1.0, ema50=1.0, ema200=1.0, rsi=1.0, macd_hist=1.0,
            average_volume_20=1.0, return_20d=1.0, distance_ema20_pct=1.0,
            trend=TrendScore(72, "STRONG_TREND", ()),
            opportunity=OpportunityScore(88, opportunity_status, ()),
        )

    alternative_candidate = _candidate("ABC")
    already_owned_candidate = _candidate("XYZ")  # portfoyde zaten var, HIGH_OPPORTUNITY olsa da elenmeli

    weak = find_weak_positions([weak_position])
    alternatives = find_high_opportunity_alternatives(
        [alternative_candidate, already_owned_candidate], {"XYZ"}
    )

    assert weak == [weak_position]
    assert alternatives == [alternative_candidate]


# --- unavailable / eksik veri ---


def test_analyze_single_position_no_cache_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(portfolio_analysis, "load_cached_prices", lambda symbol, cache_dir: None)

    position = _analyze_single_position(_portfolio_row(), Path("."))

    assert position.current_price is None
    assert position.market_value is None
    assert position.cost_value == pytest.approx(1000.0)  # her zaman hesaplanabilir
    assert position.trend.score is None
    assert position.health.score is None
    assert position.action_hint is None


# --- para birimi gruplama ---


def test_summarize_portfolio_groups_by_currency_without_mixing(monkeypatch: pytest.MonkeyPatch) -> None:
    indicators = _make_indicators_df(close=110.0)
    monkeypatch.setattr(portfolio_analysis, "load_cached_prices", lambda symbol, cache_dir: _dummy_prices())
    monkeypatch.setattr(portfolio_analysis, "calculate_technical_indicators", lambda prices: indicators)

    rows = [
        _portfolio_row("TRY1", quantity=10.0, average_cost=100.0, currency="TRY"),
        _portfolio_row("USD1", quantity=5.0, average_cost=100.0, currency="USD"),
    ]
    positions = analyze_portfolio(rows, Path("."))
    summary = summarize_portfolio(positions)

    currencies = {t.currency for t in summary.totals_by_currency}
    assert currencies == {"TRY", "USD"}
    try_totals = next(t for t in summary.totals_by_currency if t.currency == "TRY")
    usd_totals = next(t for t in summary.totals_by_currency if t.currency == "USD")
    assert try_totals.total_market_value == pytest.approx(10 * 110.0)
    assert usd_totals.total_market_value == pytest.approx(5 * 110.0)
    # ayri para birimleri hicbir yerde toplanmiyor
    assert try_totals.total_market_value != pytest.approx(
        try_totals.total_market_value + usd_totals.total_market_value
    )


def test_analyze_portfolio_weight_pct_sums_to_100_within_currency(monkeypatch: pytest.MonkeyPatch) -> None:
    indicators = _make_indicators_df(close=100.0)
    monkeypatch.setattr(portfolio_analysis, "load_cached_prices", lambda symbol, cache_dir: _dummy_prices())
    monkeypatch.setattr(portfolio_analysis, "calculate_technical_indicators", lambda prices: indicators)

    rows = [
        _portfolio_row("A", quantity=10.0, currency="TRY"),
        _portfolio_row("B", quantity=30.0, currency="TRY"),
    ]
    positions = analyze_portfolio(rows, Path("."))

    total_weight = sum(p.weight_pct for p in positions if p.weight_pct is not None)
    assert total_weight == pytest.approx(100.0)


# --- load_concentration_thresholds ---


def test_load_concentration_thresholds_reads_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "[portfolio_analysis]\nsingle_position_threshold_pct = 30\ntop3_threshold_pct = 70\n",
        encoding="utf-8",
    )

    single, top3 = load_concentration_thresholds(config_path)

    assert single == pytest.approx(30.0)
    assert top3 == pytest.approx(70.0)


def test_load_concentration_thresholds_falls_back_on_missing_file(tmp_path: Path) -> None:
    single, top3 = load_concentration_thresholds(tmp_path / "does_not_exist.toml")

    assert single == pytest.approx(DEFAULT_SINGLE_POSITION_THRESHOLD_PCT)
    assert top3 == pytest.approx(60.0)


# --- build_portfolio_analysis_report ---


def test_build_portfolio_analysis_report_combines_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    indicators = _make_indicators_df(close=100.0, rsi=30.0, ema20=110.0, ema50=120.0, ema200=130.0)
    monkeypatch.setattr(portfolio_analysis, "load_cached_prices", lambda symbol, cache_dir: _dummy_prices())
    monkeypatch.setattr(portfolio_analysis, "calculate_technical_indicators", lambda prices: indicators)

    rows = [_portfolio_row("XYZ")]
    report = build_portfolio_analysis_report(rows, scanner_candidates=[], cache_dir=Path("."))

    assert len(report.positions) == 1
    assert report.summary.totals_by_currency
    assert isinstance(report.weak_positions, list)
    assert report.high_opportunity_alternatives == []


# --- rapor yazicilari ---


def test_write_portfolio_analysis_csv_roundtrip(tmp_path: Path) -> None:
    position = PositionAnalysis(
        symbol="XYZ", quantity=10.0, average_cost=100.0, currency="TRY",
        current_price=110.0, market_value=1100.0, cost_value=1000.0,
        unrealized_pl=100.0, unrealized_pl_pct=10.0, weight_pct=100.0,
        trend=TrendScore(70, "STRONG_TREND", ()),
        opportunity=OpportunityScore(80, "HIGH_OPPORTUNITY", ()),
        health=PositionHealth(75, "HEALTHY", ()),
        action_hint="HOLD_CANDIDATE",
    )
    path = tmp_path / "portfolio_analysis.csv"

    write_portfolio_analysis_csv([position], path)

    result = pd.read_csv(path)
    assert result.loc[0, "Symbol"] == "XYZ"
    assert result.loc[0, "Health Status"] == "HEALTHY"
    assert result.loc[0, "Action Hint"] == "HOLD_CANDIDATE"


def test_write_portfolio_summary_json_roundtrip(tmp_path: Path) -> None:
    import json

    position = PositionAnalysis(
        symbol="XYZ", quantity=10.0, average_cost=100.0, currency="TRY",
        current_price=50.0, market_value=500.0, cost_value=1000.0,
        unrealized_pl=-500.0, unrealized_pl_pct=-50.0, weight_pct=100.0,
        trend=TrendScore(20, "WEAK_TREND", ()),
        opportunity=OpportunityScore(20, "LOW", ()),
        health=PositionHealth(25, "WEAK", ()),
        action_hint="REVIEW",
    )
    summary = summarize_portfolio([position])

    full_report = PortfolioAnalysisReport(
        positions=[position], summary=summary, weak_positions=[position], high_opportunity_alternatives=[]
    )
    path = tmp_path / "portfolio_summary.json"

    write_portfolio_summary_json(full_report, path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["weak_positions"] == ["XYZ"]
    assert payload["health_counts"]["weak"] == 1
    assert payload["totals_by_currency"][0]["currency"] == "TRY"


def test_write_portfolio_analysis_csv_creates_missing_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / "reports" / "nested" / "portfolio_analysis.csv"

    write_portfolio_analysis_csv([], path)

    assert path.exists()
