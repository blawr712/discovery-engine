from src.universe import UniverseBuilder
from src.data_sources.yfinance_source import YFinanceSource
from src.data_sources.cached_source import CachedMarketDataSource
from src.data_sources.retrying_source import RetryingMarketDataSource
from src.data_sources.rate_limited_source import RateLimitedMarketDataSource
from src.report import export_report
from src.engine import DiscoveryEngine
from src.run_state import RunState, build_run_fingerprint
from src.cli import parse_args, select_universe
from src.config import (
    BENCHMARKS,
    CACHE_DIR,
    CACHE_ENABLED,
    CACHE_METADATA_TTL_HOURS,
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
    SETTINGS,
    STRATEGY,
    RATE_LIMIT_ENABLED,
    METADATA_INTERVAL_SECONDS,
    PRICE_INTERVAL_SECONDS,
    RATE_LIMIT_COOLDOWN_SECONDS,
    MAX_RATE_LIMIT_COOLDOWN_EVENTS,
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
        price_history_ttl_hours=CACHE_PRICE_HISTORY_TTL_HOURS,
        enabled=CACHE_ENABLED,
    )
    universe = UniverseBuilder().build_universe()
    try:
        universe = select_universe(
            universe,
            tickers=args.tickers,
            limit=args.limit,
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
    run_state.complete(results, output_path)

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
    print(f"Manifest saved to: {run_state.manifest_path}")


if __name__ == "__main__":
    main()
