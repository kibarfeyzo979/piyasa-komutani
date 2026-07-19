"""scoring.py testleri - tamami sentetik/skaler girdilerle, ag/dosya yok."""

from __future__ import annotations

import math

import pandas as pd

from piyasa_komutani.indicators import calculate_indicators
from piyasa_komutani.scoring import (
    DEFAULT_EMA_LONG,
    DEFAULT_RSI_OVERBOUGHT,
    DEFAULT_RSI_OVERSOLD,
    score_latest,
    score_row,
)


def test_all_bullish_signals_gives_max_score() -> None:
    result = score_row(rsi=20.0, ema_short=15.0, ema_long=10.0, macd=1.0, macd_signal=0.5)

    assert result.score == 3
    assert result.recommendation == "GUCLU AL"
    assert len(result.reasons) == 3


def test_all_bearish_signals_gives_min_score() -> None:
    result = score_row(rsi=80.0, ema_short=10.0, ema_long=15.0, macd=0.5, macd_signal=1.0)

    assert result.score == -3
    assert result.recommendation == "GUCLU SAT"
    assert len(result.reasons) == 3


def test_mixed_signals_gives_neutral_score() -> None:
    # RSI notr, EMA bullish, MACD bearish -> 0
    result = score_row(rsi=50.0, ema_short=15.0, ema_long=10.0, macd=0.5, macd_signal=1.0)

    assert result.score == 0
    assert result.recommendation == "NOTR"


def test_score_one_gives_al() -> None:
    # Sadece EMA bullish, digerleri notr
    result = score_row(rsi=50.0, ema_short=15.0, ema_long=10.0, macd=1.0, macd_signal=1.0)

    assert result.score == 1
    assert result.recommendation == "AL"


def test_score_minus_one_gives_sat() -> None:
    result = score_row(rsi=50.0, ema_short=10.0, ema_long=15.0, macd=1.0, macd_signal=1.0)

    assert result.score == -1
    assert result.recommendation == "SAT"


def test_rsi_exactly_at_thresholds_does_not_trigger_rule() -> None:
    result = score_row(
        rsi=float(DEFAULT_RSI_OVERSOLD),
        ema_short=10.0,
        ema_long=10.0,
        macd=1.0,
        macd_signal=1.0,
    )
    assert result.score == 0

    result = score_row(
        rsi=float(DEFAULT_RSI_OVERBOUGHT),
        ema_short=10.0,
        ema_long=10.0,
        macd=1.0,
        macd_signal=1.0,
    )
    assert result.score == 0


def test_nan_rsi_is_skipped_other_rules_still_apply() -> None:
    result = score_row(rsi=math.nan, ema_short=15.0, ema_long=10.0, macd=1.0, macd_signal=0.5)

    assert result.score == 2
    assert not any("RSI" in reason for reason in result.reasons)


def test_score_latest_matches_calculate_indicators_columns() -> None:
    price_data = pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=40, freq="D"),
            "Close": [100.0 + i for i in range(40)],  # surekli artan seri
        }
    )

    indicators = calculate_indicators(price_data)
    result = score_latest(indicators)

    # Surekli artan fiyat serisinde EMA kisa > EMA uzun ve MACD > sinyal beklenir.
    assert result.score >= 1
    assert result.recommendation in {"AL", "GUCLU AL"}


def test_score_latest_with_insufficient_history_is_unavailable_not_crash() -> None:
    price_data = pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "Close": [100.0, 101.0, 99.0, 102.0, 103.0],
        }
    )

    indicators = calculate_indicators(price_data)
    result = score_latest(indicators)

    assert result.score is None
    assert result.recommendation is None
    assert result.reasons == ()
    assert result.unavailable_reason is not None
    assert str(DEFAULT_EMA_LONG) in result.unavailable_reason


def test_score_latest_on_empty_indicators_is_unavailable_not_crash() -> None:
    empty = pd.DataFrame(columns=["Date", "Close", "EMA_12", "EMA_26", "RSI_14", "MACD", "MACD_Signal", "MACD_Hist"])

    result = score_latest(empty)

    assert result.score is None
    assert result.unavailable_reason is not None


def test_score_latest_reports_clear_reason_on_column_mismatch() -> None:
    # Yeterli satir var ama ema_short/ema_long parametreleri DataFrame'deki
    # gercek kolon adlariyla eslesmiyor (KeyError yerine anlasilir mesaj).
    price_data = pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=40, freq="D"),
            "Close": [100.0 + i for i in range(40)],
        }
    )
    indicators = calculate_indicators(price_data)  # EMA_12, EMA_26 uretir

    result = score_latest(indicators, ema_short=10, ema_long=20)  # DataFrame'de EMA_10/EMA_20 yok

    assert result.score is None
    assert result.unavailable_reason is not None
    assert "kolonu bulunamadi" in result.unavailable_reason
