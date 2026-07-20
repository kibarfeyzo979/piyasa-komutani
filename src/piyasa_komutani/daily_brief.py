"""Portfoy analizi + risk ozeti + Opportunity Scanner sonuclarini tek gunluk raporda birlestirir.

Bu modul YALNIZCA orkestrasyon katmanidir: market_data.py, technical_analysis.py,
portfolio_analysis.py ve opportunity_scanner.py'deki hicbir hesaplama tekrar
yazilmaz. Tek gercekten yeni mantik "Trend Score hizla kotulesen pozisyon"
tespitidir - o da yeni bir formul degil, calculate_trend_score'u (degismeden)
bugunku ve N gun onceki (indicators DataFrame'inin kesilmis bir dilimi
uzerinde, dolayisiyla look-ahead bias icermeyen) veriyle iki kez cagirip
iki sayiyi karsilastirmaktir.

Portfoy ve scanner adimlari birbirinden BAGIMSIZ try/except ile sarilir:
biri basarisiz olsa da digeri rapor uretmeye devam eder.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import pandas as pd

from piyasa_komutani.config import load_toml_value
from piyasa_komutani.data import PortfolioRow, UniverseRow
from piyasa_komutani.market_data import DEFAULT_CACHE_DIR, load_cached_prices
from piyasa_komutani.opportunity_scanner import (
    DEFAULT_MIN_AVERAGE_VOLUME,
    OpportunityCandidate,
    ScanReport,
    scan_universe,
)
from piyasa_komutani.portfolio_analysis import (
    DEFAULT_SINGLE_POSITION_THRESHOLD_PCT,
    DEFAULT_TOP3_THRESHOLD_PCT,
    PortfolioAnalysisReport,
    PositionAnalysis,
    build_portfolio_analysis_report,
)
from piyasa_komutani.technical_analysis import (
    MIN_ROWS_FOR_SCORE,
    calculate_technical_indicators,
    calculate_trend_score,
)

TREND_DETERIORATION_LOOKBACK_DAYS = 10
TREND_DETERIORATION_THRESHOLD = 20

DEFAULT_DAILY_JSON_PATH = Path("reports/daily_brief.json")
DEFAULT_DAILY_CSV_PATH = Path("reports/daily_brief.csv")
DEFAULT_DAILY_MD_PATH = Path("reports/daily_brief.md")

TOP_OPPORTUNITIES_COUNT = 10

CSV_COLUMNS = [
    "Section",
    "Symbol",
    "Weight %",
    "P/L %",
    "Trend Score",
    "Opportunity Score",
    "Health Score",
    "RSI",
    "Return 20D",
    "Distance EMA20 %",
    "Action Hint",
    "Status",
    "Detail",
]

PortfolioCondition = Literal["HEALTHY", "CAUTION", "AT_RISK", "EMPTY", "UNKNOWN"]


@dataclass(frozen=True)
class DailySummaryText:
    """Deterministik, kural tabanli gunluk metin ozeti (bolum G)."""

    portfolio_condition: PortfolioCondition
    main_risk: str
    positions_requiring_review: int
    high_opportunity_candidates: int


@dataclass(frozen=True)
class DailyBrief:
    """Tek gunluk raporun tam sonucu. Portfoy/scanner adimlari birbirinden bagimsiz basarisiz olabilir."""

    generated_at: datetime
    portfolio_status: Literal["OK", "EMPTY", "FAILED"]
    portfolio_error: str | None
    report: PortfolioAnalysisReport | None
    scanner_status: Literal["OK", "FAILED"]
    scanner_error: str | None
    scan_report: ScanReport | None
    risk_alerts: tuple[str, ...]
    deteriorating_positions: tuple[str, ...]
    positions_to_review: list[PositionAnalysis]
    strong_positions: list[PositionAnalysis]
    top_opportunities: list[OpportunityCandidate]
    summary: DailySummaryText


def load_trend_deterioration_settings(config_path: Path) -> tuple[int, int]:
    """config.toml'un [daily_brief] esiklerini okur; eksikse varsayilana duser."""
    lookback_days = load_toml_value(
        config_path, "daily_brief", "trend_deterioration_lookback_days", TREND_DETERIORATION_LOOKBACK_DAYS
    )
    threshold = load_toml_value(
        config_path, "daily_brief", "trend_deterioration_threshold", TREND_DETERIORATION_THRESHOLD
    )
    return lookback_days, threshold


def _detect_trend_deterioration(
    symbol: str,
    cache_dir: Path,
    lookback_days: int,
    threshold: int,
) -> bool:
    """Trend Score'un son `lookback_days` gunde en az `threshold` puan dustugunu tespit eder.

    calculate_trend_score'u (technical_analysis.py, degismeden) bugunku ve
    kesilmis (N gun once biten) bir dilim uzerinde cagirir - yeni bir skor
    formulu degil, look-ahead bias icermeyen bir karsilastirma. Herhangi bir
    hata/yetersiz veri durumunda sessizce False doner (bu kontrol opsiyoneldir).
    """
    try:
        prices = load_cached_prices(symbol, cache_dir=cache_dir)
        if prices is None or len(prices) < MIN_ROWS_FOR_SCORE + lookback_days:
            return False

        full_indicators = calculate_technical_indicators(prices)
        past_trend = calculate_trend_score(full_indicators.iloc[:-lookback_days])
        current_trend = calculate_trend_score(full_indicators)

        if past_trend.score is None or current_trend.score is None:
            return False

        return past_trend.score - current_trend.score >= threshold
    except Exception:
        return False


def _build_risk_alerts(
    report: PortfolioAnalysisReport | None, deteriorating_symbols: tuple[str, ...]
) -> tuple[str, ...]:
    alerts: list[str] = []

    if report is not None:
        for totals in report.summary.totals_by_currency:
            alerts.extend(totals.warnings)
        if report.weak_positions:
            symbols = ", ".join(position.symbol for position in report.weak_positions)
            alerts.append(f"Health Score cok dusuk pozisyon(lar): {symbols}.")

    if deteriorating_symbols:
        symbols = ", ".join(deteriorating_symbols)
        alerts.append(f"Trend Score hizla kotulesen pozisyon(lar): {symbols}.")

    return tuple(alerts)


def _portfolio_condition(
    portfolio_status: Literal["OK", "EMPTY", "FAILED"], report: PortfolioAnalysisReport | None
) -> PortfolioCondition:
    if portfolio_status == "EMPTY":
        return "EMPTY"
    if portfolio_status == "FAILED" or report is None:
        return "UNKNOWN"

    summary = report.summary
    total = summary.strong_count + summary.healthy_count + summary.caution_count + summary.weak_count
    if total == 0:
        return "EMPTY"
    if summary.weak_count / total >= 0.5:
        return "AT_RISK"
    if (summary.weak_count + summary.caution_count) / total >= 0.5:
        return "CAUTION"
    return "HEALTHY"


def _main_risk(report: PortfolioAnalysisReport | None, deteriorating_symbols: tuple[str, ...]) -> str:
    if report is not None:
        has_concentration_warning = any(totals.warnings for totals in report.summary.totals_by_currency)
        if has_concentration_warning:
            return "HIGH CONCENTRATION"
        if report.weak_positions:
            return "WEAK POSITIONS"
    if deteriorating_symbols:
        return "TREND DETERIORATION"
    return "NONE"


def build_daily_brief(
    portfolio_rows: list[PortfolioRow],
    universe_rows: list[UniverseRow],
    *,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    min_average_volume: float = DEFAULT_MIN_AVERAGE_VOLUME,
    single_position_threshold_pct: float = DEFAULT_SINGLE_POSITION_THRESHOLD_PCT,
    top3_threshold_pct: float = DEFAULT_TOP3_THRESHOLD_PCT,
    trend_deterioration_lookback_days: int = TREND_DETERIORATION_LOOKBACK_DAYS,
    trend_deterioration_threshold: int = TREND_DETERIORATION_THRESHOLD,
) -> DailyBrief:
    """Portfoy ve scanner adimlarini bagimsiz calistirip tek bir DailyBrief'te birlestirir.

    Hicbir zaman exception firlatmaz - bir adimin basarisiz olmasi digerini engellemez.
    """
    generated_at = datetime.now()

    scanner_status: Literal["OK", "FAILED"] = "OK"
    scanner_error: str | None = None
    scan_report: ScanReport | None = None
    try:
        scan_report = scan_universe(universe_rows, cache_dir=cache_dir, min_average_volume=min_average_volume)
    except Exception as exc:
        scanner_status = "FAILED"
        scanner_error = str(exc)

    candidates = scan_report.candidates if scan_report is not None else []

    portfolio_status: Literal["OK", "EMPTY", "FAILED"]
    portfolio_error: str | None
    report: PortfolioAnalysisReport | None

    if not portfolio_rows:
        portfolio_status, portfolio_error, report = "EMPTY", None, None
    else:
        try:
            report = build_portfolio_analysis_report(
                portfolio_rows,
                candidates,
                cache_dir=cache_dir,
                single_position_threshold_pct=single_position_threshold_pct,
                top3_threshold_pct=top3_threshold_pct,
            )
            portfolio_status, portfolio_error = "OK", None
        except Exception as exc:
            portfolio_status, portfolio_error, report = "FAILED", str(exc), None

    deteriorating: list[str] = []
    if report is not None:
        for position in report.positions:
            if _detect_trend_deterioration(
                position.symbol, cache_dir, trend_deterioration_lookback_days, trend_deterioration_threshold
            ):
                deteriorating.append(position.symbol)
    deteriorating_positions = tuple(deteriorating)

    if report is not None:
        positions_to_review = [
            position
            for position in report.positions
            if position.health.status in ("WEAK", "CAUTION")
            or position.health.status is None
            or position.action_hint == "RISK_ALERT"
        ]
        strong_positions = [position for position in report.positions if position.health.status == "STRONG"]
        high_opportunity_alternatives_count = len(report.high_opportunity_alternatives)
    else:
        positions_to_review = []
        strong_positions = []
        high_opportunity_alternatives_count = 0

    summary = DailySummaryText(
        portfolio_condition=_portfolio_condition(portfolio_status, report),
        main_risk=_main_risk(report, deteriorating_positions),
        positions_requiring_review=len(positions_to_review),
        high_opportunity_candidates=high_opportunity_alternatives_count,
    )

    return DailyBrief(
        generated_at=generated_at,
        portfolio_status=portfolio_status,
        portfolio_error=portfolio_error,
        report=report,
        scanner_status=scanner_status,
        scanner_error=scanner_error,
        scan_report=scan_report,
        risk_alerts=_build_risk_alerts(report, deteriorating_positions),
        deteriorating_positions=deteriorating_positions,
        positions_to_review=positions_to_review,
        strong_positions=strong_positions,
        top_opportunities=candidates[:TOP_OPPORTUNITIES_COUNT],
        summary=summary,
    )


def _main_reason_text(position: PositionAnalysis) -> str:
    negative = next((reason for reason in position.health.reasons if reason.startswith("-")), None)
    if negative is not None:
        return negative
    if position.health.reasons:
        return position.health.reasons[0]
    return position.health.unavailable_reason or "-"


def write_daily_brief_json(brief: DailyBrief, path: Path = DEFAULT_DAILY_JSON_PATH) -> None:
    """DailyBrief'i JSON'a atomik olarak yazar (once gecici dosyaya, sonra yerine tasir)."""
    payload: dict[str, object] = {
        "generated_at": brief.generated_at.isoformat(),
        "portfolio_status": brief.portfolio_status,
        "portfolio_error": brief.portfolio_error,
        "scanner_status": brief.scanner_status,
        "scanner_error": brief.scanner_error,
        "risk_alerts": list(brief.risk_alerts),
        "deteriorating_positions": list(brief.deteriorating_positions),
        "positions_to_review": [position.symbol for position in brief.positions_to_review],
        "strong_positions": [position.symbol for position in brief.strong_positions],
        "top_opportunities": [candidate.symbol for candidate in brief.top_opportunities],
        "alternative_candidates": (
            [candidate.symbol for candidate in brief.report.high_opportunity_alternatives]
            if brief.report is not None
            else []
        ),
        "summary": {
            "portfolio_condition": brief.summary.portfolio_condition,
            "main_risk": brief.summary.main_risk,
            "positions_requiring_review": brief.summary.positions_requiring_review,
            "high_opportunity_candidates": brief.summary.high_opportunity_candidates,
        },
    }
    if brief.report is not None:
        payload["totals_by_currency"] = [
            {
                "currency": totals.currency,
                "total_market_value": totals.total_market_value,
                "total_cost_value": totals.total_cost_value,
                "total_unrealized_pl": totals.total_unrealized_pl,
                "total_unrealized_pl_pct": totals.total_unrealized_pl_pct,
            }
            for totals in brief.report.summary.totals_by_currency
        ]
    if brief.scan_report is not None:
        payload["scan_summary"] = {
            "scanned": brief.scan_report.scanned,
            "successful": brief.scan_report.successful,
            "failed": brief.scan_report.failed,
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(path)


def write_daily_brief_csv(brief: DailyBrief, path: Path = DEFAULT_DAILY_CSV_PATH) -> None:
    """DailyBrief'i cok-bolumlu bir CSV'ye atomik olarak yazar.

    Tasarim: tum satirlar ayni dosyada, ilk kolon 'Section'
    (POSITION/OPPORTUNITY/ALERT/SUMMARY) hangi bolume ait oldugunu belirtir;
    o bolume uygun olmayan kolonlar bos birakilir.
    """
    rows: list[dict[str, object]] = []

    if brief.report is not None:
        for position in brief.report.positions:
            rows.append(
                {
                    "Section": "POSITION",
                    "Symbol": position.symbol,
                    "Weight %": position.weight_pct,
                    "P/L %": position.unrealized_pl_pct,
                    "Trend Score": position.trend.score,
                    "Opportunity Score": position.opportunity.score,
                    "Health Score": position.health.score,
                    "Action Hint": position.action_hint,
                    "Status": position.health.status,
                }
            )

    for rank, candidate in enumerate(brief.top_opportunities, start=1):
        rows.append(
            {
                "Section": "OPPORTUNITY",
                "Symbol": candidate.symbol,
                "Trend Score": candidate.trend.score,
                "Opportunity Score": candidate.opportunity.score,
                "RSI": candidate.rsi,
                "Return 20D": candidate.return_20d,
                "Distance EMA20 %": candidate.distance_ema20_pct,
                "Status": candidate.opportunity.status,
                "Detail": f"Rank {rank}",
            }
        )

    for alert in brief.risk_alerts:
        rows.append({"Section": "ALERT", "Detail": alert})

    rows.append(
        {
            "Section": "SUMMARY",
            "Status": brief.summary.portfolio_condition,
            "Detail": (
                f"Main risk: {brief.summary.main_risk}; "
                f"Positions requiring review: {brief.summary.positions_requiring_review}; "
                f"High opportunity candidates: {brief.summary.high_opportunity_candidates}"
            ),
        }
    )

    data = pd.DataFrame(rows, columns=CSV_COLUMNS)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    data.to_csv(tmp_path, index=False)
    tmp_path.replace(path)


def write_daily_brief_markdown(brief: DailyBrief, path: Path = DEFAULT_DAILY_MD_PATH) -> None:
    """DailyBrief'i insan tarafindan okunabilir bir Markdown raporuna atomik olarak yazar."""
    lines: list[str] = [f"# Daily Brief - {brief.generated_at.isoformat(timespec='seconds')}", ""]

    lines.append("## A. Portfolio Summary")
    if brief.portfolio_status == "FAILED":
        lines.append(f"Portfolio status: FAILED ({brief.portfolio_error})")
    elif brief.portfolio_status == "EMPTY":
        lines.append("Portfolio status: EMPTY")
    elif brief.report is not None:
        for totals in brief.report.summary.totals_by_currency:
            pl_pct = f"{totals.total_unrealized_pl_pct:.2f}%" if totals.total_unrealized_pl_pct is not None else "-"
            lines.append(f"- **Total Value ({totals.currency})**: {totals.total_market_value:.2f}")
            lines.append(f"- **Total Cost ({totals.currency})**: {totals.total_cost_value:.2f}")
            lines.append(f"- **Unrealized P/L ({totals.currency})**: {totals.total_unrealized_pl:.2f} ({pl_pct})")
    lines.append("")

    lines.append("## B. Risk Alerts")
    lines.extend([f"- {alert}" for alert in brief.risk_alerts] if brief.risk_alerts else ["Yok"])
    lines.append("")

    lines.append("## C. Positions to Review")
    if brief.positions_to_review:
        lines.append("| Symbol | Weight % | P/L % | Trend Score | Health Score | Action Hint | Main Reason |")
        lines.append("|---|---|---|---|---|---|---|")
        for position in brief.positions_to_review:
            weight = f"{position.weight_pct:.2f}" if position.weight_pct is not None else "-"
            pl_pct = f"{position.unrealized_pl_pct:.2f}" if position.unrealized_pl_pct is not None else "-"
            trend_score = position.trend.score if position.trend.score is not None else "-"
            health_score = position.health.score if position.health.score is not None else "-"
            lines.append(
                f"| {position.symbol} | {weight} | {pl_pct} | {trend_score} | {health_score} | "
                f"{position.action_hint or '-'} | {_main_reason_text(position)} |"
            )
    else:
        lines.append("Yok")
    lines.append("")

    lines.append("## D. Strong Portfolio Positions")
    if brief.strong_positions:
        for position in brief.strong_positions:
            lines.append(f"- {position.symbol}: Health Score {position.health.score}, Trend Score {position.trend.score}")
    else:
        lines.append("Yok")
    lines.append("")

    lines.append("## E. Top Market Opportunities")
    if brief.scanner_status == "FAILED":
        lines.append(f"Scanner status: FAILED ({brief.scanner_error})")
    elif brief.top_opportunities:
        lines.append(
            "| Rank | Symbol | Trend Score | Opportunity Score | RSI | Return 20D | "
            "Distance EMA20 % | Opportunity Status |"
        )
        lines.append("|---|---|---|---|---|---|---|---|")
        for rank, candidate in enumerate(brief.top_opportunities, start=1):
            lines.append(
                f"| {rank} | {candidate.symbol} | {candidate.trend.score} | {candidate.opportunity.score} | "
                f"{candidate.rsi:.1f} | {candidate.return_20d:.2f} | {candidate.distance_ema20_pct:.2f} | "
                f"{candidate.opportunity.status} |"
            )
    else:
        lines.append("Yok")
    lines.append("")

    lines.append("## F. Alternative Candidates")
    alternatives = brief.report.high_opportunity_alternatives if brief.report is not None else []
    if alternatives:
        for candidate in alternatives:
            lines.append(
                f"- {candidate.symbol}: Opportunity Score {candidate.opportunity.score} "
                f"({candidate.opportunity.status}), Trend Score {candidate.trend.score}"
            )
    else:
        lines.append("Yok")
    lines.append("")

    lines.append("## G. Daily Summary")
    lines.append(f"- Portfolio condition: {brief.summary.portfolio_condition}")
    lines.append(f"- Main risk: {brief.summary.main_risk}")
    lines.append(f"- Positions requiring review: {brief.summary.positions_requiring_review}")
    lines.append(f"- High opportunity candidates: {brief.summary.high_opportunity_candidates}")

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp_path.replace(path)
