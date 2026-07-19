"""render_portfolio_table, render_opportunity_table ve render_scanner_table testleri."""

from piyasa_komutani.data import PortfolioRow
from piyasa_komutani.display import (
    OpportunityRow,
    render_opportunity_table,
    render_portfolio_table,
    render_position_table,
    render_scanner_table,
)
from piyasa_komutani.opportunity_scanner import OpportunityCandidate
from piyasa_komutani.portfolio_analysis import PositionAnalysis, PositionHealth
from piyasa_komutani.technical_analysis import OpportunityScore, TrendScore


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
    trend = TrendScore(85, "VERY_STRONG_TREND", ("neden",))
    opportunity = OpportunityScore(72, "INTERESTING", ("+ neden",))
    rows = [OpportunityRow("THYAO.IS", 330.0, 320.0, 300.0, 280.0, 55.5, 0.123, trend, opportunity)]

    output = render_opportunity_table(rows)

    assert "Trend Score" in output
    assert "Opportunity Score" in output
    assert "THYAO.IS" in output
    assert "85" in output
    assert "VERY_STRONG_TREND" in output
    assert "72" in output
    assert "INTERESTING" in output


def test_render_opportunity_table_shows_placeholder_for_unavailable_score() -> None:
    trend = TrendScore(None, None, (), "Yetersiz gecmis veri.")
    opportunity = OpportunityScore(None, None, (), "Yetersiz gecmis veri.")
    rows = [OpportunityRow("BILINMEYEN", None, None, None, None, None, None, trend, opportunity)]

    output = render_opportunity_table(rows)

    assert "Yetersiz gecmis veri." in output
    assert "-" in output


def _candidate(symbol: str, opportunity_score: int, trend_score: int = 70) -> OpportunityCandidate:
    return OpportunityCandidate(
        symbol=symbol,
        close=110.0,
        ema20=105.0,
        ema50=100.0,
        ema200=90.0,
        rsi=60.0,
        macd_hist=1.5,
        average_volume_20=300_000.0,
        return_20d=5.0,
        distance_ema20_pct=1.5,
        trend=TrendScore(trend_score, "STRONG_TREND", ("neden",)),
        opportunity=OpportunityScore(opportunity_score, "INTERESTING", ("+ neden",)),
    )


def test_render_scanner_table_includes_headers_and_rank() -> None:
    candidates = [_candidate("AAA", 90), _candidate("BBB", 80)]

    output = render_scanner_table(candidates)

    assert "Rank" in output
    assert "Average Volume 20" in output
    assert "Trend Score" in output
    assert "Trend Status" in output
    assert "Opportunity Score" in output
    assert "Opportunity Status" in output
    assert "Return 20D" in output
    assert "Distance EMA20 %" in output
    assert "AAA" in output
    assert "BBB" in output
    assert "300,000" in output


def test_render_scanner_table_limit_truncates_results() -> None:
    candidates = [_candidate(f"SYM{i}", 100 - i) for i in range(15)]

    output = render_scanner_table(candidates, limit=10)

    assert "SYM9" in output
    assert "SYM10" not in output


def test_render_position_table_includes_headers_and_values() -> None:
    position = PositionAnalysis(
        symbol="XYZ", quantity=10.0, average_cost=100.0, currency="TRY",
        current_price=110.0, market_value=1100.0, cost_value=1000.0,
        unrealized_pl=100.0, unrealized_pl_pct=10.0, weight_pct=42.5,
        trend=TrendScore(70, "STRONG_TREND", ()),
        opportunity=OpportunityScore(80, "HIGH_OPPORTUNITY", ()),
        health=PositionHealth(75, "HEALTHY", ()),
        action_hint="HOLD_CANDIDATE",
    )

    output = render_position_table([position])

    assert "Weight %" in output
    assert "P/L %" in output
    assert "Action Hint" in output
    assert "XYZ" in output
    assert "42.50" in output
    assert "10.00" in output
    assert "STRONG_TREND" in output
    assert "HEALTHY" in output
    assert "HOLD_CANDIDATE" in output


def test_render_position_table_shows_placeholder_for_unavailable() -> None:
    position = PositionAnalysis(
        symbol="ABC", quantity=1.0, average_cost=10.0, currency="TRY",
        current_price=None, market_value=None, cost_value=10.0,
        unrealized_pl=None, unrealized_pl_pct=None, weight_pct=None,
        trend=TrendScore(None, None, (), "Cache'lenmis veri yok."),
        opportunity=OpportunityScore(None, None, (), "Cache'lenmis veri yok."),
        health=PositionHealth(None, None, (), "Cache'lenmis veri yok."),
        action_hint=None,
    )

    output = render_position_table([position])

    assert "ABC" in output
    assert "-" in output
