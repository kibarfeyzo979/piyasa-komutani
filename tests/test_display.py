"""render_portfolio_table ve render_opportunity_table testleri."""

from piyasa_komutani.data import PortfolioRow
from piyasa_komutani.display import OpportunityRow, render_opportunity_table, render_portfolio_table
from piyasa_komutani.technical_analysis import OpportunityScore


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


def test_render_opportunity_table_includes_headers_and_values() -> None:
    score = OpportunityScore(72, "PROMISING", ("neden",))
    rows = [OpportunityRow("THYAO.IS", 330.0, 320.0, 300.0, 280.0, 55.5, 0.123, score)]

    output = render_opportunity_table(rows)

    assert "Opportunity Score" in output
    assert "Status" in output
    assert "THYAO.IS" in output
    assert "72" in output
    assert "PROMISING" in output


def test_render_opportunity_table_shows_placeholder_for_unavailable_score() -> None:
    score = OpportunityScore(None, None, (), "Yetersiz gecmis veri.")
    rows = [OpportunityRow("BILINMEYEN", None, None, None, None, None, None, score)]

    output = render_opportunity_table(rows)

    assert "Yetersiz gecmis veri." in output
    assert "-" in output
