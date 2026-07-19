"""Portfoy ve sembol evreni CSV dosyalarini okuma ve dogrulama."""

from __future__ import annotations

import csv
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

ALLOWED_ASSET_TYPES = {"stock", "crypto"}
ALLOWED_CURRENCIES = {"TRY", "USD"}
ALLOWED_ENABLED_VALUES = {"true", "false"}

T = TypeVar("T")


def _read_validated_csv(
    path: Path,
    validate_row: Callable[[dict[str, str], int], tuple[T | None, str | None]],
) -> tuple[list[T], list[str]]:
    """CSV'yi DictReader ile okur, her satiri validate_row ile dogrular.

    Gecerli satirlari ve hatali satirlar icin anlasilir hata mesajlarini
    ayri listeler halinde dondurur. Bir satirdaki hata digerlerinin
    islenmesini engellemez.

    Dosya bulunamazsa veya okunamazsa OSError yukselir; bu durumu
    kullaniciya bildirmek cagiranin sorumlulugundadir.
    """
    valid_rows: list[T] = []
    errors: list[str] = []

    with path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        for line_number, raw_row in enumerate(reader, start=2):
            row, error = validate_row(raw_row, line_number)
            if row is not None:
                valid_rows.append(row)
            else:
                assert error is not None
                errors.append(error)

    return valid_rows, errors


@dataclass(frozen=True)
class PortfolioRow:
    """Portfoydeki tek bir varligi temsil eder."""

    symbol: str
    asset_type: str
    quantity: float
    average_cost: float
    currency: str


def _validate_row(raw_row: dict[str, str], line_number: int) -> tuple[PortfolioRow | None, str | None]:
    """Tek bir CSV satirini dogrular.

    Gecerliyse (PortfolioRow, None), degilse (None, hata_mesaji) doner.
    """
    symbol = raw_row.get("symbol", "").strip()
    asset_type = raw_row.get("asset_type", "").strip()
    currency = raw_row.get("currency", "").strip()
    quantity_raw = raw_row.get("quantity", "").strip()
    average_cost_raw = raw_row.get("average_cost", "").strip()

    if not symbol:
        return None, f"Satir {line_number}: symbol bos olamaz."

    if asset_type not in ALLOWED_ASSET_TYPES:
        return None, (
            f"Satir {line_number} ({symbol}): asset_type '{asset_type}' gecersiz, "
            f"yalnizca {sorted(ALLOWED_ASSET_TYPES)} olabilir."
        )

    try:
        quantity = float(quantity_raw)
    except ValueError:
        return None, f"Satir {line_number} ({symbol}): quantity sayisal bir deger olmali, '{quantity_raw}' gecersiz."

    if not math.isfinite(quantity):
        return None, f"Satir {line_number} ({symbol}): quantity sonlu bir sayi olmali, '{quantity_raw}' gecersiz."

    if quantity <= 0:
        return None, f"Satir {line_number} ({symbol}): quantity negatif veya sifir olamaz."

    try:
        average_cost = float(average_cost_raw)
    except ValueError:
        return None, (
            f"Satir {line_number} ({symbol}): average_cost sayisal bir deger olmali, "
            f"'{average_cost_raw}' gecersiz."
        )

    if not math.isfinite(average_cost):
        return None, (
            f"Satir {line_number} ({symbol}): average_cost sonlu bir sayi olmali, "
            f"'{average_cost_raw}' gecersiz."
        )

    if average_cost <= 0:
        return None, f"Satir {line_number} ({symbol}): average_cost negatif veya sifir olamaz."

    if currency not in ALLOWED_CURRENCIES:
        return None, (
            f"Satir {line_number} ({symbol}): currency '{currency}' gecersiz, "
            f"yalnizca {sorted(ALLOWED_CURRENCIES)} olabilir."
        )

    return PortfolioRow(
        symbol=symbol,
        asset_type=asset_type,
        quantity=quantity,
        average_cost=average_cost,
        currency=currency,
    ), None


def read_portfolio(path: Path) -> tuple[list[PortfolioRow], list[str]]:
    """portfolio.csv dosyasini okur ve dogrular."""
    return _read_validated_csv(path, _validate_row)


@dataclass(frozen=True)
class UniverseRow:
    """Tarama evrenindeki (universe.csv) tek bir sembolu temsil eder."""

    symbol: str
    name: str
    market: str
    enabled: bool


def _validate_universe_row(raw_row: dict[str, str], line_number: int) -> tuple[UniverseRow | None, str | None]:
    """Tek bir universe.csv satirini dogrular."""
    symbol = raw_row.get("symbol", "").strip()
    name = raw_row.get("name", "").strip()
    market = raw_row.get("market", "").strip()
    enabled_raw = raw_row.get("enabled", "").strip().lower()

    if not symbol:
        return None, f"Satir {line_number}: symbol bos olamaz."

    if not name:
        return None, f"Satir {line_number} ({symbol}): name bos olamaz."

    if not market:
        return None, f"Satir {line_number} ({symbol}): market bos olamaz."

    if enabled_raw not in ALLOWED_ENABLED_VALUES:
        return None, (
            f"Satir {line_number} ({symbol}): enabled 'true' veya 'false' olmali, "
            f"'{enabled_raw}' gecersiz."
        )

    return UniverseRow(
        symbol=symbol,
        name=name,
        market=market,
        enabled=enabled_raw == "true",
    ), None


def read_universe(path: Path) -> tuple[list[UniverseRow], list[str]]:
    """universe.csv dosyasini okur ve dogrular."""
    return _read_validated_csv(path, _validate_universe_row)
