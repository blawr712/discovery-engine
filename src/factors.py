"""Common result model for explainable Discovery Score factors."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from numbers import Real


@dataclass(frozen=True)
class FactorResult:
    """Capture one factor's value, score contribution, and explanation."""

    name: str
    raw_value: object
    points: float
    max_points: float
    available: bool
    explanation: str

    def to_dict(self) -> dict:
        """Return a JSON-safe representation for reports and checkpoints."""
        result = asdict(self)
        if isinstance(self.raw_value, Real) and not isinstance(
            self.raw_value,
            bool,
        ):
            result["raw_value"] = round(float(self.raw_value), 4)
        result["points"] = round(float(self.points), 2)
        result["max_points"] = round(float(self.max_points), 2)
        return result


def score_confidence(factors: list[FactorResult]) -> float:
    """Return the percentage of configured factor weight with usable data."""
    total_weight = sum(factor.max_points for factor in factors)
    if total_weight <= 0:
        return 0.0
    available_weight = sum(
        factor.max_points for factor in factors if factor.available
    )
    return round((available_weight / total_weight) * 100, 2)


def serialize_factor_breakdown(factors: list[FactorResult]) -> str:
    """Serialize factors as stable JSON keyed by factor name."""
    return json.dumps(
        {factor.name: factor.to_dict() for factor in factors},
        sort_keys=True,
        separators=(",", ":"),
    )
