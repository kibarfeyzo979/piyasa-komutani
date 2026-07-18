"""Portfoy verisinin terminalde gorsellestirilmesi."""

from __future__ import annotations

from io import StringIO

from rich import box
from rich.console import Console
from rich.table import Table

from piyasa_komutani.data import PortfolioRow


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
