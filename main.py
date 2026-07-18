from pathlib import Path

from piyasa_komutani.data import read_portfolio
from piyasa_komutani.display import render_portfolio_table

PORTFOLIO_PATH = Path(__file__).resolve().parent / "portfolio.csv"


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
        print(render_portfolio_table(rows), end="")
    else:
        print("Gosterilecek gecerli portfoy satiri yok.")


if __name__ == "__main__":
    main()
