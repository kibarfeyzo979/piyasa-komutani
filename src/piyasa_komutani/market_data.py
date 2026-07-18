"""yfinance uzerinden gunluk OHLCV fiyat verisi cekme ve yerel CSV cache'i.

Her sembol bagimsiz islenir: bir sembolde hata olmasi digerlerinin
islenmesini engellemez (bkz. sync_portfolio_symbols).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 365
DEFAULT_CACHE_DIR = Path("data/market_data")
OHLCV_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


@dataclass(frozen=True)
class SymbolSyncResult:
    """Tek bir sembol icin senkronizasyon sonucu."""

    symbol: str
    status: Literal["fresh", "updated", "failed"]
    message: str | None = None


def _cache_path(symbol: str, cache_dir: Path) -> Path:
    return cache_dir / f"{symbol}.csv"


def _load_cached(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_csv(path, parse_dates=["Date"])


def _save_cache(path: Path, data: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(path, index=False)


def _last_expected_trading_day(today: date) -> date:
    """Bugunden onceki en son hafta ici (Pazartesi-Cuma) gunu dondurur."""
    day = today - timedelta(days=1)
    while day.weekday() >= 5:  # Cumartesi=5, Pazar=6
        day -= timedelta(days=1)
    return day


def _is_fresh(last_cached_date: date, today: date) -> bool:
    return last_cached_date >= _last_expected_trading_day(today)


def _download_history(symbol: str, start: date, end: date) -> pd.DataFrame:
    """yfinance'ten gunluk OHLCV verisini ceker.

    Bu fonksiyon testlerde monkeypatch ile degistirilerek gercek ag
    erisimi yapilmadan mock'lanir.
    """
    history = yf.Ticker(symbol).history(start=start, end=end, interval="1d", auto_adjust=False)
    if history.empty:
        return pd.DataFrame(columns=["Date", *OHLCV_COLUMNS])

    history = history[OHLCV_COLUMNS].reset_index(names="Date")
    dates = pd.to_datetime(history["Date"])
    if dates.dt.tz is not None:
        dates = dates.dt.tz_localize(None)
    history["Date"] = dates.dt.normalize()
    return history


def _merge(old: pd.DataFrame | None, new: pd.DataFrame) -> pd.DataFrame:
    combined = new if old is None else pd.concat([old, new], ignore_index=True)
    combined = combined.drop_duplicates(subset="Date", keep="last")
    return combined.sort_values("Date").reset_index(drop=True)


def sync_symbol(symbol: str, cache_dir: Path, *, today: date | None = None) -> SymbolSyncResult:
    """Tek bir sembolun fiyat gecmisini cache ile senkronize eder.

    Ag/veri hatalarinda exception firlatmaz; SymbolSyncResult(status="failed")
    doner ve hatayi loglar.
    """
    resolved_today = today if today is not None else date.today()
    path = _cache_path(symbol, cache_dir)

    try:
        cached = _load_cached(path)
    except Exception:
        logger.exception("Sembol %s icin cache dosyasi okunamadi: %s", symbol, path)
        cached = None

    last_cached_date: date | None = None
    if cached is not None and not cached.empty:
        last_cached_date = cached["Date"].max().date()
        if _is_fresh(last_cached_date, resolved_today):
            return SymbolSyncResult(symbol, "fresh", "cache guncel")
        start = last_cached_date + timedelta(days=1)
    else:
        start = resolved_today - timedelta(days=LOOKBACK_DAYS)

    end = resolved_today + timedelta(days=1)

    try:
        new_data = _download_history(symbol, start, end)
    except Exception as exc:
        logger.error("Sembol %s icin fiyat verisi indirilemedi: %s", symbol, exc)
        return SymbolSyncResult(symbol, "failed", str(exc))

    if new_data.empty:
        if last_cached_date is None:
            message = f"'{symbol}' icin veri bulunamadi."
            logger.error(message)
            return SymbolSyncResult(symbol, "failed", message)
        return SymbolSyncResult(symbol, "fresh", "yeni gun yok")

    merged = _merge(cached, new_data)
    _save_cache(path, merged)

    previous_row_count = 0 if cached is None else len(cached)
    new_day_count = len(merged) - previous_row_count
    logger.info("Sembol %s icin %d yeni gun cache'lendi.", symbol, new_day_count)
    return SymbolSyncResult(symbol, "updated", f"{new_day_count} yeni gun")


def sync_portfolio_symbols(
    symbols: Iterable[str],
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> list[SymbolSyncResult]:
    """Portfoydeki her tekil sembol icin fiyat verisini senkronize eder.

    Bir sembolun basarisiz olmasi digerlerinin islenmesini engellemez.
    """
    unique_symbols = list(dict.fromkeys(symbols))
    return [sync_symbol(symbol, cache_dir) for symbol in unique_symbols]
