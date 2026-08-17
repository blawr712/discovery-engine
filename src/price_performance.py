"""Offline percentage-return metrics and normalized chart series."""

from __future__ import annotations

from datetime import date, timedelta


PERIODS = {"1W": 7, "1M": 30, "3M": 91, "6M": 182, "1Y": 365}
BENCHMARK_DEFINITIONS = {
    "SPY": "SPDR S&P 500 ETF Trust, used as the broad U.S. equity benchmark.",
    "XIU.TO": "iShares S&P/TSX 60 Index ETF, used as the Canadian equity benchmark.",
}


def build_price_performance(equity: dict | None, benchmark: dict | None) -> dict | None:
    if not equity or not equity.get("points"):
        return None
    equity_points = equity["points"]
    benchmark_points = benchmark["points"] if benchmark else []
    anomalies = _price_anomalies(equity_points)
    benchmark_anomalies = _price_anomalies(benchmark_points)
    equity_returns = _period_returns(equity_points, anomalies)
    benchmark_returns = (
        _period_returns(benchmark_points, benchmark_anomalies)
        if benchmark_points else {}
    )
    metrics = {
        period: {
            "ticker_return": result["return"],
            "benchmark_return": benchmark_returns.get(period, {}).get("return"),
            "relative_return": _difference(
                result["return"], benchmark_returns.get(period, {}).get("return")
            ),
            "reliable": result["reliable"],
            "warning": result["warning"],
        }
        for period, result in equity_returns.items()
    }
    common_start = max(
        equity_points[0]["date"],
        benchmark_points[0]["date"] if benchmark_points else equity_points[0]["date"],
    )
    return {
        "ticker": equity["ticker"],
        "benchmark": benchmark.get("ticker") if benchmark else None,
        "benchmark_definition": BENCHMARK_DEFINITIONS.get(
            benchmark.get("ticker") if benchmark else None,
            "Configured market benchmark used for relative performance.",
        ),
        "start_date": equity["start_date"],
        "end_date": equity["end_date"],
        "point_count": equity["point_count"],
        "source_mtime": equity["source_mtime"],
        "period_returns": metrics,
        "data_quality": "possible_corporate_action" if anomalies else "ok",
        "anomalies": anomalies,
        "series": {
            "price": [
                {"date": point["date"], "value": point["close"]}
                for point in equity_points
            ],
            "ticker": _normalized(equity_points, common_start),
            "benchmark": _normalized(benchmark_points, common_start),
        },
        "volume": [
            {"date": point["date"], "value": point.get("volume")}
            for point in equity_points
        ],
        "interpretation": (
            "Historical adjusted-close performance from the immutable snapshot "
            "linked to this run; past performance is not a forecast."
        ),
    }


def _period_returns(points: list[dict], anomalies: list[dict]) -> dict[str, dict]:
    if len(points) < 2:
        return {
            period: {"return": None, "reliable": False,
                     "warning": "Insufficient price history"}
            for period in PERIODS
        }
    end = date.fromisoformat(points[-1]["date"])
    results = {}
    for period, days in PERIODS.items():
        target = end - timedelta(days=days)
        start, value = _return_from(points, target)
        crossed = [
            anomaly for anomaly in anomalies
            if start is not None and anomaly["date"] > start["date"]
        ]
        results[period] = {
            "return": None if crossed else value,
            "reliable": not crossed and value is not None,
            "warning": (
                "Possible split or corporate action crosses this period"
                if crossed else None
            ),
        }
    return results


def _return_from(points: list[dict], target: date) -> tuple[dict | None, float | None]:
    eligible = [point for point in points if date.fromisoformat(point["date"]) >= target]
    start = eligible[0] if eligible else points[0]
    start_price = start["close"]
    end_price = points[-1]["close"]
    if not start_price:
        return start, None
    return start, round((end_price / start_price - 1) * 100, 2)


def _price_anomalies(points: list[dict]) -> list[dict]:
    anomalies = []
    for previous, current in zip(points, points[1:]):
        if not previous.get("close"):
            continue
        change = (current["close"] / previous["close"] - 1) * 100
        if change >= 300 or change <= -75:
            anomalies.append({
                "date": current["date"],
                "change_percent": round(change, 2),
                "previous_close": previous["close"],
                "close": current["close"],
                "classification": "possible_split_or_corporate_action",
            })
    return anomalies


def _normalized(points: list[dict], start_date: str) -> list[dict]:
    selected = [point for point in points if point["date"] >= start_date]
    if not selected or not selected[0]["close"]:
        return []
    base = selected[0]["close"]
    return [
        {"date": point["date"], "value": round(point["close"] / base * 100, 3)}
        for point in selected
    ]


def _difference(left, right):
    if left is None or right is None:
        return None
    return round(left - right, 2)
