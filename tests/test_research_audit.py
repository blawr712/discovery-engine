import csv
import json
from pathlib import Path
import tempfile
import unittest

from src.research_audit import (
    audit_research_payload,
    export_research_audit,
    finalize_research_review,
)


def payload_with_synthesis():
    citation = {"url": "https://www.sec.gov/filing", "content_hash": "a" * 64}
    claim = {
        "text": "A supported fact.",
        "classification": "sourced_fact",
        "citations": [citation],
    }
    return {
        "run_id": "run-1",
        "official_scores_and_ranks_unchanged": True,
        "packets": [
            {
                "ticker": "USCO", "country": "US", "selected_rank": 1,
                "official_rank": 2,
                "evidence_documents": [{**citation, "source_type": "regulatory_filing", "publisher": "SEC"}],
            },
            {
                "ticker": "CACO", "country": "CA", "selected_rank": 2,
                "official_rank": 1, "evidence_documents": [],
            },
        ],
        "outputs": [
            {
                "ticker": "USCO", "status": "complete", "cached": False,
                "synthesis": {
                    "business_overview": [claim],
                    "growth_drivers": [claim],
                    "risks": [claim],
                    "recent_developments": [claim],
                    "unanswered_questions": ["What remains unknown?"],
                },
            },
            {"ticker": "CACO", "status": "skipped_no_evidence", "synthesis": None},
        ],
    }


class ResearchAuditTests(unittest.TestCase):
    def setUp(self):
        self.gates = {
            "minimum_evidence_coverage_percent": 50,
            "minimum_synthesis_completion_percent": 100,
            "minimum_citation_coverage_percent": 100,
            "minimum_section_coverage_percent": 75,
            "minimum_sourced_claims_per_synthesis": 1,
            "maximum_synthesis_errors": 0,
        }

    def test_passes_automated_gates_but_requires_human_signoff(self):
        audit = audit_research_payload(payload_with_synthesis(), self.gates)

        self.assertEqual(audit["automated_status"], "pass")
        self.assertEqual(audit["release_status"], "pending_human_review")
        self.assertTrue(audit["human_signoff_required"])
        self.assertEqual(audit["metrics"]["country_evidence_coverage"]["CA"]["coverage_percent"], 0)
        self.assertEqual(audit["metrics"]["country_evidence_coverage"]["US"]["coverage_percent"], 100)
        self.assertEqual(audit["metrics"]["citation_coverage_percent"], 100)

    def test_packet_only_payload_marks_synthesis_gates_not_evaluated(self):
        payload = payload_with_synthesis()
        payload["outputs"][0] = {"ticker": "USCO", "status": "packet_only", "synthesis": None}
        audit = audit_research_payload(payload, self.gates)

        self.assertEqual(audit["automated_status"], "not_evaluated")
        self.assertIn("synthesis_completion", audit["not_evaluated_gates"])

    def test_ranking_integrity_failure_blocks_audit(self):
        payload = payload_with_synthesis()
        payload["official_scores_and_ranks_unchanged"] = False
        audit = audit_research_payload(payload, self.gates)

        self.assertEqual(audit["automated_status"], "fail")
        self.assertIn("ranking_integrity", audit["failed_gates"])

    def test_exports_claim_level_human_review_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            artifacts = export_research_audit(
                payload_with_synthesis(), "run-1", Path(directory), self.gates,
            )
            audit = json.loads(Path(artifacts["research_audit_json_path"]).read_text(encoding="utf-8"))
            with open(artifacts["research_human_review_csv_path"], encoding="utf-8", newline="") as file:
                rows = list(csv.DictReader(file))

        self.assertEqual(audit["automated_status"], "pass")
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["human_review_status"], "pending")
        self.assertEqual(rows[0]["accuracy_review"], "")

    def test_finalizes_only_completed_human_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = export_research_audit(
                payload_with_synthesis(), "run-1", root, self.gates,
            )
            review_path = Path(artifacts["research_human_review_csv_path"])
            with review_path.open(encoding="utf-8", newline="") as file:
                rows = list(csv.DictReader(file))
                fields = rows[0].keys()
            for row in rows:
                row["accuracy_review"] = "pass"
                row["citation_support_review"] = "pass"
                row["human_review_status"] = "approved"
            with review_path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)

            decision = finalize_research_review(
                Path(artifacts["research_audit_json_path"]),
                review_path,
                "run-1",
                root,
            )

        self.assertEqual(decision["human_review_decision"], "approved")
        self.assertEqual(decision["approved_row_count"], 4)

    def test_incomplete_review_cannot_be_approved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = export_research_audit(
                payload_with_synthesis(), "run-1", root, self.gates,
            )
            decision = finalize_research_review(
                Path(artifacts["research_audit_json_path"]),
                Path(artifacts["research_human_review_csv_path"]),
                "run-1",
                root,
            )

        self.assertEqual(decision["human_review_decision"], "incomplete")
        self.assertTrue(decision["pending_csv_rows"])


if __name__ == "__main__":
    unittest.main()
