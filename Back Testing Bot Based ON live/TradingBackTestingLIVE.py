import asyncio
import logging
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import numpy as np
from collections import defaultdict
import aiohttp
import csv
import aiofiles

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from alpaca.trading.stream import TradingStream
from alpaca.common.exceptions import APIError

# ---------------- Logging ---------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("NextGenBot")
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("alpaca").setLevel(logging.INFO)

# ---------------- Discord Helper ---------------- #
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1411161891958685760/3kzCLgkoV85u05MuoiEgKQTpkmGvAcaGfunxhWHZ52BG96IpN2oIKkBRMtOWEf79_Lgl"


# Discord message queue to prevent 429 rate limits — max 5 messages/sec, 500ms apart
_discord_queue = asyncio.Queue()
_discord_last_send = 0.0
_discord_lock = asyncio.Lock()


async def _discord_sender():
    """Background task that drains the Discord message queue with spacing."""
    global _discord_last_send
    while True:
        message, level = await _discord_queue.get()
        try:
            async with _discord_lock:
                now = datetime.now(timezone.utc).timestamp()
                elapsed = now - _discord_last_send
                if elapsed < 0.5:
                    await asyncio.sleep(0.5 - elapsed)
            async with aiohttp.ClientSession() as session:
                payload = {"content": f"[{level.upper()}] {message}"}
                async with session.post(DISCORD_WEBHOOK_URL, json=payload) as resp:
                    text = await resp.text()
                    if resp.status == 429:
                        retry_after = 0.5
                        try:
                            data = json.loads(text)
                            retry_after = float(data.get("retry_after", 0.5))
                        except Exception:
                            pass
                        logger.warning(f"Discord rate limited, sleeping {retry_after}s")
                        await asyncio.sleep(retry_after)
                        # Re-queue the message
                        await _discord_queue.put((message, level))
                    elif resp.status not in (200, 204):
                        logger.warning(f"Discord webhook failed: {resp.status} {text}")
            async with _discord_lock:
                _discord_last_send = datetime.now(timezone.utc).timestamp()
        except Exception:
            logger.exception("Failed to send Discord message")
        finally:
            _discord_queue.task_done()


async def send_discord_message(message: str, level: str = "info"):
    if not DISCORD_WEBHOOK_URL:
        return
    await _discord_queue.put((message, level))


# ---------------- Simple Async RateLimiter ---------------- #
def RateLimiter(max_calls, period_sec):
    class _RateLimiter:
        def __init__(self):
            self.max_calls = max_calls
            self.period = period_sec
            self.calls = []
            self.lock = asyncio.Lock()

        async def acquire(self):
            async with self.lock:
                now = datetime.now(timezone.utc).timestamp()
                self.calls = [t for t in self.calls if now - t < self.period]
                if len(self.calls) >= self.max_calls:
                    logger.warning(
                        f"Rate limit reached ({self.max_calls} calls in {self.period}s). Waiting..."
                    )
                    while len(self.calls) >= self.max_calls:
                        await asyncio.sleep(0.5)
                        now = datetime.now(timezone.utc).timestamp()
                        self.calls = [t for t in self.calls if now - t < self.period]
                self.calls.append(now)

    return _RateLimiter()


# ---------------- Next-Gen Trading Bot ---------------- #
class NextGenTradingBot:
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        symbols: List[str],
        paper: bool,
        max_exposure_pct: float = 0.1,
        sma_period: int = 20,
        risk_pct: float = 0.01,
        max_holding_period: int = 5,
        enable_trailing: bool = False,
        max_loss_pct: float = 0.05,
        per_symbol_settings: dict = None,
    ):
        self.api_key = api_key
        self.secret_key = secret_key
        self.symbols = symbols
        self.trading_client = TradingClient(api_key, secret_key, paper=paper)
        self.data_client = StockHistoricalDataClient(api_key, secret_key)
        self.rate_limiter = RateLimiter(200, 60)
        self.paper = paper
        self.max_exposure_pct = max_exposure_pct
        self.sma_period = sma_period
        self.risk_pct = risk_pct
        self.max_holding_period = max_holding_period
        self.enable_trailing = enable_trailing
        self.default_max_loss_pct = max_loss_pct
        self.per_symbol_settings = per_symbol_settings or {
            symbol: {
                "rsi_period": 14,
                "rsi_buy_threshold": 30,
                "rsi_sell_threshold": 70,
                "stop_loss_pct": 0.02,
                "take_profit_pct": 0.05,
                "max_loss_pct": self.default_max_loss_pct,
            }
            for symbol in symbols
        }
        for symbol in symbols:
            if symbol not in self.per_symbol_settings:
                logger.warning(f"No per-symbol settings for {symbol}, using defaults")
                self.per_symbol_settings[symbol] = {
                    "rsi_period": 14,
                    "rsi_buy_threshold": 30,
                    "rsi_sell_threshold": 70,
                    "stop_loss_pct": 0.02,
                    "take_profit_pct": 0.05,
                    "max_loss_pct": self.default_max_loss_pct,
                }
            else:
                self.per_symbol_settings[symbol].setdefault(
                    "max_loss_pct", self.default_max_loss_pct
                )
        self.submitted_order_ids: List[str] = []
        self.session_start = datetime.now(timezone.utc)
        self.session_trades: Dict[str, List[Dict]] = defaultdict(list)
        self.csv_file = "session_trades.csv"
        self.metrics_file = "metrics_history.csv"
        logger.info(
            f"Initialized NextGenTradingBot v1 in {'paper' if paper else 'live'} mode"
        )

        if not os.path.exists(self.csv_file):
            with open(self.csv_file, "w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "timestamp",
                        "symbol",
                        "side",
                        "qty",
                        "entry_price",
                        "exit_price",
                        "stop_loss",
                        "take_profit",
                        "status",
                    ],
                )
                writer.writeheader()

        if not os.path.exists(self.metrics_file):
            with open(self.metrics_file, "w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "timestamp",
                        "symbol",
                        "win_rate",
                        "pl_ratio",
                        "total_pnl",
                        "trade_count",
                        "sharpe_ratio",
                    ],
                )
                writer.writeheader()

    async def compute_metrics(self, interval_seconds: int = 1800):
        while True:
            try:
                for symbol in self.symbols:
                    await self.compute_metrics_once(symbol)
                await asyncio.sleep(interval_seconds)
            except Exception as e:
                logger.exception(f"Error computing metrics: {e}")
                await send_discord_message("Error computing metrics", "error")
                await asyncio.sleep(interval_seconds)

    async def compute_metrics_once(self, symbol: str):
        try:
            trades = self.session_trades[symbol]
            filled_trades = [
                t
                for t in trades
                if t["status"] == "filled" and t["exit_price"] is not None
            ]
            if not filled_trades:
                logger.info(f"No filled trades for {symbol} to compute metrics")
                return

            wins = 0
            total_pnl = 0.0
            profits = []
            losses = []
            pnls = []
            for trade in filled_trades:
                if trade["side"] == "buy":
                    pnl = (trade["exit_price"] - trade["entry_price"]) * trade["qty"]
                else:
                    pnl = (trade["entry_price"] - trade["exit_price"]) * trade["qty"]
                total_pnl += pnl
                pnls.append(pnl)
                if pnl > 0:
                    wins += 1
                    profits.append(pnl)
                elif pnl < 0:
                    losses.append(abs(pnl))
            win_rate = wins / len(filled_trades) if filled_trades else 0.0
            avg_profit = sum(profits) / len(profits) if profits else 0.0
            avg_loss = sum(losses) / len(losses) if losses else 0.0
            pl_ratio = (
                avg_profit / avg_loss
                if avg_loss > 0
                else float("inf")
                if avg_profit > 0
                else 0.0
            )
            sharpe_ratio = (
                (total_pnl / len(filled_trades)) / np.std(pnls)
                if len(pnls) > 1 and np.std(pnls) != 0
                else 0.0
            )

            msg = (
                f"Metrics for {symbol}: "
                f"Win Rate={win_rate:.2%}, "
                f"P/L Ratio={pl_ratio:.2f}, "
                f"Total P&L=${total_pnl:.2f}, "
                f"Trades={len(filled_trades)}, "
                f"Sharpe Ratio={sharpe_ratio:.2f}"
            )
            logger.info(msg)
            await send_discord_message(msg, "info")

            async with aiofiles.open(self.metrics_file, "a", newline="") as f:
                await f.write(
                    ",".join(
                        [
                            datetime.now(timezone.utc).isoformat(),
                            symbol,
                            str(win_rate),
                            str(pl_ratio),
                            str(total_pnl),
                            str(len(filled_trades)),
                            str(sharpe_ratio),
                        ]
                    )
                    + "\n"
                )
        except Exception as e:
            logger.exception(f"Error computing metrics for {symbol}: {e}")
            await send_discord_message(
                f"Error computing metrics for {symbol}", "error"
            )

    async def is_market_open(self) -> bool:
        try:
            await self.rate_limiter.acquire()
            clock = self.trading_client.get_clock()
            return bool(getattr(clock, "is_open", False))
        except APIError as e:
            logger.error(f"API error checking market hours: {e}")
            await send_discord_message("API error checking market hours", "error")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error checking market hours: {e}")
            await send_discord_message(
                "Unexpected error checking market hours", "error"
            )
            return False

    async def get_market_price(self, symbol: str) -> Optional[float]:
        try:
            await self.rate_limiter.acquire()
            req = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quote = self.data_client.get_stock_latest_quote(req)
            if (
                isinstance(quote, dict)
                and symbol in quote
                and getattr(quote[symbol], "ask_price", None)
            ):
                return float(quote[symbol].ask_price)
        except APIError as e:
            logger.error(f"API error fetching market price for {symbol}: {e}")
            await send_discord_message(
                f"API error fetching market price for {symbol}", "error"
            )
        except Exception as e:
            logger.exception(f"Unexpected error fetching market price for {symbol}: {e}")
            await send_discord_message(
                f"Unexpected error fetching market price for {symbol}", "error"
            )
        return None

    async def fetch_bars(self, symbol: str, limit: int = 1000):
        try:
            await self.rate_limiter.acquire()
            start = datetime.now(timezone.utc) - timedelta(days=30)
            end = datetime.now(timezone.utc)
            req = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame(1, TimeFrameUnit.Hour),
                start=start.isoformat(),
                end=end.isoformat(),
                limit=limit,
            )
            resp = self.data_client.get_stock_bars(req)
            bars = resp.data.get(symbol, []) if hasattr(resp, "data") else resp.get(
                symbol, []
            )
            return bars
        except APIError as e:
            logger.error(f"API error fetching bars for {symbol}: {e}")
            await send_discord_message(
                f"API error fetching bars for {symbol}", "error"
            )
            return []
        except Exception as e:
            logger.exception(f"Unexpected error fetching bars for {symbol}: {e}")
            await send_discord_message(
                f"Unexpected error fetching bars for {symbol}", "error"
            )
            return []

    async def get_account_info(self) -> Dict[str, float]:
        try:
            await self.rate_limiter.acquire()
            account = self.trading_client.get_account()
            cash = float(getattr(account, "cash", 0.0) or 0.0)
            buying_power = float(getattr(account, "buying_power", 0.0) or 0.0)
            equity = float(getattr(account, "equity", 0.0) or 0.0)
            logger.info(
                f"Account info: cash={cash:.2f}, buying_power={buying_power:.2f}, equity={equity:.2f}"
            )
            return {"cash": cash, "buying_power": buying_power, "equity": equity}
        except APIError as e:
            logger.error(f"API error fetching account info: {e}")
            await send_discord_message(
                "API error fetching account info", "error"
            )
            return {"cash": 0.0, "buying_power": 0.0, "equity": 0.0}
        except Exception as e:
            logger.exception(f"Unexpected error fetching account info: {e}")
            await send_discord_message(
                "Unexpected error fetching account info", "error"
            )
            return {"cash": 0.0, "buying_power": 0.0, "equity": 0.0}

    async def log_open_orders(self, symbol: str):
        try:
            await self.rate_limiter.acquire()
            request = GetOrdersRequest(status="open", symbols=[symbol])
            orders = self.trading_client.get_orders(request)
            logger.info(f"Open orders for {symbol}: {len(orders)} found")
            for o in orders:
                logger.info(
                    f"Order ID: {o.id}, Type: {o.order_type}, Side: {o.side}, Status: {o.status}, Qty: {o.qty}"
                )
            await send_discord_message(
                f"Open orders for {symbol}: {len(orders)} found", "info"
            )
            return orders
        except Exception as e:
            logger.error(f"Error fetching open orders for {symbol}: {e}")
            await send_discord_message(
                f"Error fetching open orders for {symbol}: {e}", "error"
            )
            return []

    async def monitor_orders(self):
        while True:
            try:
                stream = TradingStream(
                    self.api_key, self.secret_key, paper=self.paper
                )

                async def handle_order_update(update):
                    order_id = getattr(update, "id", "unknown")
                    symbol = getattr(update, "symbol", "unknown")
                    status = str(getattr(update, "status", "")).lower()
                    qty = getattr(update, "qty", "unknown")
                    side = str(getattr(update, "side", "")).lower()
                    filled_price = getattr(update, "filled_avg_price", None)
                    reason = (
                        getattr(update, "rejected_reason", "none")
                        if status in {"rejected", "canceled"}
                        else ""
                    )
                    msg = (
                        f"Order update: {symbol} {side.upper()} qty={qty}, "
                        f"status={status}, reason={reason}"
                    )
                    if filled_price:
                        msg += f", filled_price={float(filled_price):.2f}"
                    logger.info(msg)
                    await send_discord_message(msg, "info")
                    if (
                        status
                        in {"filled", "canceled", "expired", "rejected"}
                        and order_id in self.submitted_order_ids
                    ):
                        self.submitted_order_ids.remove(order_id)
                        for trade in self.session_trades[symbol]:
                            if (
                                trade["status"] == "submitted"
                                and trade["qty"] == qty
                            ):
                                trade["status"] = status
                                trade["exit_price"] = (
                                    float(filled_price) if filled_price else None
                                )
                                async with aiofiles.open(
                                    self.csv_file, "a", newline=""
                                ) as f:
                                    await f.write(
                                        ",".join(
                                            [
                                                str(
                                                    v.isoformat()
                                                    if isinstance(v, datetime)
                                                    else v
                                                )
                                                for v in trade.values()
                                            ]
                                        )
                                        + "\n"
                                    )
                                if status == "filled":
                                    await self.compute_metrics_once(symbol)

                stream.subscribe_trade_updates(handle_order_update)
                await stream._run_forever()
            except Exception as e:
                logger.exception(f"WebSocket error: {e}")
                await send_discord_message(
                    f"WebSocket error in order monitoring: {str(e)}", "error"
                )
                await asyncio.sleep(5)

    async def cancel_stale_orders(self, symbol: str):
        try:
            await self.rate_limiter.acquire()
            request = GetOrdersRequest(status="open", symbols=[symbol])
            open_orders = self.trading_client.get_orders(request)
            if not open_orders:
                return
            for o in open_orders:
                if getattr(o, "symbol", None) == symbol:
                    submitted_at = getattr(o, "submitted_at", None)
                    try:
                        if isinstance(submitted_at, str):
                            submitted_at = datetime.fromisoformat(
                                submitted_at.replace("Z", "+00:00")
                            )
                        age = datetime.now(timezone.utc) - (
                            submitted_at or datetime.now(timezone.utc)
                        )
                        if age > timedelta(minutes=5):
                            self.trading_client.cancel_order_by_id(o.id)
                            msg = f"Canceled stale order {o.id} for {symbol}"
                            logger.info(msg)
                            await send_discord_message(msg, "warning")
                    except ValueError as e:
                        logger.error(
                            f"Error parsing submitted_at for order {o.id} of {symbol}: {e}"
                        )
                        await send_discord_message(
                            f"Error parsing order timestamp for {symbol}", "error"
                        )
        except APIError as e:
            logger.error(f"API error canceling stale orders for {symbol}: {e}")
            await send_discord_message(
                f"API error canceling stale orders for {symbol}", "error"
            )
        except Exception as e:
            logger.exception(
                f"Unexpected error canceling stale orders for {symbol}: {e}"
            )
            await send_discord_message(
                f"Unexpected error canceling stale orders for {symbol}", "error"
            )

    async def place_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        stop_loss: float,
        take_profit: float,
        trailing: Optional[float] = None,
    ):
        price = await self.get_market_price(symbol)
        if not price:
            msg = f"Cannot place order for {symbol}: price unavailable"
            logger.warning(msg)
            await send_discord_message(msg, "warning")
            return None
        try:
            logger.info(
                f"place_order params: symbol={symbol}, qty={qty}, side={side}, "
                f"stop_loss={stop_loss:.2f}, take_profit={take_profit:.2f}, "
                f"trailing={trailing}, enable_trailing={self.enable_trailing}"
            )

            if trailing:
                if stop_loss > 0 or take_profit > 0:
                    msg = (
                        f"Invalid trailing stop order for {symbol}: "
                        f"stop_loss and take_profit must be 0 when trailing is set"
                    )
                    logger.error(msg)
                    await send_discord_message(msg, "error")
                    return None
                order_class = OrderClass.TRAILING_STOP
                stop_loss_param = None
                take_profit_param = None
                trail_percent_param = trailing * 100
            elif stop_loss > 0 and take_profit > 0:
                order_class = OrderClass.BRACKET
                stop_loss_param = {"stop_price": round(stop_loss, 2)}
                take_profit_param = {"limit_price": round(take_profit, 2)}
                trail_percent_param = None
            else:
                order_class = OrderClass.SIMPLE
                stop_loss_param = None
                take_profit_param = None
                trail_percent_param = None

            logger.info(
                f"Submitting {side.upper()} {symbol} qty={qty} @ {price:.2f} "
                f"{'trail_percent=' + str(trail_percent_param) if trailing else f'stop={stop_loss:.2f} tp={take_profit:.2f}' if order_class == OrderClass.BRACKET else 'simple order'}"
            )
            order = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
                order_class=order_class,
                stop_loss=stop_loss_param,
                take_profit=take_profit_param,
                trail_percent=trail_percent_param,
            )
            resp = self.trading_client.submit_order(order)
            logger.info(f"Order response for {symbol}: {resp}")
            order_id = getattr(resp, "id", None)
            status = str(getattr(resp, "status", "")).lower()

            if status in {"rejected", "canceled", "expired"}:
                reason = getattr(resp, "rejected_reason", "Unknown")
                msg = (
                    f"Order not accepted for {symbol}: status={status}, reason={reason}"
                )
                logger.error(msg)
                await send_discord_message(msg, "error")
                return None

            if order_id:
                self.submitted_order_ids.append(order_id)
                trade_record = {
                    "timestamp": datetime.now(timezone.utc),
                    "symbol": symbol,
                    "side": side,
                    "qty": qty,
                    "entry_price": price,
                    "exit_price": None,
                    "stop_loss": stop_loss
                    if not trailing
                    else f"trail_{trailing * 100}%",
                    "take_profit": take_profit if not trailing else None,
                    "status": "submitted",
                }
                self.session_trades[symbol].append(trade_record)
                async with aiofiles.open(self.csv_file, "a", newline="") as f:
                    await f.write(
                        ",".join(
                            [
                                str(
                                    v.isoformat()
                                    if isinstance(v, datetime)
                                    else v
                                )
                                for v in trade_record.values()
                            ]
                        )
                        + "\n"
                    )

                msg = (
                    f"**Trade Executed**: {symbol} {side.upper()} qty={qty} @ {price:.2f} "
                )
                msg += (
                    f"trail={trailing * 100:.2f}%"
                    if trailing
                    else f"SL={stop_loss:.2f}, TP={take_profit:.2f}"
                    if order_class == OrderClass.BRACKET
                    else "simple order"
                )
                await send_discord_message(msg, "info")
            await asyncio.sleep(1)
            return resp
        except APIError as e:
            logger.error(f"API error placing order for {symbol}: {e}")
            await send_discord_message(
                f"API error placing order for {symbol}", "error"
            )
            return None
        except Exception as e:
            logger.exception(f"Unexpected error placing order for {symbol}: {e}")
            await send_discord_message(
                f"Unexpected error placing order for {symbol}", "error"
            )
            return None

    async def has_open_position_or_order(self, symbol: str) -> bool:
        try:
            await self.cancel_stale_orders(symbol)
            await self.log_open_orders(symbol)

            # Check positions FIRST - use list_positions instead of get_open_position
            await self.rate_limiter.acquire()
            positions = self.trading_client.get_all_positions()
            for pos in positions:
                if pos.symbol == symbol and float(pos.qty) != 0:
                    logger.info(f"Open position found for {symbol}: {pos.qty}")
                    return True

            # Check orders
            await self.rate_limiter.acquire()
            request = GetOrdersRequest(status="open", symbols=[symbol])
            open_orders = self.trading_client.get_orders(request)
            for o in open_orders:
                if o.symbol == symbol:
                    logger.info(f"Open order found for {symbol}: {o.id}")
                    return True

            logger.info(f"No positions or orders for {symbol}")
            return False

        except Exception as e:
            logger.exception(f"Error checking {symbol}: {e}")
            return False  # Don't block trading on errors

    async def compute_qty(self, symbol: str, price: float, is_short: bool) -> int:
        try:
            info = await self.get_account_info()
            bp = info["buying_power"]
            equity = info["equity"]
            max_exposure = equity * self.max_exposure_pct
            stop_distance = price * self.per_symbol_settings[symbol]["stop_loss_pct"]
            risk_amount = equity * self.risk_pct
            qty_risk = int(risk_amount / stop_distance) if stop_distance > 0 else 0
            cap = int(min(bp, max_exposure) // price)
            qty = max(1, min(qty_risk, cap))
            logger.info(
                f"compute_qty for {symbol}: qty_risk={qty_risk}, cap={cap}, qty={qty}"
            )
            return qty
        except Exception as e:
            logger.exception(f"Error computing quantity for {symbol}: {e}")
            await send_discord_message(
                f"Error computing quantity for {symbol}", "error"
            )
            return 0

    async def trade_symbol(self, symbol: str, interval_seconds: int = 300):
        while True:
            try:
                if not await self.is_market_open():
                    msg = f"Market is closed. Waiting {interval_seconds} seconds..."
                    logger.info(msg)
                    await send_discord_message(msg, "info")
                    await asyncio.sleep(interval_seconds)
                    continue

                try:
                    pos = self.trading_client.get_open_position(symbol)
                    if pos and float(pos.qty) != 0:
                        avg_entry = float(pos.avg_entry_price)
                        current_price = (
                            float(pos.current_price)
                            if hasattr(pos, "current_price") and pos.current_price is not None
                            else await self.get_market_price(symbol)
                        )
                        unrealized_plpc = (
                            float(pos.unrealized_plpc)
                            if hasattr(pos, "unrealized_plpc") and pos.unrealized_plpc is not None
                            else 0
                        )
                        qty = int(abs(float(pos.qty)))
                        settings = self.per_symbol_settings[symbol]
                        stop_loss_pct = settings["stop_loss_pct"]
                        take_profit_pct = settings["take_profit_pct"]
                        max_loss_pct = settings.get("max_loss_pct", self.default_max_loss_pct)

                        logger.info(
                            f"Monitoring {symbol} position: qty={qty}, entry={avg_entry:.2f}, "
                            f"current={current_price if current_price else 'N/A'}, plpc={unrealized_plpc*100:.2f}%, "
                            f"sl_pct={stop_loss_pct*100:.2f}%, tp_pct={take_profit_pct*100:.2f}%"
                        )

                        if current_price is None:
                            logger.warning(f"Cannot monitor {symbol}: price unavailable, skipping exit checks")
                        else:
                            # Check if bracket orders still exist. If not (expired DAY orders), actively manage exits.
                            await self.rate_limiter.acquire()
                            open_orders = self.trading_client.get_orders(
                                GetOrdersRequest(status="open", symbols=[symbol])
                            )
                            has_bracket = any(
                                o.order_class in (OrderClass.BRACKET, OrderClass.OTO)
                                for o in open_orders
                            )

                            if not has_bracket:
                                logger.info(f"No active bracket orders for {symbol} — managing exits client-side")

                                if pos.side == "long":
                                    gain_pct = (current_price - avg_entry) / avg_entry
                                else:
                                    gain_pct = (avg_entry - current_price) / avg_entry

                                if gain_pct >= take_profit_pct:
                                    side = "sell" if pos.side == "long" else "buy"
                                    await self.place_order(symbol, qty, side, 0, 0)
                                    msg = (
                                        f"Take Profit hit for {symbol}: gain={gain_pct*100:.2f}% "
                                        f"(target: {take_profit_pct*100:.2f}%), closing {pos.side}"
                                    )
                                    logger.info(msg)
                                    await send_discord_message(msg, "info")
                                elif gain_pct <= -stop_loss_pct:
                                    side = "sell" if pos.side == "long" else "buy"
                                    await self.place_order(symbol, qty, side, 0, 0)
                                    msg = (
                                        f"Stop Loss hit for {symbol}: loss={gain_pct*100:.2f}% "
                                        f"(threshold: {stop_loss_pct*100:.2f}%), closing {pos.side}"
                                    )
                                    logger.info(msg)
                                    await send_discord_message(msg, "warning")
                                elif gain_pct < -max_loss_pct:
                                    side = "sell" if pos.side == "long" else "buy"
                                    await self.place_order(symbol, qty, side, 0, 0)
                                    msg = (
                                        f"Max loss exceeded for {symbol}: loss={gain_pct*100:.2f}% "
                                        f"(threshold: {max_loss_pct*100:.2f}%), closing {pos.side}"
                                    )
                                    logger.info(msg)
                                    await send_discord_message(msg, "warning")

                        # Holding period check
                        entry_time = getattr(pos, "created_at", None)
                        if entry_time:
                            if isinstance(entry_time, str):
                                entry_time = datetime.fromisoformat(
                                    entry_time.replace("Z", "+00:00")
                                )
                            logger.info(f"{symbol} position entry time: {entry_time}")
                            if (
                                datetime.now(timezone.utc) - entry_time
                                > timedelta(days=self.max_holding_period)
                            ):
                                side = "sell" if float(pos.qty) > 0 else "buy"
                                await self.place_order(
                                    symbol, int(abs(float(pos.qty))), side, 0, 0
                                )
                                msg = (
                                    f"Max holding period exceeded for {symbol}, closing position."
                                )
                                logger.info(msg)
                                await send_discord_message(msg, "warning")
                except APIError as e:
                    if "position does not exist" not in str(e).lower():
                        logger.error(
                            f"API error enforcing max holding or loss check for {symbol}: {e}"
                        )
                        await send_discord_message(
                            f"API error enforcing max holding or loss check for {symbol}",
                            "error",
                        )
                except Exception as e:
                    logger.exception(
                        f"Unexpected error enforcing max holding or loss check for {symbol}: {e}"
                    )
                    await send_discord_message(
                        f"Unexpected error enforcing max holding or loss check for {symbol}",
                        "error",
                    )

                bars = await self.fetch_bars(
                    symbol,
                    limit=self.sma_period
                    + self.per_symbol_settings[symbol]["rsi_period"]
                    + 1,
                )
                needed = (
                    self.sma_period
                    + self.per_symbol_settings[symbol]["rsi_period"]
                )
                if len(bars) < needed:
                    msg = f"Not enough bars for {symbol}. Waiting..."
                    logger.warning(msg)
                    await send_discord_message(msg, "warning")
                    await asyncio.sleep(interval_seconds)
                    continue

                closes = np.array([b.close for b in bars])
                sma = np.mean(closes[-self.sma_period:])
                diffs = np.diff(
                    closes[
                        -(
                            self.per_symbol_settings[symbol]["rsi_period"]
                            + 1
                        ) :
                    ]
                )
                gains = np.where(diffs > 0, diffs, 0)
                losses_arr = np.where(diffs < 0, -diffs, 0)
                avg_gain = np.mean(gains)
                avg_loss = np.mean(losses_arr)
                rs = avg_gain / avg_loss if avg_loss != 0 else float("inf")
                rsi = (
                    100 - (100 / (1 + rs))
                    if rs != float("inf")
                    else 100
                )
                price = await self.get_market_price(symbol)
                if not price:
                    msg = f"Cannot proceed for {symbol}: price unavailable"
                    logger.warning(msg)
                    await send_discord_message(msg, "warning")
                    await asyncio.sleep(interval_seconds)
                    continue

                info = await self.get_account_info()
                msg = (
                    f"{symbol}: price={price:.2f} SMA={sma:.2f} RSI={rsi:.1f} "
                    f"cash={info['cash']:.2f} bp={info['buying_power']:.2f}"
                )
                logger.info(msg)
                await send_discord_message(msg, "info")

                if await self.has_open_position_or_order(symbol):
                    msg = (
                        f"Skipping new entry for {symbol}: open position or pending order exists"
                    )
                    logger.info(msg)
                    await send_discord_message(msg, "info")
                    await asyncio.sleep(interval_seconds)
                    continue

                settings = self.per_symbol_settings[symbol]
                rsi_buy_threshold = settings["rsi_buy_threshold"]
                rsi_sell_threshold = settings["rsi_sell_threshold"]
                stop_loss_pct = settings["stop_loss_pct"]
                take_profit_pct = settings["take_profit_pct"]

                logger.info(
                    f"Trade evaluation for {symbol}: rsi={rsi:.1f}, "
                    f"buy_threshold={rsi_buy_threshold}, sell_threshold={rsi_sell_threshold}, "
                    f"enable_trailing={self.enable_trailing}"
                )

                if rsi < rsi_buy_threshold:
                    qty = await self.compute_qty(symbol, price, is_short=False)
                    stop_price = (
                        price * (1 - stop_loss_pct)
                        if not self.enable_trailing
                        else 0
                    )
                    take_price = (
                        price * (1 + take_profit_pct)
                        if not self.enable_trailing
                        else 0
                    )
                    logger.info(
                        f"Buy order for {symbol}: qty={qty}, stop_price={stop_price:.2f}, "
                        f"take_price={take_price:.2f}"
                    )
                    if (
                        not self.enable_trailing
                        and (stop_price <= 0 or take_price <= price)
                    ):
                        msg = (
                            f"Invalid buy order prices for {symbol}: "
                            f"stop={stop_price:.2f}, take={take_price:.2f}"
                        )
                        logger.warning(msg)
                        await send_discord_message(msg, "warning")
                    else:
                        await self.place_order(
                            symbol,
                            qty,
                            "buy",
                            stop_price,
                            take_price,
                            trailing=stop_loss_pct if self.enable_trailing else None,
                        )
                elif rsi > rsi_sell_threshold:
                    qty = await self.compute_qty(symbol, price, is_short=True)
                    stop_price = (
                        price * (1 + stop_loss_pct)
                        if not self.enable_trailing
                        else 0
                    )
                    take_price = (
                        price * (1 - take_profit_pct)
                        if not self.enable_trailing
                        else 0
                    )
                    logger.info(
                        f"Sell order for {symbol}: qty={qty}, stop_price={stop_price:.2f}, "
                        f"take_price={take_price:.2f}"
                    )
                    if (
                        not self.enable_trailing
                        and (stop_price < price + 0.01 or take_price >= price)
                    ):
                        msg = (
                            f"Invalid sell order prices for {symbol}: "
                            f"stop={stop_price:.2f}, take={take_price:.2f}"
                        )
                        logger.warning(msg)
                        await send_discord_message(msg, "warning")
                    else:
                        await self.place_order(
                            symbol,
                            qty,
                            "sell",
                            stop_price,
                            take_price,
                            trailing=stop_loss_pct if self.enable_trailing else None,
                        )
                else:
                    msg = (
                        f"No trade for {symbol}: RSI={rsi:.1f} not below "
                        f"{rsi_buy_threshold} or above {rsi_sell_threshold}"
                    )
                    logger.info(msg)
                    await send_discord_message(msg, "info")

                await asyncio.sleep(interval_seconds)
            except Exception as e:
                logger.exception(f"Error in trading loop for {symbol}: {e}")
                await send_discord_message(
                    f"Error in trading loop for {symbol}", "error"
                )
                await asyncio.sleep(interval_seconds)


async def main():
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(BASE_DIR, "config6.json")

        with open(config_path) as f:
            config = json.load(f)

        if not all(k in config for k in ["symbols", "paper"]):
            logger.error("Invalid config: missing required keys")
            return

    except FileNotFoundError:
        logger.error(f"{config_path} not found")
        return
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in {config_path}")
        return

    API_KEY = os.getenv("APCA_API_KEY_ID", config.get("APCA_API_KEY_ID"))
    SECRET_KEY = os.getenv("APCA_API_SECRET_KEY", config.get("APCA_API_SECRET_KEY"))

    if not API_KEY or not SECRET_KEY:
        logger.error("API key or secret key missing")
        return

    # Test Discord on startup
    await send_discord_message("Bot starting up ✅", "info")

    SYMBOLS = config.get("symbols", ["AAPL"])
    PAPER = config.get("paper", True)

    bot = NextGenTradingBot(
        API_KEY,
        SECRET_KEY,
        symbols=SYMBOLS,
        paper=PAPER,
        max_exposure_pct=config.get("max_exposure_pct", 0.1),
        sma_period=config.get("sma_period", 20),
        risk_pct=config.get("risk_pct", 0.01),
        max_holding_period=config.get("max_holding_period", 5),
        enable_trailing=config.get("enable_trailing", False),
        max_loss_pct=config.get("max_loss_pct", 0.05),
        per_symbol_settings=config.get("per_symbol_settings", {}),
    )

    tasks = [
        bot.trade_symbol(sym, interval_seconds=config.get("interval_seconds", 300))
        for sym in SYMBOLS
    ]

    tasks.append(bot.monitor_orders())
    tasks.append(
        bot.compute_metrics(
            interval_seconds=config.get("metrics_interval_seconds", 1800)
        )
    )
    tasks.append(_discord_sender())

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually.")
