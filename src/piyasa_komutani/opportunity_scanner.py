"""Portfoyden bagimsiz bir sembol evrenini tarayip Firsat Skoru'na gore siralar.

Mevcut market_data.py (indirme/cache) ve technical_analysis.py
(gosterge + skor) modullerini oldugu gibi yeniden kullanir. Bu bir
yatirim tavsiyesi/AL-SAT sistemi degildir - yalnizca teknik acidan
guclu firsat adaylarini siralar (bkz. technical_analysis.py).
"""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from piyasa_komutani.data import UniverseRow
from piyasa_komutani.indicators import calculate_average_volume
from piyasa_komutani.market_data import DEFAULT_CACHE_DIR, load_cached_prices, sync_portfolio_symbols
from piyasa_komutani.technical_analysis import (
    OpportunityScore,
    TrendScore,
    calculate_opportunity_score,
    calculate_technical_indicators,
    calculate_trend_score,
)

logger = logging.getLogger(__name__)

DEFAULT_MIN_AVERAGE_VOLUME = 100_000.0
AVERAGE_VOLUME_PERIOD = 20
DEFAULT_REPORT_PATH = Path("reports/opportunities.csv")

CSV_COLUMNS = [
    "Rank",
    "Symbol",
    "Close",
    "EMA20",
    "EMA50",
    "EMA200",
    "RSI",
    "MACD Histogram",
    "Average Volume 20",
    "Trend Score",
    "Trend Status",
    "Opportunity Score",
    "Opportunity Status",
    "Return 20D",
    "Distance EMA20 %",
]


@dataclass(frozen=True)
class ScanOutcome:
    """Ilerleme/ozet icin: her sembol icin OK/ERROR durumu."""

    symbol: str
    status: Literal["ok", "error"]
    message: str | None = None


@dataclass(frozen=True)
class OpportunityCandidate:
    """Basariyla taranmis VE likidite filtresini gecmis bir aday."""

    symbol: str
    close: float
    ema20: float
    ema50: float
    ema200: float
    rsi: float
    macd_hist: float
    average_volume_20: float
    return_20d: float
    distance_ema20_pct: float
    trend: TrendScore
    opportunity: OpportunityScore


@dataclass(frozen=True)
class ScanReport:
    """Bir taramanin tam sonucu: ilerleme kayitlari + siralanmis adaylar."""

    outcomes: list[ScanOutcome]
    candidates: list[OpportunityCandidate]

    @property
    def scanned(self) -> int:
        return len(self.outcomes)

    @property
    def successful(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.status == "ok")

    @property
    def failed(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.status == "error")

    @property
    def high_opportunity_count(self) -> int:
        return sum(1 for candidate in self.candidates if candidate.opportunity.status == "HIGH_OPPORTUNITY")

    @property
    def interesting_count(self) -> int:
        return sum(1 for candidate in self.candidates if candidate.opportunity.status == "INTERESTING")


def load_min_average_volume(config_path: Path) -> float:
    """config.toml'un [scanner].min_average_volume degerini okur.

    Dosya, bolum veya anahtar yoksa ya da TOML bozuksa, sessizce
    DEFAULT_MIN_AVERAGE_VOLUME'a duser (config her zaman opsiyoneldir).
    """
    try:
        with config_path.open("rb") as config_file:
            config = tomllib.load(config_file)
        return float(config["scanner"]["min_average_volume"])
    except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError, ValueError):
        return DEFAULT_MIN_AVERAGE_VOLUME


def _scan_symbol(symbol: str, cache_dir: Path, min_average_volume: float) -> tuple[ScanOutcome, OpportunityCandidate | None]:
    """Tek bir sembolu tarar. Hicbir zaman exception firlatmaz."""
    try:
        prices = load_cached_prices(symbol, cache_dir=cache_dir)
        if prices is None or prices.empty:
            return ScanOutcome(symbol, "error", "Piyasa verisi yok."), None

        indicators = calculate_technical_indicators(prices)
        trend = calculate_trend_score(indicators)
        if trend.score is None:
            return ScanOutcome(symbol, "error", trend.unavailable_reason), None

        opportunity = calculate_opportunity_score(indicators, trend)

        average_volume = calculate_average_volume(prices["Volume"], AVERAGE_VOLUME_PERIOD).iloc[-1]
        if pd.isna(average_volume) or average_volume < min_average_volume:
            return ScanOutcome(symbol, "ok"), None

        latest = indicators.iloc[-1]
        candidate = OpportunityCandidate(
            symbol=symbol,
            close=latest["Close"],
            ema20=latest["EMA_20"],
            ema50=latest["EMA_50"],
            ema200=latest["EMA_200"],
            rsi=latest["RSI_14"],
            macd_hist=latest["MACD_Hist"],
            average_volume_20=average_volume,
            return_20d=latest["Return_20D"],
            distance_ema20_pct=latest["Distance_EMA20_Pct"],
            trend=trend,
            opportunity=opportunity,
        )
        return ScanOutcome(symbol, "ok"), candidate
    except Exception as exc:
        logger.error("Sembol %s taranirken beklenmeyen hata: %s", symbol, exc)
        return ScanOutcome(symbol, "error", str(exc)), None


def scan_universe(
    rows: list[UniverseRow],
    *,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    min_average_volume: float = DEFAULT_MIN_AVERAGE_VOLUME,
) -> ScanReport:
    """Evrendeki enabled=true sembolleri tarar.

    Once market_data.sync_portfolio_symbols ile cache'i gunceller, sonra
    her sembolu bagimsiz tarar - biri basarisiz olsa da digerleri islenir.
    """
    symbols = [row.symbol for row in rows if row.enabled]
    sync_portfolio_symbols(symbols, cache_dir=cache_dir)

    outcomes: list[ScanOutcome] = []
    candidates: list[OpportunityCandidate] = []
    for symbol in symbols:
        outcome, candidate = _scan_symbol(symbol, cache_dir, min_average_volume)
        outcomes.append(outcome)
        if candidate is not None:
            candidates.append(candidate)

    candidates.sort(key=lambda candidate: (candidate.opportunity.score, candidate.trend.score), reverse=True)
    return ScanReport(outcomes, candidates)


def write_opportunities_csv(candidates: list[OpportunityCandidate], path: Path = DEFAULT_REPORT_PATH) -> None:
    """Siralanmis tum adaylari CSV'ye atomik olarak yazar (once gecici dosyaya, sonra yerine tasir)."""
    rows = [
        {
            "Rank": rank,
            "Symbol": candidate.symbol,
            "Close": candidate.close,
            "EMA20": candidate.ema20,
            "EMA50": candidate.ema50,
            "EMA200": candidate.ema200,
            "RSI": candidate.rsi,
            "MACD Histogram": candidate.macd_hist,
            "Average Volume 20": candidate.average_volume_20,
            "Trend Score": candidate.trend.score,
            "Trend Status": candidate.trend.status,
            "Opportunity Score": candidate.opportunity.score,
            "Opportunity Status": candidate.opportunity.status,
            "Return 20D": candidate.return_20d,
            "Distance EMA20 %": candidate.distance_ema20_pct,
        }
        for rank, candidate in enumerate(candidates, start=1)
    ]
    data = pd.DataFrame(rows, columns=CSV_COLUMNS)

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    data.to_csv(tmp_path, index=False)
    tmp_path.replace(path)
