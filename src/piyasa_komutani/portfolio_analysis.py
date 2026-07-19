"""Portfoy pozisyonlarini teknik acidan degerlendirip Position Health Score uretir.

Mevcut technical_analysis.py (Trend Score, Opportunity Score) ve
market_data.py (cache) modullerini oldugu gibi yeniden kullanir -
gosterge/skor matematigi burada tekrar yazilmaz. opportunity_scanner.py
sonuclariyla (OpportunityCandidate) karsilastirma yapar ama "AL/SAT"
onerisi uretmez - yalnizca "Weak Portfolio Positions" ve
"High Opportunity Alternatives" olarak ayri listeler sunar.

Hesaplama mantigi (bu modul) terminal/CSV/JSON yazma mantigindan
tamamen ayridir; bu modul dosya/ekran G/C yapmaz (rapor yazicilari
haric - onlar da saf I/O, hesaplama icermez).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

import pandas as pd

from piyasa_komutani.config import load_toml_value
from piyasa_komutani.data import PortfolioRow
from piyasa_komutani.market_data import DEFAULT_CACHE_DIR, load_cached_prices
from piyasa_komutani.opportunity_scanner import OpportunityCandidate
from piyasa_komutani.technical_analysis import (
    OpportunityScore,
    TrendScore,
    calculate_opportunity_score,
    calculate_technical_indicators,
    calculate_trend_score,
)

DEFAULT_SINGLE_POSITION_THRESHOLD_PCT = 25.0
DEFAULT_TOP3_THRESHOLD_PCT = 60.0
DEFAULT_ANALYSIS_CSV_PATH = Path("reports/portfolio_analysis.csv")
DEFAULT_SUMMARY_JSON_PATH = Path("reports/portfolio_summary.json")

# --- Position Health Score puanlari (taban=50, notr baslangic) ---
HEALTH_BASE_SCORE = 50
HEALTH_TREND_SCORE_THRESHOLD = 60
RSI_HEALTHY_MIN = 45
RSI_HEALTHY_MAX = 70
RSI_WEAK_THRESHOLD = 40
STRONG_NEGATIVE_RETURN_5D_PCT = -5.0

POINTS_HEALTH_TREND_STRONG = 15
POINTS_HEALTH_PRICE_ABOVE_EMAS = 10
POINTS_HEALTH_BULLISH_ALIGNMENT = 15
POINTS_HEALTH_MACD_POSITIVE = 10
POINTS_HEALTH_RSI_HEALTHY = 10

PENALTY_HEALTH_PRICE_BELOW_EMA20 = 10
PENALTY_HEALTH_PRICE_BELOW_EMA50 = 10
PENALTY_HEALTH_EMA20_BELOW_EMA50 = 15
PENALTY_HEALTH_MACD_NEGATIVE = 10
PENALTY_HEALTH_RSI_WEAK = 10
PENALTY_HEALTH_SHARP_DECLINE_5D = 10
PENALTY_HEALTH_NEGATIVE_20D = 10

HealthStatus = Literal["WEAK", "CAUTION", "HEALTHY", "STRONG"]
ActionHint = Literal["HOLD_CANDIDATE", "MONITOR", "REVIEW", "RISK_ALERT"]

ANALYSIS_CSV_COLUMNS = [
    "Symbol",
    "Currency",
    "Quantity",
    "Average Cost",
    "Current Price",
    "Market Value",
    "Cost Value",
    "Unrealized P/L",
    "Unrealized P/L %",
    "Portfolio Weight %",
    "Trend Score",
    "Trend Status",
    "Opportunity Score",
    "Opportunity Status",
    "Health Score",
    "Health Status",
    "Action Hint",
]


@dataclass(frozen=True)
class PositionHealth:
    """0-100 arasi "Position Health Score". Pozisyonun elde tutulma kalitesini olcer.

    Yetersiz gecmis veri varsa score/status None olur ve unavailable_reason doldurulur.
    """

    score: int | None
    status: HealthStatus | None
    reasons: tuple[str, ...]
    unavailable_reason: str | None = None


@dataclass(frozen=True)
class PositionAnalysis:
    """Bir portfoy pozisyonunun degerleme + teknik skor + saglik + eylem ipucu birlesimi."""

    symbol: str
    quantity: float
    average_cost: float
    currency: str
    current_price: float | None
    market_value: float | None
    cost_value: float
    unrealized_pl: float | None
    unrealized_pl_pct: float | None
    weight_pct: float | None
    trend: TrendScore
    opportunity: OpportunityScore
    health: PositionHealth
    action_hint: ActionHint | None


@dataclass(frozen=True)
class CurrencyTotals:
    """Bir para birimi grubu icin portfoy toplamlari ve yogunlasma riski."""

    currency: str
    total_market_value: float
    total_cost_value: float
    total_unrealized_pl: float
    total_unrealized_pl_pct: float | None
    largest_position_symbol: str | None
    largest_position_weight_pct: float | None
    top3_weight_pct: float | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class PortfolioSummary:
    """Portfoy seviyesinde ozet: para birimi bazinda toplamlar + saglik dagilimi."""

    totals_by_currency: tuple[CurrencyTotals, ...]
    strong_count: int
    healthy_count: int
    caution_count: int
    weak_count: int


@dataclass(frozen=True)
class PortfolioAnalysisReport:
    """Bir portfoy analizinin tam sonucu."""

    positions: list[PositionAnalysis]
    summary: PortfolioSummary
    weak_positions: list[PositionAnalysis]
    high_opportunity_alternatives: list[OpportunityCandidate]


def load_concentration_thresholds(config_path: Path) -> tuple[float, float]:
    """config.toml'un [portfolio_analysis] esiklerini okur; eksikse varsayilana duser."""
    single = load_toml_value(
        config_path, "portfolio_analysis", "single_position_threshold_pct", DEFAULT_SINGLE_POSITION_THRESHOLD_PCT
    )
    top3 = load_toml_value(config_path, "portfolio_analysis", "top3_threshold_pct", DEFAULT_TOP3_THRESHOLD_PCT)
    return single, top3


def _health_status_for(score: int) -> HealthStatus:
    if score >= 80:
        return "STRONG"
    if score >= 60:
        return "HEALTHY"
    if score >= 40:
        return "CAUTION"
    return "WEAK"


def _score_health(
    *,
    trend_score: float,
    close: float,
    ema20: float,
    ema50: float,
    ema200: float,
    macd_hist: float,
    rsi: float,
    return_5d: float,
    return_20d: float,
) -> tuple[int, tuple[str, ...]]:
    """Skaler degerlerden Position Health Score'u (henuz kirpilmamis) ve sebepleri hesaplar.

    NaN olan degerler ilgili kurali sessizce atlar (yetersiz veri, hata degil).
    """
    score = HEALTH_BASE_SCORE
    reasons: list[str] = []

    if pd.notna(trend_score) and trend_score >= HEALTH_TREND_SCORE_THRESHOLD:
        score += POINTS_HEALTH_TREND_STRONG
        reasons.append("+ Long-term trend strong.")

    if pd.notna(close) and pd.notna(ema20) and pd.notna(ema50) and close > ema20 and close > ema50:
        score += POINTS_HEALTH_PRICE_ABOVE_EMAS
        reasons.append("+ Price above EMA20 and EMA50.")

    if pd.notna(ema20) and pd.notna(ema50) and pd.notna(ema200) and ema20 > ema50 > ema200:
        score += POINTS_HEALTH_BULLISH_ALIGNMENT
        reasons.append("+ Bullish EMA alignment (EMA20 > EMA50 > EMA200).")

    if pd.notna(macd_hist):
        if macd_hist > 0:
            score += POINTS_HEALTH_MACD_POSITIVE
            reasons.append("+ MACD momentum positive.")
        elif macd_hist < 0:
            score -= PENALTY_HEALTH_MACD_NEGATIVE
            reasons.append("- MACD momentum negative.")

    if pd.notna(rsi):
        if RSI_HEALTHY_MIN <= rsi <= RSI_HEALTHY_MAX:
            score += POINTS_HEALTH_RSI_HEALTHY
            reasons.append("+ RSI in healthy range.")
        elif rsi < RSI_WEAK_THRESHOLD:
            score -= PENALTY_HEALTH_RSI_WEAK
            reasons.append("- RSI weak (below 40).")

    if pd.notna(close) and pd.notna(ema20) and close < ema20:
        score -= PENALTY_HEALTH_PRICE_BELOW_EMA20
        reasons.append("- Price below EMA20.")

    if pd.notna(close) and pd.notna(ema50) and close < ema50:
        score -= PENALTY_HEALTH_PRICE_BELOW_EMA50
        reasons.append("- Price below EMA50.")

    if pd.notna(ema20) and pd.notna(ema50) and ema20 < ema50:
        score -= PENALTY_HEALTH_EMA20_BELOW_EMA50
        reasons.append("- EMA20 below EMA50 (bearish crossover).")

    if pd.notna(return_5d) and return_5d <= STRONG_NEGATIVE_RETURN_5D_PCT:
        score -= PENALTY_HEALTH_SHARP_DECLINE_5D
        reasons.append("- Sharp short-term decline (5-day).")

    if pd.notna(return_20d) and return_20d < 0:
        score -= PENALTY_HEALTH_NEGATIVE_20D
        reasons.append("- 20-day trend negative.")

    return score, tuple(reasons)


def calculate_position_health(indicators: pd.DataFrame, trend: TrendScore) -> PositionHealth:
    """indicators'in son satirindan (technical_analysis.calculate_technical_indicators
    ciktisi) ve trend'den Position Health Score hesaplar. trend.score None ise
    (yetersiz veri) health de uretilemez."""
    if trend.score is None:
        return PositionHealth(None, None, (), trend.unavailable_reason)

    latest = indicators.iloc[-1]
    raw, reasons = _score_health(
        trend_score=trend.score,
        close=latest["Close"],
        ema20=latest["EMA_20"],
        ema50=latest["EMA_50"],
        ema200=latest["EMA_200"],
        macd_hist=latest["MACD_Hist"],
        rsi=latest["RSI_14"],
        return_5d=latest["Return_5D"],
        return_20d=latest["Return_20D"],
    )
    clamped = max(0, min(100, raw))
    return PositionHealth(clamped, _health_status_for(clamped), reasons)


def _determine_action_hint(
    health: PositionHealth,
    trend: TrendScore,
    weight_pct: float | None,
    single_position_threshold_pct: float,
) -> ActionHint | None:
    """Deterministik eylem ipucu (AL/SAT degil). Asiri yogun + zayif trend her zaman kazanir."""
    if health.status is None:
        return None

    if weight_pct is not None and weight_pct > single_position_threshold_pct and trend.status == "WEAK_TREND":
        return "RISK_ALERT"

    if health.status in ("STRONG", "HEALTHY"):
        return "HOLD_CANDIDATE"
    if health.status == "CAUTION":
        return "MONITOR" if health.score is not None and health.score >= 50 else "REVIEW"
    return "REVIEW"  # WEAK


def _analyze_single_position(row: PortfolioRow, cache_dir: Path) -> PositionAnalysis:
    """Bir pozisyonu weight_pct/action_hint OLMADAN analiz eder (portfoy toplami henuz bilinmiyor)."""
    cost_value = row.quantity * row.average_cost
    prices = load_cached_prices(row.symbol, cache_dir=cache_dir)

    if prices is None or prices.empty:
        reason = "Cache'lenmis veri yok."
        unavailable_trend = TrendScore(None, None, (), reason)
        unavailable_opportunity = OpportunityScore(None, None, (), reason)
        unavailable_health = PositionHealth(None, None, (), reason)
        return PositionAnalysis(
            symbol=row.symbol,
            quantity=row.quantity,
            average_cost=row.average_cost,
            currency=row.currency,
            current_price=None,
            market_value=None,
            cost_value=cost_value,
            unrealized_pl=None,
            unrealized_pl_pct=None,
            weight_pct=None,
            trend=unavailable_trend,
            opportunity=unavailable_opportunity,
            health=unavailable_health,
            action_hint=None,
        )

    indicators = calculate_technical_indicators(prices)
    trend = calculate_trend_score(indicators)
    opportunity = calculate_opportunity_score(indicators, trend)
    health = calculate_position_health(indicators, trend)

    current_price = float(indicators["Close"].iloc[-1])
    market_value = row.quantity * current_price
    unrealized_pl = market_value - cost_value
    unrealized_pl_pct = unrealized_pl / cost_value * 100

    return PositionAnalysis(
        symbol=row.symbol,
        quantity=row.quantity,
        average_cost=row.average_cost,
        currency=row.currency,
        current_price=current_price,
        market_value=market_value,
        cost_value=cost_value,
        unrealized_pl=unrealized_pl,
        unrealized_pl_pct=unrealized_pl_pct,
        weight_pct=None,
        trend=trend,
        opportunity=opportunity,
        health=health,
        action_hint=None,
    )


def analyze_portfolio(
    rows: list[PortfolioRow],
    cache_dir: Path = DEFAULT_CACHE_DIR,
    *,
    single_position_threshold_pct: float = DEFAULT_SINGLE_POSITION_THRESHOLD_PCT,
) -> list[PositionAnalysis]:
    """Her pozisyonu analiz eder. Iki gecis: (1) fiyat/skor/health, (2) para birimi
    grubu bazinda Portfolio Weight % ve Action Hint."""
    partial_positions = [_analyze_single_position(row, cache_dir) for row in rows]

    totals_by_currency: dict[str, float] = {}
    for position in partial_positions:
        if position.market_value is not None:
            totals_by_currency[position.currency] = (
                totals_by_currency.get(position.currency, 0.0) + position.market_value
            )

    positions: list[PositionAnalysis] = []
    for position in partial_positions:
        currency_total = totals_by_currency.get(position.currency, 0.0)
        weight_pct = (
            position.market_value / currency_total * 100
            if position.market_value is not None and currency_total > 0
            else None
        )
        action_hint = _determine_action_hint(
            position.health, position.trend, weight_pct, single_position_threshold_pct
        )
        positions.append(replace(position, weight_pct=weight_pct, action_hint=action_hint))

    return positions


def summarize_portfolio(
    positions: list[PositionAnalysis],
    *,
    single_position_threshold_pct: float = DEFAULT_SINGLE_POSITION_THRESHOLD_PCT,
    top3_threshold_pct: float = DEFAULT_TOP3_THRESHOLD_PCT,
) -> PortfolioSummary:
    """Pozisyonlari para birimine gore gruplayip her grup icin toplam + yogunlasma riski hesaplar."""
    by_currency: dict[str, list[PositionAnalysis]] = {}
    for position in positions:
        by_currency.setdefault(position.currency, []).append(position)

    totals: list[CurrencyTotals] = []
    for currency, group in by_currency.items():
        valued = [p for p in group if p.market_value is not None]
        total_market_value = sum(p.market_value for p in valued)
        total_cost_value = sum(p.cost_value for p in group)
        total_unrealized_pl = sum(p.unrealized_pl for p in valued)
        total_unrealized_pl_pct = (
            total_unrealized_pl / total_cost_value * 100 if total_cost_value > 0 else None
        )

        by_value_desc = sorted(valued, key=lambda p: p.market_value, reverse=True)
        largest = by_value_desc[0] if by_value_desc else None
        top3 = by_value_desc[:3]
        top3_weight_pct = (
            sum(p.weight_pct for p in top3 if p.weight_pct is not None) if top3 else None
        )

        warnings: list[str] = []
        if largest is not None and largest.weight_pct is not None and largest.weight_pct > single_position_threshold_pct:
            warnings.append(
                f"HIGH concentration: {largest.symbol} alone is {largest.weight_pct:.1f}% "
                f"of the {currency} portfolio."
            )
        if top3_weight_pct is not None and top3_weight_pct > top3_threshold_pct:
            warnings.append(f"Top 3 positions are {top3_weight_pct:.1f}% of the {currency} portfolio.")

        totals.append(
            CurrencyTotals(
                currency=currency,
                total_market_value=total_market_value,
                total_cost_value=total_cost_value,
                total_unrealized_pl=total_unrealized_pl,
                total_unrealized_pl_pct=total_unrealized_pl_pct,
                largest_position_symbol=largest.symbol if largest else None,
                largest_position_weight_pct=largest.weight_pct if largest else None,
                top3_weight_pct=top3_weight_pct,
                warnings=tuple(warnings),
            )
        )

    return PortfolioSummary(
        totals_by_currency=tuple(totals),
        strong_count=sum(1 for p in positions if p.health.status == "STRONG"),
        healthy_count=sum(1 for p in positions if p.health.status == "HEALTHY"),
        caution_count=sum(1 for p in positions if p.health.status == "CAUTION"),
        weak_count=sum(1 for p in positions if p.health.status == "WEAK"),
    )


def find_weak_positions(positions: list[PositionAnalysis]) -> list[PositionAnalysis]:
    """Health Status == WEAK olan pozisyonlari dondurur."""
    return [position for position in positions if position.health.status == "WEAK"]


def find_high_opportunity_alternatives(
    candidates: list[OpportunityCandidate], portfolio_symbols: set[str]
) -> list[OpportunityCandidate]:
    """Scanner adaylarindan HIGH_OPPORTUNITY olup portfoyde ZATEN bulunmayanlari dondurur."""
    return [
        candidate
        for candidate in candidates
        if candidate.opportunity.status == "HIGH_OPPORTUNITY" and candidate.symbol not in portfolio_symbols
    ]


def build_portfolio_analysis_report(
    portfolio_rows: list[PortfolioRow],
    scanner_candidates: list[OpportunityCandidate],
    *,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    single_position_threshold_pct: float = DEFAULT_SINGLE_POSITION_THRESHOLD_PCT,
    top3_threshold_pct: float = DEFAULT_TOP3_THRESHOLD_PCT,
) -> PortfolioAnalysisReport:
    """Portfoy analizini + ozetini + zayif pozisyon/alternatif karsilastirmasini birlestirir."""
    positions = analyze_portfolio(
        portfolio_rows, cache_dir, single_position_threshold_pct=single_position_threshold_pct
    )
    summary = summarize_portfolio(
        positions,
        single_position_threshold_pct=single_position_threshold_pct,
        top3_threshold_pct=top3_threshold_pct,
    )
    weak_positions = find_weak_positions(positions)
    portfolio_symbols = {row.symbol for row in portfolio_rows}
    alternatives = find_high_opportunity_alternatives(scanner_candidates, portfolio_symbols)

    return PortfolioAnalysisReport(
        positions=positions,
        summary=summary,
        weak_positions=weak_positions,
        high_opportunity_alternatives=alternatives,
    )


def _analysis_row_to_cells(position: PositionAnalysis) -> list[object]:
    return [
        position.symbol,
        position.currency,
        position.quantity,
        position.average_cost,
        position.current_price,
        position.market_value,
        position.cost_value,
        position.unrealized_pl,
        position.unrealized_pl_pct,
        position.weight_pct,
        position.trend.score,
        position.trend.status,
        position.opportunity.score,
        position.opportunity.status,
        position.health.score,
        position.health.status,
        position.action_hint,
    ]


def write_portfolio_analysis_csv(
    positions: list[PositionAnalysis], path: Path = DEFAULT_ANALYSIS_CSV_PATH
) -> None:
    """Tum pozisyonlari CSV'ye atomik olarak yazar (once gecici dosyaya, sonra yerine tasir)."""
    rows = [_analysis_row_to_cells(position) for position in positions]
    data = pd.DataFrame(rows, columns=ANALYSIS_CSV_COLUMNS)

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    data.to_csv(tmp_path, index=False)
    tmp_path.replace(path)


def write_portfolio_summary_json(
    report: PortfolioAnalysisReport, path: Path = DEFAULT_SUMMARY_JSON_PATH
) -> None:
    """Portfoy ozetini JSON'a atomik olarak yazar (once gecici dosyaya, sonra yerine tasir)."""
    payload = {
        "totals_by_currency": [
            {
                "currency": totals.currency,
                "total_market_value": totals.total_market_value,
                "total_cost_value": totals.total_cost_value,
                "total_unrealized_pl": totals.total_unrealized_pl,
                "total_unrealized_pl_pct": totals.total_unrealized_pl_pct,
                "largest_position_symbol": totals.largest_position_symbol,
                "largest_position_weight_pct": totals.largest_position_weight_pct,
                "top3_weight_pct": totals.top3_weight_pct,
                "warnings": list(totals.warnings),
            }
            for totals in report.summary.totals_by_currency
        ],
        "health_counts": {
            "strong": report.summary.strong_count,
            "healthy": report.summary.healthy_count,
            "caution": report.summary.caution_count,
            "weak": report.summary.weak_count,
        },
        "weak_positions": [position.symbol for position in report.weak_positions],
        "high_opportunity_alternatives": [
            candidate.symbol for candidate in report.high_opportunity_alternatives
        ],
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(path)
