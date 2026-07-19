import logging
from pathlib import Path

from piyasa_komutani.data import read_universe
from piyasa_komutani.display import render_scanner_table
from piyasa_komutani.opportunity_scanner import load_min_average_volume, scan_universe, write_opportunities_csv

UNIVERSE_PATH = Path(__file__).resolve().parent / "data" / "universe.csv"
MARKET_DATA_DIR = Path(__file__).resolve().parent / "data" / "market_data"
CONFIG_PATH = Path(__file__).resolve().parent / "config.toml"
REPORT_PATH = Path(__file__).resolve().parent / "reports" / "opportunities.csv"

TOP_N = 10


def main() -> None:
    try:
        rows, errors = read_universe(UNIVERSE_PATH)
    except OSError as exc:
        print(f"Evren dosyasi okunamadi ({UNIVERSE_PATH}): {exc}")
        return

    if errors:
        print("Hatali satirlar:")
        for error in errors:
            print(f"  - {error}")
        print()

    if not any(row.enabled for row in rows):
        print("Taranacak aktif (enabled=true) sembol yok.")
        return

    min_average_volume = load_min_average_volume(CONFIG_PATH)
    report = scan_universe(rows, cache_dir=MARKET_DATA_DIR, min_average_volume=min_average_volume)

    for outcome in report.outcomes:
        suffix = f" - {outcome.message}" if outcome.message else ""
        print(f"{outcome.symbol} {outcome.status.upper()}{suffix}")
    print()

    top_count = min(TOP_N, len(report.candidates))
    print(f"Ilk {top_count} firsat adayi:")
    print(render_scanner_table(report.candidates, limit=TOP_N), end="")
    print()

    try:
        write_opportunities_csv(report.candidates, REPORT_PATH)
        print(f"Sonuclar yazildi: {REPORT_PATH}")
    except OSError as exc:
        print(f"CSV yazilamadi ({REPORT_PATH}): {exc}")
    print()

    print(f"Scanned: {report.scanned}")
    print(f"Successful: {report.successful}")
    print(f"Failed: {report.failed}")
    print(f"Strong: {report.strong_count}")
    print(f"Promising: {report.promising_count}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    main()
