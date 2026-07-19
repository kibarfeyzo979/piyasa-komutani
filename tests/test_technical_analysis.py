"""technical_analysis.py testleri - tamami sentetik veriyle, ag/dosya erisimi yok."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from piyasa_komutani.indicators import calculate_ema
from piyasa_komutani.technical_analysis import (
    MIN_ROWS_FOR_SCORE,
    POINTS_CLOSE_ABOVE_EMA20,
    POINTS_EMA20_ABOVE_EMA50,
    POINTS_EMA50_ABOVE_EMA200,
    POINTS_MACD_ABOVE_SIGNAL,
    POINTS_MACD_HIST_RISING,
    POINTS_RSI_HEALTHY,
    POINTS_RSI_WEAK,
    _score_signals,
    _status_for,
    calculate_opportunity_score,
    calculate_technical_indicators,
)

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
    macd_hist_last3: tuple[float, float, float] = (0.0, 0.0, 0.0),
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
    data.loc[data.index[-3:], "MACD_Hist"] = macd_hist_last3
    return data


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
    ]
    assert len(result) == 250
    pd.testing.assert_series_equal(
        result["EMA_20"], calculate_ema(price_data["Close"], 20), check_names=False
    )


# --- _score_signals sinir degerleri ---


def test_rsi_49_gives_weak_momentum_points() -> None:
    raw, _ = _score_signals(
        close=NAN, ema20=NAN, ema50=NAN, ema200=NAN, rsi=49.0, macd=NAN, macd_signal=NAN, macd_hist_last3=None
    )
    assert raw == POINTS_RSI_WEAK


def test_rsi_50_gives_healthy_momentum_points() -> None:
    raw, _ = _score_signals(
        close=NAN, ema20=NAN, ema50=NAN, ema200=NAN, rsi=50.0, macd=NAN, macd_signal=NAN, macd_hist_last3=None
    )
    assert raw == POINTS_RSI_HEALTHY


def test_rsi_70_gives_healthy_momentum_points() -> None:
    raw, _ = _score_signals(
        close=NAN, ema20=NAN, ema50=NAN, ema200=NAN, rsi=70.0, macd=NAN, macd_signal=NAN, macd_hist_last3=None
    )
    assert raw == POINTS_RSI_HEALTHY


def test_rsi_75_gives_no_momentum_points() -> None:
    raw, _ = _score_signals(
        close=NAN, ema20=NAN, ema50=NAN, ema200=NAN, rsi=75.0, macd=NAN, macd_signal=NAN, macd_hist_last3=None
    )
    assert raw == 0


def test_full_bullish_trend_gives_max_trend_points() -> None:
    raw, reasons = _score_signals(
        close=110, ema20=105, ema50=100, ema200=90, rsi=NAN, macd=NAN, macd_signal=NAN, macd_hist_last3=None
    )
    assert raw == POINTS_CLOSE_ABOVE_EMA20 + POINTS_EMA20_ABOVE_EMA50 + POINTS_EMA50_ABOVE_EMA200
    assert len(reasons) == 3


def test_full_bearish_trend_gives_zero_trend_points() -> None:
    raw, reasons = _score_signals(
        close=90, ema20=100, ema50=105, ema200=110, rsi=NAN, macd=NAN, macd_signal=NAN, macd_hist_last3=None
    )
    assert raw == 0
    assert reasons == ()


def test_macd_above_signal_gives_points() -> None:
    raw, _ = _score_signals(
        close=NAN, ema20=NAN, ema50=NAN, ema200=NAN, rsi=NAN, macd=1.0, macd_signal=0.5, macd_hist_last3=None
    )
    assert raw == POINTS_MACD_ABOVE_SIGNAL


def test_macd_below_signal_gives_no_points() -> None:
    raw, _ = _score_signals(
        close=NAN, ema20=NAN, ema50=NAN, ema200=NAN, rsi=NAN, macd=0.5, macd_signal=1.0, macd_hist_last3=None
    )
    assert raw == 0


def test_macd_above_signal_and_hist_positive_is_not_double_counted() -> None:
    # MACD_Hist := MACD - MACD_Signal, yani "MACD > Signal" ve "Hist > 0"
    # matematiksel olarak ayni kosul - ayri bir "Hist > 0" bonusu YOK.
    raw, reasons = _score_signals(
        close=NAN,
        ema20=NAN,
        ema50=NAN,
        ema200=NAN,
        rsi=NAN,
        macd=1.0,
        macd_signal=0.5,
        macd_hist_last3=(0.1, 0.1, 0.1),  # pozitif ama duz (yukselmiyor)
    )
    assert raw == POINTS_MACD_ABOVE_SIGNAL
    assert len(reasons) == 1


def test_macd_histogram_flat_positive_without_macd_gives_no_points() -> None:
    # macd/macd_signal NaN oldugunda "Hist pozitif" tek basina puan vermez
    # (ayri bir kural olarak kaldirildi) - sadece "yukseliyor mu" kontrol edilir.
    raw, _ = _score_signals(
        close=NAN,
        ema20=NAN,
        ema50=NAN,
        ema200=NAN,
        rsi=NAN,
        macd=NAN,
        macd_signal=NAN,
        macd_hist_last3=(0.1, 0.1, 0.1),
    )
    assert raw == 0


def test_macd_histogram_non_positive_gives_no_points() -> None:
    raw, _ = _score_signals(
        close=NAN,
        ema20=NAN,
        ema50=NAN,
        ema200=NAN,
        rsi=NAN,
        macd=NAN,
        macd_signal=NAN,
        macd_hist_last3=(-0.1, -0.1, -0.1),
    )
    assert raw == 0


def test_macd_histogram_rising_3_days_gives_bonus_independent_of_macd() -> None:
    # "Rising" kurali macd/macd_signal'a bagli degil, sadece son 3 gunun
    # sirasina bakar.
    raw, _ = _score_signals(
        close=NAN,
        ema20=NAN,
        ema50=NAN,
        ema200=NAN,
        rsi=NAN,
        macd=NAN,
        macd_signal=NAN,
        macd_hist_last3=(0.1, 0.2, 0.3),
    )
    assert raw == POINTS_MACD_HIST_RISING


def test_macd_histogram_falling_gives_no_rising_bonus() -> None:
    raw, _ = _score_signals(
        close=NAN,
        ema20=NAN,
        ema50=NAN,
        ema200=NAN,
        rsi=NAN,
        macd=NAN,
        macd_signal=NAN,
        macd_hist_last3=(0.3, 0.2, 0.1),
    )
    assert raw == 0


def test_all_nan_inputs_give_zero_score_and_no_reasons() -> None:
    raw, reasons = _score_signals(
        close=NAN, ema20=NAN, ema50=NAN, ema200=NAN, rsi=NAN, macd=NAN, macd_signal=NAN, macd_hist_last3=None
    )
    assert raw == 0
    assert reasons == ()


# --- calculate_opportunity_score ---


def test_insufficient_history_returns_unavailable_without_crashing() -> None:
    price_data = pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=50, freq="D"),
            "Close": [100.0] * 50,
        }
    )
    ta = calculate_technical_indicators(price_data)

    result = calculate_opportunity_score(ta)

    assert result.score is None
    assert result.status is None
    assert result.unavailable_reason is not None
    assert "50" in result.unavailable_reason


def test_all_rules_triggered_normalizes_raw_85_to_100() -> None:
    ta = _make_indicators_df(
        close=110,
        ema20=105,
        ema50=100,
        ema200=90,
        rsi=60,
        macd=1.0,
        macd_signal=0.5,
        macd_hist_last3=(0.1, 0.2, 0.3),
    )

    result = calculate_opportunity_score(ta)

    assert result.score == 100
    assert result.status == "STRONG"
    assert len(result.reasons) == 6  # MACD>Signal ve Hist>0 artik tek kural


def test_no_rules_triggered_gives_zero_score() -> None:
    ta = _make_indicators_df(
        close=90,
        ema20=100,
        ema50=105,
        ema200=110,
        rsi=20,
        macd=0.5,
        macd_signal=1.0,
        macd_hist_last3=(-0.1, -0.2, -0.3),
    )

    result = calculate_opportunity_score(ta)

    assert result.score == 0
    assert result.status == "WEAK"


@pytest.mark.parametrize(
    ("score", "expected_status"),
    [
        (0, "WEAK"),
        (39, "WEAK"),
        (40, "WATCH"),
        (59, "WATCH"),
        (60, "PROMISING"),
        (74, "PROMISING"),
        (75, "STRONG"),
        (100, "STRONG"),
    ],
)
def test_status_boundaries(score: int, expected_status: str) -> None:
    assert _status_for(score) == expected_status
