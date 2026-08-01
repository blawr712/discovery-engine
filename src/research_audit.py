"""Offline research quality audit and human-review queue exports."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from pathlib import Path

from src.config import OUTPUT_DIR, RESEARCH_REVIEW_CONFIG
from src.research import validate_synthesis


SECTIONS = (
    "business_overview", "growth_drivers", "risks", "recent_developments",
)


def audit_research_payload(payload: dict, gates: dict | None = None) -> dict:
    """Revalidate a saved research payload and evaluate automated gates."""
    gates = gates or RESEARCH_REVIEW_CONFIG
    packets = payload.get("packets", [])
    outputs = payload.get("outputs", [])
    output_lookup = {str(row.get("ticker")): row for row in outputs}
    companies = []
    for packet in packets:
        ticker = str(packet.get("ticker", ""))
        output = output_lookup.get(ticker, {})
        evidence = packet.get("evidence_documents", [])
        synthesis = output.get("synthesis")
        validation_error = None
        validation = None
        if isinstance(synthesis, dict):
            try:
                validation = validate_synthesis(packet, synthesis)
            except (TypeError, ValueError) as error:
                validation_error = str(error)
        section_presence = {
            section: bool(synthesis.get(section)) if isinstance(synthesis, dict) else False
            for section in SECTIONS
        }
        companies.append({
            "ticker": ticker,
            "country": packet.get("country") or "UNKNOWN",
            "selected_rank": packet.get("selected_rank"),
            "official_rank": packet.get("official_rank"),
            "evidence_document_count": len(evidence),
            "evidence_source_types": sorted({
                str(row.get("source_type")) for row in evidence if row.get("source_type")
            }),
            "evidence_publishers": sorted({
                str(row.get("publisher")) for row in evidence if row.get("publisher")
            }),
            "synthesis_status": output.get("status", "missing"),
            "cached": bool(output.get("cached")),
            "validation_status": (
                "pass" if validation else "fail" if validation_error else "not_evaluated"
            ),
            "validation_error": validation_error,
            "claim_count": validation.get("claim_count", 0) if validation else 0,
            "sourced_claim_count": validation.get("sourced_claim_count", 0) if validation else 0,
            "citation_count": validation.get("citation_count", 0) if validation else 0,
            "section_presence": section_presence,
            "human_review_status": "pending" if validation else "not_ready",
        })

    count = len(companies)
    evidenced = [row for row in companies if row["evidence_document_count"] > 0]
    completed = [row for row in evidenced if row["validation_status"] == "pass"]
    sourced_claims = sum(row["sourced_claim_count"] for row in completed)
    citations = sum(row["citation_count"] for row in completed)
    section_slots = len(completed) * len(SECTIONS)
    sections_present = sum(
        sum(row["section_presence"].values()) for row in completed
    )
    metrics = {
        "candidate_count": count,
        "evidenced_candidate_count": len(evidenced),
        "validated_synthesis_count": len(completed),
        "synthesis_error_count": sum(
            row["synthesis_status"] == "error" or row["validation_status"] == "fail"
            for row in companies
        ),
        "evidence_coverage_percent": _percent(len(evidenced), count),
        "synthesis_completion_percent": _percent(len(completed), len(evidenced)),
        "citation_coverage_percent": (
            100.0 if sourced_claims == 0 and completed
            else _percent(sourced_claims, sourced_claims) if sourced_claims else 0.0
        ),
        "section_coverage_percent": _percent(sections_present, section_slots),
        "claim_count": sum(row["claim_count"] for row in completed),
        "sourced_claim_count": sourced_claims,
        "citation_count": citations,
        "average_sourced_claims_per_synthesis": round(
            sourced_claims / len(completed), 2
        ) if completed else 0.0,
        "country_evidence_coverage": _country_coverage(companies),
    }
    gate_results = _gate_results(
        metrics,
        gates,
        synthesis_present=bool(completed),
        ranking_integrity=payload.get("official_scores_and_ranks_unchanged") is True,
    )
    failed = [name for name, row in gate_results.items() if row["status"] == "fail"]
    not_evaluated = [
        name for name, row in gate_results.items() if row["status"] == "not_evaluated"
    ]
    automated_status = "fail" if failed else "not_evaluated" if not_evaluated else "pass"
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": payload.get("run_id"),
        "scores_and_ranks_unchanged": payload.get("official_scores_and_ranks_unchanged") is True,
        "metrics": metrics,
        "gates": gate_results,
        "automated_status": automated_status,
        "failed_gates": failed,
        "not_evaluated_gates": not_evaluated,
        "human_signoff_required": True,
        "release_status": "pending_human_review" if automated_status == "pass" else automated_status,
        "companies": companies,
    }


def export_research_audit(
    payload: dict,
    run_id: str,
    output_directory: Path | None = None,
    gates: dict | None = None,
) -> dict:
    """Export audit JSON plus a claim-level human-review CSV."""
    output_directory = Path(output_directory or OUTPUT_DIR)
    output_directory.mkdir(parents=True, exist_ok=True)
    audit = audit_research_payload(payload, gates=gates)
    audit_path = output_directory / f"research_audit_{run_id}.json"
    review_path = output_directory / f"research_human_review_{run_id}.csv"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")
    rows = _review_rows(payload, audit)
    fields = [
        "ticker", "country", "selected_rank", "section", "classification",
        "claim", "citation_urls", "citation_hashes", "automated_validation",
        "accuracy_review", "citation_support_review", "materiality_notes",
        "human_review_status",
    ]
    with review_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return {
        "research_audit_json_path": str(audit_path),
        "research_human_review_csv_path": str(review_path),
        "automated_status": audit["automated_status"],
        "release_status": audit["release_status"],
        "metrics": audit["metrics"],
        "failed_gates": audit["failed_gates"],
        "not_evaluated_gates": audit["not_evaluated_gates"],
        "review_row_count": len(rows),
    }


def finalize_research_review(
    audit_path: Path,
    review_path: Path,
    run_id: str,
    output_directory: Path | None = None,
) -> dict:
    """Create a decision record from an automated pass and completed review CSV."""
    audit = json.loads(Path(audit_path).read_text(encoding="utf-8"))
    if audit.get("run_id") != run_id:
        raise ValueError("Research audit run ID does not match.")
    if audit.get("automated_status") != "pass":
        raise ValueError("Automated research gates must pass before finalization.")
    with Path(review_path).open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    if not rows:
        raise ValueError("Human review queue has no claim rows.")
    required = {"accuracy_review", "citation_support_review", "human_review_status"}
    if not required.issubset(rows[0]):
        raise ValueError("Human review queue is missing required decision columns.")
    pending = []
    rejected = []
    for index, row in enumerate(rows, start=2):
        accuracy = str(row.get("accuracy_review", "")).strip().lower()
        support = str(row.get("citation_support_review", "")).strip().lower()
        status = str(row.get("human_review_status", "")).strip().lower()
        if accuracy not in {"pass", "fail"} or support not in {"pass", "fail"} or status not in {"approved", "rejected"}:
            pending.append(index)
        elif "fail" in {accuracy, support} or status == "rejected":
            rejected.append(index)
    if pending:
        decision = "incomplete"
    elif rejected:
        decision = "rejected"
    else:
        decision = "approved"
    record = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "automated_status": audit["automated_status"],
        "human_review_decision": decision,
        "research_release_status": decision,
        "review_row_count": len(rows),
        "approved_row_count": len(rows) - len(pending) - len(rejected),
        "pending_csv_rows": pending,
        "rejected_csv_rows": rejected,
        "scores_and_ranks_unchanged": audit.get("scores_and_ranks_unchanged") is True,
        "source_audit_path": str(Path(audit_path)),
        "source_review_path": str(Path(review_path)),
    }
    output_directory = Path(output_directory or OUTPUT_DIR)
    decision_path = output_directory / f"research_acceptance_{run_id}.json"
    decision_path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return {**record, "research_acceptance_json_path": str(decision_path)}


def _review_rows(payload: dict, audit: dict) -> list[dict]:
    packets = {str(row.get("ticker")): row for row in payload.get("packets", [])}
    companies = {row["ticker"]: row for row in audit["companies"]}
    rows = []
    for output in payload.get("outputs", []):
        ticker = str(output.get("ticker", ""))
        synthesis = output.get("synthesis")
        if not isinstance(synthesis, dict):
            continue
        packet = packets.get(ticker, {})
        company = companies.get(ticker, {})
        for section in SECTIONS:
            for claim in synthesis.get(section, []):
                citations = claim.get("citations", [])
                rows.append({
                    "ticker": ticker,
                    "country": packet.get("country"),
                    "selected_rank": packet.get("selected_rank"),
                    "section": section,
                    "classification": claim.get("classification"),
                    "claim": claim.get("text"),
                    "citation_urls": json.dumps([row.get("url") for row in citations]),
                    "citation_hashes": json.dumps([row.get("content_hash") for row in citations]),
                    "automated_validation": company.get("validation_status"),
                    "accuracy_review": "",
                    "citation_support_review": "",
                    "materiality_notes": "",
                    "human_review_status": "pending",
                })
    return rows


def _gate_results(
    metrics: dict,
    gates: dict,
    synthesis_present: bool,
    ranking_integrity: bool,
) -> dict:
    definitions = {
        "evidence_coverage": (
            metrics["evidence_coverage_percent"],
            float(gates.get("minimum_evidence_coverage_percent", 80)),
        ),
        "synthesis_completion": (
            metrics["synthesis_completion_percent"],
            float(gates.get("minimum_synthesis_completion_percent", 100)),
        ),
        "citation_coverage": (
            metrics["citation_coverage_percent"],
            float(gates.get("minimum_citation_coverage_percent", 100)),
        ),
        "section_coverage": (
            metrics["section_coverage_percent"],
            float(gates.get("minimum_section_coverage_percent", 75)),
        ),
    }
    results = {}
    for name, (actual, required) in definitions.items():
        if name != "evidence_coverage" and not synthesis_present:
            status = "not_evaluated"
        else:
            status = "pass" if actual >= required else "fail"
        results[name] = {"status": status, "actual": actual, "minimum": required}
    minimum_sourced = float(gates.get("minimum_sourced_claims_per_synthesis", 1))
    results["sourced_evidence_use"] = {
        "status": (
            "not_evaluated" if not synthesis_present
            else "pass" if metrics["average_sourced_claims_per_synthesis"] >= minimum_sourced
            else "fail"
        ),
        "actual": metrics["average_sourced_claims_per_synthesis"],
        "minimum": minimum_sourced,
    }
    results["ranking_integrity"] = {
        "status": "pass" if ranking_integrity else "fail",
        "actual": ranking_integrity,
        "required": True,
    }
    maximum = int(gates.get("maximum_synthesis_errors", 0))
    results["synthesis_errors"] = {
        "status": (
            "not_evaluated" if not synthesis_present and metrics["synthesis_error_count"] == 0
            else "pass" if metrics["synthesis_error_count"] <= maximum else "fail"
        ),
        "actual": metrics["synthesis_error_count"],
        "maximum": maximum,
    }
    return results


def _country_coverage(companies: list[dict]) -> dict:
    result = {}
    countries = sorted({str(row["country"]) for row in companies})
    for country in countries:
        rows = [row for row in companies if str(row["country"]) == country]
        evidenced = sum(row["evidence_document_count"] > 0 for row in rows)
        result[country] = {
            "candidates": len(rows),
            "evidenced": evidenced,
            "coverage_percent": _percent(evidenced, len(rows)),
        }
    return result


def _percent(numerator: int, denominator: int) -> float:
    return round(100 * numerator / denominator, 2) if denominator else 0.0
