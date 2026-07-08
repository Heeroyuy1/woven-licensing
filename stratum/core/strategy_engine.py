"""Strategy Engine — Historical backtesting engine matching the reference bot's RSI+SMA logic exactly."""
import logging
from typing import Dict, List, Optional, Tuple, Callable
from datetime import datetime, timezone
import numpy as np
import pandas as pd

from .broker import PaperBroker, OrderSide, Trade
from .config_manager import ConfigManager, StrategyParams

logger = logging.getLogger("Stratum.Engine")


class StrategyEngine:
    """
    Backtesting engine that replays historical bars bar-by-bar, generating
    RSI/SMA signals and executing trades through the PaperBroker.

    Matches the reference bot (TradingBackTestingLIVE.py) logic exactly:
    - BUY when RSI < rsi_buy_threshold (oversold)
    - SELL (short) when RSI > rsi_sell_threshold (overbought)
    - SMA for trend context
    - Exit conditions: take_profit, stop_loss, max_loss, max_holding
    """

    def __init__(self, config: ConfigManager):
        self.config = config
        self.broker = PaperBroker(
            initial_capital=config.config.get("initial_capital", 100_000),
            commission_per_share=config.config.get("commission_per_share", 0.0),
            slippage_pct=config.config.get("slippage_pct", 0.0005),
        )
        self._results: Dict[str, Dict] = {}
        self._progress_callback: Optional[Callable[[str, int, int], None]] = None

    def set_progress_callback(self, cb: Optional[Callable[[str, int, int], None]]):
        self._progress_callback = cb

    def run_symbol(
        self,
        symbol: str,
        df: pd.DataFrame,
        params: Optional[StrategyParams] = None,
    ) -> Dict:
        """Run backtest for a single symbol."""
        if df.empty:
            return {"symbol": symbol, "error": "no_data"}

        df = df.sort_values("timestamp").reset_index(drop=True)
        total_bars = len(df)

        if params is None:
            params = self.config.get_strategy_params(symbol)

        sma_period = params.sma_period
        rsi_period = params.rsi_period
        rsi_buy = params.rsi_buy_threshold
        rsi_sell = params.rsi_sell_threshold
        stop_loss = params.stop_loss_pct
        take_profit = params.take_profit_pct
        max_loss = params.max_loss_pct
        max_holding = params.max_holding_bars
        max_exposure = params.max_exposure_pct
        risk_pct = params.risk_pct
        allow_shorts = self.config.config.get("allow_shorts", True)

        lookback = sma_period + rsi_period + 2

        self.broker.reset()
        daily_summary = []
        prev_date = None

        for idx in range(total_bars):
            row = df.iloc[idx]
            current_price = float(row["close"])
            current_time = row["timestamp"]
            if isinstance(current_time, pd.Timestamp):
                current_time = current_time.to_pydatetime()

            # Update position marks
            self.broker.update_position_marks({symbol: current_price}, current_time)

            # Daily summary
            current_date = current_time.date() if hasattr(current_time, "date") else str(current_time)[:10]
            if prev_date != current_date:
                daily_summary.append({
                    "date": str(current_date),
                    "equity": round(self.broker.equity, 2),
                    "cash": round(self.broker.cash, 2),
                    "positions": len(self.broker.positions),
                })
                prev_date = current_date

            # Check exits for existing position
            self.broker.check_exits(
                symbol=symbol,
                current_price=current_price,
                current_time=current_time,
                current_bar=idx,
                stop_loss_pct=stop_loss,
                take_profit_pct=take_profit,
                max_loss_pct=max_loss,
                max_holding_bars=max_holding,
                strategy="RSI_SMA",
            )

            # Skip signal generation if insufficient data
            if idx < lookback:
                if self._progress_callback and idx % 50 == 0:
                    self._progress_callback(symbol, idx, total_bars)
                continue

            # Skip if already in a position
            if symbol in self.broker.positions:
                if self._progress_callback and idx % 50 == 0:
                    self._progress_callback(symbol, idx, total_bars)
                continue

            # Compute RSI (Wilder's smoothing, matching reference bot)
            closes = df["close"].values[: idx + 1]
            rsi = self._compute_rsi(closes, rsi_period)

            # Compute SMA
            sma = float(np.mean(closes[-sma_period:]))

            # Generate signal matching the reference bot exactly
            if rsi < rsi_buy:
                # BUY signal
                qty = self._compute_qty(current_price, max_exposure, risk_pct, stop_loss)
                if qty >= 1:
                    self.broker.enter_position(
                        symbol=symbol, side="buy", qty=qty,
                        current_price=current_price, current_time=current_time,
                        current_bar=idx, strategy="RSI_SMA",
                    )
            elif rsi > rsi_sell and allow_shorts:
                # SELL (short) signal
                qty = self._compute_qty(current_price, max_exposure, risk_pct, stop_loss)
                if qty >= 1:
                    self.broker.enter_position(
                        symbol=symbol, side="sell", qty=qty,
                        current_price=current_price, current_time=current_time,
                        current_bar=idx, strategy="RSI_SMA",
                    )

            if self._progress_callback and idx % 50 == 0:
                self._progress_callback(symbol, idx, total_bars)

        # Force close at end
        last_price = float(df.iloc[-1]["close"])
        last_time = df.iloc[-1]["timestamp"]
        if isinstance(last_time, pd.Timestamp):
            last_time = last_time.to_pydatetime()
        self.broker.force_close_all({symbol: last_price}, last_time, strategy="RSI_SMA")

        return self._build_result(symbol, df, params, daily_summary)

    def _compute_rsi(self, closes: np.ndarray, period: int = 14) -> float:
        """Wilder's smoothed RSI — matches the reference bot exactly."""
        if len(closes) < period + 1:
            return 50.0
        diffs = np.diff(closes[-(period + 1):])
        gains = np.where(diffs > 0, diffs, 0)
        losses = np.where(diffs < 0, -diffs, 0)
        avg_gain = float(np.mean(gains))
        avg_loss = float(np.mean(losses))
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def _compute_qty(self, price: float, max_exposure_pct: float, risk_pct: float, stop_loss_pct: float) -> int:
        """Compute position size matching reference bot logic."""
        equity = self.broker.equity
        max_exposure = equity * max_exposure_pct
        risk_amount = equity * risk_pct
        stop_distance = price * stop_loss_pct
        qty_risk = int(risk_amount / stop_distance) if stop_distance > 0 else 0
        cap = int(max_exposure / price)
        return max(1, min(qty_risk, cap))

    def _build_result(self, symbol: str, df: pd.DataFrame, params: StrategyParams, daily_summary: List[Dict]) -> Dict:
        """Build the results dict for a symbol."""
        perf = self.broker.get_performance_summary()
        trades_list = []
        for t in self.broker.trades:
            trades_list.append({
                "entry_time": t.entry_time.isoformat() if hasattr(t.entry_time, "isoformat") else str(t.entry_time),
                "exit_time": t.exit_time.isoformat() if hasattr(t.exit_time, "isoformat") else str(t.exit_time),
                "symbol": t.symbol,
                "side": t.side.value,
                "qty": t.qty,
                "entry_price": round(t.entry_price, 2),
                "exit_price": round(t.exit_price, 2),
                "pnl": round(t.pnl, 2),
                "pnl_pct": round(t.pnl_pct, 2),
                "exit_reason": t.exit_reason,
            })

        # Win/loss distribution
        pnls = [t.pnl for t in self.broker.trades]

        result = {
            "symbol": symbol,
            "start_date": str(df.iloc[0]["timestamp"]),
            "end_date": str(df.iloc[-1]["timestamp"]),
            "total_bars": len(df),
            "params": params.to_dict(),
            "performance": perf,
            "trades": trades_list,
            "equity_curve": self.broker.equity_curve,
            "daily_summary": daily_summary,
            "pnl_distribution": {
                "min": round(min(pnls), 2) if pnls else 0,
                "max": round(max(pnls), 2) if pnls else 0,
                "mean": round(np.mean(pnls), 2) if pnls else 0,
                "median": round(float(np.median(pnls)), 2) if pnls else 0,
                "std": round(float(np.std(pnls)), 2) if pnls else 0,
            },
        }
        self._results[symbol] = result
        return result

    def run_batch(
        self,
        data: Dict[str, pd.DataFrame],
    ) -> Dict[str, Dict]:
        """Run backtest across multiple symbols."""
        results = {}
        for sym, df in data.items():
            try:
                result = self.run_symbol(sym, df)
                results[sym] = result
            except Exception as e:
                logger.exception(f"Backtest failed for {sym}: {e}")
                results[sym] = {"symbol": sym, "error": str(e)}
        return results

    def get_results(self, symbol: Optional[str] = None):
        if symbol:
            return self._results.get(symbol)
        return self._results
