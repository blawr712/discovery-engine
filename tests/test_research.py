import json
from pathlib import Path
import tempfile
import unittest

from src.research import (
    ResearchCache,
    ResearchRunner,
    build_research_packets,
    build_research_prompt,
    export_research_packets,
)


def factor(name, points, maximum, quality="fresh"):
    return json.dumps({
        name: {
            "name": name,
            "points": points,
            "max_points": maximum,
            "available": True,
            "applicable": True,
            "data_quality": quality,
            "explanation": f"{name} explanation",
        }
    })


class CountingProvider:
    def __init__(self):
        self.calls = 0

    def generate(self, packet, prompt):
        self.calls += 1
        return {
            "business_overview": packet["company_name"],
            "citations": [],
        }


class FailingProvider:
    def generate(self, packet, prompt):
        if packet["ticker"] == "BAD":
            raise RuntimeError("provider failure")
        return {"business_overview": "ok", "citations": []}


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.results = [
            {
                "ticker": "ONE",
                "company_name": "One Co",
                "status": "OK",
                "country": "US",
                "sector": "Technology",
                "industry": "Software",
                "market_cap": 100_000_000,
                "factor_breakdown": factor("trend", 10, 10),
                "fundamental_breakdown": factor("profitability", 8, 8),
            },
            {
                "ticker": "TWO",
                "company_name": "Two Co",
                "status": "OK",
                "country": "CA",
                "sector": "Industrials",
                "factor_breakdown": factor("trend", 0, 10),
                "fundamental_breakdown": factor("profitability", 0, 8),
            },
        ]
        self.calibration = {
            "rows": [
                {
                    "ticker": "ONE",
                    "official_rank": 2,
                    "discovery_score": 60,
                    "technical_percentile": 90,
                    "core_fundamental_score": 100,
                    "core_fundamental_confidence": 100,
                    "peer_fundamental_percentile": 90,
                    "fundamental_peer_group": "US / Technology",
                    "outlier_flags": "",
                    "experimental_selected_rank": 1,
                    "experimental_selected_score": 80,
                },
                {
                    "ticker": "TWO",
                    "official_rank": 1,
                    "discovery_score": 70,
                    "technical_percentile": 100,
                    "core_fundamental_score": 0,
                    "core_fundamental_confidence": 100,
                    "peer_fundamental_percentile": 10,
                    "fundamental_peer_group": "CA / Industrials",
                    "outlier_flags": "",
                    "experimental_selected_rank": 2,
                    "experimental_selected_score": 70,
                },
            ],
            "summary": {
                "research_ranking_config": {
                    "selected_scenario": "selected",
                },
                "scenario_acceptance": {
                    "selected": {"status": "pass", "failures": []},
                },
                "coverage_neutral_model": {
                    "core_factors": ["profitability"],
                },
            },
        }

    def test_builds_ranked_deterministic_packets_without_changing_rank(self):
        packets, metadata = build_research_packets(
            self.results,
            1,
            calibration=self.calibration,
        )

        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0]["ticker"], "ONE")
        self.assertEqual(packets[0]["selected_rank"], 1)
        self.assertEqual(packets[0]["official_rank"], 2)
        self.assertTrue(
            packets[0]["source_policy"]["synthesis_must_not_change_rank"]
        )
        self.assertEqual(metadata["selected_scenario"], "selected")

    def test_prompt_forbids_rank_changes_and_requires_citations(self):
        packets, _ = build_research_packets(
            self.results,
            1,
            calibration=self.calibration,
        )
        prompt = build_research_prompt(packets[0], "v-test")

        self.assertIn("Do not change", prompt)
        self.assertIn("citations", prompt)
        self.assertIn("v-test", prompt)

    def test_runner_reuses_cache_and_isolates_provider_failures(self):
        packets, _ = build_research_packets(
            self.results,
            2,
            calibration=self.calibration,
        )
        with tempfile.TemporaryDirectory() as directory:
            provider = CountingProvider()
            cache = ResearchCache(Path(directory), "v-test")
            runner = ResearchRunner(provider, cache, "v-test")
            first = runner.run(packets)
            second = runner.run(packets)

            self.assertEqual(provider.calls, 2)
            self.assertTrue(all(row["status"] == "complete" for row in first))
            self.assertTrue(all(row["cached"] for row in second))

            failing_packets = [dict(packets[0], ticker="BAD"), packets[1]]
            failed = ResearchRunner(
                FailingProvider(),
                ResearchCache(Path(directory) / "fail", "v-test"),
                "v-test",
            ).run(failing_packets)

        self.assertEqual(failed[0]["status"], "error")
        self.assertEqual(failed[1]["status"], "complete")

    def test_packet_only_mode_and_exports(self):
        packets, metadata = build_research_packets(
            self.results,
            2,
            calibration=self.calibration,
        )
        outputs = ResearchRunner(provider=None).run(packets)
        with tempfile.TemporaryDirectory() as directory:
            artifacts = export_research_packets(
                packets,
                outputs,
                metadata,
                "run-1",
                Path(directory),
            )
            with open(
                artifacts["research_packets_json_path"],
                "r",
                encoding="utf-8",
            ) as file:
                payload = json.load(file)
            markdown = Path(
                artifacts["research_packets_markdown_path"]
            ).read_text(encoding="utf-8")

        self.assertEqual(payload["official_scores_and_ranks_unchanged"], True)
        self.assertEqual(artifacts["synthesis_statuses"], {"packet_only": 2})
        self.assertIn("Research questions", markdown)


if __name__ == "__main__":
    unittest.main()
