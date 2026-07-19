import logging
from pathlib import Path

from piyasa_komutani.data import PortfolioRow, read_portfolio
from piyasa_komutani.display import OpportunityRow, render_opportunity_table, render_portfolio_table
from piyasa_komutani.export import ReportRow, write_report
from piyasa_komutani.indicators import calculate_indicators
from piyasa_komutani.market_data import load_cached_prices, sync_portfolio_symbols
from piyasa_komutani.scoring import score_latest
from piyasa_komutani.technical_analysis import (
    OpportunityScore,
    calculate_opportunity_score,
    calculate_technical_indicators,
)

PORTFOLIO_PATH = Path(__file__).resolve().parent / "portfolio.csv"
MARKET_DATA_DIR = Path(__file__).resolve().parent / "data" / "market_data"
OUTPUT_PATH = Path(__file__).resolve().parent / "output" / "sonuclar.xlsx"

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
            opportunity_rows.append(
                OpportunityRow(
                    portfolio_row.symbol,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    OpportunityScore(None, None, (), "Cache'lenmis veri yok."),
                )
            )
            continue

        ta = calculate_technical_indicators(prices)
        score = calculate_opportunity_score(ta)
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
                score,
            )
        )

    return opportunity_rows


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

        report_rows = _build_report_rows(rows)

        print("Firsat puani:")
        for report_row in report_rows:
            if report_row.score is None:
                print(f"  - {report_row.portfolio.symbol}: veri yok")
            else:
                print(f"  - {report_row.portfolio.symbol}: {report_row.score.score} ({report_row.score.recommendation})")
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    main()
