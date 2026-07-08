"""
Historical Data Loader
Fetches OHLCV data from Alpaca (or Yahoo Finance fallback), caches locally as Parquet/CSV.
Supports batch loading across hundreds of symbols.
"""
import os
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import numpy as np
import pandas as pd

logger = logging.getLogger("Harper.DataLoader")


class DataLoader:
    """Loads and caches historical OHLCV data for backtesting."""

    def __init__(
        self,
        cache_dir: str = "data",
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        use_alpaca: bool = True,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.api_key = api_key or os.getenv("APCA_API_KEY_ID")
        self.secret_key = secret_key or os.getenv("APCA_API_SECRET_KEY")
        self.use_alpaca = use_alpaca and bool(self.api_key and self.secret_key)
        self._alpaca_client = None

    def _get_alpaca_client(self):
        if self._alpaca_client is None and self.use_alpaca:
            try:
                from alpaca.data.historical import StockHistoricalDataClient
                self._alpaca_client = StockHistoricalDataClient(
                    self.api_key, self.secret_key
                )
            except ImportError:
                logger.warning("alpaca-py not installed; falling back to Yahoo Finance")
                self.use_alpaca = False
            except Exception as e:
                logger.warning(f"Alpaca client init failed: {e}; falling back to Yahoo Finance")
                self.use_alpaca = False
        return self._alpaca_client

    def _cache_path(self, symbol: str, interval: str) -> Path:
        return self.cache_dir / f"{symbol}_{interval}.parquet"

    def _is_cache_fresh(self, path: Path, max_age_days: int = 1) -> bool:
        if not path.exists():
            return False
        age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
        return age.days < max_age_days

    async def fetch_symbol(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1d",
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data for a single symbol. Caches locally.

        Args:
            symbol: Stock ticker (e.g., AAPL)
            start_date: ISO date string (e.g., '2020-01-01')
            end_date: ISO date string
            interval: Bar interval — '1d', '1h', '15min', etc.
            force_refresh: Skip cache, re-download

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume, symbol
        """
        path = self._cache_path(symbol, interval)

        if not force_refresh and self._is_cache_fresh(path):
            df = pd.read_parquet(path)
            if not df.empty:
                df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
                start_ts = pd.Timestamp(start_date, tz="UTC")
                end_ts = pd.Timestamp(end_date, tz="UTC")
                df = df[(df["timestamp"] >= start_ts) & (df["timestamp"] <= end_ts)]
                if len(df) > 0:
                    logger.info(f"Loaded {symbol} ({interval}) from cache: {len(df)} rows")
                    return df

        if self.use_alpaca:
            df = await self._fetch_alpaca(symbol, start_date, end_date, interval)
        else:
            df = self._fetch_yahoo(symbol, start_date, end_date, interval)

        if df is not None and not df.empty:
            df["symbol"] = symbol
            # Merge with existing cache to avoid overwriting with smaller date ranges
            if path.exists():
                try:
                    existing = pd.read_parquet(path)
                    existing["timestamp"] = pd.to_datetime(existing["timestamp"], utc=True)
                    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
                    combined = pd.concat([existing, df], ignore_index=True)
                    combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
                    combined = combined.sort_values("timestamp")
                    df = combined
                except Exception:
                    pass  # if merge fails, just use new data
            df.to_parquet(path, index=False)
            logger.info(f"Cached {symbol} ({interval}): {len(df)} rows -> {path}")
        return df

    async def _fetch_alpaca(
        self, symbol: str, start_date: str, end_date: str, interval: str
    ) -> pd.DataFrame:
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

        client = self._get_alpaca_client()
        if client is None:
            return self._fetch_yahoo(symbol, start_date, end_date, interval)

        try:
            tf_map = {
                "1d": TimeFrame(1, TimeFrameUnit.Day),
                "1h": TimeFrame(1, TimeFrameUnit.Hour),
                "15min": TimeFrame(15, TimeFrameUnit.Minute),
                "5min": TimeFrame(5, TimeFrameUnit.Minute),
                "1min": TimeFrame(1, TimeFrameUnit.Minute),
            }
            tf = tf_map.get(interval, TimeFrame(1, TimeFrameUnit.Day))

            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=tf,
                start=start_date,
                end=end_date,
                limit=10000,
            )
            resp = client.get_stock_bars(request)
            bars = resp.data.get(symbol, []) if hasattr(resp, "data") else []
            if not bars:
                logger.warning(f"No Alpaca data for {symbol}")
                return self._fetch_yahoo(symbol, start_date, end_date, interval)

            records = [
                {
                    "timestamp": b.timestamp,
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "close": b.close,
                    "volume": b.volume,
                }
                for b in bars
            ]
            df = pd.DataFrame(records)
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            return df
        except Exception as e:
            logger.warning(f"Alpaca fetch failed for {symbol}: {e}, falling back to Yahoo")
            return self._fetch_yahoo(symbol, start_date, end_date, interval)

    def _fetch_yahoo(
        self, symbol: str, start_date: str, end_date: str, interval: str
    ) -> pd.DataFrame:
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            yf_interval_map = {
                "1d": "1d", "1h": "1h", "15min": "15m",
                "5min": "5m", "1min": "1m"
            }
            yf_int = yf_interval_map.get(interval, "1d")
            df = ticker.history(start=start_date, end=end_date, interval=yf_int)
            if df.empty:
                logger.warning(f"No Yahoo data for {symbol}")
                return pd.DataFrame()
            df = df.reset_index()
            df.rename(columns={
                "Date": "timestamp", "Datetime": "timestamp",
                "Open": "open", "High": "high",
                "Low": "low", "Close": "close",
                "Volume": "volume"
            }, inplace=True)
            df = df[["timestamp", "open", "high", "low", "close", "volume"]]
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            logger.info(f"Yahoo: {symbol} ({interval}) — {len(df)} rows")
            return df
        except ImportError:
            logger.error("yfinance not installed. Run: pip install yfinance")
            raise
        except Exception as e:
            logger.error(f"Yahoo fetch failed for {symbol}: {e}")
            return pd.DataFrame()

    async def fetch_batch(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        interval: str = "1d",
        force_refresh: bool = False,
    ) -> Dict[str, pd.DataFrame]:
        """Fetch multiple symbols. Returns dict of symbol -> DataFrame."""
        results = {}
        for sym in symbols:
            try:
                df = await self.fetch_symbol(sym, start_date, end_date, interval, force_refresh)
                if not df.empty:
                    results[sym] = df
            except Exception as e:
                logger.error(f"Failed to fetch {sym}: {e}")
        return results

    def load_cached_symbols(self) -> List[str]:
        """List all symbols that have cached data."""
        symbols = set()
        for f in self.cache_dir.glob("*.parquet"):
            name = f.stem
            sym = name.rsplit("_", 1)[0]
            symbols.add(sym)
        return sorted(symbols)

    def get_date_range(self, symbol: str, interval: str = "1d") -> Tuple[Optional[str], Optional[str]]:
        """Get available date range for a cached symbol."""
        path = self._cache_path(symbol, interval)
        if not path.exists():
            return None, None
        df = pd.read_parquet(path)
        if df.empty:
            return None, None
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        return (
            df["timestamp"].min().strftime("%Y-%m-%d"),
            df["timestamp"].max().strftime("%Y-%m-%d"),
        )
