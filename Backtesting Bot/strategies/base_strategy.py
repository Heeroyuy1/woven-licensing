"""
Base Strategy — Abstract interface for all trading strategies.
Each strategy receives historical data and generates signals.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from enum import Enum
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger("Harper.Strategy")


class SignalType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"


@dataclass
class Signal:
    timestamp: datetime
    symbol: str
    signal_type: SignalType
    price: float
    confidence: float = 1.0  # 0.0 - 1.0
    metadata: Dict = field(default_factory=dict)
    strategy_name: str = "base"


@dataclass
class StrategyConfig:
    name: str
    params: Dict = field(default_factory=dict)


class BaseStrategy(ABC):
    """Abstract base for all trading strategies."""

    def __init__(self, config: StrategyConfig):
        self.config = config
        self.name = config.name

    @abstractmethod
    def generate_signals(
        self, df: pd.DataFrame, current_idx: int
    ) -> Signal:
        """
        Generate a trading signal for the given point in time.

        Args:
            df: Full historical DataFrame up to current_idx (lookback available)
            current_idx: Current bar index being evaluated

        Returns:
            Signal with type and metadata
        """
        ...

    @abstractmethod
    def get_required_lookback(self) -> int:
        """Minimum number of bars needed before this strategy can produce signals."""
        ...

    def compute_position_size(
        self,
        price: float,
        equity: float,
        max_exposure_pct: float = 0.1,
        risk_pct: float = 0.01,
        stop_loss_pct: float = 0.02,
        rounding: int = 1,
    ) -> int:
        """
        Calculate position size based on risk management rules.

        Args:
            price: Current price
            equity: Total account equity
            max_exposure_pct: Max percentage of equity per position
            risk_pct: Percentage of equity to risk per trade
            stop_loss_pct: Stop loss distance as decimal
            rounding: Round to nearest N shares

        Returns:
            Number of shares
        """
        max_exposure = equity * max_exposure_pct
        risk_amount = equity * risk_pct
        stop_distance = price * stop_loss_pct

        qty_risk = int(risk_amount / stop_distance) if stop_distance > 0 else 0
        cap = int(max_exposure / price)
        qty = max(1, min(qty_risk, cap))

        if rounding > 1:
            qty = (qty // rounding) * rounding
        return max(1, qty)
