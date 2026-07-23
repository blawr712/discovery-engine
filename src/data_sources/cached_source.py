"""Persistent caching for any market-data provider."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Callable

import pandas as pd

from .base import MarketDataSource


@dataclass
class CacheStats:
    """Track cache behavior during one engine run."""

    hits: int = 0
    misses: int = 0
    expired: int = 0
    read_errors: int = 0


class CachedMarketDataSource(MarketDataSource):
    """Add persistent, expiring disk caching to a market-data source."""

    def __init__(
        self,
        source: MarketDataSource,
        cache_directory: Path,
        metadata_ttl_hours: float = 168,
        price_history_ttl_hours: float = 24,
        enabled: bool = True,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if metadata_ttl_hours < 0 or price_history_ttl_hours < 0:
            raise ValueError("Cache TTL values cannot be negative.")

        self.source = source
        self.cache_directory = Path(cache_directory)
        self.metadata_ttl_seconds = metadata_ttl_hours * 60 * 60
        self.price_history_ttl_seconds = price_history_ttl_hours * 60 * 60
        self.enabled = enabled
        self.clock = clock
        self.stats = CacheStats()

        if self.enabled:
            (self.cache_directory / "metadata").mkdir(parents=True, exist_ok=True)
            (self.cache_directory / "prices").mkdir(parents=True, exist_ok=True)

    def get_stock_data(self, ticker: str) -> dict:
        """Return company metadata from cache or the wrapped provider."""
        if not self.enabled:
            return self.source.get_stock_data(ticker)

        path = self._cache_path("metadata", ticker, "json")
        cached = self._read_json(path, self.metadata_ttl_seconds)

        if cached is not None:
            return cached

        data = self.source.get_stock_data(ticker)
        self._write_json(path, data)
        return data

    def get_price_history(
        self,
        ticker: str,
        period: str = "1y",
    ) -> pd.DataFrame:
        """Return price history from cache or the wrapped provider."""
        if not self.enabled:
            return self.source.get_price_history(ticker, period)

        key = f"{ticker}|{period}"
        path = self._cache_path("prices", key, "json")
        cached = self._read_price_history(
            path,
            self.price_history_ttl_seconds,
        )

        if cached is not None:
            return cached

        data = self.source.get_price_history(ticker, period)
        self._write_price_history(path, data)
        return data

    def _cache_path(self, category: str, key: str, suffix: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.cache_directory / category / f"{digest}.{suffix}"

    def _fresh(self, path: Path, ttl_seconds: float) -> bool:
        if not path.exists():
            self.stats.misses += 1
            return False

        age_seconds = max(0, self.clock() - path.stat().st_mtime)

        if age_seconds > ttl_seconds:
            self.stats.expired += 1
            return False

        return True

    def _read_json(self, path: Path, ttl_seconds: float) -> dict | None:
        if not self._fresh(path, ttl_seconds):
            return None

        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError, TypeError):
            self.stats.read_errors += 1
            return None

        if not isinstance(data, dict):
            self.stats.read_errors += 1
            return None

        self.stats.hits += 1
        return data

    def _read_price_history(
        self,
        path: Path,
        ttl_seconds: float,
    ) -> pd.DataFrame | None:
        if not self._fresh(path, ttl_seconds):
            return None

        try:
            data = pd.read_json(path, orient="table")
        except (OSError, ValueError, TypeError, KeyError):
            self.stats.read_errors += 1
            return None

        self.stats.hits += 1
        return data

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        temporary_path = CachedMarketDataSource._temporary_path(path)

        try:
            with temporary_path.open("w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False)
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _write_price_history(path: Path, data: pd.DataFrame) -> None:
        temporary_path = CachedMarketDataSource._temporary_path(path)

        try:
            data.to_json(
                temporary_path,
                orient="table",
                date_format="iso",
                index=False,
            )
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _temporary_path(path: Path) -> Path:
        descriptor, name = tempfile.mkstemp(
            prefix=f".{path.stem}-",
            suffix=f".{path.suffix.lstrip('.')}",
            dir=path.parent,
        )
        os.close(descriptor)
        return Path(name)
