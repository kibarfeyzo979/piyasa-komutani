"""Sonuclari Excel dosyasina yazma."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from piyasa_komutani.data import PortfolioRow
from piyasa_komutani.scoring import ScoreResult

DEFAULT_OUTPUT_PATH = Path("output/sonuclar.xlsx")

HEADERS = [
    "Symbol",
    "Type",
    "Quantity",
    "Avg Cost",
    "Currency",
    "Close",
    "Score",
    "Recommendation",
    "Reasons",
]


@dataclass(frozen=True)
class ReportRow:
    """Bir portfoy satirinin fiyat + skor bilgisiyle birlestirilmis hali.

    close_price/score, sembol icin veri uretilemediyse (market_data
    senkronizasyonu basarisiz olmasi veya cache bulunmamasi gibi) None olur.
    """

    portfolio: PortfolioRow
    close_price: float | None
    score: ScoreResult | None


def _row_to_cells(row: ReportRow) -> list[object]:
    portfolio = row.portfolio
    close_cell = "Veri yok" if row.close_price is None else row.close_price

    if row.score is None:
        return [
            portfolio.symbol,
            portfolio.asset_type,
            portfolio.quantity,
            portfolio.average_cost,
            portfolio.currency,
            close_cell,
            "",
            "VERI YOK",
            "",
        ]

    if row.score.score is None:
        return [
            portfolio.symbol,
            portfolio.asset_type,
            portfolio.quantity,
            portfolio.average_cost,
            portfolio.currency,
            close_cell,
            "",
            row.score.unavailable_reason or "VERI YOK",
            "",
        ]

    return [
        portfolio.symbol,
        portfolio.asset_type,
        portfolio.quantity,
        portfolio.average_cost,
        portfolio.currency,
        row.close_price,
        row.score.score,
        row.score.recommendation,
        "; ".join(row.score.reasons),
    ]


def write_report(rows: list[ReportRow], path: Path = DEFAULT_OUTPUT_PATH) -> None:
    """Rapor satirlarini bir Excel dosyasina yazar. Ust dizin yoksa olusturur."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sonuclar"

    sheet.append(HEADERS)
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for row in rows:
        sheet.append(_row_to_cells(row))

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
