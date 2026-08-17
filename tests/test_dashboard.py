from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from src.dashboard import DASHBOARD_HTML, DashboardStore
from src.history import index_saved_run
from src.run_state import RunState


class DashboardTests(unittest.TestCase):
    def test_read_only_store_exposes_overview_candidates_timeline_and_weekly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            database = root / "history.sqlite3"
            old_id = self._save(runs, "old", datetime(2026, 8, 1, tzinfo=timezone.utc), [
                self._row("AAA", "FILTERED", 40, "US"),
                self._row("BBB", "OK", 70, "CA"),
            ])
            new_id = self._save(runs, "new", datetime(2026, 8, 8, tzinfo=timezone.utc), [
                self._row("AAA", "OK", 80, "US"),
                self._row("BBB", "FILTERED", 30, "CA"),
            ])
            index_saved_run(database, runs, old_id)
            index_saved_run(database, runs, new_id)
            store = DashboardStore(database)

            overview = store.overview()
            candidates = store.candidates(new_id, status="OK", country="US")
            timeline = store.ticker_history("aaa")
            detail = store.candidate_detail("aaa", new_id)
            weekly = store.weekly_report()

            self.assertEqual(overview["run_count"], 2)
            self.assertEqual(overview["result_count"], 4)
            self.assertEqual(candidates["rows"][0]["ticker"], "AAA")
            self.assertEqual(timeline["appearances"], 2)
            self.assertEqual(detail["candidate"]["scores"]["discovery"]["value"], 80)
            self.assertEqual(detail["candidate"]["scores"]["discovery"]["descriptor"], "Top tier")
            self.assertIn("discovery_score", detail["glossary"])
            self.assertEqual(weekly["promotions_to_ok"][0]["ticker"], "AAA")
            self.assertNotIn("rows", weekly)

    def test_dashboard_asset_is_self_contained(self):
        html = DASHBOARD_HTML.read_text(encoding="utf-8")

        self.assertIn("Discovery history", html)
        self.assertIn("/api/candidates", html)
        self.assertIn("/api/candidate/", html)
        self.assertIn("Price performance", html)
        self.assertIn("color-scheme:dark", html)
        self.assertNotIn("https://", html)

    @staticmethod
    def _row(ticker, status, score, country):
        return {
            "ticker": ticker, "company_name": f"{ticker} Company",
            "status": status, "country": country, "sector": "Technology",
            "exchange": "NASDAQ", "discovery_score": score,
            "score_confidence": 80, "fundamental_confidence": 60,
            "fundamental_data_quality": "fresh",
        }

    @staticmethod
    def _save(runs, fingerprint, now, rows):
        state = RunState.start_or_resume(
            runs, fingerprint, len(rows), clock=lambda: now,
        )
        for position, row in enumerate(rows):
            state.record_result(position, row)
        state.complete(rows, "report.csv")
        return state.run_id


if __name__ == "__main__":
    unittest.main()
