"""Basit, kural tabanli firsat puani hesaplama.

Saf hesaplama modulu: indicators.py'yi import etmez, yalnizca onun
urettigi DataFrame seklini (Date, Close, EMA_*, RSI_*, MACD,
MACD_Signal, MACD_Hist) tuketir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from piyasa_komutani.indicators import DEFAULT_EMA_LONG, DEFAULT_EMA_SHORT, DEFAULT_RSI_PERIOD

DEFAULT_RSI_OVERSOLD = 30
DEFAULT_RSI_OVERBOUGHT = 70

Recommendation = Literal["GUCLU AL", "AL", "NOTR", "SAT", "GUCLU SAT"]


@dataclass(frozen=True)
class ScoreResult:
    """Kural tabanli firsat puani sonucu.

    Yetersiz gecmis veri veya beklenmeyen kolon adlari durumunda
    score/recommendation None olur ve unavailable_reason doldurulur.
    """

    score: int | None
    recommendation: Recommendation | None
    reasons: tuple[str, ...]
    unavailable_reason: str | None = None


def _recommendation_for(score: int) -> Recommendation:
    if score >= 2:
        return "GUCLU AL"
    if score == 1:
        return "AL"
    if score == 0:
        return "NOTR"
    if score == -1:
        return "SAT"
    return "GUCLU SAT"


def score_row(
    *,
    rsi: float,
    ema_short: float,
    ema_long: float,
    macd: float,
    macd_signal: float,
    rsi_oversold: int = DEFAULT_RSI_OVERSOLD,
    rsi_overbought: int = DEFAULT_RSI_OVERBOUGHT,
) -> ScoreResult:
    """Tek bir zaman noktasindaki skaler indikator degerlerinden puan uretir.

    NaN olan degerler ilgili kurali sessizce atlar (yetersiz veri,
    hata degil).
    """
    score = 0
    reasons: list[str] = []

    if pd.notna(rsi):
        if rsi < rsi_oversold:
            score += 1
            reasons.append("RSI asiri satim bolgesinde, potansiyel alim firsati.")
        elif rsi > rsi_overbought:
            score -= 1
            reasons.append("RSI asiri alim bolgesinde, potansiyel satim sinyali.")

    if pd.notna(ema_short) and pd.notna(ema_long):
        if ema_short > ema_long:
            score += 1
            reasons.append("Kisa vadeli trend yukselis yonlu (EMA kisa > EMA uzun).")
        elif ema_short < ema_long:
            score -= 1
            reasons.append("Kisa vadeli trend dusus yonlu (EMA kisa < EMA uzun).")

    if pd.notna(macd) and pd.notna(macd_signal):
        if macd > macd_signal:
            score += 1
            reasons.append("MACD sinyal cizgisinin ustunde, momentum pozitif.")
        elif macd < macd_signal:
            score -= 1
            reasons.append("MACD sinyal cizgisinin altinda, momentum negatif.")

    return ScoreResult(score, _recommendation_for(score), tuple(reasons))


def score_latest(
    indicators: pd.DataFrame,
    *,
    ema_short: int = DEFAULT_EMA_SHORT,
    ema_long: int = DEFAULT_EMA_LONG,
    rsi_period: int = DEFAULT_RSI_PERIOD,
    rsi_oversold: int = DEFAULT_RSI_OVERSOLD,
    rsi_overbought: int = DEFAULT_RSI_OVERBOUGHT,
) -> ScoreResult:
    """indicators.calculate_indicators ciktisinin son satirini puanlar.

    ema_short/ema_long/rsi_period yalnizca DataFrame'deki dinamik kolon
    isimlerini (EMA_12, RSI_14 gibi) bulmak icin kullanilir; varsayilanlar
    indicators.py'deki sabitlerle aynidir.

    EMA_{ema_long} anlamli olmasi icin en az ema_long/rsi_period kadar
    gunluk veri gerekir; yetersizse (veya kolon adlari eslesmiyorsa)
    skor uretilmez ama exception firlatilmaz.
    """
    min_rows = max(ema_long, rsi_period)
    if len(indicators) < min_rows:
        reason = (
            f"Yetersiz gecmis veri: EMA{ema_long} icin en az {min_rows} gun "
            f"gerekli, mevcut {len(indicators)} gun."
        )
        return ScoreResult(None, None, (), reason)

    latest = indicators.iloc[-1]
    try:
        rsi = latest[f"RSI_{rsi_period}"]
        ema_short_value = latest[f"EMA_{ema_short}"]
        ema_long_value = latest[f"EMA_{ema_long}"]
        macd = latest["MACD"]
        macd_signal = latest["MACD_Signal"]
    except KeyError as exc:
        reason = (
            f"Beklenen indikator kolonu bulunamadi ({exc}): ema_short/ema_long/"
            "rsi_period parametreleri indicators DataFrame'iyle eslesmiyor olabilir."
        )
        return ScoreResult(None, None, (), reason)

    return score_row(
        rsi=rsi,
        ema_short=ema_short_value,
        ema_long=ema_long_value,
        macd=macd,
        macd_signal=macd_signal,
        rsi_oversold=rsi_oversold,
        rsi_overbought=rsi_overbought,
    )
