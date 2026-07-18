"""scoring.py testleri - tamami sentetik/skaler girdilerle, ag/dosya yok."""

from __future__ import annotations

import math

import pandas as pd

from piyasa_komutani.indicators import calculate_indicators
from piyasa_komutani.scoring import DEFAULT_RSI_OVERBOUGHT, DEFAULT_RSI_OVERSOLD, score_latest, score_row


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
