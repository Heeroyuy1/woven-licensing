"""
RSI + SMA Strategy — Ported from TradingBackTestingLIVE.
Uses RSI oversold/overbought thresholds with SMA trend filter.
Configurable per-symbol parameters.
"""
import logging
from typing import Dict, Optional
import numpy as np
import pandas as pd
from datetime import datetime

from strategies.base_strategy import (
    BaseStrategy, StrategyConfig, Signal, SignalType
)

logger = logging.getLogger("Harper.Strategy.RSI_SMA")


class RSISMAStrategy(BaseStrategy):
    """
    Original bot's strategy:
    - BUY when RSI < rsi_buy_threshold (oversold)
    - SELL (short) when RSI > rsi_sell_threshold (overbought)
    - Uses SMA for trend context
    """

    def __init__(
        self,
        sma_period: int = 20,
        rsi_period: int = 14,
        rsi_buy_threshold: float = 30.0,
        rsi_sell_threshold: float = 70.0,
    ):
        config = StrategyConfig(
            name="RSI_SMA",
            params={
                "sma_period": sma_period,
                "rsi_period": rsi_period,
                "rsi_buy_threshold": rsi_buy_threshold,
                "rsi_sell_threshold": rsi_sell_threshold,
            },
        )
        super().__init__(config)
        self.sma_period = sma_period
        self.rsi_period = rsi_period
        self.rsi_buy_threshold = rsi_buy_threshold
        self.rsi_sell_threshold = rsi_sell_threshold

    def get_required_lookback(self) -> int:
        return self.sma_period + self.rsi_period + 2

    def generate_signals(
        self, df: pd.DataFrame, current_idx: int
    ) -> Signal:
        """
        Generate signal at current_idx using only data up to and including current_idx.
        """
        symbol = df.iloc[current_idx].get("symbol", "UNKNOWN")
        price = df.iloc[current_idx]["close"]
        timestamp = df.iloc[current_idx]["timestamp"]

        if hasattr(timestamp, "to_pydatetime"):
            timestamp = timestamp.to_pydatetime()

        lookback = self.get_required_lookback()
        if current_idx < lookback:
            return Signal(
                timestamp=timestamp,
                symbol=symbol,
                signal_type=SignalType.HOLD,
                price=price,
                confidence=0.0,
                metadata={"reason": "insufficient_data"},
                strategy_name=self.name,
            )

        # Slice up to current_idx (inclusive)
        window = df.iloc[: current_idx + 1]
        closes = window["close"].values

        # Compute SMA
        sma = np.mean(closes[-self.sma_period:])

        # Compute RSI
        rsi = self._compute_rsi(closes, self.rsi_period)

        # Price above/below SMA for trend context
        trend = "bullish" if price > sma else "bearish"

        metadata = {
            "rsi": round(rsi, 2),
            "sma": round(sma, 2),
            "price": price,
            "trend": trend,
        }

        if rsi < self.rsi_buy_threshold:
            # Oversold → BUY signal
            confidence = min(1.0, (self.rsi_buy_threshold - rsi) / self.rsi_buy_threshold)
            return Signal(
                timestamp=timestamp,
                symbol=symbol,
                signal_type=SignalType.BUY,
                price=price,
                confidence=round(confidence, 3),
                metadata=metadata,
                strategy_name=self.name,
            )
        elif rsi > self.rsi_sell_threshold:
            # Overbought → SELL (short) signal
            confidence = min(1.0, (rsi - self.rsi_sell_threshold) / (100 - self.rsi_sell_threshold))
            return Signal(
                timestamp=timestamp,
                symbol=symbol,
                signal_type=SignalType.SELL,
                price=price,
                confidence=round(confidence, 3),
                metadata=metadata,
                strategy_name=self.name,
            )
        else:
            return Signal(
                timestamp=timestamp,
                symbol=symbol,
                signal_type=SignalType.HOLD,
                price=price,
                confidence=0.0,
                metadata=metadata,
                strategy_name=self.name,
            )

    @staticmethod
    def _compute_rsi(closes: np.ndarray, period: int = 14) -> float:
        """Compute RSI using Wilder's smoothing method."""
        if len(closes) < period + 1:
            return 50.0

        diffs = np.diff(closes[-(period + 1):])
        gains = np.where(diffs > 0, diffs, 0)
        losses = np.where(diffs < 0, -diffs, 0)

        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))


class PerSymbolRSISMAStrategy:
    """
    Adapter that manages multiple RSISMAStrategy instances with
    per-symbol parameter overrides, matching the original bot's
    per_symbol_settings pattern.
    """

    def __init__(
        self,
        symbols: list,
        default_sma_period: int = 20,
        default_rsi_period: int = 14,
        default_rsi_buy: float = 30.0,
        default_rsi_sell: float = 70.0,
        per_symbol_settings: Optional[Dict] = None,
    ):
        self.strategies: Dict[str, RSISMAStrategy] = {}
        self.symbols = symbols
        self.per_symbol_settings = per_symbol_settings or {}

        for sym in symbols:
            settings = self.per_symbol_settings.get(sym, {})
            self.strategies[sym] = RSISMAStrategy(
                sma_period=default_sma_period,
                rsi_period=settings.get("rsi_period", default_rsi_period),
                rsi_buy_threshold=settings.get("rsi_buy_threshold", default_rsi_buy),
                rsi_sell_threshold=settings.get("rsi_sell_threshold", default_rsi_sell),
            )

    def generate_signal(self, symbol: str, df: pd.DataFrame, idx: int) -> Signal:
        strategy = self.strategies.get(symbol)
        if strategy is None:
            return Signal(
                timestamp=df.iloc[idx]["timestamp"],
                symbol=symbol,
                signal_type=SignalType.HOLD,
                price=df.iloc[idx]["close"],
                confidence=0.0,
                metadata={"reason": "no_strategy"},
            )
        return strategy.generate_signals(df, idx)

    def get_lookback(self, symbol: str = None) -> int:
        if symbol and symbol in self.strategies:
            return self.strategies[symbol].get_required_lookback()
        # max across all
        return max(s.get_required_lookback() for s in self.strategies.values())
