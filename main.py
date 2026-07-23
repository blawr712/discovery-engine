from src.universe import UniverseBuilder
from src.data_sources.yfinance_source import YFinanceSource
from src.data_sources.cached_source import CachedMarketDataSource
from src.scoring import calculate_scores
from src.report import export_report
from src.config import (
    BENCHMARKS,
    CACHE_DIR,
    CACHE_ENABLED,
    CACHE_METADATA_TTL_HOURS,
    CACHE_PRICE_HISTORY_TTL_HOURS,
)
from src.pre_filter import evaluate_stock, filtered_result


def main():
    source = CachedMarketDataSource(
        YFinanceSource(),
        cache_directory=CACHE_DIR,
        metadata_ttl_hours=CACHE_METADATA_TTL_HOURS,
        price_history_ttl_hours=CACHE_PRICE_HISTORY_TTL_HOURS,
        enabled=CACHE_ENABLED,
    )
    universe = UniverseBuilder().build_universe()

    benchmark_cache = {}
    results = []

    print(f"Loaded {len(universe)} tickers from universe.csv")

    for item in universe:
        ticker = item["ticker"]
        print(f"Analyzing {ticker}...")

        try:
            stock_data = source.get_stock_data(ticker)

            pre_filter = evaluate_stock(stock_data)
            if not pre_filter.passed:
                results.append(
                    filtered_result(
                        stock_data,
                        pre_filter.reason or "Failed pre-filter",
                    )
                )
                continue

            country = item.get("country") or stock_data.get("country")
            benchmark_ticker = BENCHMARKS.get(country, "SPY")

            if benchmark_ticker not in benchmark_cache:
                benchmark_cache[benchmark_ticker] = source.get_price_history(benchmark_ticker)

            price_history = source.get_price_history(ticker)
            benchmark_history = benchmark_cache[benchmark_ticker]

            score = calculate_scores(stock_data, price_history, benchmark_history)
            results.append(score)

        except Exception as e:
            results.append({
                "ticker": ticker,
                "status": "ERROR",
                "reason_flags": str(e),
                "discovery_score": 0,
            })

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
