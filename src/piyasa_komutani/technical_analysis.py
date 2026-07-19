"""EMA20/50/200, RSI14 ve MACD tabanli Trend Score ve Opportunity Score.

Saf hesaplama modulu: indicators.py'nin genel EMA/RSI/MACD
fonksiyonlarini farkli periyotlarla yeniden kullanir, ama
market_data.py'yi (indirme/cache) hic bilmez. indicators.py/scoring.py
ile ayni pipeline'a dahil degildir - bagimsiz, ek bir analiz.

Trend Score, bir varligin mevcut trendinin ne kadar guclu oldugunu
olcer (saf teknik durum). Opportunity Score, Trend Score'u GIRDI olarak
alip "yeni giris acisindan ne kadar ilginc" sorusuna cevap arayan ayri
bir hesap - asiri uzama/RSI asiri alim/asiri getiri gibi giris
zamanlamasi sinyalleriyle Trend Score'u yukari/asagi ayarlar.

Bu modulun urettigi skorlar yatirim tavsiyesi veya AL/SAT sinyali
degildir; sadece basit, aciklanabilir puanlardir. Tum metrikler
(pct_change, .diff(N), ayni-satir EMA/Close farki) causal'dir -
yalnizca t anindaki ve oncesindeki veriyi kullanir, look-ahead bias
yoktur.
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

# --- Trend Score puanlari (toplam tam 100, normalize gerekmiyor) ---
POINTS_TREND_CLOSE_ABOVE_EMA20 = 10
POINTS_TREND_EMA20_ABOVE_EMA50 = 15
POINTS_TREND_EMA50_ABOVE_EMA200 = 15
POINTS_TREND_RSI_HEALTHY = 10  # RSI 50-70
POINTS_TREND_MACD_BULLISH = 20  # MACD > Signal (Hist > 0 ile matematiksel olarak ayni - tek kural)
POINTS_TREND_RETURN_20D_POSITIVE = 10
POINTS_TREND_EMA20_SLOPE_POSITIVE = 10
POINTS_TREND_EMA50_SLOPE_POSITIVE = 10

TREND_MAX_SCORE = (
    POINTS_TREND_CLOSE_ABOVE_EMA20
    + POINTS_TREND_EMA20_ABOVE_EMA50
    + POINTS_TREND_EMA50_ABOVE_EMA200
    + POINTS_TREND_RSI_HEALTHY
    + POINTS_TREND_MACD_BULLISH
    + POINTS_TREND_RETURN_20D_POSITIVE
    + POINTS_TREND_EMA20_SLOPE_POSITIVE
    + POINTS_TREND_EMA50_SLOPE_POSITIVE
)  # 100

# --- Opportunity Score ayarlamalari (taban = Trend Score) ---
OVEREXTENDED_TREND_THRESHOLD = 60
OVEREXTENDED_DISTANCE_PCT = 8.0
PENALTY_OVEREXTENDED = 20

RSI_OVERBOUGHT_THRESHOLD = 75
PENALTY_RSI_OVERBOUGHT = 15

EXTREME_RETURN_20D_PCT = 20.0
PENALTY_EXTREME_RETURN = 15

BONUS_MACD_CROSS_UP = 15

RSI_NEUTRAL_RISING_MIN = 45
RSI_NEUTRAL_RISING_MAX = 60
BONUS_RSI_RISING_NEUTRAL = 10

SUPPORT_DISTANCE_PCT = 2.0
BONUS_NEAR_SUPPORT = 10

MOMENTUM_STRENGTHENING_TREND_MIN = 40
MOMENTUM_STRENGTHENING_TREND_MAX = 80  # ust sinir haric (VERY_STRONG_TREND disarida)
BONUS_MOMENTUM_STRENGTHENING = 10

TrendStatus = Literal["WEAK_TREND", "NEUTRAL_TREND", "STRONG_TREND", "VERY_STRONG_TREND"]
OpportunityStatus = Literal["LOW", "WATCH", "INTERESTING", "HIGH_OPPORTUNITY"]


@dataclass(frozen=True)
class TrendScore:
    """0-100 arasi "Trend Score". Mevcut trendin gucunu olcer.

    Yetersiz gecmis veri varsa score/status None olur ve unavailable_reason doldurulur.
    """

    score: int | None
    status: TrendStatus | None
    reasons: tuple[str, ...]
    unavailable_reason: str | None = None


@dataclass(frozen=True)
class OpportunityScore:
    """0-100 arasi "Opportunity Score". Yeni giris acisindan cazibeyi olcer.

    Yatirim tavsiyesi veya AL/SAT sinyali degildir. reasons, "+ ..." /
    "- ..." onekli aciklanabilir cumlelerden olusur. Yetersiz gecmis
    veri varsa score/status None olur ve unavailable_reason doldurulur.
    """

    score: int | None
    status: OpportunityStatus | None
    reasons: tuple[str, ...]
    unavailable_reason: str | None = None


def calculate_return_pct(close: pd.Series, period: int) -> pd.Series:
    """Son `period` gundeki yuzde getiriyi hesaplar (causal: sadece t ve t-period)."""
    return close.pct_change(periods=period) * 100


def calculate_distance_from_ema_pct(close: pd.Series, ema: pd.Series) -> pd.Series:
    """Kapanis fiyatinin EMA'dan yuzde uzakligini hesaplar (ayni satirda, causal)."""
    return (close - ema) / ema * 100


def calculate_slope(series: pd.Series, period: int = 5) -> pd.Series:
    """Bir serinin `period` gun onceki degerine gore degisimini (egimini) hesaplar."""
    return series.diff(periods=period)


def calculate_technical_indicators(price_data: pd.DataFrame) -> pd.DataFrame:
    """Date+Close fiyat verisinden EMA20/50/200, RSI14, MACD ve turetilmis metrikleri hesaplar."""
    close = price_data["Close"]
    ema20 = calculate_ema(close, EMA_TREND_SHORT)
    ema50 = calculate_ema(close, EMA_TREND_MID)
    macd = calculate_macd(close)
    rsi = calculate_rsi(close, RSI_PERIOD)

    return pd.DataFrame(
        {
            "Date": price_data["Date"],
            "Close": close,
            f"EMA_{EMA_TREND_SHORT}": ema20,
            f"EMA_{EMA_TREND_MID}": ema50,
            f"EMA_{EMA_TREND_LONG}": calculate_ema(close, EMA_TREND_LONG),
            f"RSI_{RSI_PERIOD}": rsi,
            "MACD": macd.macd_line,
            "MACD_Signal": macd.signal_line,
            "MACD_Hist": macd.histogram,
            "Return_5D": calculate_return_pct(close, 5),
            "Return_20D": calculate_return_pct(close, 20),
            "Distance_EMA20_Pct": calculate_distance_from_ema_pct(close, ema20),
            "Distance_EMA50_Pct": calculate_distance_from_ema_pct(close, ema50),
            "EMA20_Slope": calculate_slope(ema20, 5),
            "EMA50_Slope": calculate_slope(ema50, 5),
            "RSI_Change_3D": rsi.diff(periods=3),
            "MACD_Hist_Change_3D": macd.histogram.diff(periods=3),
        }
    )


def _score_trend(
    *,
    close: float,
    ema20: float,
    ema50: float,
    ema200: float,
    rsi: float,
    macd: float,
    macd_signal: float,
    return_20d: float,
    ema20_slope: float,
    ema50_slope: float,
) -> tuple[int, tuple[str, ...]]:
    """Skaler degerlerden Trend Score'u (0-100) ve sebepleri hesaplar.

    NaN olan degerler ilgili kurali sessizce atlar (yetersiz veri, hata degil).
    """
    score = 0
    reasons: list[str] = []

    # Trend yapisi
    if pd.notna(close) and pd.notna(ema20) and close > ema20:
        score += POINTS_TREND_CLOSE_ABOVE_EMA20
        reasons.append(f"Close > EMA{EMA_TREND_SHORT}.")
    if pd.notna(ema20) and pd.notna(ema50) and ema20 > ema50:
        score += POINTS_TREND_EMA20_ABOVE_EMA50
        reasons.append(f"EMA{EMA_TREND_SHORT} > EMA{EMA_TREND_MID}.")
    if pd.notna(ema50) and pd.notna(ema200) and ema50 > ema200:
        score += POINTS_TREND_EMA50_ABOVE_EMA200
        reasons.append(f"EMA{EMA_TREND_MID} > EMA{EMA_TREND_LONG}.")

    # Momentum
    if pd.notna(rsi) and 50 <= rsi <= 70:
        score += POINTS_TREND_RSI_HEALTHY
        reasons.append("RSI 50-70 araliginda (saglikli momentum).")
    if pd.notna(macd) and pd.notna(macd_signal) and macd > macd_signal:
        score += POINTS_TREND_MACD_BULLISH
        reasons.append("MACD sinyal cizgisinin ustunde (histogram pozitif).")

    # Trend surekliligi
    if pd.notna(return_20d) and return_20d > 0:
        score += POINTS_TREND_RETURN_20D_POSITIVE
        reasons.append("Son 20 gunde pozitif getiri.")
    if pd.notna(ema20_slope) and ema20_slope > 0:
        score += POINTS_TREND_EMA20_SLOPE_POSITIVE
        reasons.append(f"EMA{EMA_TREND_SHORT} egimi pozitif.")
    if pd.notna(ema50_slope) and ema50_slope > 0:
        score += POINTS_TREND_EMA50_SLOPE_POSITIVE
        reasons.append(f"EMA{EMA_TREND_MID} egimi pozitif.")

    return score, tuple(reasons)


def _trend_status_for(score: int) -> TrendStatus:
    if score >= 80:
        return "VERY_STRONG_TREND"
    if score >= 60:
        return "STRONG_TREND"
    if score >= 40:
        return "NEUTRAL_TREND"
    return "WEAK_TREND"


def calculate_trend_score(indicators: pd.DataFrame) -> TrendScore:
    """indicators.calculate_technical_indicators ciktisinin son satirindan Trend Score hesaplar.

    EMA200'un anlamli olmasi icin en az MIN_ROWS_FOR_SCORE gunluk veri
    gerekir; yetersizse skor uretilmez ama program cokmez.
    """
    if len(indicators) < MIN_ROWS_FOR_SCORE:
        reason = (
            f"Yetersiz gecmis veri: EMA{EMA_TREND_LONG} icin en az "
            f"{MIN_ROWS_FOR_SCORE} gun gerekli, mevcut {len(indicators)} gun."
        )
        return TrendScore(None, None, (), reason)

    latest = indicators.iloc[-1]
    score, reasons = _score_trend(
        close=latest["Close"],
        ema20=latest[f"EMA_{EMA_TREND_SHORT}"],
        ema50=latest[f"EMA_{EMA_TREND_MID}"],
        ema200=latest[f"EMA_{EMA_TREND_LONG}"],
        rsi=latest[f"RSI_{RSI_PERIOD}"],
        macd=latest["MACD"],
        macd_signal=latest["MACD_Signal"],
        return_20d=latest["Return_20D"],
        ema20_slope=latest["EMA20_Slope"],
        ema50_slope=latest["EMA50_Slope"],
    )
    return TrendScore(score, _trend_status_for(score), reasons)


def _score_opportunity(
    *,
    trend_score: int,
    trend_status: TrendStatus,
    rsi: float,
    return_20d: float,
    distance_ema20_pct: float,
    distance_ema50_pct: float,
    rsi_change_3d: float,
    macd_hist_prev: float,
    macd_hist_now: float,
    macd_hist_change_3d: float,
) -> tuple[int, tuple[str, ...]]:
    """Trend Score'u taban alip giris-zamanlamasi sinyalleriyle ayarlar.

    Donen deger henuz [0,100] araligina kirpilmamis olabilir (cagiran kirpar).
    NaN olan degerler ilgili kurali sessizce atlar.
    """
    score = trend_score
    reasons: list[str] = []

    if trend_status in ("STRONG_TREND", "VERY_STRONG_TREND"):
        reasons.append("+ Trend is healthy.")
    elif trend_status == "WEAK_TREND":
        reasons.append("- Trend is weak.")

    # Cezalar
    if (
        trend_score >= OVEREXTENDED_TREND_THRESHOLD
        and pd.notna(distance_ema20_pct)
        and distance_ema20_pct > OVEREXTENDED_DISTANCE_PCT
    ):
        score -= PENALTY_OVEREXTENDED
        reasons.append("- Price extended far above EMA20.")
    if pd.notna(rsi) and rsi > RSI_OVERBOUGHT_THRESHOLD:
        score -= PENALTY_RSI_OVERBOUGHT
        reasons.append("- RSI overbought.")
    if pd.notna(return_20d) and return_20d > EXTREME_RETURN_20D_PCT:
        score -= PENALTY_EXTREME_RETURN
        reasons.append("- 20-day return already high.")

    # Bonuslar
    if pd.notna(macd_hist_prev) and pd.notna(macd_hist_now) and macd_hist_prev <= 0 and macd_hist_now > 0:
        score += BONUS_MACD_CROSS_UP
        reasons.append("+ MACD momentum improving (bullish cross).")
    if pd.notna(rsi) and pd.notna(rsi_change_3d) and RSI_NEUTRAL_RISING_MIN <= rsi <= RSI_NEUTRAL_RISING_MAX and rsi_change_3d > 0:
        score += BONUS_RSI_RISING_NEUTRAL
        reasons.append("+ RSI rising from neutral zone.")
    near_ema20 = pd.notna(distance_ema20_pct) and abs(distance_ema20_pct) <= SUPPORT_DISTANCE_PCT
    near_ema50 = pd.notna(distance_ema50_pct) and abs(distance_ema50_pct) <= SUPPORT_DISTANCE_PCT
    if near_ema20 or near_ema50:
        score += BONUS_NEAR_SUPPORT
        reasons.append("+ Price near EMA20/EMA50 support.")
    if (
        MOMENTUM_STRENGTHENING_TREND_MIN <= trend_score < MOMENTUM_STRENGTHENING_TREND_MAX
        and pd.notna(macd_hist_change_3d)
        and macd_hist_change_3d > 0
    ):
        score += BONUS_MOMENTUM_STRENGTHENING
        reasons.append("+ Momentum strengthening.")

    return score, tuple(reasons)


def _opportunity_status_for(score: int) -> OpportunityStatus:
    if score >= 75:
        return "HIGH_OPPORTUNITY"
    if score >= 60:
        return "INTERESTING"
    if score >= 40:
        return "WATCH"
    return "LOW"


def calculate_opportunity_score(indicators: pd.DataFrame, trend: TrendScore) -> OpportunityScore:
    """Trend Score'u taban alip indicators'in son satirindan Opportunity Score hesaplar.

    trend.score None ise (yetersiz veri) Opportunity Score de uretilemez.
    """
    if trend.score is None or trend.status is None:
        return OpportunityScore(None, None, (), trend.unavailable_reason)

    latest = indicators.iloc[-1]
    hist = indicators["MACD_Hist"]
    macd_hist_prev = hist.iloc[-2] if len(hist) >= 2 else float("nan")
    macd_hist_now = hist.iloc[-1]

    raw, reasons = _score_opportunity(
        trend_score=trend.score,
        trend_status=trend.status,
        rsi=latest[f"RSI_{RSI_PERIOD}"],
        return_20d=latest["Return_20D"],
        distance_ema20_pct=latest["Distance_EMA20_Pct"],
        distance_ema50_pct=latest["Distance_EMA50_Pct"],
        rsi_change_3d=latest["RSI_Change_3D"],
        macd_hist_prev=macd_hist_prev,
        macd_hist_now=macd_hist_now,
        macd_hist_change_3d=latest["MACD_Hist_Change_3D"],
    )

    clamped = max(0, min(100, raw))
    return OpportunityScore(clamped, _opportunity_status_for(clamped), reasons)
