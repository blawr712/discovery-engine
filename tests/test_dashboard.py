from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from urllib.request import Request, urlopen

from src.dashboard import DASHBOARD_HTML, DashboardStore, create_dashboard_server
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
            watchlist_path = root / "watchlists.json"
            store = DashboardStore(database, watchlist_path)

            overview = store.overview()
            candidates = store.candidates(new_id, status="OK", country="US")
            timeline = store.ticker_history("aaa")
            detail = store.candidate_detail("aaa", new_id)
            comparison = store.compare_candidates(["aaa", "bbb"], new_id)
            watchlist = store.create_watchlist("Research queue")
            store.add_to_watchlist(watchlist["id"], "aaa")
            watchlists = store.watchlists(new_id)
            weekly = store.weekly_report()

            self.assertEqual(overview["run_count"], 2)
            self.assertEqual(overview["result_count"], 4)
            self.assertEqual(overview["latest_price_coverage_percent"], 0)
            self.assertEqual(candidates["rows"][0]["ticker"], "AAA")
            self.assertEqual(timeline["appearances"], 2)
            self.assertEqual(detail["candidate"]["scores"]["discovery"]["value"], 80)
            self.assertEqual(detail["candidate"]["scores"]["discovery"]["descriptor"], "Top tier")
            self.assertIn("discovery_score", detail["glossary"])
            self.assertEqual(comparison["tickers"], ["AAA", "BBB"])
            self.assertEqual(comparison["candidate_count"], 2)
            self.assertEqual(
                comparison["candidates"][0]["fundamental_score"]["value"], None
            )
            tracked = watchlists["watchlists"][0]["items"][0]
            self.assertEqual(watchlists["previous_run_id"], old_id)
            self.assertIn("fingerprints differ", watchlists["comparison_warnings"][0])
            self.assertEqual(tracked["ticker"], "AAA")
            self.assertEqual(tracked["current_status"], "OK")
            self.assertEqual(tracked["previous_status"], "FILTERED")
            self.assertEqual(tracked["score_change"], 40)
            store.remove_from_watchlist(watchlist["id"], "AAA")
            store.delete_watchlist(watchlist["id"])
            self.assertEqual(store.watchlists(new_id)["watchlists"], [])
            self.assertEqual(weekly["promotions_to_ok"][0]["ticker"], "AAA")
            self.assertNotIn("rows", weekly)

    def test_dashboard_asset_is_self_contained(self):
        html = DASHBOARD_HTML.read_text(encoding="utf-8")

        self.assertIn("Discovery history", html)
        self.assertIn("/api/candidates", html)
        self.assertIn("/api/candidate/", html)
        self.assertIn("Price performance", html)
        self.assertIn("color-scheme:dark", html)
        self.assertIn("/api/compare", html)
        self.assertIn("/api/watchlists", html)
        self.assertNotIn("https://", html)

    def test_comparison_requires_two_to_five_unique_tickers(self):
        store = DashboardStore(Path("missing.sqlite3"))

        with self.assertRaisesRegex(ValueError, "2 to 5"):
            store.compare_candidates(["AAA", "aaa"])
        with self.assertRaisesRegex(ValueError, "2 to 5"):
            store.compare_candidates(["A", "B", "C", "D", "E", "F"])

    def test_watchlist_rejects_ticker_missing_from_indexed_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            database = root / "history.sqlite3"
            run_id = self._save(
                runs, "one", datetime(2026, 8, 1, tzinfo=timezone.utc),
                [self._row("AAA", "OK", 80, "US")],
            )
            index_saved_run(database, runs, run_id)
            store = DashboardStore(database, root / "watchlists.json")
            watchlist = store.create_watchlist("Ideas")

            with self.assertRaisesRegex(ValueError, "not present"):
                store.add_to_watchlist(watchlist["id"], "MISSING")

    def test_watchlist_http_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            database = root / "history.sqlite3"
            run_id = self._save(
                runs, "one", datetime(2026, 8, 1, tzinfo=timezone.utc),
                [self._row("AAA", "OK", 80, "US")],
            )
            index_saved_run(database, runs, run_id)
            server = create_dashboard_server(
                database, port=0, watchlist_path=root / "watchlists.json"
            )
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                created = self._request(
                    base_url + "/api/watchlists", "POST", {"name": "Ideas"}
                )
                self._request(
                    base_url + f"/api/watchlists/{created['id']}/items",
                    "POST", {"ticker": "AAA"},
                )
                payload = self._request(
                    base_url + f"/api/watchlists?run_id={run_id}"
                )
                self.assertEqual(
                    payload["watchlists"][0]["items"][0]["ticker"], "AAA"
                )
                self._request(
                    base_url + f"/api/watchlists/{created['id']}/items/AAA",
                    "DELETE",
                )
                self._request(
                    base_url + f"/api/watchlists/{created['id']}", "DELETE"
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    @staticmethod
    def _request(url, method="GET", payload=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            url, data=data, method=method,
            headers={"Content-Type": "application/json"} if data else {},
        )
        with urlopen(request, timeout=3) as response:
            return json.loads(response.read().decode("utf-8"))

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
