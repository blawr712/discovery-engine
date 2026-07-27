import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from src.report import export_candidate_report


def breakdown(name, points, maximum, explanation):
    return json.dumps(
        {
            name: {
                "name": name,
                "points": points,
                "max_points": maximum,
                "available": True,
                "explanation": explanation,
            }
        }
    )


class CandidateReportTests(unittest.TestCase):
    def test_exports_ranked_successful_candidates_only(self):
        results = [
            {
                "ticker": "LOW",
                "status": "OK",
                "discovery_score": 40,
                "fundamental_score_normalized": 90,
                "factor_breakdown": breakdown(
                    "trend", 0, 10, "Weak trend"
                ),
                "fundamental_breakdown": breakdown(
                    "growth", 10, 10, "Strong growth"
                ),
            },
            {
                "ticker": "HIGH",
                "status": "OK",
                "discovery_score": 70,
                "fundamental_score_normalized": 50,
                "factor_breakdown": breakdown(
                    "trend", 10, 10, "Strong trend"
                ),
                "fundamental_breakdown": breakdown(
                    "growth", 0, 10, "Weak growth"
                ),
            },
            {
                "ticker": "FILTERED",
                "status": "FILTERED",
                "discovery_score": 0,
            },
        ]

        with tempfile.TemporaryDirectory() as directory:
            path = export_candidate_report(
                results,
                "run-1",
                Path(directory),
                top_n=10,
            )
            frame = pd.read_csv(path)

        self.assertEqual(frame["ticker"].tolist(), ["HIGH", "LOW"])
        self.assertEqual(frame["rank"].tolist(), [1, 2])
        self.assertEqual(frame["fundamental_rank"].tolist(), [2, 1])
        self.assertIn("Strong trend", frame.iloc[0]["strongest_signals"])
        self.assertIn("Weak growth", frame.iloc[0]["principal_risks"])

    def test_applies_top_candidate_limit(self):
        results = [
            {
                "ticker": str(index),
                "status": "OK",
                "discovery_score": index,
            }
            for index in range(5)
        ]

        with tempfile.TemporaryDirectory() as directory:
            path = export_candidate_report(
                results,
                "run-2",
                Path(directory),
                top_n=2,
            )
            frame = pd.read_csv(path)

        self.assertEqual(frame["ticker"].astype(str).tolist(), ["4", "3"])


if __name__ == "__main__":
    unittest.main()
