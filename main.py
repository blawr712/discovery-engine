import os
import json
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
    record_recalibration,
    record_research_packets,
)
from src.research import (
    ResearchRunner,
    build_research_packets,
    export_research_packets,
)
from src.evidence import (
    HttpCache,
    ManifestEvidenceProvider,
    SecEdgarProvider,
    attach_evidence,
    collect_evidence,
    export_evidence,
)
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
    if args.recalibrate_run:
        recalibrate_saved_run(args.recalibrate_run)
        return
    if args.research_run:
        research_saved_run(
            args.research_run,
            args.top or RESEARCH_DEFAULT_TOP,
            collect_sources=args.collect_sources,
            source_manifest=args.source_manifest,
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
) -> None:
    """Build deterministic research packets from a completed local run."""
    try:
        _, results = load_saved_run(RUN_DIR, run_id)
        calibration = build_calibration(results)
        packets, metadata = build_research_packets(
            results,
            top_n,
            calibration=calibration,
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
    if providers:
        evidence = collect_evidence(packets, providers)
        attach_evidence(packets, evidence)
        evidence_artifact = export_evidence(evidence, run_id, OUTPUT_DIR)
        metadata["evidence"] = {
            "collection_enabled": True,
            "providers": [provider.name for provider in providers],
            "document_count": evidence["document_count"],
            "failure_count": evidence["failure_count"],
            "evidence_manifest_path": evidence_artifact,
        }
    else:
        metadata["evidence"] = {"collection_enabled": False}
    outputs = ResearchRunner(provider=None).run(packets)
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
    print("AI synthesis: disabled (packet-only mode)")
    if evidence_artifact:
        print(f"Evidence manifest saved to: {evidence_artifact}")
    print(f"JSON packets saved to: {artifacts['research_packets_json_path']}")
    print(
        "Markdown packets saved to: "
        f"{artifacts['research_packets_markdown_path']}"
    )
    print(f"Manifest updated: {manifest_path}")


if __name__ == "__main__":
    main()
