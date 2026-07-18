import logging
from pathlib import Path

from piyasa_komutani.data import read_portfolio
from piyasa_komutani.display import render_portfolio_table
from piyasa_komutani.market_data import sync_portfolio_symbols

PORTFOLIO_PATH = Path(__file__).resolve().parent / "portfolio.csv"
MARKET_DATA_DIR = Path(__file__).resolve().parent / "data" / "market_data"

STATUS_LABELS = {
    "fresh": "guncel",
    "updated": "guncellendi",
    "failed": "HATA",
}


def main() -> None:
    try:
        rows, errors = read_portfolio(PORTFOLIO_PATH)
    except OSError as exc:
        print(f"Portfoy dosyasi okunamadi ({PORTFOLIO_PATH}): {exc}")
        return

    if errors:
        print("Hatali satirlar:")
        for error in errors:
            print(f"  - {error}")
        print()

    if rows:
        symbols = [row.symbol for row in rows]
        sync_results = sync_portfolio_symbols(symbols, cache_dir=MARKET_DATA_DIR)

        print("Piyasa verisi:")
        for result in sync_results:
            label = STATUS_LABELS[result.status]
            suffix = f" ({result.message})" if result.message else ""
            print(f"  - {result.symbol}: {label}{suffix}")
        print()

        print(render_portfolio_table(rows), end="")
    else:
        print("Gosterilecek gecerli portfoy satiri yok.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    main()
