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
from piyasa_komutani.technical_analysis import OpportunityScore


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
    """Bir sembolun teknik gostergeleri + Firsat Skoru'nun birlestirilmis hali."""

    symbol: str
    close: float | None
    ema20: float | None
    ema50: float | None
    ema200: float | None
    rsi: float | None
    macd_hist: float | None
    score: OpportunityScore


def _format_number(value: float | None, fmt: str = ".2f") -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{value:{fmt}}"


def render_opportunity_table(rows: list[OpportunityRow]) -> str:
    """OpportunityRow listesini rich ile bicimlendirilmis bir tablo metnine donusturur.

    Skor uretilemeyen semboller icin sayisal kolonlar '-' gosterilir,
    Status kolonuna nedeni yazilir.
    """
    table = Table(show_header=True, header_style="bold", box=box.ASCII)
    table.add_column("Symbol")
    table.add_column("Close", justify="right")
    table.add_column("EMA20", justify="right")
    table.add_column("EMA50", justify="right")
    table.add_column("EMA200", justify="right")
    table.add_column("RSI", justify="right")
    table.add_column("MACD Histogram", justify="right")
    table.add_column("Opportunity Score", justify="right")
    table.add_column("Status")

    for row in rows:
        score = row.score
        status_text = score.status if score.status is not None else (score.unavailable_reason or "-")
        table.add_row(
            row.symbol,
            _format_number(row.close),
            _format_number(row.ema20),
            _format_number(row.ema50),
            _format_number(row.ema200),
            _format_number(row.rsi, ".1f"),
            _format_number(row.macd_hist, ".3f"),
            str(score.score) if score.score is not None else "-",
            status_text,
        )

    buffer = StringIO()
    console = Console(file=buffer, width=160, no_color=True)
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
    table.add_column("Opportunity Score", justify="right")
    table.add_column("Status")

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
            str(candidate.score.score),
            candidate.score.status or "-",
        )

    buffer = StringIO()
    console = Console(file=buffer, width=170, no_color=True)
    console.print(table)
    return buffer.getvalue()
