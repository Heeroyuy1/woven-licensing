"""
Strategy Runner — Replays historical data day-by-day (or bar-by-bar),
executes strategies, and records all trades via the PaperBroker.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import pandas as pd
import csv
import os

from core.paper_broker import PaperBroker, Trade, OrderSide
from strategies.base_strategy import Signal, SignalType, BaseStrategy
from strategies.rsi_sma_strategy import PerSymbolRSISMAStrategy

logger = logging.getLogger("Harper.StrategyRunner")


class StrategyRunner:
    """
    Orchestrates the backtest: iterates through historical bars,
    generates signals, executes simulated trades, logs everything.
    """

    def __init__(
        self,
        broker: PaperBroker,
        strategy: PerSymbolRSISMAStrategy,
        stop_loss_pct: float = 0.02,
        take_profit_pct: float = 0.05,
        max_loss_pct: float = 0.05,
        max_holding_days: int = 5,
        max_exposure_pct: float = 0.1,
        risk_pct: float = 0.01,
        allow_shorts: bool = True,
        logs_dir: str = "logs",
    ):
        self.broker = broker
        self.strategy = strategy
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_loss_pct = max_loss_pct
        self.max_holding_days = max_holding_days
        self.max_exposure_pct = max_exposure_pct
        self.risk_pct = risk_pct
        self.allow_shorts = allow_shorts
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.signals_log: List[Dict] = []
        self.trades_log: List[Dict] = []
        self.daily_summary: List[Dict] = []

        # Per-symbol tracking for duplicate entry prevention
        self._has_position_or_pending: Dict[str, bool] = {}

    def run(
        self,
        symbol: str,
        df: pd.DataFrame,
        progress_callback=None,
    ) -> Dict:
        """
        Run backtest for a single symbol across all bars in df.

        Args:
            symbol: Stock ticker
            df: OHLCV DataFrame sorted by timestamp ascending
            progress_callback: Optional callable(current_idx, total) for progress

        Returns:
            Dict with full results summary
        """
        if df.empty:
            logger.warning(f"No data for {symbol}")
            return {"symbol": symbol, "error": "no_data"}

        df = df.sort_values("timestamp").reset_index(drop=True)
        total_bars = len(df)
        lookback = self.strategy.get_lookback(symbol)

        logger.info(
            f"Running backtest for {symbol}: {total_bars} bars, "
            f"lookback={lookback}, range={df.iloc[0]['timestamp']} → {df.iloc[-1]['timestamp']}"
        )

        prev_date = None

        for idx in range(total_bars):
            row = df.iloc[idx]
            current_price = row["close"]
            current_time = row["timestamp"]
            if isinstance(current_time, pd.Timestamp):
                current_time = current_time.to_pydatetime()
            elif hasattr(current_time, "to_pydatetime"):
                current_time = current_time.to_pydatetime()

            # Update position marks & record daily equity
            self.broker.update_positions({symbol: current_price}, current_time)

            current_date = current_time.date() if hasattr(current_time, "date") else current_time
            if hasattr(current_time, "date"):
                current_date = current_time.date()
            else:
                current_date = str(current_time)[:10]

            if prev_date != current_date:
                # Log daily summary
                self.daily_summary.append({
                    "date": str(current_date),
                    "symbol": symbol,
                    "equity": round(self.broker.equity, 2),
                    "cash": round(self.broker.cash, 2),
                    "positions": len(self.broker.positions),
                })
                prev_date = current_date

            # Check exit conditions for existing positions
            exited = self.broker.check_exits(
                {symbol: current_price},
                current_time,
                max_holding_days=self.max_holding_days,
                stop_loss_pct=self.stop_loss_pct,
                take_profit_pct=self.take_profit_pct,
                max_loss_pct=self.max_loss_pct,
                strategy="RSI_SMA",
            )
            for trade in exited:
                self.trades_log.append({
                    "timestamp": current_time.isoformat(),
                    "symbol": trade.symbol,
                    "side": trade.side.value,
                    "qty": trade.qty,
                    "entry_price": trade.entry_price,
                    "exit_price": trade.exit_price,
                    "pnl": round(trade.pnl, 2),
                    "pnl_pct": round(trade.pnl_pct, 2),
                    "exit_reason": trade.exit_reason,
                    "strategy": trade.strategy,
                })

            # Update position tracker after exits
            self._has_position_or_pending[symbol] = symbol in self.broker.positions

            # Generate signal
            signal = self.strategy.generate_signal(symbol, df, idx)
            self.signals_log.append({
                "timestamp": current_time.isoformat(),
                "symbol": signal.symbol,
                "signal": signal.signal_type.value,
                "price": signal.price,
                "confidence": signal.confidence,
                "metadata": str(signal.metadata),
            })

            # Act on signal — skip SELL if shorts disabled
            if signal.signal_type == SignalType.SELL and not self.allow_shorts:
                pass  # short selling disabled
            elif signal.signal_type in (SignalType.BUY, SignalType.SELL):
                if self._has_position_or_pending.get(symbol, False):
                    logger.debug(
                        f"Skipping {signal.signal_type.value} for {symbol}: "
                        f"already have position/pending order"
                    )
                    continue

                side = signal.signal_type.value
                qty = self.strategy.strategies[symbol].compute_position_size(
                    price=current_price,
                    equity=self.broker.equity,
                    max_exposure_pct=self.max_exposure_pct,
                    risk_pct=self.risk_pct,
                    stop_loss_pct=self.stop_loss_pct,
                )
                if qty < 1:
                    continue

                order = self.broker.place_market_order(
                    symbol=symbol,
                    side=side,
                    qty=qty,
                    current_price=current_price,
                    strategy="RSI_SMA",
                )
                if order:
                    self._has_position_or_pending[symbol] = True

            if progress_callback and idx % 50 == 0:
                progress_callback(idx, total_bars)

        # Close any remaining positions at last price
        for sym, pos in list(self.broker.positions.items()):
            last_price = df.iloc[-1]["close"]
            last_time = df.iloc[-1]["timestamp"]
            if isinstance(last_time, pd.Timestamp):
                last_time = last_time.to_pydatetime()

            self.broker.check_exits(
                {sym: last_price},
                last_time,
                max_holding_days=0,  # force close
                stop_loss_pct=0,
                take_profit_pct=0,
                max_loss_pct=0,
                strategy="RSI_SMA",
            )
            if sym in self.broker.positions:
                # Force-close remaining
                fill_price = self.broker.apply_slippage(
                    last_price, OrderSide.SELL if pos.side == OrderSide.BUY else OrderSide.BUY
                )
                close_side = "sell" if pos.side == OrderSide.BUY else "buy"
                self.broker.place_market_order(
                    symbol=sym, side=close_side, qty=pos.qty,
                    current_price=last_price, strategy="RSI_SMA",
                )

            self.trades_log.append({
                "timestamp": last_time.isoformat() if hasattr(last_time, "isoformat") else str(last_time),
                "symbol": sym,
                "side": pos.side.value,
                "qty": pos.qty,
                "entry_price": pos.avg_entry_price,
                "exit_price": last_price,
                "exit_reason": "end_of_backtest",
                "strategy": "RSI_SMA",
            })

        # Build results
        perf = self.broker.get_performance_summary()
        result = {
            "symbol": symbol,
            "start_date": str(df.iloc[0]["timestamp"]),
            "end_date": str(df.iloc[-1]["timestamp"]),
            "total_bars": total_bars,
            "performance": perf,
            "total_signals": len(self.signals_log),
            "buy_signals": sum(1 for s in self.signals_log if s["signal"] == "buy"),
            "sell_signals": sum(1 for s in self.signals_log if s["signal"] == "sell"),
            "trades": self.trades_log,
            "signals": self.signals_log,
            "daily_summary": self.daily_summary,
        }

        perf = self.broker.get_performance_summary()
        logger.info(
            f"  {symbol}: {perf['total_trades']} trades, "
            f"return={perf['total_return_pct']:+.2f}%, "
            f"sharpe={perf['sharpe_ratio']:.2f}, "
            f"maxDD={perf['max_drawdown_pct']:.2f}%, "
            f"win={perf['win_rate']:.1f}%"
        )
        self._save_logs(symbol, result)
        return result

    def _save_logs(self, symbol: str, result: Dict):
        """Persist trade logs and signals to CSV files."""
        # Trades
        trade_path = self.logs_dir / f"trades_{symbol}.csv"
        if self.trades_log:
            with open(trade_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.trades_log[0].keys())
                writer.writeheader()
                writer.writerows(self.trades_log)
            logger.info(f"Trade log saved: {trade_path} ({len(self.trades_log)} trades)")

        # Signals
        signal_path = self.logs_dir / f"signals_{symbol}.csv"
        if self.signals_log:
            with open(signal_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.signals_log[0].keys())
                writer.writeheader()
                writer.writerows(self.signals_log)

        # Daily summary
        daily_path = self.logs_dir / f"daily_{symbol}.csv"
        if self.daily_summary:
            with open(daily_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.daily_summary[0].keys())
                writer.writeheader()
                writer.writerows(self.daily_summary)

    def run_batch(
        self,
        data: Dict[str, pd.DataFrame],
        progress_callback=None,
    ) -> Dict[str, Dict]:
        """
        Run backtest across multiple symbols.

        Args:
            data: Dict of symbol -> DataFrame
            progress_callback: Optional callable(symbol, idx, total)

        Returns:
            Dict of symbol -> results dict
        """
        results = {}
        for sym, df in data.items():
            self.broker.reset()
            self.signals_log.clear()
            self.trades_log.clear()
            self.daily_summary.clear()
            self._has_position_or_pending.clear()

            try:
                result = self.run(sym, df)
                results[sym] = result
                if progress_callback:
                    progress_callback(sym, len(df), len(df))
            except Exception as e:
                logger.exception(f"Backtest failed for {sym}: {e}")
                results[sym] = {"symbol": sym, "error": str(e)}

        return results

    def get_combined_equity_curve(self, results: Dict[str, Dict]) -> pd.DataFrame:
        """Combine equity curves from all symbols into a single view."""
        all_daily = []
        for sym, result in results.items():
            if "daily_summary" in result:
                for d in result["daily_summary"]:
                    d["symbol"] = sym
                    all_daily.append(d)
        if not all_daily:
            return pd.DataFrame()
        df = pd.DataFrame(all_daily)
        df["date"] = pd.to_datetime(df["date"])
        # Group by date, sum equity across symbols
        combined = df.groupby("date")["equity"].sum().reset_index()
        combined["return_pct"] = combined["equity"].pct_change() * 100
        return combined
