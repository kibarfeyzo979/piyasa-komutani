import argparse
import logging
from pathlib import Path

from piyasa_komutani.data import PortfolioRow, read_portfolio, read_universe
from piyasa_komutani.display import (
    OpportunityRow,
    render_opportunity_table,
    render_portfolio_table,
    render_position_table,
    render_scanner_table,
)
from piyasa_komutani.export import ReportRow, write_report
from piyasa_komutani.indicators import calculate_indicators
from piyasa_komutani.market_data import load_cached_prices, sync_portfolio_symbols
from piyasa_komutani.opportunity_scanner import load_min_average_volume, scan_universe, write_opportunities_csv
from piyasa_komutani.portfolio_analysis import (
    build_portfolio_analysis_report,
    load_concentration_thresholds,
    write_portfolio_analysis_csv,
    write_portfolio_summary_json,
)
from piyasa_komutani.scoring import score_latest
from piyasa_komutani.technical_analysis import (
    OpportunityScore,
    TrendScore,
    calculate_opportunity_score,
    calculate_technical_indicators,
    calculate_trend_score,
)

PORTFOLIO_PATH = Path(__file__).resolve().parent / "portfolio.csv"
MARKET_DATA_DIR = Path(__file__).resolve().parent / "data" / "market_data"
OUTPUT_PATH = Path(__file__).resolve().parent / "output" / "sonuclar.xlsx"
UNIVERSE_PATH = Path(__file__).resolve().parent / "data" / "universe.csv"
CONFIG_PATH = Path(__file__).resolve().parent / "config.toml"
REPORT_PATH = Path(__file__).resolve().parent / "reports" / "opportunities.csv"
ANALYSIS_CSV_PATH = Path(__file__).resolve().parent / "reports" / "portfolio_analysis.csv"
SUMMARY_JSON_PATH = Path(__file__).resolve().parent / "reports" / "portfolio_summary.json"

SCAN_TOP_N = 10

STATUS_LABELS = {
    "fresh": "guncel",
    "updated": "guncellendi",
    "failed": "HATA",
}


def _build_report_rows(rows: list[PortfolioRow]) -> list[ReportRow]:
    report_rows: list[ReportRow] = []
    for portfolio_row in rows:
        prices = load_cached_prices(portfolio_row.symbol, cache_dir=MARKET_DATA_DIR)
        if prices is None or prices.empty:
            report_rows.append(ReportRow(portfolio_row, None, None))
            continue

        indicators = calculate_indicators(prices)
        score = score_latest(indicators)
        close_price = float(indicators["Close"].iloc[-1])
        report_rows.append(ReportRow(portfolio_row, close_price, score))

    return report_rows


def _build_opportunity_rows(rows: list[PortfolioRow]) -> list[OpportunityRow]:
    opportunity_rows: list[OpportunityRow] = []
    for portfolio_row in rows:
        prices = load_cached_prices(portfolio_row.symbol, cache_dir=MARKET_DATA_DIR)
        if prices is None or prices.empty:
            unavailable = TrendScore(None, None, (), "Cache'lenmis veri yok.")
            opportunity_rows.append(
                OpportunityRow(
                    portfolio_row.symbol,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    unavailable,
                    OpportunityScore(None, None, (), "Cache'lenmis veri yok."),
                )
            )
            continue

        ta = calculate_technical_indicators(prices)
        trend = calculate_trend_score(ta)
        opportunity = calculate_opportunity_score(ta, trend)
        latest = ta.iloc[-1]
        opportunity_rows.append(
            OpportunityRow(
                portfolio_row.symbol,
                latest["Close"],
                latest["EMA_20"],
                latest["EMA_50"],
                latest["EMA_200"],
                latest["RSI_14"],
                latest["MACD_Hist"],
                trend,
                opportunity,
            )
        )

    return opportunity_rows


def run_portfolio() -> None:
    """Portfoy analizini calistirir: piyasa verisi, firsat puani, Excel export, teknik analiz tablosu."""
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

        report_rows = _build_report_rows(rows)

        print("Firsat puani:")
        for report_row in report_rows:
            symbol = report_row.portfolio.symbol
            if report_row.score is None:
                print(f"  - {symbol}: veri yok")
            elif report_row.score.score is None:
                print(f"  - {symbol}: {report_row.score.unavailable_reason}")
            else:
                print(f"  - {symbol}: {report_row.score.score} ({report_row.score.recommendation})")
        print()

        try:
            write_report(report_rows, OUTPUT_PATH)
            print(f"Sonuclar yazildi: {OUTPUT_PATH}")
        except OSError as exc:
            print(f"Excel dosyasi yazilamadi ({OUTPUT_PATH}): {exc}")
        print()

        opportunity_rows = _build_opportunity_rows(rows)
        print("Teknik Analiz / Firsat Skoru:")
        print(render_opportunity_table(opportunity_rows), end="")
        print()

        print(render_portfolio_table(rows), end="")
    else:
        print("Gosterilecek gecerli portfoy satiri yok.")


def run_scan() -> None:
    """Opportunity Scanner'i calistirir: universe.csv taramasi, ilk 10 aday, CSV export."""
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

    top_count = min(SCAN_TOP_N, len(report.candidates))
    print(f"Ilk {top_count} firsat adayi:")
    print(render_scanner_table(report.candidates, limit=SCAN_TOP_N), end="")
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
    print(f"High Opportunity: {report.high_opportunity_count}")
    print(f"Interesting: {report.interesting_count}")


def run_analyze() -> None:
    """Portfoy Position Health analizini calistirir: degerleme, saglik skoru,
    yogunlasma riski, scanner karsilastirmasi, terminal ozeti, CSV/JSON raporlari."""
    try:
        portfolio_rows, portfolio_errors = read_portfolio(PORTFOLIO_PATH)
    except OSError as exc:
        print(f"Portfoy dosyasi okunamadi ({PORTFOLIO_PATH}): {exc}")
        return

    if portfolio_errors:
        print("Hatali portfoy satirlari:")
        for error in portfolio_errors:
            print(f"  - {error}")
        print()

    if not portfolio_rows:
        print("Analiz edilecek gecerli portfoy satiri yok.")
        return

    portfolio_symbols = [row.symbol for row in portfolio_rows]
    sync_portfolio_symbols(portfolio_symbols, cache_dir=MARKET_DATA_DIR)

    try:
        universe_rows, universe_errors = read_universe(UNIVERSE_PATH)
    except OSError as exc:
        print(f"Evren dosyasi okunamadi ({UNIVERSE_PATH}): {exc} - karsilastirma alternatifsiz devam edecek.")
        universe_rows, universe_errors = [], []

    if universe_errors:
        print("Hatali evren satirlari:")
        for error in universe_errors:
            print(f"  - {error}")
        print()

    min_average_volume = load_min_average_volume(CONFIG_PATH)
    scan_report = scan_universe(universe_rows, cache_dir=MARKET_DATA_DIR, min_average_volume=min_average_volume)

    single_threshold, top3_threshold = load_concentration_thresholds(CONFIG_PATH)
    report = build_portfolio_analysis_report(
        portfolio_rows,
        scan_report.candidates,
        cache_dir=MARKET_DATA_DIR,
        single_position_threshold_pct=single_threshold,
        top3_threshold_pct=top3_threshold,
    )

    print("PORTFOLIO SUMMARY")
    for totals in report.summary.totals_by_currency:
        pl_pct = f"{totals.total_unrealized_pl_pct:.2f}%" if totals.total_unrealized_pl_pct is not None else "-"
        print(f"  Total Value ({totals.currency}): {totals.total_market_value:.2f}")
        print(f"  Total Cost ({totals.currency}): {totals.total_cost_value:.2f}")
        print(f"  Unrealized P/L ({totals.currency}): {totals.total_unrealized_pl:.2f} ({pl_pct})")
        if totals.warnings:
            for warning in totals.warnings:
                print(f"  Concentration Risk: {warning}")
        else:
            print(f"  Concentration Risk ({totals.currency}): Yok")
    print()

    print("POSITIONS")
    print(render_position_table(report.positions), end="")
    print()

    print("WEAK POSITIONS")
    if report.weak_positions:
        for position in report.weak_positions:
            print(
                f"  - {position.symbol}: Health Score {position.health.score} (WEAK), "
                f"Trend Score {position.trend.score}"
            )
    else:
        print("  Yok")
    print()

    print("HIGH OPPORTUNITY ALTERNATIVES")
    if report.high_opportunity_alternatives:
        for candidate in report.high_opportunity_alternatives:
            print(
                f"  - {candidate.symbol}: Opportunity Score {candidate.opportunity.score} "
                f"(HIGH_OPPORTUNITY), Trend Score {candidate.trend.score}"
            )
    else:
        print("  Yok")
    print()

    try:
        write_portfolio_analysis_csv(report.positions, ANALYSIS_CSV_PATH)
        print(f"Sonuclar yazildi: {ANALYSIS_CSV_PATH}")
    except OSError as exc:
        print(f"CSV yazilamadi ({ANALYSIS_CSV_PATH}): {exc}")

    try:
        write_portfolio_summary_json(report, SUMMARY_JSON_PATH)
        print(f"Ozet yazildi: {SUMMARY_JSON_PATH}")
    except OSError as exc:
        print(f"JSON yazilamadi ({SUMMARY_JSON_PATH}): {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="main.py", description="Piyasa Komutani CLI")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("portfolio", help="Portfoy analizini calistirir (varsayilan)")
    subparsers.add_parser("scan", help="Opportunity Scanner'i calistirir")
    subparsers.add_parser("analyze", help="Portfoy Position Health analizini calistirir")

    args = parser.parse_args()
    command = args.command or "portfolio"

    if command == "portfolio":
        run_portfolio()
    elif command == "scan":
        run_scan()
    else:
        run_analyze()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    main()
