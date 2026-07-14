from pathlib import Path

from piyasa_komutani.data import PortfolioRow, read_portfolio

PORTFOLIO_PATH = Path("portfolio.csv")


def format_table(rows: list[PortfolioRow]) -> str:
    """Portfoy satirlarini hizalanmis bir metin tablosuna donusturur."""
    headers = ["Symbol", "Type", "Quantity", "Avg Cost", "Currency"]
    lines = [
        [
            row.symbol,
            row.asset_type,
            f"{row.quantity:g}",
            f"{row.average_cost:.2f}",
            row.currency,
        ]
        for row in rows
    ]

    widths = [max(len(header), *(len(line[i]) for line in lines)) if lines else len(header) for i, header in enumerate(headers)]

    def format_row(cells: list[str]) -> str:
        return "  ".join(cell.ljust(width) for cell, width in zip(cells, widths, strict=True))

    header_line = format_row(headers)
    separator = "  ".join("-" * width for width in widths)
    body_lines = [format_row(line) for line in lines]
    return "\n".join([header_line, separator, *body_lines])


def main() -> None:
    rows, errors = read_portfolio(PORTFOLIO_PATH)

    if errors:
        print("Hatali satirlar:")
        for error in errors:
            print(f"  - {error}")
        print()

    if rows:
        print(format_table(rows))
    else:
        print("Gosterilecek gecerli portfoy satiri yok.")


if __name__ == "__main__":
    main()
