"""Command-line options for full and controlled Discovery Engine runs."""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse mutually exclusive universe-selection options."""
    parser = argparse.ArgumentParser(
        description="Analyze the Discovery Engine equity universe.",
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--tickers",
        nargs="+",
        metavar="TICKER",
        help="analyze only these tickers from the configured universe",
    )
    selection.add_argument(
        "--limit",
        type=_positive_integer,
        metavar="COUNT",
        help="analyze only the first COUNT universe entries",
    )
    selection.add_argument(
        "--balanced-sample",
        type=_positive_integer,
        metavar="PER_COUNTRY",
        help="interleave up to PER_COUNTRY Canadian and U.S. listings",
    )
    selection.add_argument(
        "--recalibrate-run",
        metavar="RUN_ID",
        help="regenerate calibration artifacts from a completed saved run",
    )
    return parser.parse_args(arguments)


def select_universe(
    universe: list[dict],
    tickers: list[str] | None = None,
    limit: int | None = None,
    balanced_sample: int | None = None,
) -> list[dict]:
    """Select a reproducible subset while retaining universe metadata."""
    selections = sum(
        value is not None for value in (tickers, limit, balanced_sample)
    )
    if selections > 1:
        raise ValueError("ticker, limit, and balanced sample options cannot be combined")

    if balanced_sample is not None:
        if (
            isinstance(balanced_sample, bool)
            or not isinstance(balanced_sample, int)
            or balanced_sample < 1
        ):
            raise ValueError("balanced sample must be a positive integer")
        by_country = {
            country: [
                item
                for item in universe
                if str(item.get("country", "")).upper() == country
            ][:balanced_sample]
            for country in ("CA", "US")
        }
        selected = []
        for index in range(max(len(group) for group in by_country.values())):
            for country in ("CA", "US"):
                if index < len(by_country[country]):
                    selected.append(by_country[country][index])
        return selected

    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        return universe[:limit]

    if tickers is None:
        return universe

    lookup = {
        str(item["ticker"]).strip().upper(): item
        for item in universe
    }
    requested = list(dict.fromkeys(
        str(ticker).strip().upper()
        for ticker in tickers
        if str(ticker).strip()
    ))
    missing = [ticker for ticker in requested if ticker not in lookup]

    if missing:
        raise ValueError(
            "Tickers not found in the configured universe: "
            + ", ".join(missing)
        )

    return [lookup[ticker] for ticker in requested]


def _positive_integer(value: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error

    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")

    return number
