import os
import json
import sqlite3
from pathlib import Path

from src.universe import UniverseBuilder
from src.data_sources.yfinance_source import YFinanceSource
from src.data_sources.cached_source import CachedMarketDataSource
from src.data_sources.retrying_source import RetryingMarketDataSource
from src.data_sources.rate_limited_source import RateLimitedMarketDataSource
from src.report import (
    export_candidate_report,
    export_experimental_research_reports,
    export_report,
)
from src.analytics import export_run_analytics
from src.calibration import build_calibration, export_calibration
from src.engine import DiscoveryEngine
from src.run_state import (
    RunState,
    build_run_fingerprint,
    load_saved_run,
    load_saved_manifest,
    record_recalibration,
    record_research_packets,
    record_research_audit,
    record_research_acceptance,
)
from src.research import (
    ResearchCache,
    ResearchRunner,
    build_research_packets,
    export_research_packets,
)
from src.evidence import (
    CanadianIssuerManifestProvider,
    HttpCache,
    ManifestEvidenceProvider,
    SecEdgarProvider,
    attach_evidence,
    collect_evidence,
    export_evidence,
)
from src.openai_research import OpenAIResearchProvider
from src.research_audit import export_research_audit, finalize_research_review
from src.history import history_summary, index_saved_run
from src.history_comparison import compare_indexed_runs, export_run_comparison
from src.history_reporting import (
    build_ticker_history,
    build_weekly_report,
    export_ticker_history,
    export_weekly_report,
)
from src.dashboard import run_dashboard
from src.cli import parse_args, select_universe
from src.config import (
    BENCHMARKS,
    CACHE_DIR,
    CACHE_ENABLED,
    CACHE_METADATA_TTL_HOURS,
    CACHE_METADATA_VERSION,
    CACHE_PRICE_HISTORY_TTL_HOURS,
    MAX_CONCURRENT_DOWNLOADS,
    METADATA_CONCURRENT_DOWNLOADS,
    PRICE_CONCURRENT_DOWNLOADS,
    RETRY_BASE_DELAY_SECONDS,
    RETRY_ENABLED,
    RETRY_JITTER_SECONDS,
    RETRY_MAX_ATTEMPTS,
    RETRY_MAX_DELAY_SECONDS,
    RESUME_ENABLED,
    RETRY_ERRORS_ON_RESUME,
    RUN_DIR,
    OUTPUT_DIR,
    SETTINGS,
    STRATEGY,
    RATE_LIMIT_ENABLED,
    METADATA_INTERVAL_SECONDS,
    PRICE_INTERVAL_SECONDS,
    RATE_LIMIT_COOLDOWN_SECONDS,
    MAX_RATE_LIMIT_COOLDOWN_EVENTS,
    RESEARCH_DEFAULT_TOP,
    RESEARCH_AI_ENABLED,
    RESEARCH_CACHE_DIR,
    RESEARCH_PROMPT_VERSION,
    SYNTHESIS_MODEL,
    SYNTHESIS_PROVIDER,
    HISTORY_DATABASE,
)


def print_progress(
    phase: str,
    completed: int,
    total: int,
    ticker: str,
) -> None:
    """Print compact progress for each collection phase."""
    print(f"[{phase}] {completed}/{total}: {ticker}")


def main(arguments=None):
    args = parse_args(arguments)
    if args.index_run:
        index_history_run(args.index_run)
        return
    if args.history_summary:
        print_history_summary()
        return
    if args.compare_runs:
        compare_history_runs(*args.compare_runs)
        return
    if args.ticker_history:
        export_history_timeline(args.ticker_history)
        return
    if args.weekly_report:
        generate_weekly_history_report()
        return
    if args.dashboard:
        try:
            run_dashboard(HISTORY_DATABASE, port=args.dashboard_port)
        except (FileNotFoundError, OSError, ValueError, sqlite3.Error) as error:
            raise SystemExit(f"Unable to start history dashboard: {error}") from error
        return
    if args.recalibrate_run:
        recalibrate_saved_run(args.recalibrate_run)
        return
    if args.audit_research:
        audit_saved_research(args.audit_research)
        return
    if args.finalize_research_review:
        finalize_saved_research_review(args.finalize_research_review)
        return
    if args.research_run:
        research_saved_run(
            args.research_run,
            (
                args.top
                or (args.balanced_research * 2 if args.balanced_research else None)
                or RESEARCH_DEFAULT_TOP
            ),
            collect_sources=args.collect_sources,
            source_manifest=args.source_manifest,
            canadian_source_manifest=args.canadian_source_manifest,
            synthesize=args.synthesize,
            balanced_per_country=args.balanced_research,
        )
        return
    provider = RateLimitedMarketDataSource(
        YFinanceSource(),
        metadata_interval_seconds=METADATA_INTERVAL_SECONDS,
        price_interval_seconds=PRICE_INTERVAL_SECONDS,
        cooldown_seconds=RATE_LIMIT_COOLDOWN_SECONDS,
        max_cooldown_events=MAX_RATE_LIMIT_COOLDOWN_EVENTS,
        enabled=RATE_LIMIT_ENABLED,
    )
    retry_source = RetryingMarketDataSource(
        provider,
        max_attempts=RETRY_MAX_ATTEMPTS if RETRY_ENABLED else 1,
        base_delay_seconds=RETRY_BASE_DELAY_SECONDS,
        max_delay_seconds=RETRY_MAX_DELAY_SECONDS,
        jitter_seconds=RETRY_JITTER_SECONDS,
    )
    source = CachedMarketDataSource(
        retry_source,
        cache_directory=CACHE_DIR,
        metadata_ttl_hours=CACHE_METADATA_TTL_HOURS,
        metadata_version=CACHE_METADATA_VERSION,
        price_history_ttl_hours=CACHE_PRICE_HISTORY_TTL_HOURS,
        enabled=CACHE_ENABLED,
    )
    universe = UniverseBuilder().build_universe()
    try:
        universe = select_universe(
            universe,
            tickers=args.tickers,
            limit=args.limit,
            balanced_sample=args.balanced_sample,
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error
    fingerprint = build_run_fingerprint(universe, STRATEGY, SETTINGS)
    run_state = RunState.start_or_resume(
        RUN_DIR,
        fingerprint,
        len(universe),
        resume_enabled=RESUME_ENABLED,
    )
    prior_results = run_state.load_results(
        retry_errors=RETRY_ERRORS_ON_RESUME,
    )

    print(f"Selected {len(universe)} tickers for analysis")
    print(f"Concurrent downloads: {MAX_CONCURRENT_DOWNLOADS}")
    print(f"Metadata workers: {METADATA_CONCURRENT_DOWNLOADS}")
    print(f"Price workers: {PRICE_CONCURRENT_DOWNLOADS}")
    print(f"Run ID: {run_state.run_id}")
    print(f"Resumed results: {len(prior_results)}")

    engine = DiscoveryEngine(
        source,
        benchmarks=BENCHMARKS,
        max_workers=MAX_CONCURRENT_DOWNLOADS,
        metadata_workers=METADATA_CONCURRENT_DOWNLOADS,
        price_workers=PRICE_CONCURRENT_DOWNLOADS,
        progress_callback=print_progress,
        result_callback=run_state.record_result,
    )
    results = engine.run(universe, prior_results=prior_results)

    output_path = export_report(results, run_id=run_state.run_id)
    candidate_output_path = export_candidate_report(
        results,
        run_id=run_state.run_id,
    )
    analytics_output_path = export_run_analytics(
        results,
        run_id=run_state.run_id,
        output_directory=OUTPUT_DIR,
    )
    intelligence = export_intelligence_artifacts(results, run_state.run_id)
    calibration_csv_path = intelligence["calibration_csv_path"]
    calibration_json_path = intelligence["calibration_json_path"]
    run_state.complete(
        results,
        output_path,
        candidate_report_path=candidate_output_path,
        analytics_path=analytics_output_path,
        calibration_csv_path=calibration_csv_path,
        calibration_json_path=calibration_json_path,
        research_artifacts=intelligence["research_artifacts"],
    )

    passed = sum(1 for r in results if r.get("status") == "OK")
    filtered = sum(1 for r in results if r.get("status") == "FILTERED")
    scoring_failed = sum(1 for r in results if r.get("status") == "FAILED")
    errors = sum(1 for r in results if r.get("status") == "ERROR")

    print("\nRun Summary")
    print(f"Total: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Filtered: {filtered}")
    print(f"Scoring failed: {scoring_failed}")
    print(f"Errors: {errors}")
    if source.enabled:
        print(f"Cache hits: {source.stats.hits}")
        print(f"Cache misses: {source.stats.misses}")
        print(f"Cache expired: {source.stats.expired}")
        print(f"Cache read errors: {source.stats.read_errors}")
    print(f"Provider retries: {retry_source.stats.retries}")
    print(f"Retries exhausted: {retry_source.stats.exhausted}")
    if provider.enabled:
        print(f"Pacing waits: {provider.stats.pacing_waits}")
        print(f"Rate-limit cooldowns: {provider.stats.cooldown_events}")
        print(f"Cooldown waits: {provider.stats.cooldown_waits}")
        print(f"Circuit opened: {provider.stats.circuit_open_events}")
        print(f"Circuit rejections: {provider.stats.circuit_rejections}")

    print("\nDone.")
    print(f"Run status: {run_state.manifest['status']}")
    print(f"Report saved to: {output_path}")
    print(f"Candidate report saved to: {candidate_output_path}")
    print(f"Analytics saved to: {analytics_output_path}")
    print(f"Calibration rows saved to: {calibration_csv_path}")
    print(f"Calibration analysis saved to: {calibration_json_path}")
    print(
        "Research review saved to: "
        f"{intelligence['research_artifacts']['review_report_path']}"
    )
    print(
        "Selected v0.3 research queue saved to: "
        f"{intelligence['research_artifacts']['selected_research_report_path']}"
    )
    print(f"Manifest saved to: {run_state.manifest_path}")


def index_history_run(run_id: str) -> None:
    try:
        result = index_saved_run(HISTORY_DATABASE, RUN_DIR, run_id)
    except (FileNotFoundError, OSError, ValueError, sqlite3.Error) as error:
        raise SystemExit(f"Unable to index saved run: {error}") from error
    print(f"History index complete for run: {result['run_id']}")
    print(f"Indexed results: {result['indexed_results']}")
    print(f"History database: {result['database_path']}")


def print_history_summary() -> None:
    try:
        result = history_summary(HISTORY_DATABASE)
    except (OSError, sqlite3.Error) as error:
        raise SystemExit(f"Unable to read history index: {error}") from error
    print("Discovery Engine history summary")
    print(f"Indexed runs: {result['run_count']}")
    print(f"Indexed results: {result['result_count']}")
    if result["latest_run"]:
        print(f"Latest run: {result['latest_run']['run_id']}")


def compare_history_runs(old_run_id: str, new_run_id: str) -> None:
    try:
        result = compare_indexed_runs(HISTORY_DATABASE, old_run_id, new_run_id)
        csv_path, json_path = export_run_comparison(result, OUTPUT_DIR)
    except (FileNotFoundError, OSError, ValueError, sqlite3.Error) as error:
        raise SystemExit(f"Unable to compare indexed runs: {error}") from error
    summary = result["summary"]
    print(f"History comparison complete: {old_run_id} -> {new_run_id}")
    print(f"Entrants: {summary['entrants']}")
    print(f"Exits: {summary['exits']}")
    print(f"Retained: {summary['retained']}")
    print(f"Status transitions: {summary['status_transitions']}")
    print(f"Rank changes: {summary['rank_changes']}")
    print(f"Score changes: {summary['score_changes']}")
    print(f"Data-quality changes: {summary['data_quality_changes']}")
    print(f"Comparison CSV saved to: {csv_path}")
    print(f"Comparison JSON saved to: {json_path}")


def export_history_timeline(ticker: str) -> None:
    try:
        history = build_ticker_history(HISTORY_DATABASE, ticker)
        csv_path, json_path = export_ticker_history(history, OUTPUT_DIR)
    except (FileNotFoundError, OSError, ValueError, sqlite3.Error) as error:
        raise SystemExit(f"Unable to build ticker history: {error}") from error
    print(f"Ticker history complete: {history['ticker']}")
    print(f"Indexed appearances: {history['appearances']}")
    print(f"Best rank: {history['best_rank']}")
    print(f"Worst rank: {history['worst_rank']}")
    print(f"Timeline CSV saved to: {csv_path}")
    print(f"Timeline JSON saved to: {json_path}")


def generate_weekly_history_report() -> None:
    try:
        report = build_weekly_report(HISTORY_DATABASE)
        markdown_path, csv_path, json_path = export_weekly_report(report, OUTPUT_DIR)
    except (FileNotFoundError, OSError, ValueError, sqlite3.Error) as error:
        raise SystemExit(f"Unable to build weekly history report: {error}") from error
    print(
        f"Weekly history report complete: {report['old_run_id']} -> "
        f"{report['new_run_id']}"
    )
    print(f"Compatibility: {report['compatibility']['classification']}")
    print(f"Promotions to OK: {len(report['promotions_to_ok'])}")
    print(f"Demotions from OK: {len(report['demotions_from_ok'])}")
    print(f"Markdown briefing saved to: {markdown_path}")
    print(f"Comparison CSV saved to: {csv_path}")
    print(f"Comparison JSON saved to: {json_path}")


def export_intelligence_artifacts(results: list[dict], run_id: str) -> dict:
    """Export calibration and decision-ready research artifacts once."""
    calibration = build_calibration(results)
    calibration_csv_path, calibration_json_path = export_calibration(
        results,
        run_id=run_id,
        output_directory=OUTPUT_DIR,
        calibration=calibration,
    )
    research_artifacts = export_experimental_research_reports(
        results,
        calibration,
        run_id,
        output_directory=OUTPUT_DIR,
    )
    return {
        "calibration_csv_path": calibration_csv_path,
        "calibration_json_path": calibration_json_path,
        "research_artifacts": research_artifacts,
    }


def recalibrate_saved_run(run_id: str) -> None:
    """Regenerate intelligence artifacts without provider initialization."""
    try:
        manifest, results = load_saved_run(RUN_DIR, run_id)
    except (FileNotFoundError, ValueError) as error:
        raise SystemExit(str(error)) from error
    intelligence = export_intelligence_artifacts(results, run_id)
    artifacts = {
        **intelligence,
        "source_fingerprint": manifest.get("fingerprint"),
        "source_completed_at": manifest.get("completed_at"),
    }
    manifest_path = record_recalibration(RUN_DIR, run_id, artifacts)
    research = intelligence["research_artifacts"]

    print(f"Offline recalibration complete for run: {run_id}")
    print(f"Loaded saved results: {len(results)}")
    print(
        "Calibration rows saved to: "
        f"{intelligence['calibration_csv_path']}"
    )
    print(
        "Calibration analysis saved to: "
        f"{intelligence['calibration_json_path']}"
    )
    for scenario, path in research["scenario_report_paths"].items():
        print(f"{scenario} research report saved to: {path}")
    print(f"Top-25 review saved to: {research['review_report_path']}")
    print(f"Scenario summary saved to: {research['scenario_summary_path']}")
    print(
        "Scenario comparison saved to: "
        f"{research['scenario_comparison_path']}"
    )
    print(
        "Research decision saved to: "
        f"{research['research_decision_path']}"
    )
    print(
        "Selected v0.3 research queue saved to: "
        f"{research['selected_research_report_path']}"
    )
    print(f"Manifest updated: {manifest_path}")


def research_saved_run(
    run_id: str,
    top_n: int,
    collect_sources: bool = False,
    source_manifest: str | None = None,
    canadian_source_manifest: str | None = None,
    synthesize: bool = False,
    balanced_per_country: int | None = None,
) -> None:
    """Build deterministic research packets from a completed local run."""
    try:
        _, results = load_saved_run(RUN_DIR, run_id)
        calibration = build_calibration(results)
        packets, metadata = build_research_packets(
            results,
            top_n,
            calibration=calibration,
            balanced_per_country=balanced_per_country,
        )
    except (FileNotFoundError, ValueError) as error:
        raise SystemExit(str(error)) from error
    evidence_artifact = None
    providers = []
    if collect_sources:
        user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
        if not user_agent:
            raise SystemExit(
                "--collect-sources requires SEC_USER_AGENT, for example "
                "'Discovery Engine your-email@example.com'."
            )
        providers.append(SecEdgarProvider(user_agent, HttpCache()))
    if source_manifest:
        try:
            providers.append(ManifestEvidenceProvider(Path(source_manifest)))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise SystemExit(f"Invalid source manifest: {error}") from error
    if canadian_source_manifest:
        user_agent = (
            os.environ.get("SOURCE_USER_AGENT", "").strip()
            or os.environ.get("SEC_USER_AGENT", "").strip()
        )
        if not user_agent:
            raise SystemExit(
                "--canadian-source-manifest requires SOURCE_USER_AGENT or "
                "SEC_USER_AGENT with a contact email."
            )
        try:
            providers.append(CanadianIssuerManifestProvider(
                Path(canadian_source_manifest),
                user_agent,
                HttpCache(),
            ))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise SystemExit(f"Invalid Canadian source manifest: {error}") from error
    if providers:
        evidence = collect_evidence(packets, providers)
        attach_evidence(packets, evidence)
        evidence_artifact = export_evidence(evidence, run_id, OUTPUT_DIR)
        metadata["evidence"] = {
            "collection_enabled": True,
            "providers": [provider.name for provider in providers],
            "document_count": evidence["document_count"],
            "failure_count": evidence["failure_count"],
            "cache": evidence["cache"],
            "evidence_manifest_path": evidence_artifact,
        }
    else:
        metadata["evidence"] = {"collection_enabled": False}
    synthesis_provider = None
    if synthesize:
        if not RESEARCH_AI_ENABLED:
            raise SystemExit(
                "AI synthesis is disabled in config/settings.json. Set "
                "research.ai_synthesis_enabled to true before using --synthesize."
            )
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise SystemExit("--synthesize requires OPENAI_API_KEY.")
        if SYNTHESIS_PROVIDER != "openai":
            raise SystemExit(f"Unsupported synthesis provider: {SYNTHESIS_PROVIDER}")
        synthesis_provider = OpenAIResearchProvider(api_key)
        metadata["synthesis"] = {
            "enabled": True,
            "provider": synthesis_provider.name,
            "model": synthesis_provider.model,
            "prompt_version": RESEARCH_PROMPT_VERSION,
        }
    else:
        metadata["synthesis"] = {"enabled": False}
    outputs = ResearchRunner(
        provider=synthesis_provider,
        cache=ResearchCache(
            RESEARCH_CACHE_DIR,
            RESEARCH_PROMPT_VERSION,
            f"openai:{SYNTHESIS_MODEL}" if synthesis_provider else "packet-only",
        ),
    ).run(packets)
    artifacts = export_research_packets(
        packets,
        outputs,
        metadata,
        run_id,
        output_directory=OUTPUT_DIR,
    )
    if evidence_artifact:
        artifacts["evidence_manifest_path"] = evidence_artifact
    manifest_path = record_research_packets(
        RUN_DIR,
        run_id,
        artifacts,
    )

    print(f"Offline research packets complete for run: {run_id}")
    print(f"Selected scenario: {metadata['selected_scenario']}")
    print(f"Research packets: {len(packets)}")
    if synthesis_provider:
        statuses = artifacts["synthesis_statuses"]
        print(f"AI synthesis: enabled ({synthesis_provider.model})")
        print(f"Synthesis complete: {statuses.get('complete', 0)}")
        print(f"Synthesis skipped (no evidence): {statuses.get('skipped_no_evidence', 0)}")
        print(f"Synthesis errors: {statuses.get('error', 0)}")
        print(f"Synthesis cache hits: {artifacts['synthesis_cache_hits']}")
        print(f"Validated claims: {artifacts['validated_claim_count']}")
        print(f"Validated citations: {artifacts['validated_citation_count']}")
        usage = artifacts["synthesis_usage"]
        print(f"Synthesis input tokens: {usage['input_tokens']}")
        print(f"Synthesis output tokens: {usage['output_tokens']}")
        print(f"Synthesis total tokens: {usage['total_tokens']}")
    else:
        print("AI synthesis: disabled (packet-only mode)")
    if evidence_artifact:
        cache = metadata["evidence"]["cache"]
        print(f"Evidence documents: {metadata['evidence']['document_count']}")
        print(f"Evidence failures: {metadata['evidence']['failure_count']}")
        print(f"Evidence cache hits: {cache['hits']}")
        print(f"Evidence cache misses: {cache['misses']}")
        print(f"Evidence cache expired: {cache['expired']}")
        print(f"Evidence cache read errors: {cache['read_errors']}")
        print(f"Evidence manifest saved to: {evidence_artifact}")
    print(f"JSON packets saved to: {artifacts['research_packets_json_path']}")
    print(
        "Markdown packets saved to: "
        f"{artifacts['research_packets_markdown_path']}"
    )
    print(
        "Research briefs saved to: "
        f"{artifacts['research_briefs_markdown_path']}"
    )
    print(f"Manifest updated: {manifest_path}")


def audit_saved_research(run_id: str) -> None:
    """Audit the latest saved research artifact without external providers."""
    try:
        manifest = load_saved_manifest(RUN_DIR, run_id)
        artifact = manifest.get("research_packet_artifacts") or {}
        source_value = artifact.get("research_packets_json_path")
        if not source_value:
            raise ValueError("Saved run has no research packet artifact to audit.")
        source_path = Path(source_value).resolve()
        if not source_path.is_relative_to(OUTPUT_DIR.resolve()):
            raise ValueError("Research artifact is outside the configured export directory.")
        with source_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if payload.get("run_id") != run_id:
            raise ValueError("Research artifact run ID does not match the requested run.")
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"Unable to audit saved research: {error}") from error

    artifacts = export_research_audit(payload, run_id, OUTPUT_DIR)
    manifest_path = record_research_audit(RUN_DIR, run_id, artifacts)
    metrics = artifacts["metrics"]
    print(f"Offline research audit complete for run: {run_id}")
    print(f"Automated status: {artifacts['automated_status']}")
    print(f"Release status: {artifacts['release_status']}")
    print(f"Candidates audited: {metrics['candidate_count']}")
    print(f"Evidence coverage: {metrics['evidence_coverage_percent']}%")
    print(f"Synthesis completion: {metrics['synthesis_completion_percent']}%")
    print(f"Citation coverage: {metrics['citation_coverage_percent']}%")
    print(f"Section coverage: {metrics['section_coverage_percent']}%")
    print(f"Human review rows: {artifacts['review_row_count']}")
    sampling = artifacts["review_sampling"]
    print(
        "Human review sampling: "
        f"{sampling['selected_claim_count']}/{sampling['total_claim_count']} "
        f"({sampling['coverage_percent']}%)"
    )
    if artifacts["failed_gates"]:
        print(f"Failed gates: {', '.join(artifacts['failed_gates'])}")
    if artifacts["not_evaluated_gates"]:
        print(f"Not evaluated: {', '.join(artifacts['not_evaluated_gates'])}")
    print(f"Audit saved to: {artifacts['research_audit_json_path']}")
    print(f"Human review queue saved to: {artifacts['research_human_review_csv_path']}")
    print(f"Candidate audit saved to: {artifacts['research_candidate_audit_csv_path']}")
    print(f"Claim triage saved to: {artifacts['research_claim_triage_csv_path']}")
    print(f"Manifest updated: {manifest_path}")


def finalize_saved_research_review(run_id: str) -> None:
    """Finalize a completed claim-level human review for a saved run."""
    try:
        manifest = load_saved_manifest(RUN_DIR, run_id)
        artifacts = manifest.get("research_audit_artifacts") or {}
        audit_path = _validated_export_path(artifacts.get("research_audit_json_path"))
        review_path = _validated_export_path(artifacts.get("research_human_review_csv_path"))
        decision = finalize_research_review(audit_path, review_path, run_id, OUTPUT_DIR)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"Unable to finalize research review: {error}") from error
    manifest_path = record_research_acceptance(RUN_DIR, run_id, decision)
    print(f"Research review finalized for run: {run_id}")
    print(f"Human decision: {decision['human_review_decision']}")
    print(f"Review rows: {decision['review_row_count']}")
    if decision["pending_csv_rows"]:
        print(f"Pending CSV rows: {decision['pending_csv_rows']}")
    if decision["rejected_csv_rows"]:
        print(f"Rejected CSV rows: {decision['rejected_csv_rows']}")
    print(f"Acceptance record saved to: {decision['research_acceptance_json_path']}")
    print(f"Candidate release report saved to: {decision['research_release_csv_path']}")
    print(f"Manifest updated: {manifest_path}")


def _validated_export_path(value: object) -> Path:
    if not value:
        raise ValueError("Saved run is missing a required research review artifact.")
    path = Path(str(value)).resolve()
    if not path.is_relative_to(OUTPUT_DIR.resolve()):
        raise ValueError("Research review artifact is outside the export directory.")
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


if __name__ == "__main__":
    main()
