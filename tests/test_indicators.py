"""indicators.py testleri - tamami sentetik veriyle, ag/dosya erisimi yok."""

from __future__ import annotations

import pandas as pd
import pytest

from piyasa_komutani.indicators import (
    calculate_average_volume,
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


def test_calculate_rsi_matches_hand_computed_wilder_seeding() -> None:
    """Ilk deger duz SMA ile tohumlanmali, sonrakiler Wilder ozyinelemesiyle.

    Elle hesap (period=3):
      gain=[NaN,2,0,2,3,0,2], loss=[NaN,0,1,0,0,1,0]
      avg_gain[3]=mean(2,0,2)=4/3, avg_loss[3]=mean(0,1,0)=1/3 (SMA tohum)
        -> RS=4 -> RSI=100-100/5=80.0
      avg_gain[6]/avg_loss[6] Wilder ozyinelemesiyle (index 4,5,6) ilerletilir
        -> RSI=82.43243243243244
    """
    close = pd.Series([100.0, 102.0, 101.0, 103.0, 106.0, 105.0, 107.0])

    result = calculate_rsi(close, period=3)

    assert result.iloc[3] == pytest.approx(80.0)
    assert result.iloc[6] == pytest.approx(82.43243243243244)


def test_calculate_rsi_seed_differs_from_naive_ewm_from_first_observation() -> None:
    """Duzgun Wilder tohumlamasi (SMA), naif ewm(adjust=False)'in ilk gecerli
    gozlemden baslayan ozyinelemesinden FARKLI bir deger uretmeli - aksi
    halde tohumlama duzeltmesi hicbir sey degistirmiyor demektir."""
    close = pd.Series([100.0, 102.0, 101.0, 103.0, 106.0, 105.0, 107.0])
    period = 3

    proper = calculate_rsi(close, period=period)

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    naive_avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    naive_avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    naive_rsi = 100 - (100 / (1 + naive_avg_gain / naive_avg_loss))

    assert proper.iloc[-1] != pytest.approx(naive_rsi.iloc[-1])


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


def test_calculate_average_volume_matches_simple_average() -> None:
    volume = pd.Series([100.0, 200.0, 300.0])

    result = calculate_average_volume(volume, period=3)

    assert result.iloc[2] == pytest.approx(200.0)


def test_calculate_average_volume_is_nan_before_period_completes() -> None:
    volume = pd.Series([100.0, 200.0, 300.0, 400.0, 500.0])

    result = calculate_average_volume(volume, period=3)

    assert result.iloc[:2].isna().all()
    assert result.iloc[2:].notna().all()
