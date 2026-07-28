"""Shadow-score validation and calibration artifacts."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import tempfile

import pandas as pd

from src.config import (
    CALIBRATION_CONFIG,
    FUNDAMENTAL_DATA_POLICY,
    OUTPUT_DIR,
)


def build_calibration(results: list[dict], config: dict | None = None) -> dict:
    """Build company rows and aggregate shadow-score diagnostics."""
    config = config or CALIBRATION_CONFIG
    candidates = [dict(row) for row in results if row.get("status") == "OK"]
    candidates.sort(key=_official_sort_key)

    technical_percentiles = _percentiles(candidates, "discovery_score")
    fundamental_percentiles = _percentiles(
        candidates,
        "fundamental_score_normalized",
    )
    country_percentiles = _group_percentiles(
        candidates,
        "country",
        "discovery_score",
    )
    sector_percentiles = _group_percentiles(
        candidates,
        "sector",
        "discovery_score",
    )
    fundamental_ranks = _ranks(
        candidates,
        "fundamental_score_normalized",
    )
    minimum_blend_confidence = float(
        config.get("minimum_blend_confidence", 50)
    )
    eligibility = {
        str(row.get("ticker", "")): _blend_eligibility_reason(
            row,
            minimum_blend_confidence,
        )
        for row in candidates
    }
    confidence_adjusted_values = {
        str(row.get("ticker", "")): _confidence_adjusted_score(row)
        for row in candidates
        if eligibility[str(row.get("ticker", ""))] is None
    }
    adjusted_rows = [
        {
            "ticker": ticker,
            "confidence_adjusted_fundamental_score": value,
            "sector": next(
                row.get("sector")
                for row in candidates
                if str(row.get("ticker", "")) == ticker
            ),
        }
        for ticker, value in confidence_adjusted_values.items()
        if value is not None
    ]
    adjusted_percentiles = _percentiles(
        adjusted_rows,
        "confidence_adjusted_fundamental_score",
    )
    sector_fundamental_percentiles = _group_percentiles(
        adjusted_rows,
        "sector",
        "confidence_adjusted_fundamental_score",
    )
    adjusted_ranks = _rank_values(confidence_adjusted_values)
    scenarios = _validated_scenarios(config.get("blend_scenarios", {}))
    scenario_scores: dict[str, dict[str, float | None]] = {}

    for name, weights in scenarios.items():
        scenario_scores[name] = {}
        for row in candidates:
            ticker = str(row.get("ticker", ""))
            technical = technical_percentiles.get(ticker)
            fundamental = adjusted_percentiles.get(ticker)
            scenario_scores[name][ticker] = _blend_score(
                technical,
                fundamental,
                weights,
            )

    scenario_ranks = {
        name: _rank_values(values)
        for name, values in scenario_scores.items()
    }
    low_confidence_threshold = float(
        config.get("low_confidence_threshold", 50)
    )
    rows = []

    for official_rank, row in enumerate(candidates, start=1):
        ticker = str(row.get("ticker", ""))
        outliers = _outlier_flags(
            row,
            FUNDAMENTAL_DATA_POLICY.get("factor_input_policies", {}),
        )
        calibration_row = {
            "official_rank": official_rank,
            "ticker": ticker,
            "company_name": row.get("company_name"),
            "country": row.get("country"),
            "sector": row.get("sector"),
            "discovery_score": row.get("discovery_score"),
            "technical_percentile": technical_percentiles.get(ticker),
            "country_technical_percentile": country_percentiles.get(ticker),
            "sector_technical_percentile": sector_percentiles.get(ticker),
            "fundamental_rank": fundamental_ranks.get(ticker),
            "fundamental_score_normalized": row.get(
                "fundamental_score_normalized"
            ),
            "fundamental_percentile": fundamental_percentiles.get(ticker),
            "confidence_adjusted_fundamental_score": (
                confidence_adjusted_values.get(ticker)
            ),
            "calibrated_fundamental_rank": adjusted_ranks.get(ticker),
            "sector_fundamental_percentile": (
                sector_fundamental_percentiles.get(ticker)
            ),
            "fundamental_confidence": row.get("fundamental_confidence"),
            "fundamental_data_quality": row.get("fundamental_data_quality"),
            "low_fundamental_confidence": (
                _numeric(row.get("fundamental_confidence"), 0)
                < low_confidence_threshold
            ),
            "experimental_blend_eligible": eligibility[ticker] is None,
            "experimental_blend_ineligibility_reason": eligibility[ticker],
            "rank_disagreement": (
                abs(official_rank - fundamental_ranks[ticker])
                if ticker in fundamental_ranks
                else None
            ),
            "outlier_flags": "; ".join(outliers),
        }
        for name in scenarios:
            calibration_row[f"experimental_{name}_score"] = (
                scenario_scores[name].get(ticker)
            )
            calibration_row[f"experimental_{name}_rank"] = (
                scenario_ranks[name].get(ticker)
            )
        rows.append(calibration_row)

    top_n = int(config.get("top_n", 100))
    return {
        "rows": rows,
        "summary": {
            "official_order_authoritative": True,
            "experimental_scores_control_official_order": False,
            "successful_candidates": len(candidates),
            "rank_correlation": _correlation(
                technical_percentiles,
                adjusted_percentiles,
            ),
            "top_overlap": _top_overlap(candidates, adjusted_ranks, top_n),
            "top_overlaps": {
                str(cutoff): _top_overlap(
                    candidates,
                    adjusted_ranks,
                    int(cutoff),
                )
                for cutoff in config.get("overlap_cutoffs", [20, 50, 100])
            },
            "largest_rank_disagreements": sorted(
                (
                    {
                        "ticker": row["ticker"],
                        "official_rank": row["official_rank"],
                        "fundamental_rank": row["fundamental_rank"],
                        "absolute_difference": row["rank_disagreement"],
                    }
                    for row in rows
                    if row["rank_disagreement"] is not None
                ),
                key=lambda item: (
                    -item["absolute_difference"],
                    item["ticker"],
                ),
            )[:20],
            "low_confidence_candidates": sum(
                1 for row in rows if row["low_fundamental_confidence"]
            ),
            "outlier_candidates": sum(
                1 for row in rows if row["outlier_flags"]
            ),
            "factor_distributions": _factor_distributions(candidates),
            "factor_readiness": _factor_readiness(candidates, config),
            "scenario_movements": _scenario_movements(
                rows,
                scenarios,
            ),
            "experimental_blend_eligible_candidates": sum(
                1 for reason in eligibility.values() if reason is None
            ),
            "experimental_blend_ineligible_reasons": _reason_counts(
                eligibility.values()
            ),
            "blend_scenarios": scenarios,
        },
    }


def export_calibration(
    results: list[dict],
    run_id: str,
    output_directory: Path | None = None,
    config: dict | None = None,
) -> tuple[str, str]:
    """Export officially ordered calibration rows and aggregate JSON."""
    output_directory = Path(output_directory or OUTPUT_DIR)
    output_directory.mkdir(parents=True, exist_ok=True)
    calibration = build_calibration(results, config)
    csv_path = output_directory / f"discovery_calibration_{run_id}.csv"
    json_path = output_directory / f"discovery_calibration_{run_id}.json"
    pd.DataFrame(calibration["rows"]).to_csv(csv_path, index=False)
    _atomic_json(json_path, calibration["summary"])
    return str(csv_path), str(json_path)


def _percentiles(rows: list[dict], field: str) -> dict[str, float]:
    values = {
        str(row.get("ticker", "")): value
        for row in rows
        if (value := _numeric(row.get(field))) is not None
    }
    if not values:
        return {}
    if len(values) == 1:
        return {ticker: 100.0 for ticker in values}
    return {
        ticker: round(
            sum(other < value for other in values.values())
            / (len(values) - 1)
            * 100,
            2,
        )
        for ticker, value in values.items()
    }


def _group_percentiles(
    rows: list[dict],
    dimension: str,
    field: str,
) -> dict[str, float]:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(str(row.get(dimension) or "UNKNOWN"), []).append(row)
    return {
        ticker: percentile
        for group in groups.values()
        for ticker, percentile in _percentiles(group, field).items()
    }


def _ranks(rows: list[dict], field: str) -> dict[str, int]:
    ordered = [
        row
        for row in rows
        if _numeric(row.get(field)) is not None
    ]
    ordered.sort(
        key=lambda row: (
            -_numeric(row.get(field), 0),
            str(row.get("ticker", "")),
        )
    )
    return {
        str(row.get("ticker", "")): rank
        for rank, row in enumerate(ordered, start=1)
    }


def _rank_values(values: dict[str, float | None]) -> dict[str, int]:
    ordered = sorted(
        ((ticker, value) for ticker, value in values.items() if value is not None),
        key=lambda item: (-item[1], item[0]),
    )
    return {
        ticker: rank
        for rank, (ticker, _) in enumerate(ordered, start=1)
    }


def _blend_score(
    technical: float | None,
    fundamental: float | None,
    weights: dict,
) -> float | None:
    if technical is None:
        return None
    technical_weight = float(weights["technical_weight"])
    fundamental_weight = float(weights["fundamental_weight"])
    if fundamental is None and fundamental_weight > 0:
        return None
    return round(
        technical * technical_weight
        + (fundamental or 0) * fundamental_weight,
        2,
    )


def _confidence_adjusted_score(row: dict) -> float | None:
    score = _numeric(row.get("fundamental_score_normalized"))
    confidence = _numeric(row.get("fundamental_confidence"))
    if score is None or confidence is None:
        return None
    return round(score * confidence / 100, 2)


def _blend_eligibility_reason(
    row: dict,
    minimum_confidence: float,
) -> str | None:
    if _numeric(row.get("fundamental_score_normalized")) is None:
        return "Missing normalized fundamental score"
    confidence = _numeric(row.get("fundamental_confidence"))
    if confidence is None:
        return "Missing fundamental confidence"
    if confidence < minimum_confidence:
        return (
            f"Fundamental confidence {confidence:g}% is below "
            f"{minimum_confidence:g}%"
        )
    if row.get("fundamental_data_quality") == "stale":
        return "Fundamental data is stale"
    return None


def _validated_scenarios(scenarios: dict) -> dict:
    validated = {}
    for name, scenario in scenarios.items():
        technical = float(scenario.get("technical_weight", 0))
        fundamental = float(scenario.get("fundamental_weight", 0))
        if technical < 0 or fundamental < 0:
            raise ValueError(f"Blend scenario {name} has negative weights.")
        if not math.isclose(technical + fundamental, 1.0):
            raise ValueError(f"Blend scenario {name} weights must total 1.")
        validated[str(name)] = {
            "technical_weight": technical,
            "fundamental_weight": fundamental,
            "experimental": True,
        }
    return validated


def _correlation(
    first: dict[str, float],
    second: dict[str, float],
) -> dict:
    tickers = sorted(set(first) & set(second))
    if len(tickers) < 2:
        return {"method": "spearman", "count": len(tickers), "value": None}
    x = [first[ticker] for ticker in tickers]
    y = [second[ticker] for ticker in tickers]
    mean_x = sum(x) / len(x)
    mean_y = sum(y) / len(y)
    numerator = sum(
        (left - mean_x) * (right - mean_y)
        for left, right in zip(x, y)
    )
    denominator = math.sqrt(
        sum((value - mean_x) ** 2 for value in x)
        * sum((value - mean_y) ** 2 for value in y)
    )
    return {
        "method": "spearman",
        "count": len(tickers),
        "value": round(numerator / denominator, 4) if denominator else None,
    }


def _top_overlap(
    candidates: list[dict],
    fundamental_ranks: dict[str, int],
    top_n: int,
) -> dict:
    technical = {
        str(row.get("ticker", ""))
        for row in candidates[:top_n]
    }
    fundamental = {
        ticker for ticker, rank in fundamental_ranks.items() if rank <= top_n
    }
    denominator = min(top_n, len(technical), len(fundamental))
    overlap = len(technical & fundamental)
    return {
        "requested_top_n": top_n,
        "comparison_size": denominator,
        "count": overlap,
        "percentage": (
            round(overlap / denominator * 100, 2) if denominator else None
        ),
    }


def _outlier_flags(row: dict, bounds: dict) -> list[str]:
    breakdown = _breakdown(row.get("fundamental_breakdown"))
    flags = []
    for name, limits in bounds.items():
        factor = breakdown.get(name, {})
        value = _numeric(
            factor.get("source_value"),
            _numeric(factor.get("raw_value")),
        )
        if value is None:
            continue
        minimum = _numeric(limits.get("minimum"))
        maximum = _numeric(limits.get("maximum"))
        if minimum is not None and value < minimum:
            flags.append(f"{name} below {minimum:g}: {value:g}")
        elif maximum is not None and value > maximum:
            flags.append(f"{name} above {maximum:g}: {value:g}")
    return flags


def _factor_readiness(rows: list[dict], config: dict) -> dict:
    names = sorted({
        name
        for row in rows
        for name in _breakdown(row.get("fundamental_breakdown"))
    })
    readiness_config = config.get("factor_readiness", {})
    ready_minimum = float(
        readiness_config.get("ready_minimum_coverage", 75)
    )
    limited_minimum = float(
        readiness_config.get("limited_minimum_coverage", 40)
    )
    result = {}
    for name in names:
        factors = [
            _breakdown(row.get("fundamental_breakdown")).get(name, {})
            for row in rows
        ]
        applicable = sum(
            1
            for factor in factors
            if factor.get("applicable", True) is not False
        )
        available = sum(
            1
            for factor in factors
            if factor.get("available") is True
            and factor.get("applicable", True) is not False
        )
        coverage = round(available / applicable * 100, 2) if applicable else 0
        if coverage >= ready_minimum:
            status = "ready"
        elif coverage >= limited_minimum:
            status = "limited"
        else:
            status = "shadow_only"
        result[name] = {
            "status": status,
            "available": available,
            "applicable": applicable,
            "coverage_percentage": coverage,
        }
    return result


def _scenario_movements(rows: list[dict], scenarios: dict) -> dict:
    movements = {}
    for name in scenarios:
        rank_field = f"experimental_{name}_rank"
        comparable = [
            {
                "ticker": row["ticker"],
                "official_rank": row["official_rank"],
                "experimental_rank": row[rank_field],
                "rank_movement": (
                    row["official_rank"] - row[rank_field]
                ),
            }
            for row in rows
            if row.get(rank_field) is not None
        ]
        promotions = sorted(
            comparable,
            key=lambda item: (-item["rank_movement"], item["ticker"]),
        )[:20]
        demotions = sorted(
            comparable,
            key=lambda item: (item["rank_movement"], item["ticker"]),
        )[:20]
        movements[name] = {
            "ranked_candidates": len(comparable),
            "largest_promotions": promotions,
            "largest_demotions": demotions,
        }
    return movements


def _reason_counts(reasons) -> dict:
    counts: dict[str, int] = {}
    for reason in reasons:
        if reason is None:
            continue
        category = (
            "low_confidence"
            if str(reason).startswith("Fundamental confidence")
            else str(reason)
        )
        counts[category] = counts.get(category, 0) + 1
    return dict(sorted(counts.items()))


def _factor_distributions(rows: list[dict]) -> dict:
    factors: dict[str, dict[str, list[float]]] = {}
    for row in rows:
        for name, factor in _breakdown(
            row.get("fundamental_breakdown")
        ).items():
            if not isinstance(factor, dict):
                continue
            entry = factors.setdefault(name, {"raw_values": [], "points": []})
            raw_value = _numeric(factor.get("raw_value"))
            points = _numeric(factor.get("points"))
            if raw_value is not None:
                entry["raw_values"].append(raw_value)
            if points is not None and factor.get("available") is True:
                entry["points"].append(points)
    return {
        name: {
            "raw_values": _distribution(values["raw_values"]),
            "points": _distribution(values["points"]),
        }
        for name, values in sorted(factors.items())
    }


def _distribution(values: list[float]) -> dict:
    values = sorted(values)
    if not values:
        return {
            "count": 0,
            "min": None,
            "median": None,
            "max": None,
        }
    middle = len(values) // 2
    median = (
        values[middle]
        if len(values) % 2
        else (values[middle - 1] + values[middle]) / 2
    )
    return {
        "count": len(values),
        "min": round(values[0], 4),
        "median": round(median, 4),
        "max": round(values[-1], 4),
    }


def _breakdown(value: object) -> dict:
    if not value:
        return {}
    try:
        result = json.loads(value) if isinstance(value, str) else value
    except (json.JSONDecodeError, TypeError):
        return {}
    return result if isinstance(result, dict) else {}


def _official_sort_key(row: dict) -> tuple:
    return (
        -_numeric(row.get("discovery_score"), 0),
        str(row.get("ticker", "")),
    )


def _numeric(value: object, default: float | None = None) -> float | None:
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _atomic_json(path: Path, data: dict) -> None:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{path.stem}-",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, sort_keys=True)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
