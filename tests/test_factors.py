import json
import unittest

from src.factors import (
    FactorResult,
    score_confidence,
    serialize_factor_breakdown,
)


class FactorResultTests(unittest.TestCase):
    def test_serializes_stable_factor_breakdown(self):
        factor = FactorResult(
            name="growth",
            raw_value=0.123456,
            points=7.126,
            max_points=10,
            available=True,
            explanation="Revenue is growing",
        )

        result = json.loads(serialize_factor_breakdown([factor]))

        self.assertEqual(result["growth"]["raw_value"], 0.1235)
        self.assertEqual(result["growth"]["points"], 7.13)

    def test_confidence_uses_available_factor_weight(self):
        factors = [
            FactorResult("one", 1, 5, 10, True, "available"),
            FactorResult("two", None, 0, 30, False, "missing"),
        ]

        self.assertEqual(score_confidence(factors), 25.0)
        self.assertEqual(score_confidence([]), 0.0)


if __name__ == "__main__":
    unittest.main()
