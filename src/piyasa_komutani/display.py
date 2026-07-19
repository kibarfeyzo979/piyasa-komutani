"""Portfoy verisinin terminalde gorsellestirilmesi."""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO

import pandas as pd
from rich import box
from rich.console import Console
from rich.table import Table

from piyasa_komutani.data import PortfolioRow
from piyasa_komutani.opportunity_scanner import OpportunityCandidate
from piyasa_komutani.portfolio_analysis import PositionAnalysis
from piyasa_komutani.technical_analysis import OpportunityScore, TrendScore


def render_portfolio_table(rows: list[PortfolioRow]) -> str:
    """Portfoy satirlarini rich ile bicimlendirilmis bir tablo metnine donusturur."""
    table = Table(show_header=True, header_style="bold", box=box.ASCII)
    table.add_column("Symbol")
    table.add_column("Type")
    table.add_column("Quantity", justify="right")
    table.add_column("Avg Cost", justify="right")
    table.add_column("Currency")

    for row in rows:
        table.add_row(
            row.symbol,
            row.asset_type,
            f"{row.quantity:g}",
            f"{row.average_cost:.2f}",
            row.currency,
        )

    buffer = StringIO()
    console = Console(file=buffer, width=100, no_color=True)
    console.print(table)
    return buffer.getvalue()


@dataclass(frozen=True)
class OpportunityRow:
    """Bir sembolun teknik gostergeleri + Trend Score + Opportunity Score'un birlestirilmis hali."""

    symbol: str
    close: float | None
    ema20: float | None
    ema50: float | None
    ema200: float | None
    rsi: float | None
    macd_hist: float | None
    trend: TrendScore
    opportunity: OpportunityScore


def _format_number(value: float | None, fmt: str = ".2f") -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{value:{fmt}}"


def render_opportunity_table(rows: list[OpportunityRow]) -> str:
    """OpportunityRow listesini rich ile bicimlendirilmis bir tablo metnine donusturur.

    Skor uretilemeyen semboller icin sayisal kolonlar '-' gosterilir,
    Status kolonlarina nedeni yazilir.
    """
    table = Table(show_header=True, header_style="bold", box=box.ASCII)
    table.add_column("Symbol")
    table.add_column("Close", justify="right")
    table.add_column("EMA20", justify="right")
    table.add_column("EMA50", justify="right")
    table.add_column("EMA200", justify="right")
    table.add_column("RSI", justify="right")
    table.add_column("MACD Histogram", justify="right")
    table.add_column("Trend Score", justify="right")
    table.add_column("Trend Status")
    table.add_column("Opportunity Score", justify="right")
    table.add_column("Opportunity Status")

    for row in rows:
        trend = row.trend
        opportunity = row.opportunity
        trend_status_text = trend.status if trend.status is not None else (trend.unavailable_reason or "-")
        opportunity_status_text = (
            opportunity.status if opportunity.status is not None else (opportunity.unavailable_reason or "-")
        )
        table.add_row(
            row.symbol,
            _format_number(row.close),
            _format_number(row.ema20),
            _format_number(row.ema50),
            _format_number(row.ema200),
            _format_number(row.rsi, ".1f"),
            _format_number(row.macd_hist, ".3f"),
            str(trend.score) if trend.score is not None else "-",
            trend_status_text,
            str(opportunity.score) if opportunity.score is not None else "-",
            opportunity_status_text,
        )

    buffer = StringIO()
    console = Console(file=buffer, width=200, no_color=True)
    console.print(table)
    return buffer.getvalue()


def render_scanner_table(candidates: list[OpportunityCandidate], *, limit: int | None = None) -> str:
    """Siralanmis firsat adaylarini rich ile bicimlendirilmis bir tablo metnine donusturur.

    limit verilirse yalnizca ilk `limit` aday gosterilir (Rank hep 1'den baslar).
    """
    table = Table(show_header=True, header_style="bold", box=box.ASCII)
    table.add_column("Rank", justify="right")
    table.add_column("Symbol")
    table.add_column("Close", justify="right")
    table.add_column("EMA20", justify="right")
    table.add_column("EMA50", justify="right")
    table.add_column("EMA200", justify="right")
    table.add_column("RSI", justify="right")
    table.add_column("MACD Histogram", justify="right")
    table.add_column("Average Volume 20", justify="right")
    table.add_column("Trend Score", justify="right")
    table.add_column("Trend Status")
    table.add_column("Opportunity Score", justify="right")
    table.add_column("Opportunity Status")
    table.add_column("Return 20D", justify="right")
    table.add_column("Distance EMA20 %", justify="right")

    rows_to_show = candidates if limit is None else candidates[:limit]
    for rank, candidate in enumerate(rows_to_show, start=1):
        table.add_row(
            str(rank),
            candidate.symbol,
            _format_number(candidate.close),
            _format_number(candidate.ema20),
            _format_number(candidate.ema50),
            _format_number(candidate.ema200),
            _format_number(candidate.rsi, ".1f"),
            _format_number(candidate.macd_hist, ".3f"),
            _format_number(candidate.average_volume_20, ",.0f"),
            str(candidate.trend.score),
            candidate.trend.status or "-",
            str(candidate.opportunity.score),
            candidate.opportunity.status or "-",
            _format_number(candidate.return_20d, ".2f"),
            _format_number(candidate.distance_ema20_pct, ".2f"),
        )

    buffer = StringIO()
    console = Console(file=buffer, width=230, no_color=True)
    console.print(table)
    return buffer.getvalue()


def render_position_table(positions: list[PositionAnalysis]) -> str:
    """Portfoy pozisyonlarinin ozet analiz tablosunu rich ile bicimlendirir.

    Tam detay (Market Value, Cost Value vb.) CSV'de; bu, terminal icin
    kisaltilmis bir gorunum.
    """
    table = Table(show_header=True, header_style="bold", box=box.ASCII)
    table.add_column("Symbol")
    table.add_column("Weight %", justify="right")
    table.add_column("P/L %", justify="right")
    table.add_column("Trend")
    table.add_column("Health")
    table.add_column("Action Hint")

    for position in positions:
        trend_text = position.trend.status if position.trend.status is not None else "-"
        health_text = position.health.status if position.health.status is not None else "-"
        table.add_row(
            position.symbol,
            _format_number(position.weight_pct),
            _format_number(position.unrealized_pl_pct),
            trend_text,
            health_text,
            position.action_hint or "-",
        )

    buffer = StringIO()
    console = Console(file=buffer, width=100, no_color=True)
    console.print(table)
    return buffer.getvalue()
