"""
Paper Trading Broker — Simulates trade execution with virtual money.
Tracks: positions, orders, fills, P&L, commissions, and full trade history.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import numpy as np

logger = logging.getLogger("Harper.PaperBroker")


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"


@dataclass
class Order:
    order_id: str
    symbol: str
    side: OrderSide
    qty: int
    order_type: str  # 'market', 'limit', 'bracket'
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    trail_percent: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_price: Optional[float] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    filled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    parent_order_id: Optional[str] = None  # for bracket leg tracking
    is_exit_order: bool = False  # True if this is a stop-loss or take-profit exit


@dataclass
class Position:
    symbol: str
    side: OrderSide
    qty: int
    avg_entry_price: float
    entry_time: datetime
    current_price: float = 0.0
    unrealized_pl: float = 0.0
    unrealized_pl_pct: float = 0.0


@dataclass
class Trade:
    """Completed round-trip trade."""
    symbol: str
    side: OrderSide
    qty: int
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_pct: float
    exit_reason: str  # 'take_profit', 'stop_loss', 'max_holding', 'signal', 'manual'
    strategy: str = "default"


class PaperBroker:
    """
    Virtual brokerage for backtesting.
    Simulates fills at market prices, handles bracket orders,
    tracks positions, commissions, and generates trade records.
    """

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        commission_per_share: float = 0.0,
        slippage_pct: float = 0.0005,  # 5 bps slippage
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.commission_per_share = commission_per_share
        self.slippage_pct = slippage_pct

        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.trades: List[Trade] = []
        self.equity_curve: List[Dict] = []  # timestamp, equity
        self._order_counter = 0

    def _next_order_id(self) -> str:
        self._order_counter += 1
        return f"sim_{self._order_counter:06d}"

    @property
    def equity(self) -> float:
        """Total equity = cash + unrealized P&L of open positions."""
        unrealized = sum(p.unrealized_pl for p in self.positions.values())
        return self.cash + unrealized

    @property
    def total_realized_pnl(self) -> float:
        return self.equity - self.initial_capital

    @property
    def win_count(self) -> int:
        return sum(1 for t in self.trades if t.pnl > 0)

    @property
    def loss_count(self) -> int:
        return sum(1 for t in self.trades if t.pnl < 0)

    @property
    def win_rate(self) -> float:
        total = self.win_count + self.loss_count
        return self.win_count / total if total > 0 else 0.0

    @property
    def total_return_pct(self) -> float:
        return ((self.equity - self.initial_capital) / self.initial_capital) * 100

    def get_max_drawdown_pct(self) -> float:
        """Calculate maximum drawdown from equity curve."""
        if not self.equity_curve:
            return 0.0
        values = [e["equity"] for e in self.equity_curve]
        peak = values[0]
        max_dd = 0.0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100
            if dd > max_dd:
                max_dd = dd
        return max_dd

    def get_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Annualized Sharpe ratio from equity curve daily returns."""
        if len(self.equity_curve) < 2:
            return 0.0
        eq = pd.DataFrame(self.equity_curve)
        eq["date"] = pd.to_datetime(eq["timestamp"], utc=True).dt.date
        daily = eq.groupby("date")["equity"].last().pct_change().dropna()
        if len(daily) < 2 or daily.std() == 0:
            return 0.0
        excess = daily.mean() - (risk_free_rate / 252)
        return (excess / daily.std()) * np.sqrt(252) if daily.std() > 0 else 0.0

    def update_positions(self, current_prices: Dict[str, float], current_time: Optional[datetime] = None):
        """Mark all open positions to market. Optionally pass the bar timestamp."""
        for sym, pos in list(self.positions.items()):
            if sym in current_prices:
                price = current_prices[sym]
                pos.current_price = price
                if pos.side == OrderSide.BUY:
                    pos.unrealized_pl = (price - pos.avg_entry_price) * pos.qty
                    pos.unrealized_pl_pct = ((price - pos.avg_entry_price) / pos.avg_entry_price) * 100
                else:  # short
                    pos.unrealized_pl = (pos.avg_entry_price - price) * pos.qty
                    pos.unrealized_pl_pct = ((pos.avg_entry_price - price) / pos.avg_entry_price) * 100

        ts = current_time if current_time else datetime.now(timezone.utc)
        self.equity_curve.append({
            "timestamp": ts.isoformat() if hasattr(ts, 'isoformat') else str(ts),
            "equity": self.equity,
            "cash": self.cash,
            "positions_value": self.equity - self.cash,
        })

    def apply_slippage(self, price: float, side: OrderSide) -> float:
        """Apply slippage: adverse price movement on fills. Public for external use."""
        if side == OrderSide.BUY:
            return price * (1 + self.slippage_pct)
        else:
            return price * (1 - self.slippage_pct)

    def place_market_order(
        self,
        symbol: str,
        side: str,
        qty: int,
        current_price: float,
        strategy: str = "default",
    ) -> Optional[Order]:
        """
        Place and immediately fill a market order.

        Returns the filled Order, or None if rejected (insufficient funds, etc.).
        """
        order_id = self._next_order_id()
        side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

        fill_price = self.apply_slippage(current_price, side_enum)
        cost = fill_price * qty
        commission = self.commission_per_share * qty

        # Validate
        if side_enum == OrderSide.BUY:
            if cost + commission > self.cash:
                logger.warning(
                    f"Insufficient cash for {symbol} BUY {qty} @ {fill_price:.2f}: "
                    f"need ${cost + commission:.2f}, have ${self.cash:.2f}"
                )
                order = Order(
                    order_id=order_id, symbol=symbol, side=side_enum,
                    qty=qty, order_type="market",
                    status=OrderStatus.REJECTED,
                    cancel_reason="insufficient_funds",
                )
                self.orders[order_id] = order
                return None

            # Deduct cash
            self.cash -= cost + commission

            # Update or create position
            if symbol in self.positions:
                pos = self.positions[symbol]
                if pos.side == OrderSide.BUY:
                    # Average up
                    total_qty = pos.qty + qty
                    pos.avg_entry_price = (
                        (pos.avg_entry_price * pos.qty) + (fill_price * qty)
                    ) / total_qty
                    pos.qty = total_qty
                else:
                    # Closing short — realized P&L from the portion closed
                    closed_qty = min(qty, pos.qty)
                    remaining = qty - closed_qty
                    realized = (pos.avg_entry_price - fill_price) * closed_qty
                    self.cash += realized
                    # Record trade
                    self.trades.append(Trade(
                        symbol=symbol, side=pos.side, qty=closed_qty,
                        entry_price=pos.avg_entry_price, exit_price=fill_price,
                        entry_time=pos.entry_time,
                        exit_time=datetime.now(timezone.utc),
                        pnl=realized, pnl_pct=((pos.avg_entry_price - fill_price) / pos.avg_entry_price) * 100,
                        exit_reason="signal", strategy=strategy,
                    ))
                    if remaining > 0:
                        pos.qty = remaining
                    else:
                        del self.positions[symbol]
                    # Open long if more
                    if remaining < 0:
                        self.positions[symbol] = Position(
                            symbol=symbol, side=OrderSide.BUY, qty=abs(remaining),
                            avg_entry_price=fill_price,
                            entry_time=datetime.now(timezone.utc),
                        )
            else:
                self.positions[symbol] = Position(
                    symbol=symbol, side=OrderSide.BUY, qty=qty,
                    avg_entry_price=fill_price,
                    entry_time=datetime.now(timezone.utc),
                )

        else:  # SELL
            # For a short sell, we need sufficient margin. Simplified: use cash as margin proxy.
            if symbol in self.positions:
                pos = self.positions[symbol]
                if pos.side == OrderSide.SELL:
                    total_qty = pos.qty + qty
                    pos.avg_entry_price = (
                        (pos.avg_entry_price * pos.qty) + (fill_price * qty)
                    ) / total_qty
                    pos.qty = total_qty
                else:
                    # Closing long
                    closed_qty = min(qty, pos.qty)
                    remaining = qty - closed_qty
                    realized = (fill_price - pos.avg_entry_price) * closed_qty
                    self.cash += realized + (fill_price * closed_qty) - commission
                    self.trades.append(Trade(
                        symbol=symbol, side=pos.side, qty=closed_qty,
                        entry_price=pos.avg_entry_price, exit_price=fill_price,
                        entry_time=pos.entry_time,
                        exit_time=datetime.now(timezone.utc),
                        pnl=realized, pnl_pct=((fill_price - pos.avg_entry_price) / pos.avg_entry_price) * 100,
                        exit_reason="signal", strategy=strategy,
                    ))
                    if remaining > 0:
                        pos.qty = remaining
                    else:
                        del self.positions[symbol]
                    if remaining < 0:
                        self.positions[symbol] = Position(
                            symbol=symbol, side=OrderSide.SELL, qty=abs(remaining),
                            avg_entry_price=fill_price,
                            entry_time=datetime.now(timezone.utc),
                        )
                    return Order(
                        order_id=order_id, symbol=symbol, side=side_enum,
                        qty=qty, order_type="market", status=OrderStatus.FILLED,
                        filled_price=fill_price, filled_at=datetime.now(timezone.utc),
                    )
            else:
                self.positions[symbol] = Position(
                    symbol=symbol, side=OrderSide.SELL, qty=qty,
                    avg_entry_price=fill_price,
                    entry_time=datetime.now(timezone.utc),
                )
            # For new short: receive cash from sale
            self.cash += (fill_price * qty) - commission

        order = Order(
            order_id=order_id, symbol=symbol, side=side_enum,
            qty=qty, order_type="market", status=OrderStatus.FILLED,
            filled_price=fill_price, filled_at=datetime.now(timezone.utc),
        )
        self.orders[order_id] = order
        logger.debug(
            f"FILLED: {symbol} {side.upper()} qty={qty} @ ${fill_price:.2f} "
            f"| Cash: ${self.cash:.2f} | Equity: ${self.equity:.2f}"
        )
        return order

    def check_exits(
        self,
        current_prices: Dict[str, float],
        current_time: datetime,
        max_holding_days: int = 5,
        stop_loss_pct: float = 0.02,
        take_profit_pct: float = 0.05,
        max_loss_pct: float = 0.05,
        strategy: str = "default",
    ) -> List[Trade]:
        """
        Check all open positions for stop-loss, take-profit, and
        max holding period breaches. Auto-close positions that trigger.

        Returns list of new Trade records from exits.
        """
        exited_trades = []
        for sym, pos in list(self.positions.items()):
            price = current_prices.get(sym)
            if price is None:
                continue

            if pos.side == OrderSide.BUY:
                gain_pct = (price - pos.avg_entry_price) / pos.avg_entry_price
            else:
                gain_pct = (pos.avg_entry_price - price) / pos.avg_entry_price

            exit_reason = None
            close_side = OrderSide.SELL if pos.side == OrderSide.BUY else OrderSide.BUY

            if gain_pct >= take_profit_pct:
                exit_reason = "take_profit"
            elif gain_pct <= -stop_loss_pct:
                exit_reason = "stop_loss"
            elif gain_pct < -max_loss_pct:
                exit_reason = "max_loss"
            elif max_holding_days > 0:
                holding_days = (current_time - pos.entry_time).days
                if holding_days >= max_holding_days:
                    exit_reason = "max_holding"

            if exit_reason:
                fill_price = self.apply_slippage(price, close_side)
                if pos.side == OrderSide.BUY:
                    realized = (fill_price - pos.avg_entry_price) * pos.qty
                    pnl_pct = ((fill_price - pos.avg_entry_price) / pos.avg_entry_price) * 100
                else:
                    realized = (pos.avg_entry_price - fill_price) * pos.qty
                    pnl_pct = ((pos.avg_entry_price - fill_price) / pos.avg_entry_price) * 100

                commission = self.commission_per_share * pos.qty
                if pos.side == OrderSide.BUY:
                    self.cash += (fill_price * pos.qty) - commission
                else:
                    # Short exit: deduct cover cost + commission, realized P&L is already in cash from entry
                    self.cash -= (fill_price * pos.qty) + commission

                trade = Trade(
                    symbol=sym, side=pos.side, qty=pos.qty,
                    entry_price=pos.avg_entry_price, exit_price=fill_price,
                    entry_time=pos.entry_time, exit_time=current_time,
                    pnl=realized, pnl_pct=pnl_pct,
                    exit_reason=exit_reason, strategy=strategy,
                )
                self.trades.append(trade)
                exited_trades.append(trade)
                del self.positions[sym]
                logger.debug(
                    f"EXIT [{exit_reason}]: {sym} {pos.side.value} qty={pos.qty} "
                    f"entry=${pos.avg_entry_price:.2f} exit=${fill_price:.2f} "
                    f"P&L=${realized:.2f} ({pnl_pct:.2f}%)"
                )

        return exited_trades

    def get_positions_summary(self) -> List[Dict]:
        """Return summary of all open positions."""
        return [
            {
                "symbol": p.symbol,
                "side": p.side.value,
                "qty": p.qty,
                "avg_entry": round(p.avg_entry_price, 2),
                "current_price": round(p.current_price, 2),
                "unrealized_pl": round(p.unrealized_pl, 2),
                "unrealized_pl_pct": round(p.unrealized_pl_pct, 2),
                "holding_days": (datetime.now(timezone.utc) - p.entry_time).days,
            }
            for p in self.positions.values()
        ]

    def get_performance_summary(self) -> Dict:
        """Compute full performance metrics."""
        total_trades = len(self.trades)
        wins = [t for t in self.trades if t.pnl > 0]
        losses = [t for t in self.trades if t.pnl < 0]

        avg_win = sum(t.pnl for t in wins) / len(wins) if wins else 0.0
        avg_loss = sum(abs(t.pnl) for t in losses) / len(losses) if losses else 0.0
        pl_ratio = avg_win / avg_loss if avg_loss > 0 else (float("inf") if avg_win > 0 else 0.0)

        return {
            "initial_capital": self.initial_capital,
            "final_equity": round(self.equity, 2),
            "total_return_pct": round(self.total_return_pct, 2),
            "total_realized_pnl": round(self.total_realized_pnl, 2),
            "cash": round(self.cash, 2),
            "total_trades": total_trades,
            "win_count": len(wins),
            "loss_count": len(losses),
            "win_rate": round(self.win_rate * 100, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "pl_ratio": round(pl_ratio, 2),
            "max_drawdown_pct": round(self.get_max_drawdown_pct(), 2),
            "sharpe_ratio": round(self.get_sharpe_ratio(), 2),
        }

    def reset(self):
        """Reset broker state for a fresh backtest run."""
        self.cash = self.initial_capital
        self.positions.clear()
        self.orders.clear()
        self.trades.clear()
        self.equity_curve.clear()
        self._order_counter = 0


# deferred import to avoid circularity
import pandas as pd
