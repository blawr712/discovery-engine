from src.universe import UniverseBuilder
from src.data_sources.yfinance_source import YFinanceSource
from src.scoring import calculate_scores
from src.report import export_report
from src.config import BENCHMARKS


def main():
    source = YFinanceSource()
    universe = UniverseBuilder().build_universe()

    benchmark_cache = {}
    results = []

    print(f"Loaded {len(universe)} tickers from universe.csv")

    for item in universe:
        ticker = item["ticker"]
        print(f"Analyzing {ticker}...")

        try:
            stock_data = source.get_stock_data(ticker)

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
    failed = sum(1 for r in results if r.get("status") != "OK")

    print("\nRun Summary")
    print(f"Total: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    print("\nDone.")
    print(f"Report saved to: {output_path}")


if __name__ == "__main__":
    main()