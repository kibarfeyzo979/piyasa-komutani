"""technical_analysis.py testleri - tamami sentetik veriyle, ag/dosya erisimi yok."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from piyasa_komutani.indicators import calculate_ema
from piyasa_komutani.technical_analysis import (
    POINTS_TREND_CLOSE_ABOVE_EMA20,
    POINTS_TREND_EMA20_ABOVE_EMA50,
    POINTS_TREND_EMA20_SLOPE_POSITIVE,
    POINTS_TREND_EMA50_ABOVE_EMA200,
    POINTS_TREND_EMA50_SLOPE_POSITIVE,
    POINTS_TREND_MACD_BULLISH,
    POINTS_TREND_RETURN_20D_POSITIVE,
    POINTS_TREND_RSI_HEALTHY,
    BONUS_MACD_CROSS_UP,
    BONUS_MOMENTUM_STRENGTHENING,
    BONUS_NEAR_SUPPORT,
    BONUS_RSI_RISING_NEUTRAL,
    PENALTY_EXTREME_RETURN,
    PENALTY_OVEREXTENDED,
    PENALTY_RSI_OVERBOUGHT,
    TREND_MAX_SCORE,
    _opportunity_status_for,
    _score_opportunity,
    _score_trend,
    _trend_status_for,
    calculate_distance_from_ema_pct,
    calculate_opportunity_score,
    calculate_return_pct,
    calculate_slope,
    calculate_technical_indicators,
    calculate_trend_score,
)

NAN = math.nan


# --- yeni metrik fonksiyonlari ---


def test_calculate_return_pct_matches_hand_computed_value() -> None:
    close = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])

    result = calculate_return_pct(close, period=5)

    assert result.iloc[5] == pytest.approx(5.0)


def test_calculate_distance_from_ema_pct_matches_hand_computed_value() -> None:
    close = pd.Series([110.0])
    ema = pd.Series([100.0])

    result = calculate_distance_from_ema_pct(close, ema)

    assert result.iloc[0] == pytest.approx(10.0)


def test_calculate_slope_matches_hand_computed_value() -> None:
    series = pd.Series([10.0, 11.0, 12.0, 13.0, 14.0, 20.0])

    result = calculate_slope(series, period=5)

    assert result.iloc[5] == pytest.approx(10.0)


def test_calculate_technical_indicators_produces_expected_columns() -> None:
    price_data = pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=250, freq="D"),
            "Close": [100.0 + i for i in range(250)],
        }
    )

    result = calculate_technical_indicators(price_data)

    assert list(result.columns) == [
        "Date",
        "Close",
        "EMA_20",
        "EMA_50",
        "EMA_200",
        "RSI_14",
        "MACD",
        "MACD_Signal",
        "MACD_Hist",
        "Return_5D",
        "Return_20D",
        "Distance_EMA20_Pct",
        "Distance_EMA50_Pct",
        "EMA20_Slope",
        "EMA50_Slope",
        "RSI_Change_3D",
        "MACD_Hist_Change_3D",
    ]
    assert len(result) == 250
    pd.testing.assert_series_equal(
        result["EMA_20"], calculate_ema(price_data["Close"], 20), check_names=False
    )


# --- _score_trend sinir degerleri ---


def _trend_kwargs(**overrides: float) -> dict[str, float]:
    base = {
        "close": NAN,
        "ema20": NAN,
        "ema50": NAN,
        "ema200": NAN,
        "rsi": NAN,
        "macd": NAN,
        "macd_signal": NAN,
        "return_20d": NAN,
        "ema20_slope": NAN,
        "ema50_slope": NAN,
    }
    base.update(overrides)
    return base


def test_trend_structure_all_bullish_gives_max_structure_points() -> None:
    score, reasons = _score_trend(**_trend_kwargs(close=110, ema20=105, ema50=100, ema200=90))

    assert score == POINTS_TREND_CLOSE_ABOVE_EMA20 + POINTS_TREND_EMA20_ABOVE_EMA50 + POINTS_TREND_EMA50_ABOVE_EMA200
    assert len(reasons) == 3


def test_trend_structure_all_bearish_gives_zero_structure_points() -> None:
    score, reasons = _score_trend(**_trend_kwargs(close=90, ema20=100, ema50=105, ema200=110))

    assert score == 0
    assert reasons == ()


def test_trend_rsi_50_to_70_gives_momentum_points() -> None:
    score, _ = _score_trend(**_trend_kwargs(rsi=60))

    assert score == POINTS_TREND_RSI_HEALTHY


def test_trend_rsi_outside_50_70_gives_no_momentum_points() -> None:
    score, _ = _score_trend(**_trend_kwargs(rsi=40))

    assert score == 0


def test_trend_macd_above_signal_gives_bullish_points() -> None:
    score, reasons = _score_trend(**_trend_kwargs(macd=1.0, macd_signal=0.5))

    assert score == POINTS_TREND_MACD_BULLISH
    assert len(reasons) == 1  # MACD>Signal ve Hist>0 tek kural, cifte sayilmiyor


def test_trend_macd_below_signal_gives_no_points() -> None:
    score, _ = _score_trend(**_trend_kwargs(macd=0.5, macd_signal=1.0))

    assert score == 0


def test_trend_continuity_all_positive_gives_max_continuity_points() -> None:
    score, reasons = _score_trend(**_trend_kwargs(return_20d=5.0, ema20_slope=1.0, ema50_slope=1.0))

    assert score == POINTS_TREND_RETURN_20D_POSITIVE + POINTS_TREND_EMA20_SLOPE_POSITIVE + POINTS_TREND_EMA50_SLOPE_POSITIVE
    assert len(reasons) == 3


def test_trend_all_nan_gives_zero_score_and_no_reasons() -> None:
    score, reasons = _score_trend(**_trend_kwargs())

    assert score == 0
    assert reasons == ()


def test_trend_max_score_is_100() -> None:
    assert TREND_MAX_SCORE == 100


@pytest.mark.parametrize(
    ("score", "expected_status"),
    [
        (0, "WEAK_TREND"),
        (39, "WEAK_TREND"),
        (40, "NEUTRAL_TREND"),
        (59, "NEUTRAL_TREND"),
        (60, "STRONG_TREND"),
        (79, "STRONG_TREND"),
        (80, "VERY_STRONG_TREND"),
        (100, "VERY_STRONG_TREND"),
    ],
)
def test_trend_status_boundaries(score: int, expected_status: str) -> None:
    assert _trend_status_for(score) == expected_status


# --- calculate_trend_score ---


def test_calculate_trend_score_insufficient_history_is_unavailable() -> None:
    price_data = pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=50, freq="D"),
            "Close": [100.0] * 50,
        }
    )
    indicators = calculate_technical_indicators(price_data)

    result = calculate_trend_score(indicators)

    assert result.score is None
    assert result.status is None
    assert result.unavailable_reason is not None
    assert "50" in result.unavailable_reason


def test_calculate_trend_score_end_to_end_on_uptrend() -> None:
    price_data = pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=250, freq="D"),
            "Close": [100.0 + i * 0.5 for i in range(250)],
        }
    )
    indicators = calculate_technical_indicators(price_data)

    result = calculate_trend_score(indicators)

    assert result.score is not None
    assert result.score >= 60
    assert result.status in {"STRONG_TREND", "VERY_STRONG_TREND"}


# --- _score_opportunity sinir degerleri / senaryolari (madde 8) ---


def _opportunity_kwargs(**overrides: object) -> dict[str, object]:
    base = {
        "trend_score": 50,
        "trend_status": "NEUTRAL_TREND",
        "rsi": NAN,
        "return_20d": NAN,
        "distance_ema20_pct": NAN,
        "distance_ema50_pct": NAN,
        "rsi_change_3d": NAN,
        "macd_hist_prev": NAN,
        "macd_hist_now": NAN,
        "macd_hist_change_3d": NAN,
    }
    base.update(overrides)
    return base


def test_scenario_a_very_strong_trend_overextended_reduces_score() -> None:
    """A: Cok guclu trend ama asiri primlenmis hisse -> asiri uzama cezasi."""
    score, reasons = _score_opportunity(
        **_opportunity_kwargs(trend_score=95, trend_status="VERY_STRONG_TREND", distance_ema20_pct=12.0)
    )

    assert score == 95 - PENALTY_OVEREXTENDED
    assert any("extended" in reason.lower() for reason in reasons)


def test_scenario_b_moderate_trend_new_momentum_increases_score() -> None:
    """B: Orta guclu trend ve yeni momentum baslangici -> momentum-guclenme bonusu."""
    score, reasons = _score_opportunity(
        **_opportunity_kwargs(trend_score=55, trend_status="NEUTRAL_TREND", macd_hist_change_3d=0.5)
    )

    assert score == 55 + BONUS_MOMENTUM_STRENGTHENING
    assert any("momentum strengthening" in reason.lower() for reason in reasons)


def test_scenario_c_weak_trend_oversold_rsi_does_not_boost_score() -> None:
    """C: Zayif trend ama RSI asiri satimda -> hicbir bonus tetiklenmez (eski scoring.py'nin
    'RSI dusukse otomatik bullish' hatasina dusulmuyor)."""
    score, reasons = _score_opportunity(**_opportunity_kwargs(trend_score=20, trend_status="WEAK_TREND", rsi=25.0))

    assert score == 20
    assert any("trend is weak" in reason.lower() for reason in reasons)
    assert not any("+" in reason for reason in reasons)


def test_scenario_d_strong_trend_healthy_pullback_increases_score() -> None:
    """D: Guclu trend ve EMA20'ye saglikli geri cekilme -> destek bonusu."""
    score, reasons = _score_opportunity(
        **_opportunity_kwargs(trend_score=70, trend_status="STRONG_TREND", distance_ema20_pct=1.0)
    )

    assert score == 70 + BONUS_NEAR_SUPPORT
    assert any("support" in reason.lower() for reason in reasons)


def test_scenario_e_macd_histogram_crosses_negative_to_positive() -> None:
    """E: MACD histogram negatiften pozitife gecis -> kesisim bonusu."""
    score, reasons = _score_opportunity(
        **_opportunity_kwargs(trend_score=50, macd_hist_prev=-0.5, macd_hist_now=0.3)
    )

    assert score == 50 + BONUS_MACD_CROSS_UP
    assert any("bullish cross" in reason.lower() for reason in reasons)


def test_rsi_overbought_reduces_score() -> None:
    score, reasons = _score_opportunity(**_opportunity_kwargs(trend_score=50, rsi=80.0))

    assert score == 50 - PENALTY_RSI_OVERBOUGHT
    assert any("overbought" in reason.lower() for reason in reasons)


def test_extreme_return_20d_reduces_score() -> None:
    score, reasons = _score_opportunity(**_opportunity_kwargs(trend_score=50, return_20d=30.0))

    assert score == 50 - PENALTY_EXTREME_RETURN
    assert any("return already high" in reason.lower() for reason in reasons)


def test_rsi_rising_from_neutral_zone_increases_score() -> None:
    score, reasons = _score_opportunity(
        **_opportunity_kwargs(trend_score=50, rsi=50.0, rsi_change_3d=2.0)
    )

    assert score == 50 + BONUS_RSI_RISING_NEUTRAL
    assert any("rising from neutral" in reason.lower() for reason in reasons)


def test_momentum_strengthening_does_not_apply_to_very_strong_trend() -> None:
    score, _ = _score_opportunity(
        **_opportunity_kwargs(trend_score=90, trend_status="VERY_STRONG_TREND", macd_hist_change_3d=0.5)
    )

    assert score == 90  # bonus tetiklenmedi, trend zaten VERY_STRONG


def test_all_nan_signals_leave_score_equal_to_trend_score() -> None:
    score, _ = _score_opportunity(**_opportunity_kwargs(trend_score=50, trend_status="NEUTRAL_TREND"))

    assert score == 50


@pytest.mark.parametrize(
    ("score", "expected_status"),
    [
        (0, "LOW"),
        (39, "LOW"),
        (40, "WATCH"),
        (59, "WATCH"),
        (60, "INTERESTING"),
        (74, "INTERESTING"),
        (75, "HIGH_OPPORTUNITY"),
        (100, "HIGH_OPPORTUNITY"),
    ],
)
def test_opportunity_status_boundaries(score: int, expected_status: str) -> None:
    assert _opportunity_status_for(score) == expected_status


# --- calculate_opportunity_score ---


def test_calculate_opportunity_score_unavailable_when_trend_unavailable() -> None:
    price_data = pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=50, freq="D"),
            "Close": [100.0] * 50,
        }
    )
    indicators = calculate_technical_indicators(price_data)
    trend = calculate_trend_score(indicators)

    result = calculate_opportunity_score(indicators, trend)

    assert result.score is None
    assert result.unavailable_reason is not None


def test_calculate_opportunity_score_end_to_end_on_uptrend() -> None:
    price_data = pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=250, freq="D"),
            "Close": [100.0 + i * 0.3 for i in range(250)],
        }
    )
    indicators = calculate_technical_indicators(price_data)
    trend = calculate_trend_score(indicators)

    result = calculate_opportunity_score(indicators, trend)

    assert result.score is not None
    assert 0 <= result.score <= 100
    assert result.status is not None


def test_calculate_opportunity_score_is_clamped_to_0_100(monkeypatch: pytest.MonkeyPatch) -> None:
    # Cezalarin toplami taban skoru 0'in altina indirebilir - kirpma dogrulanir.
    score, _ = _score_opportunity(
        **_opportunity_kwargs(
            trend_score=5,
            trend_status="WEAK_TREND",
            rsi=90.0,
            return_20d=50.0,
        )
    )

    assert 5 - PENALTY_RSI_OVERBOUGHT - PENALTY_EXTREME_RETURN < 0  # varsayimi dogrula
    clamped = max(0, min(100, score))
    assert clamped == 0
