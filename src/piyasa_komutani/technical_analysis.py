"""EMA20/50/200, RSI14 ve MACD tabanli 0-100 Firsat Skoru (Opportunity Score).

Saf hesaplama modulu: indicators.py'nin genel EMA/RSI/MACD
fonksiyonlarini farkli periyotlarla yeniden kullanir, ama
market_data.py'yi (indirme/cache) hic bilmez. indicators.py/scoring.py
ile ayni pipeline'a dahil degildir - bagimsiz, ek bir analiz.

Bu modulun urettigi skor bir yatirim tavsiyesi veya AL/SAT sinyali
degildir; sadece basit, aciklanabilir bir "Firsat Skoru"dur.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from piyasa_komutani.indicators import calculate_ema, calculate_macd, calculate_rsi

EMA_TREND_SHORT = 20
EMA_TREND_MID = 50
EMA_TREND_LONG = 200
RSI_PERIOD = 14

MIN_ROWS_FOR_SCORE = EMA_TREND_LONG

POINTS_CLOSE_ABOVE_EMA20 = 10
POINTS_EMA20_ABOVE_EMA50 = 15
POINTS_EMA50_ABOVE_EMA200 = 20
POINTS_RSI_HEALTHY = 15  # RSI 50-70
POINTS_RSI_WEAK = 5  # RSI 40-50
POINTS_MACD_ABOVE_SIGNAL = 15
POINTS_MACD_HIST_POSITIVE = 10
POINTS_MACD_HIST_RISING = 10  # son 3 gun artan histogram

MAX_RAW_SCORE = (
    POINTS_CLOSE_ABOVE_EMA20
    + POINTS_EMA20_ABOVE_EMA50
    + POINTS_EMA50_ABOVE_EMA200
    + POINTS_RSI_HEALTHY
    + POINTS_MACD_ABOVE_SIGNAL
    + POINTS_MACD_HIST_POSITIVE
    + POINTS_MACD_HIST_RISING
)  # 95 - toplam 100'e normalize edilir

Status = Literal["WEAK", "WATCH", "PROMISING", "STRONG"]


@dataclass(frozen=True)
class OpportunityScore:
    """0-100 arasi "Firsat Skoru". Yatirim tavsiyesi veya AL/SAT sinyali degildir.

    Yetersiz gecmis veri varsa score/status None olur ve unavailable_reason doldurulur.
    """

    score: int | None
    status: Status | None
    reasons: tuple[str, ...]
    unavailable_reason: str | None = None


def calculate_technical_indicators(price_data: pd.DataFrame) -> pd.DataFrame:
    """Date+Close fiyat verisinden EMA20/50/200, RSI14 ve MACD hesaplar."""
    close = price_data["Close"]
    macd = calculate_macd(close)

    return pd.DataFrame(
        {
            "Date": price_data["Date"],
            "Close": close,
            f"EMA_{EMA_TREND_SHORT}": calculate_ema(close, EMA_TREND_SHORT),
            f"EMA_{EMA_TREND_MID}": calculate_ema(close, EMA_TREND_MID),
            f"EMA_{EMA_TREND_LONG}": calculate_ema(close, EMA_TREND_LONG),
            f"RSI_{RSI_PERIOD}": calculate_rsi(close, RSI_PERIOD),
            "MACD": macd.macd_line,
            "MACD_Signal": macd.signal_line,
            "MACD_Hist": macd.histogram,
        }
    )


def _score_signals(
    *,
    close: float,
    ema20: float,
    ema50: float,
    ema200: float,
    rsi: float,
    macd: float,
    macd_signal: float,
    macd_hist_last3: tuple[float, float, float] | None,
) -> tuple[int, tuple[str, ...]]:
    """Skaler degerlerden ham (0-95, henuz normalize edilmemis) puan + sebepler uretir.

    NaN olan degerler ilgili kurali sessizce atlar (yetersiz veri, hata degil).
    """
    raw = 0
    reasons: list[str] = []

    # Trend
    if pd.notna(close) and pd.notna(ema20) and close > ema20:
        raw += POINTS_CLOSE_ABOVE_EMA20
        reasons.append(f"Close > EMA{EMA_TREND_SHORT}.")
    if pd.notna(ema20) and pd.notna(ema50) and ema20 > ema50:
        raw += POINTS_EMA20_ABOVE_EMA50
        reasons.append(f"EMA{EMA_TREND_SHORT} > EMA{EMA_TREND_MID}.")
    if pd.notna(ema50) and pd.notna(ema200) and ema50 > ema200:
        raw += POINTS_EMA50_ABOVE_EMA200
        reasons.append(f"EMA{EMA_TREND_MID} > EMA{EMA_TREND_LONG}.")

    # Momentum (RSI>75 asiri alim, RSI<35 icin ozel dal yok - zaten
    # asagidaki araliklarin disinda kaldiklari icin 0 puan aliyorlar)
    if pd.notna(rsi):
        if 50 <= rsi <= 70:
            raw += POINTS_RSI_HEALTHY
            reasons.append("RSI 50-70 araliginda (saglikli momentum).")
        elif 40 <= rsi < 50:
            raw += POINTS_RSI_WEAK
            reasons.append("RSI 40-50 araliginda (zayif momentum).")

    # MACD
    if pd.notna(macd) and pd.notna(macd_signal) and macd > macd_signal:
        raw += POINTS_MACD_ABOVE_SIGNAL
        reasons.append("MACD sinyal cizgisinin ustunde.")
    if macd_hist_last3 is not None:
        oldest, middle, newest = macd_hist_last3
        if pd.notna(newest) and newest > 0:
            raw += POINTS_MACD_HIST_POSITIVE
            reasons.append("MACD histogram pozitif.")
        if (
            pd.notna(oldest)
            and pd.notna(middle)
            and pd.notna(newest)
            and newest > middle > oldest
        ):
            raw += POINTS_MACD_HIST_RISING
            reasons.append("MACD histogram son 3 gundur yukseliyor.")

    return raw, tuple(reasons)


def _status_for(score: int) -> Status:
    if score >= 75:
        return "STRONG"
    if score >= 60:
        return "PROMISING"
    if score >= 40:
        return "WATCH"
    return "WEAK"


def calculate_opportunity_score(indicators: pd.DataFrame) -> OpportunityScore:
    """indicators.calculate_technical_indicators ciktisinin son satirini puanlar.

    EMA200'un anlamli olmasi icin en az MIN_ROWS_FOR_SCORE gunluk veri
    gerekir; yetersizse skor uretilmez ama program cokmez.
    """
    if len(indicators) < MIN_ROWS_FOR_SCORE:
        reason = (
            f"Yetersiz gecmis veri: EMA{EMA_TREND_LONG} icin en az "
            f"{MIN_ROWS_FOR_SCORE} gun gerekli, mevcut {len(indicators)} gun."
        )
        return OpportunityScore(None, None, (), reason)

    latest = indicators.iloc[-1]
    hist_tail = indicators["MACD_Hist"].iloc[-3:]
    macd_hist_last3 = tuple(hist_tail) if len(hist_tail) == 3 else None

    raw, reasons = _score_signals(
        close=latest["Close"],
        ema20=latest[f"EMA_{EMA_TREND_SHORT}"],
        ema50=latest[f"EMA_{EMA_TREND_MID}"],
        ema200=latest[f"EMA_{EMA_TREND_LONG}"],
        rsi=latest[f"RSI_{RSI_PERIOD}"],
        macd=latest["MACD"],
        macd_signal=latest["MACD_Signal"],
        macd_hist_last3=macd_hist_last3,
    )

    normalized = round(raw * 100 / MAX_RAW_SCORE)
    normalized = max(0, min(100, normalized))

    return OpportunityScore(normalized, _status_for(normalized), reasons)
