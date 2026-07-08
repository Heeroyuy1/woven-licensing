"""Paper Broker — Simulates trade execution with virtual money, matching the reference bot's logic."""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import pandas as pd

logger = logging.getLogger("Stratum.Broker")


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"


@dataclass
class Position:
    symbol: str
    side: OrderSide
    qty: int
    avg_entry_price: float
    entry_time: datetime
    entry_bar: int = 0
    current_price: float = 0.0
    unrealized_pl: float = 0.0
    unrealized_pl_pct: float = 0.0


@dataclass
class Trade:
    symbol: str
    side: OrderSide
    qty: int
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_pct: float
    exit_reason: str  # take_profit, stop_loss, max_loss, max_holding, signal, end_of_data
    strategy: str = "default"


class PaperBroker:
    """Virtual broker that matches the reference bot's exit logic exactly."""

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        commission_per_share: float = 0.0,
        slippage_pct: float = 0.0005,
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.commission_per_share = commission_per_share
        self.slippage_pct = slippage_pct
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve: List[Dict] = []
        self._order_counter = 0

    def reset(self):
        self.cash = self.initial_capital
        self.positions.clear()
        self.trades.clear()
        self.equity_curve.clear()
        self._order_counter = 0

    @property
    def equity(self) -> float:
        unrealized = sum(p.unrealized_pl for p in self.positions.values())
        return self.cash + unrealized

    def apply_slippage(self, price: float, side: OrderSide) -> float:
        if side == OrderSide.BUY:
            return price * (1 + self.slippage_pct)
        return price * (1 - self.slippage_pct)

    def update_position_marks(self, current_prices: Dict[str, float], current_time: Optional[datetime] = None):
        for sym, pos in list(self.positions.items()):
            price = current_prices.get(sym)
            if price is None:
                continue
            pos.current_price = price
            if pos.side == OrderSide.BUY:
                pos.unrealized_pl = (price - pos.avg_entry_price) * pos.qty
                pos.unrealized_pl_pct = ((price - pos.avg_entry_price) / pos.avg_entry_price) * 100
            else:
                pos.unrealized_pl = (pos.avg_entry_price - price) * pos.qty
                pos.unrealized_pl_pct = ((pos.avg_entry_price - price) / pos.avg_entry_price) * 100

        ts = current_time or datetime.now(timezone.utc)
        self.equity_curve.append({
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            "equity": round(self.equity, 2),
            "cash": round(self.cash, 2),
            "positions_value": round(self.equity - self.cash, 2),
        })

    def enter_position(
        self,
        symbol: str,
        side: str,
        qty: int,
        current_price: float,
        current_time: datetime,
        current_bar: int = 0,
        strategy: str = "default",
    ) -> bool:
        """Enter a new position. Returns True if filled."""
        side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        fill_price = self.apply_slippage(current_price, side_enum)
        cost = fill_price * qty
        commission = self.commission_per_share * qty

        if side_enum == OrderSide.BUY:
            if cost + commission > self.cash:
                logger.debug(f"Insufficient cash for {symbol} BUY {qty} @ {fill_price:.2f}")
                return False
            self.cash -= cost + commission
            self.positions[symbol] = Position(
                symbol=symbol, side=OrderSide.BUY, qty=qty,
                avg_entry_price=fill_price, entry_time=current_time,
                entry_bar=current_bar,
            )
        else:
            # Short: receive cash from sale
            self.cash += (fill_price * qty) - commission
            self.positions[symbol] = Position(
                symbol=symbol, side=OrderSide.SELL, qty=qty,
                avg_entry_price=fill_price, entry_time=current_time,
                entry_bar=current_bar,
            )

        logger.debug(f"ENTER {symbol} {side} qty={qty} @ ${fill_price:.2f} | Cash: ${self.cash:.2f}")
        return True

    def check_exits(
        self,
        symbol: str,
        current_price: float,
        current_time: datetime,
        current_bar: int = 0,
        stop_loss_pct: float = 0.02,
        take_profit_pct: float = 0.05,
        max_loss_pct: float = 0.05,
        max_holding_bars: int = 5,
        strategy: str = "default",
    ) -> Optional[Trade]:
        """Check a position for exit conditions. Returns Trade if exited, else None."""
        pos = self.positions.get(symbol)
        if pos is None:
            return None

        if pos.side == OrderSide.BUY:
            gain_pct = (current_price - pos.avg_entry_price) / pos.avg_entry_price
        else:
            gain_pct = (pos.avg_entry_price - current_price) / pos.avg_entry_price

        exit_reason = None
        close_side = OrderSide.SELL if pos.side == OrderSide.BUY else OrderSide.BUY

        # Check exit conditions in the same order as the reference bot
        if gain_pct >= take_profit_pct:
            exit_reason = "take_profit"
        elif gain_pct <= -stop_loss_pct:
            exit_reason = "stop_loss"
        elif gain_pct < -max_loss_pct:
            exit_reason = "max_loss"
        elif max_holding_bars > 0:
            holding = current_bar - pos.entry_bar
            if holding >= max_holding_bars:
                exit_reason = "max_holding"

        if exit_reason is None:
            return None

        fill_price = self.apply_slippage(current_price, close_side)
        if pos.side == OrderSide.BUY:
            realized = (fill_price - pos.avg_entry_price) * pos.qty
            pnl_pct = ((fill_price - pos.avg_entry_price) / pos.avg_entry_price) * 100
            self.cash += (fill_price * pos.qty) - (self.commission_per_share * pos.qty)
        else:
            realized = (pos.avg_entry_price - fill_price) * pos.qty
            pnl_pct = ((pos.avg_entry_price - fill_price) / pos.avg_entry_price) * 100
            self.cash -= (fill_price * pos.qty) + (self.commission_per_share * pos.qty)

        trade = Trade(
            symbol=symbol, side=pos.side, qty=pos.qty,
            entry_price=pos.avg_entry_price, exit_price=fill_price,
            entry_time=pos.entry_time, exit_time=current_time,
            pnl=realized, pnl_pct=pnl_pct,
            exit_reason=exit_reason, strategy=strategy,
        )
        self.trades.append(trade)
        del self.positions[symbol]

        logger.debug(f"EXIT [{exit_reason}] {symbol} P&L=${realized:.2f} ({pnl_pct:.2f}%)")
        return trade

    def force_close_all(self, prices: Dict[str, float], current_time: datetime, strategy: str = "default") -> List[Trade]:
        """Force-close all remaining positions."""
        closed = []
        for sym in list(self.positions.keys()):
            price = prices.get(sym, 0)
            if price == 0:
                continue
            t = self.check_exits(sym, price, current_time, max_holding_bars=0, stop_loss_pct=0,
                                 take_profit_pct=100, max_loss_pct=100, strategy=strategy)
            if t:
                closed.append(t)
        return closed

    def get_performance_summary(self) -> Dict:
        """Full performance metrics matching the spec."""
        total_trades = len(self.trades)
        wins = [t for t in self.trades if t.pnl > 0]
        losses = [t for t in self.trades if t.pnl < 0]
        avg_win = sum(t.pnl for t in wins) / len(wins) if wins else 0.0
        avg_loss = sum(abs(t.pnl) for t in losses) / len(losses) if losses else 0.0
        pl_ratio = avg_win / avg_loss if avg_loss > 0 else (float("inf") if avg_win > 0 else 0.0)

        # Drawdown
        max_dd = 0.0
        if self.equity_curve:
            values = [e["equity"] for e in self.equity_curve]
            peak = values[0]
            for v in values:
                if v > peak:
                    peak = v
                dd = (peak - v) / peak * 100
                if dd > max_dd:
                    max_dd = dd

        # Sharpe
        sharpe = 0.0
        if len(self.equity_curve) > 2:
            eq = pd.DataFrame(self.equity_curve)
            eq["date"] = pd.to_datetime(eq["timestamp"], utc=True).dt.date
            daily = eq.groupby("date")["equity"].last().pct_change().dropna()
            if len(daily) > 1 and daily.std() > 0:
                excess = daily.mean() - (0.02 / 252)
                sharpe = (excess / daily.std()) * np.sqrt(252)

        # Consecutive wins/losses
        max_cons_wins = 0
        max_cons_losses = 0
        cur_wins = 0
        cur_losses = 0
        for t in self.trades:
            if t.pnl > 0:
                cur_wins += 1
                cur_losses = 0
                max_cons_wins = max(max_cons_wins, cur_wins)
            elif t.pnl < 0:
                cur_losses += 1
                cur_wins = 0
                max_cons_losses = max(max_cons_losses, cur_losses)

        # Average trade duration
        avg_duration = 0.0
        if self.trades:
            durations = [(t.exit_time - t.entry_time).total_seconds() / 86400 for t in self.trades]
            avg_duration = sum(durations) / len(durations)

        return {
            "initial_capital": self.initial_capital,
            "final_equity": round(self.equity, 2),
            "total_return_pct": round(((self.equity - self.initial_capital) / self.initial_capital) * 100, 2),
            "total_realized_pnl": round(self.equity - self.initial_capital, 2),
            "cash": round(self.cash, 2),
            "total_trades": total_trades,
            "win_count": len(wins),
            "loss_count": len(losses),
            "win_rate": round((len(wins) / total_trades * 100) if total_trades > 0 else 0, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "pl_ratio": round(pl_ratio, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "sharpe_ratio": round(sharpe, 2),
            "max_consecutive_wins": max_cons_wins,
            "max_consecutive_losses": max_cons_losses,
            "avg_trade_duration_days": round(avg_duration, 1),
        }
