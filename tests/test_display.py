"""render_portfolio_table testleri."""

from piyasa_komutani.data import PortfolioRow
from piyasa_komutani.display import render_portfolio_table


def test_render_includes_headers_and_rows() -> None:
    rows = [
        PortfolioRow("THYAO.IS", "stock", 100.0, 285.50, "TRY"),
        PortfolioRow("BTC-USD", "crypto", 0.05, 65000.0, "USD"),
    ]

    output = render_portfolio_table(rows)

    assert "Symbol" in output
    assert "Quantity" in output
    assert "THYAO.IS" in output
    assert "285.50" in output
    assert "BTC-USD" in output
    assert "65000.00" in output


def test_render_empty_rows_returns_header_only() -> None:
    output = render_portfolio_table([])

    assert "Symbol" in output
