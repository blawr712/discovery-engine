from src.universe import UniverseBuilder
from src.data_sources.yfinance_source import YFinanceSource
from src.data_sources.cached_source import CachedMarketDataSource
from src.report import export_report
from src.engine import DiscoveryEngine
from src.config import (
    BENCHMARKS,
    CACHE_DIR,
    CACHE_ENABLED,
    CACHE_METADATA_TTL_HOURS,
    CACHE_PRICE_HISTORY_TTL_HOURS,
    MAX_CONCURRENT_DOWNLOADS,
)


def print_progress(
    phase: str,
    completed: int,
    total: int,
    ticker: str,
) -> None:
    """Print compact progress for each collection phase."""
    print(f"[{phase}] {completed}/{total}: {ticker}")


def main():
    source = CachedMarketDataSource(
        YFinanceSource(),
        cache_directory=CACHE_DIR,
        metadata_ttl_hours=CACHE_METADATA_TTL_HOURS,
        price_history_ttl_hours=CACHE_PRICE_HISTORY_TTL_HOURS,
        enabled=CACHE_ENABLED,
    )
    universe = UniverseBuilder().build_universe()

    print(f"Loaded {len(universe)} tickers from universe.csv")
    print(f"Concurrent downloads: {MAX_CONCURRENT_DOWNLOADS}")

    engine = DiscoveryEngine(
        source,
        benchmarks=BENCHMARKS,
        max_workers=MAX_CONCURRENT_DOWNLOADS,
        progress_callback=print_progress,
    )
    results = engine.run(universe)

    output_path = export_report(results)

    passed = sum(1 for r in results if r.get("status") == "OK")
    filtered = sum(1 for r in results if r.get("status") == "FILTERED")
    failed = sum(
        1
        for r in results
        if r.get("status") not in {"OK", "FILTERED"}
    )

    print("\nRun Summary")
    print(f"Total: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Filtered: {filtered}")
    print(f"Failed: {failed}")
    if source.enabled:
        print(f"Cache hits: {source.stats.hits}")
        print(f"Cache misses: {source.stats.misses}")
        print(f"Cache expired: {source.stats.expired}")
        print(f"Cache read errors: {source.stats.read_errors}")

    print("\nDone.")
    print(f"Report saved to: {output_path}")


if __name__ == "__main__":
    main()
