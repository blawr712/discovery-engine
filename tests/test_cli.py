import unittest

from src.cli import parse_args, select_universe


class CliTests(unittest.TestCase):
    def setUp(self):
        self.universe = [
            {"ticker": "AAA", "country": "US", "exchange": "NASDAQ"},
            {"ticker": "BBB.TO", "country": "CA", "exchange": "TSX"},
            {"ticker": "CCC", "country": "US", "exchange": "NYSE"},
            {"ticker": "DDD.TO", "country": "CA", "exchange": "TSX"},
        ]

    def test_parses_tickers_and_normalizes_during_selection(self):
        args = parse_args(["--tickers", "bbb.to", "AAA"])
        selected = select_universe(self.universe, tickers=args.tickers)

        self.assertEqual(
            [item["ticker"] for item in selected],
            ["BBB.TO", "AAA"],
        )

    def test_limit_preserves_universe_order(self):
        args = parse_args(["--limit", "2"])

        self.assertEqual(
            select_universe(self.universe, limit=args.limit),
            self.universe[:2],
        )

    def test_deduplicates_requested_tickers(self):
        selected = select_universe(
            self.universe,
            tickers=["AAA", "aaa", "CCC"],
        )

        self.assertEqual(
            [item["ticker"] for item in selected],
            ["AAA", "CCC"],
        )

    def test_reports_tickers_missing_from_universe(self):
        with self.assertRaisesRegex(ValueError, "MISSING"):
            select_universe(self.universe, tickers=["AAA", "MISSING"])

    def test_rejects_nonpositive_limit(self):
        with self.assertRaises(SystemExit):
            parse_args(["--limit", "0"])

    def test_rejects_combined_selection_options(self):
        with self.assertRaises(SystemExit):
            parse_args(["--limit", "2", "--tickers", "AAA"])

    def test_no_options_returns_full_universe(self):
        args = parse_args([])

        self.assertIs(
            select_universe(
                self.universe,
                tickers=args.tickers,
                limit=args.limit,
                balanced_sample=args.balanced_sample,
            ),
            self.universe,
        )

    def test_balanced_sample_interleaves_countries(self):
        args = parse_args(["--balanced-sample", "2"])
        selected = select_universe(
            self.universe,
            balanced_sample=args.balanced_sample,
        )

        self.assertEqual(
            [item["ticker"] for item in selected],
            ["BBB.TO", "AAA", "DDD.TO", "CCC"],
        )

    def test_rejects_balanced_sample_with_other_selection(self):
        with self.assertRaises(SystemExit):
            parse_args(["--balanced-sample", "2", "--limit", "2"])

    def test_parses_offline_recalibration_as_exclusive_action(self):
        args = parse_args(["--recalibrate-run", "run-123"])

        self.assertEqual(args.recalibrate_run, "run-123")
        with self.assertRaises(SystemExit):
            parse_args(["--recalibrate-run", "run-123", "--limit", "2"])


if __name__ == "__main__":
    unittest.main()
