"""Explainable shadow scoring for company fundamentals."""

from __future__ import annotations

import json
from numbers import Real

from src.config import FUNDAMENTAL_SCORING_CONFIG, FUNDAMENTAL_WEIGHTS
from src.factors import FactorResult, score_confidence


def calculate_fundamental_scores(stock_data: dict) -> dict:
    """Calculate fundamental factors without changing Discovery Score yet."""
    factors = [
        _percentage_factor(
            "revenue_growth",
            stock_data.get("revenue_growth"),
            "Revenue growth",
        ),
        _percentage_factor(
            "earnings_growth",
            stock_data.get("earnings_growth"),
            "Earnings growth",
        ),
        _profitability_factor(stock_data),
        _free_cash_flow_factor(stock_data),
        _balance_sheet_factor(stock_data),
    ]
    score = round(sum(factor.points for factor in factors), 2)
    available_max = sum(
        factor.max_points for factor in factors if factor.available
    )
    normalized_score = (
        round((score / available_max) * 100, 2)
        if available_max > 0
        else None
    )

    return {
        "fundamental_score": score,
        "fundamental_score_max": sum(FUNDAMENTAL_WEIGHTS.values()),
        "fundamental_score_normalized": normalized_score,
        "fundamental_confidence": score_confidence(factors),
        "fundamental_breakdown": json.dumps(
            {factor.name: factor.to_dict() for factor in factors},
            sort_keys=True,
            separators=(",", ":"),
        ),
    }


def _percentage_factor(
    name: str,
    value: object,
    label: str,
) -> FactorResult:
    numeric_value = _number(value)
    return _threshold_factor(
        name,
        numeric_value,
        (
            f"{label} is {numeric_value:.1%}"
            if numeric_value is not None
            else f"{label} is unavailable"
        ),
    )


def _profitability_factor(stock_data: dict) -> FactorResult:
    operating_margin = _number(stock_data.get("operating_margin"))
    profit_margin = _number(stock_data.get("profit_margin"))
    value = operating_margin if operating_margin is not None else profit_margin
    source = "Operating margin" if operating_margin is not None else "Profit margin"
    return _threshold_factor(
        "profitability",
        value,
        (
            f"{source} is {value:.1%}"
            if value is not None
            else "Operating and profit margins are unavailable"
        ),
    )


def _free_cash_flow_factor(stock_data: dict) -> FactorResult:
    free_cash_flow = _number(stock_data.get("free_cash_flow"))
    market_cap = _positive_number(stock_data.get("market_cap"))
    value = (
        free_cash_flow / market_cap
        if free_cash_flow is not None and market_cap is not None
        else None
    )
    return _threshold_factor(
        "free_cash_flow",
        value,
        (
            f"Free-cash-flow yield is {value:.1%}"
            if value is not None
            else "Free cash flow or market capitalization is unavailable"
        ),
    )


def _balance_sheet_factor(stock_data: dict) -> FactorResult:
    total_cash = _number(stock_data.get("total_cash"))
    total_debt = _number(stock_data.get("total_debt"))
    market_cap = _positive_number(stock_data.get("market_cap"))
    value = (
        (total_cash - total_debt) / market_cap
        if total_cash is not None
        and total_debt is not None
        and market_cap is not None
        else None
    )
    return _threshold_factor(
        "balance_sheet",
        value,
        (
            f"Net cash is {value:.1%} of market capitalization"
            if value is not None
            else "Cash, debt, or market capitalization is unavailable"
        ),
    )


def _threshold_factor(
    name: str,
    value: float | None,
    explanation: str,
) -> FactorResult:
    max_points = float(FUNDAMENTAL_WEIGHTS[name])
    points = 0.0

    if value is not None:
        for threshold in FUNDAMENTAL_SCORING_CONFIG[name]["thresholds"]:
            if value >= float(threshold["minimum"]):
                points = max_points * float(threshold["points_ratio"])
                break

    return FactorResult(
        name=name,
        raw_value=value,
        points=points,
        max_points=max_points,
        available=value is not None,
        explanation=explanation,
    )


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    numeric = float(value)
    if numeric != numeric:
        return None
    return numeric


def _positive_number(value: object) -> float | None:
    numeric = _number(value)
    return numeric if numeric is not None and numeric > 0 else None
