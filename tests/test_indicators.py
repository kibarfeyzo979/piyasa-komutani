"""indicators.py testleri - tamami sentetik veriyle, ag/dosya erisimi yok."""

from __future__ import annotations

import pandas as pd
import pytest

from piyasa_komutani.indicators import (
    calculate_ema,
    calculate_indicators,
    calculate_macd,
    calculate_rsi,
)


def test_calculate_ema_matches_hand_computed_sequence() -> None:
    close = pd.Series([10.0, 11.0, 12.0])

    result = calculate_ema(close, span=2)

    # alpha = 2/(span+1) = 2/3, adjust=False:
    # EMA0 = 10
    # EMA1 = 2/3*11 + 1/3*10 = 32/3
    # EMA2 = 2/3*12 + 1/3*(32/3) = 104/9
    expected = [10.0, 32 / 3, 104 / 9]
    assert result.tolist() == pytest.approx(expected)


def test_calculate_rsi_all_gains_is_100() -> None:
    close = pd.Series([float(i) for i in range(1, 20)])  # hep artiyor

    result = calculate_rsi(close, period=14)

    assert result.iloc[-1] == pytest.approx(100.0)


def test_calculate_rsi_all_losses_is_0() -> None:
    close = pd.Series([float(i) for i in range(20, 1, -1)])  # hep azaliyor

    result = calculate_rsi(close, period=14)

    assert result.iloc[-1] == pytest.approx(0.0)


def test_calculate_rsi_is_nan_before_period_completes() -> None:
    close = pd.Series([1.0, 2.0, 1.0, 3.0, 2.0])

    result = calculate_rsi(close, period=3)

    assert result.iloc[:3].isna().all()
    assert result.iloc[3:].notna().all()


def test_calculate_macd_line_is_ema_difference() -> None:
    close = pd.Series([float(i) for i in range(1, 40)])

    result = calculate_macd(close, short_span=12, long_span=26, signal_span=9)

    expected_macd_line = calculate_ema(close, 12) - calculate_ema(close, 26)
    pd.testing.assert_series_equal(result.macd_line, expected_macd_line)


def test_calculate_macd_signal_is_ema_of_macd_line() -> None:
    close = pd.Series([float(i) for i in range(1, 40)])

    result = calculate_macd(close, short_span=12, long_span=26, signal_span=9)

    expected_signal = calculate_ema(result.macd_line, 9)
    pd.testing.assert_series_equal(result.signal_line, expected_signal)


def test_calculate_macd_histogram_is_macd_minus_signal() -> None:
    close = pd.Series([float(i) for i in range(1, 40)])

    result = calculate_macd(close)

    pd.testing.assert_series_equal(result.histogram, result.macd_line - result.signal_line)


def test_calculate_indicators_produces_expected_columns() -> None:
    price_data = pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=40, freq="D"),
            "Close": [100.0 + i for i in range(40)],
        }
    )

    result = calculate_indicators(price_data)

    assert list(result.columns) == [
        "Date",
        "Close",
        "EMA_12",
        "EMA_26",
        "RSI_14",
        "MACD",
        "MACD_Signal",
        "MACD_Hist",
    ]
    assert len(result) == 40
