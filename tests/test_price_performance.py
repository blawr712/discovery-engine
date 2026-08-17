import unittest

from src.price_performance import build_price_performance


class PricePerformanceTests(unittest.TestCase):
    def test_calculates_period_and_benchmark_relative_returns(self):
        equity = self._snapshot("AAA", [
            ("2025-08-01", 100), ("2026-02-01", 120),
            ("2026-07-01", 130), ("2026-08-01", 150),
        ])
        benchmark = self._snapshot("SPY", [
            ("2025-08-01", 100), ("2026-02-01", 110),
            ("2026-07-01", 120), ("2026-08-01", 125),
        ])

        result = build_price_performance(equity, benchmark)

        self.assertEqual(result["period_returns"]["1Y"]["ticker_return"], 50)
        self.assertEqual(result["period_returns"]["1Y"]["benchmark_return"], 25)
        self.assertEqual(result["period_returns"]["1Y"]["relative_return"], 25)
        self.assertEqual(result["series"]["ticker"][0]["value"], 100)
        self.assertEqual(result["series"]["ticker"][-1]["value"], 150)
        self.assertIn("S&P 500", result["benchmark_definition"])
        self.assertEqual(result["data_quality"], "clean")

    def test_suppresses_returns_that_cross_possible_corporate_action(self):
        equity = self._snapshot("AAA", [
            ("2026-06-01", 0.4), ("2026-07-20", 4.2),
            ("2026-08-01", 4.5),
        ])

        result = build_price_performance(equity, None)

        self.assertEqual(result["data_quality"], "unresolved_discontinuity")
        self.assertEqual(result["anomalies"][0]["date"], "2026-07-20")
        self.assertIsNone(result["period_returns"]["3M"]["ticker_return"])
        self.assertFalse(result["period_returns"]["3M"]["reliable"])

    def test_missing_equity_snapshot_returns_none(self):
        self.assertIsNone(build_price_performance(None, None))

    def test_verified_reverse_split_adjusts_prior_prices_and_restores_returns(self):
        equity = self._snapshot("AAA", [
            ("2026-06-01", 0.4), ("2026-07-20", 4.2),
            ("2026-08-01", 4.5),
        ])
        equity["points"][1]["split"] = 0.1

        result = build_price_performance(equity, None)

        self.assertEqual(result["data_quality"], "verified_adjusted")
        self.assertEqual(result["corporate_actions"][0]["status"], "verified_adjusted")
        self.assertEqual(result["series"]["price"][0]["value"], 4)
        self.assertEqual(result["period_returns"]["3M"]["ticker_return"], 12.5)

    def test_reported_split_does_not_double_adjust_already_adjusted_prices(self):
        equity = self._snapshot("AAA", [
            ("2026-06-01", 4.0), ("2026-07-20", 4.2),
            ("2026-08-01", 4.5),
        ])
        equity["points"][1]["split"] = 0.1

        result = build_price_performance(equity, None)

        self.assertEqual(result["data_quality"], "verified")
        self.assertEqual(
            result["corporate_actions"][0]["status"],
            "reported_already_adjusted",
        )
        self.assertEqual(result["series"]["price"][0]["value"], 4)

    @staticmethod
    def _snapshot(ticker, values):
        points = [
            {"date": day, "close": close, "volume": 1000}
            for day, close in values
        ]
        return {
            "ticker": ticker, "start_date": points[0]["date"],
            "end_date": points[-1]["date"], "point_count": len(points),
            "source_mtime": "2026-08-01T00:00:00+00:00", "points": points,
        }


if __name__ == "__main__":
    unittest.main()
