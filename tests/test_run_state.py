from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from src.run_state import RunState, build_run_fingerprint, summarize_results


class MutableClock:
    def __init__(self):
        self.value = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.value


class RunStateTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.clock = MutableClock()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_resumes_compatible_incomplete_run(self):
        state = RunState.start_or_resume(
            self.root,
            "same-fingerprint",
            2,
            clock=self.clock,
        )
        state.record_result(
            0,
            {"ticker": "ONE", "status": "OK", "discovery_score": 50},
        )

        resumed = RunState.start_or_resume(
            self.root,
            "same-fingerprint",
            2,
            clock=self.clock,
        )

        self.assertTrue(resumed.resumed)
        self.assertEqual(resumed.run_id, state.run_id)
        self.assertEqual(resumed.load_results()[0]["ticker"], "ONE")

    def test_does_not_resume_incompatible_or_completed_run(self):
        first = RunState.start_or_resume(
            self.root,
            "first",
            1,
            clock=self.clock,
        )
        first.complete(
            [{"ticker": "ONE", "status": "OK"}],
            "report.csv",
        )

        second = RunState.start_or_resume(
            self.root,
            "different",
            1,
            clock=self.clock,
        )

        self.assertFalse(second.resumed)
        self.assertNotEqual(second.run_id, first.run_id)

    def test_excludes_error_checkpoints_when_configured_for_retry(self):
        state = RunState.start_or_resume(
            self.root,
            "fingerprint",
            2,
            clock=self.clock,
        )
        state.record_result(
            0,
            {"ticker": "FAILED", "status": "ERROR"},
        )
        state.record_result(
            1,
            {"ticker": "FILTERED", "status": "FILTERED"},
        )

        self.assertEqual(list(state.load_results()), [1])
        self.assertEqual(len(state.load_results(retry_errors=False)), 2)

    def test_replacing_error_checkpoint_does_not_inflate_progress(self):
        state = RunState.start_or_resume(
            self.root,
            "fingerprint",
            1,
            clock=self.clock,
        )
        state.record_result(0, {"ticker": "ONE", "status": "ERROR"})
        state.record_result(0, {"ticker": "ONE", "status": "OK"})

        self.assertEqual(state.manifest["completed_count"], 1)
        self.assertEqual(state.load_results()[0]["status"], "OK")

    def test_complete_writes_structured_manifest_summary(self):
        state = RunState.start_or_resume(
            self.root,
            "fingerprint",
            2,
            clock=self.clock,
        )
        self.clock.value += timedelta(seconds=12.3456)
        results = [
            {
                "ticker": "ONE",
                "status": "OK",
                "country": "CA",
                "exchange": "TSX",
            },
            {
                "ticker": "TWO",
                "status": "ERROR",
                "reason_flags": "Metadata: TimeoutError",
            },
        ]

        state.complete(results, "final.csv")

        with state.manifest_path.open("r", encoding="utf-8") as file:
            manifest = json.load(file)
        self.assertEqual(manifest["status"], "complete")
        self.assertEqual(manifest["duration_seconds"], 12.346)
        self.assertEqual(manifest["report_path"], "final.csv")
        self.assertEqual(manifest["summary"]["statuses"], {"ERROR": 1, "OK": 1})
        self.assertEqual(manifest["summary"]["failure_stages"], {"Metadata": 1})

    def test_fingerprint_is_stable_and_input_sensitive(self):
        universe = [{"ticker": "ONE", "country": "US"}]
        first = build_run_fingerprint(universe, {"weight": 1}, {"workers": 5})
        reordered = build_run_fingerprint(
            [{"country": "US", "ticker": "ONE"}],
            {"weight": 1},
            {"workers": 5},
        )
        changed = build_run_fingerprint(
            universe,
            {"weight": 2},
            {"workers": 5},
        )

        self.assertEqual(first, reordered)
        self.assertNotEqual(first, changed)

    def test_summary_counts_unknown_dimensions(self):
        summary = summarize_results([{"ticker": "ONE", "status": "FAILED"}])

        self.assertEqual(summary["countries"], {"UNKNOWN": 1})
        self.assertEqual(summary["exchanges"], {"UNKNOWN": 1})


if __name__ == "__main__":
    unittest.main()
