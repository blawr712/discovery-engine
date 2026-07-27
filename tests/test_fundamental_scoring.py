import json
import unittest

from src.fundamental_scoring import calculate_fundamental_scores


class FundamentalScoringTests(unittest.TestCase):
    def test_scores_complete_strong_fundamentals(self):
        result = calculate_fundamental_scores(
            {
                "market_cap": 100_000_000,
                "revenue_growth": 0.40,
                "earnings_growth": 0.35,
                "operating_margin": 0.25,
                "free_cash_flow": 20_000_000,
                "total_cash": 50_000_000,
                "total_debt": 10_000_000,
            }
        )

        self.assertEqual(result["fundamental_score"], 40.0)
        self.assertEqual(result["fundamental_score_max"], 40)
        self.assertEqual(result["fundamental_score_normalized"], 100.0)
        self.assertEqual(result["fundamental_confidence"], 100.0)

    def test_missing_data_does_not_create_false_penalty(self):
        result = calculate_fundamental_scores(
            {"market_cap": 100_000_000, "revenue_growth": 0.40}
        )
        breakdown = json.loads(result["fundamental_breakdown"])

        self.assertEqual(result["fundamental_score"], 10.0)
        self.assertEqual(result["fundamental_score_normalized"], 100.0)
        self.assertEqual(result["fundamental_confidence"], 25.0)
        self.assertFalse(breakdown["earnings_growth"]["available"])

    def test_available_weak_fundamentals_score_zero_with_full_confidence(self):
        result = calculate_fundamental_scores(
            {
                "market_cap": 100_000_000,
                "revenue_growth": -0.10,
                "earnings_growth": -0.10,
                "operating_margin": -0.10,
                "free_cash_flow": -10_000_000,
                "total_cash": 0,
                "total_debt": 50_000_000,
            }
        )

        self.assertEqual(result["fundamental_score"], 0.0)
        self.assertEqual(result["fundamental_score_normalized"], 0.0)
        self.assertEqual(result["fundamental_confidence"], 100.0)

    def test_uses_profit_margin_when_operating_margin_is_missing(self):
        result = calculate_fundamental_scores(
            {"market_cap": 100_000_000, "profit_margin": 0.12}
        )
        breakdown = json.loads(result["fundamental_breakdown"])

        self.assertEqual(breakdown["profitability"]["points"], 6.0)
        self.assertIn(
            "Profit margin",
            breakdown["profitability"]["explanation"],
        )

    def test_rejects_non_numeric_and_boolean_values_as_missing(self):
        result = calculate_fundamental_scores(
            {
                "market_cap": 100_000_000,
                "revenue_growth": "20%",
                "earnings_growth": True,
            }
        )

        self.assertEqual(result["fundamental_confidence"], 0.0)


if __name__ == "__main__":
    unittest.main()
