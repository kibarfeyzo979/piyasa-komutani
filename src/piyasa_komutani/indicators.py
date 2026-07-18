"""EMA, RSI ve MACD hesaplamalari.

Saf hesaplama modulu: dosya/ag erisimi yok, yalnizca pandas
Series/DataFrame alip donuyor. Fiyat verisini yuklemek icin
market_data.load_cached_prices kullanilabilir.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

DEFAULT_EMA_SHORT = 12
DEFAULT_EMA_LONG = 26
DEFAULT_RSI_PERIOD = 14
DEFAULT_MACD_SIGNAL = 9


def calculate_ema(close: pd.Series, span: int) -> pd.Series:
    """Ussel hareketli ortalama (EMA) hesaplar."""
    return close.ewm(span=span, adjust=False).mean()


def calculate_rsi(close: pd.Series, period: int = DEFAULT_RSI_PERIOD) -> pd.Series:
    """Wilder yumusatmasiyla RSI (Goreceli Guc Endeksi) hesaplar."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


@dataclass(frozen=True)
class MACDResult:
    """MACD hesaplamasinin uc bileseni."""

    macd_line: pd.Series
    signal_line: pd.Series
    histogram: pd.Series


def calculate_macd(
    close: pd.Series,
    short_span: int = DEFAULT_EMA_SHORT,
    long_span: int = DEFAULT_EMA_LONG,
    signal_span: int = DEFAULT_MACD_SIGNAL,
) -> MACDResult:
    """MACD cizgisi, sinyal cizgisi ve histogrami hesaplar."""
    macd_line = calculate_ema(close, short_span) - calculate_ema(close, long_span)
    signal_line = calculate_ema(macd_line, signal_span)
    histogram = macd_line - signal_line
    return MACDResult(macd_line, signal_line, histogram)


def calculate_indicators(
    price_data: pd.DataFrame,
    *,
    ema_short: int = DEFAULT_EMA_SHORT,
    ema_long: int = DEFAULT_EMA_LONG,
    rsi_period: int = DEFAULT_RSI_PERIOD,
    macd_signal: int = DEFAULT_MACD_SIGNAL,
) -> pd.DataFrame:
    """Date+Close iceren fiyat verisinden tum indikatorleri tek DataFrame'de dondurur."""
    close = price_data["Close"]
    macd = calculate_macd(close, ema_short, ema_long, macd_signal)

    return pd.DataFrame(
        {
            "Date": price_data["Date"],
            "Close": close,
            f"EMA_{ema_short}": calculate_ema(close, ema_short),
            f"EMA_{ema_long}": calculate_ema(close, ema_long),
            f"RSI_{rsi_period}": calculate_rsi(close, rsi_period),
            "MACD": macd.macd_line,
            "MACD_Signal": macd.signal_line,
            "MACD_Hist": macd.histogram,
        }
    )
