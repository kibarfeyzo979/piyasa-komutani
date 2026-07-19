"""Portfoy verisinin terminalde gorsellestirilmesi."""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO

import pandas as pd
from rich import box
from rich.console import Console
from rich.table import Table

from piyasa_komutani.data import PortfolioRow
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
