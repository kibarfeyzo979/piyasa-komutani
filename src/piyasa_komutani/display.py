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
from piyasa_komutani.portfolio_analysis import PortfolioSummary, PositionAnalysis
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


def render_portfolio_summary_lines(summary: PortfolioSummary) -> list[str]:
    """PortfolioSummary'yi (para birimi basina Total/Cost/P&L/Concentration) metin
    satirlarina donusturur. main.py'nin 'analyze' ve 'daily' komutlari tarafindan
    paylasilir - ayni hesap iki dosyada tekrar edilmez."""
    lines: list[str] = []
    for totals in summary.totals_by_currency:
        pl_pct = f"{totals.total_unrealized_pl_pct:.2f}%" if totals.total_unrealized_pl_pct is not None else "-"
        lines.append(f"  Total Value ({totals.currency}): {totals.total_market_value:.2f}")
        lines.append(f"  Total Cost ({totals.currency}): {totals.total_cost_value:.2f}")
        lines.append(f"  Unrealized P/L ({totals.currency}): {totals.total_unrealized_pl:.2f} ({pl_pct})")
        if totals.warnings:
            for warning in totals.warnings:
                lines.append(f"  Concentration Risk: {warning}")
        else:
            lines.append(f"  Concentration Risk ({totals.currency}): Yok")
    return lines


def _main_reason(position: PositionAnalysis) -> str:
    """Bir pozisyonun tek satirlik 'ana nedeni': health.reasons icindeki ilk
    negatif ('-') cumle, yoksa ilk reason, o da yoksa unavailable_reason."""
    negative = next((reason for reason in position.health.reasons if reason.startswith("-")), None)
    if negative is not None:
        return negative
    if position.health.reasons:
        return position.health.reasons[0]
    return position.health.unavailable_reason or "-"


def render_review_table(positions: list[PositionAnalysis]) -> str:
    """Gozden gecirilmesi gereken pozisyonlarin (WEAK/CAUTION/RISK_ALERT/veri yok)
    tablosunu rich ile bicimlendirir."""
    table = Table(show_header=True, header_style="bold", box=box.ASCII)
    table.add_column("Symbol")
    table.add_column("Weight %", justify="right")
    table.add_column("P/L %", justify="right")
    table.add_column("Trend Score", justify="right")
    table.add_column("Health Score", justify="right")
    table.add_column("Action Hint")
    table.add_column("Main Reason")

    for position in positions:
        table.add_row(
            position.symbol,
            _format_number(position.weight_pct),
            _format_number(position.unrealized_pl_pct),
            str(position.trend.score) if position.trend.score is not None else "-",
            str(position.health.score) if position.health.score is not None else "-",
            position.action_hint or "-",
            _main_reason(position),
        )

    buffer = StringIO()
    console = Console(file=buffer, width=160, no_color=True)
    console.print(table)
    return buffer.getvalue()


def render_daily_opportunities_table(candidates: list[OpportunityCandidate], *, limit: int | None = None) -> str:
    """Firsat adaylarinin kisaltilmis (Daily Brief icin) tablosunu rich ile bicimlendirir."""
    table = Table(show_header=True, header_style="bold", box=box.ASCII)
    table.add_column("Rank", justify="right")
    table.add_column("Symbol")
    table.add_column("Trend Score", justify="right")
    table.add_column("Opportunity Score", justify="right")
    table.add_column("RSI", justify="right")
    table.add_column("Return 20D", justify="right")
    table.add_column("Distance EMA20 %", justify="right")
    table.add_column("Opportunity Status")

    rows_to_show = candidates if limit is None else candidates[:limit]
    for rank, candidate in enumerate(rows_to_show, start=1):
        table.add_row(
            str(rank),
            candidate.symbol,
            str(candidate.trend.score),
            str(candidate.opportunity.score),
            _format_number(candidate.rsi, ".1f"),
            _format_number(candidate.return_20d, ".2f"),
            _format_number(candidate.distance_ema20_pct, ".2f"),
            candidate.opportunity.status or "-",
        )

    buffer = StringIO()
    console = Console(file=buffer, width=140, no_color=True)
    console.print(table)
    return buffer.getvalue()
