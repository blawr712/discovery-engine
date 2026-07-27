from datetime import datetime
import json
from pathlib import Path
import pandas as pd

from src.config import OUTPUT_DIR, REPORTS_CONFIG


def export_report(
    results: list[dict],
    run_id: str | None = None,
    output_directory: Path | None = None,
) -> str:
    df = pd.DataFrame(results)

    if df.empty:
        raise ValueError("No results to export.")

    df = df.sort_values("discovery_score", ascending=False)

    report_id = run_id or datetime.now().strftime("%Y-%m-%d")
    output_directory = Path(output_directory or OUTPUT_DIR)
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f"discovery_scores_{report_id}.csv"

    df.to_csv(output_path, index=False)

    return str(output_path)


def export_candidate_report(
    results: list[dict],
    run_id: str,
    output_directory: Path | None = None,
    top_n: int | None = None,
) -> str:
    """Export a curated research queue containing successful companies only."""
    top_n = top_n or int(REPORTS_CONFIG.get("top_stocks", 100))
    candidates = [dict(row) for row in results if row.get("status") == "OK"]
    candidates.sort(
        key=lambda row: (
            -_numeric(row.get("discovery_score"), default=0),
            str(row.get("ticker", "")),
        )
    )

    fundamental_order = sorted(
        candidates,
        key=lambda row: (
            -_numeric(row.get("fundamental_score_normalized"), default=-1),
            str(row.get("ticker", "")),
        ),
    )
    fundamental_ranks = {
        str(row.get("ticker")): rank
        for rank, row in enumerate(fundamental_order, start=1)
        if _numeric(row.get("fundamental_score_normalized")) is not None
    }

    report_rows = []
    for rank, row in enumerate(candidates, start=1):
        strengths, risks = _factor_highlights(row)
        report_rows.append(
            {
                "rank": rank,
                "fundamental_rank": fundamental_ranks.get(str(row.get("ticker"))),
                "ticker": row.get("ticker"),
                "company_name": row.get("company_name"),
                "country": row.get("country"),
                "exchange": row.get("exchange"),
                "sector": row.get("sector"),
                "industry": row.get("industry"),
                "asset_type": row.get("asset_type"),
                "market_cap": row.get("market_cap"),
                "discovery_score": row.get("discovery_score"),
                "score_confidence": row.get("score_confidence"),
                "fundamental_score": row.get("fundamental_score"),
                "fundamental_score_normalized": row.get("fundamental_score_normalized"),
                "fundamental_confidence": row.get("fundamental_confidence"),
                "fundamental_data_quality": row.get("fundamental_data_quality"),
                "fundamental_data_as_of": row.get("fundamental_data_as_of"),
                "strongest_signals": strengths,
                "principal_risks": risks,
                "reason_flags": row.get("reason_flags"),
                "factor_breakdown": row.get("factor_breakdown"),
                "fundamental_breakdown": row.get("fundamental_breakdown"),
            }
        )

    columns = list(report_rows[0]) if report_rows else [
        "rank", "fundamental_rank", "ticker", "company_name", "country",
        "exchange", "sector", "industry", "asset_type", "market_cap",
        "discovery_score", "score_confidence", "fundamental_score",
        "fundamental_score_normalized", "fundamental_confidence",
        "fundamental_data_quality", "fundamental_data_as_of",
        "strongest_signals", "principal_risks", "reason_flags",
        "factor_breakdown", "fundamental_breakdown",
    ]
    frame = pd.DataFrame(report_rows, columns=columns).head(top_n)
    output_directory = Path(output_directory or OUTPUT_DIR)
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f"research_candidates_{run_id}.csv"
    frame.to_csv(output_path, index=False)
    return str(output_path)


def _factor_highlights(row: dict) -> tuple[str, str]:
    factors = []
    for field in ("factor_breakdown", "fundamental_breakdown"):
        value = row.get(field)
        if not value:
            continue
        try:
            breakdown = json.loads(value) if isinstance(value, str) else value
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(breakdown, dict):
            continue
        for factor in breakdown.values():
            if not isinstance(factor, dict) or not factor.get("available"):
                continue
            maximum = _numeric(factor.get("max_points"), default=0)
            points = _numeric(factor.get("points"), default=0)
            ratio = points / maximum if maximum > 0 else 0
            factors.append((ratio, str(factor.get("explanation", ""))))

    strengths = [text for ratio, text in sorted(factors, reverse=True) if ratio >= 0.75][:3]
    risks = [text for ratio, text in sorted(factors) if ratio <= 0.40][:3]
    return "; ".join(strengths), "; ".join(risks)


def _numeric(value: object, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
