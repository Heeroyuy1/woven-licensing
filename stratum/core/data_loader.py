"""Data Loader — Fetches, caches, and manages historical OHLCV data."""
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Callable
from pathlib import Path
import asyncio

import numpy as np
import pandas as pd

logger = logging.getLogger("Stratum.DataLoader")

DATA_CACHE_DIR = Path(__file__).resolve().parent.parent / "data"


class DataLoader:
    """Loads OHLCV data from multiple sources with local caching and progress reporting."""

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ):
        self.cache_dir = Path(cache_dir or DATA_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.progress_callback = progress_callback
        self._data_cache: Dict[str, pd.DataFrame] = {}

    def _cache_path(self, symbol: str, interval: str) -> Path:
        return self.cache_dir / f"{symbol}_{interval}.parquet"

    def get_cached_symbols(self) -> List[str]:
        """List symbols with cached data."""
        seen = set()
        for f in self.cache_dir.glob("*.parquet"):
            name = f.stem
            parts = name.rsplit("_", 1)
            if len(parts) >= 1:
                seen.add(parts[0])
        return sorted(seen)

    def get_cached_date_range(self, symbol: str, interval: str = "1d") -> Tuple[Optional[str], Optional[str]]:
        """Get date range for cached data."""
        path = self._cache_path(symbol, interval)
        if not path.exists():
            return None, None
        try:
            df = pd.read_parquet(path)
            if df.empty:
                return None, None
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            return (
                df["timestamp"].min().strftime("%Y-%m-%d"),
                df["timestamp"].max().strftime("%Y-%m-%d"),
            )
        except Exception:
            return None, None

    def fetch_symbol(
        self,
        symbol: str,
        start_date: str = "2020-01-01",
        end_date: str = "2025-12-31",
        interval: str = "1d",
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """Fetch data for a single symbol. Cached as parquet."""
        cache_path = self._cache_path(symbol, interval)

        # Check cache
        if not force_refresh and cache_path.exists():
            try:
                df = pd.read_parquet(cache_path)
                df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
                start_ts = pd.Timestamp(start_date, tz="UTC")
                end_ts = pd.Timestamp(end_date, tz="UTC")
                df = df[(df["timestamp"] >= start_ts) & (df["timestamp"] <= end_ts)]
                if not df.empty:
                    self._data_cache[symbol] = df
                    logger.info(f"Loaded {symbol} from cache: {len(df)} bars")
                    return df
            except Exception as e:
                logger.warning(f"Cache read failed for {symbol}: {e}")

        # Fetch from yfinance
        df = self._fetch_yahoo(symbol, start_date, end_date, interval)
        if df is not None and not df.empty:
            df["symbol"] = symbol
            # Merge with existing cache
            if cache_path.exists():
                try:
                    existing = pd.read_parquet(cache_path)
                    existing["timestamp"] = pd.to_datetime(existing["timestamp"], utc=True)
                    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
                    combined = pd.concat([existing, df], ignore_index=True)
                    combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
                    combined = combined.sort_values("timestamp")
                    df = combined
                except Exception:
                    pass
            # Filter to requested range
            start_ts = pd.Timestamp(start_date, tz="UTC")
            end_ts = pd.Timestamp(end_date, tz="UTC")
            df = df[(df["timestamp"] >= start_ts) & (df["timestamp"] <= end_ts)]
            df.to_parquet(cache_path, index=False)
            self._data_cache[symbol] = df
            logger.info(f"Fetched & cached {symbol}: {len(df)} bars")
        else:
            df = pd.DataFrame()
        return df

    def _fetch_yahoo(self, symbol: str, start_date: str, end_date: str, interval: str) -> pd.DataFrame:
        """Fetch from Yahoo Finance. Synchronous call."""
        try:
            import yfinance as yf
            yf_map = {"1d": "1d", "1h": "1h", "15min": "15m", "5min": "5m", "1min": "1m"}
            yf_int = yf_map.get(interval, "1d")
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date, interval=yf_int)
            if df.empty:
                logger.warning(f"Yahoo: no data for {symbol}")
                return pd.DataFrame()
            df = df.reset_index()
            col_map = {
                "Date": "timestamp", "Datetime": "timestamp",
                "Open": "open", "High": "high", "Low": "low",
                "Close": "close", "Volume": "volume",
            }
            df.rename(columns=col_map, inplace=True)
            cols = [c for c in ["timestamp", "open", "high", "low", "close", "volume"] if c in df.columns]
            df = df[cols]
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            logger.info(f"Yahoo: {symbol} ({interval}) — {len(df)} rows")
            return df
        except ImportError:
            logger.error("yfinance not installed. pip install yfinance")
            raise
        except Exception as e:
            logger.error(f"Yahoo fetch failed for {symbol}: {e}")
            return pd.DataFrame()

    def fetch_batch(
        self,
        symbols: List[str],
        start_date: str = "2020-01-01",
        end_date: str = "2025-12-31",
        interval: str = "1d",
        force_refresh: bool = False,
    ) -> Dict[str, pd.DataFrame]:
        """Fetch multiple symbols sequentially with progress."""
        results = {}
        total = len(symbols)
        for i, sym in enumerate(symbols):
            try:
                df = self.fetch_symbol(sym, start_date, end_date, interval, force_refresh)
                if not df.empty:
                    results[sym] = df
            except Exception as e:
                logger.error(f"Failed to fetch {sym}: {e}")
            if self.progress_callback:
                self.progress_callback(i + 1, total)
        return results

    def load_parquet(self, path: str) -> pd.DataFrame:
        """Load a parquet file."""
        df = pd.read_parquet(path)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        return df

    def from_csv(self, path: str) -> pd.DataFrame:
        """Load a CSV file."""
        df = pd.read_csv(path)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        return df

    def clear_cache(self, symbol: Optional[str] = None, interval: str = "1d"):
        """Clear cached data."""
        if symbol:
            path = self._cache_path(symbol, interval)
            if path.exists():
                path.unlink()
            self._data_cache.pop(symbol, None)
        else:
            for f in self.cache_dir.glob("*.parquet"):
                f.unlink()
            self._data_cache.clear()
        logger.info(f"Cache cleared ({symbol or 'all'})")
