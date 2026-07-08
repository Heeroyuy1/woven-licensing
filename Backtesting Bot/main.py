"""
Historical Backtesting & Pattern Discovery System — Main Entry Point

Converts the TradingBackTestingLIVE live bot into a comprehensive
historical backtesting and market pattern analysis platform.

Usage:
    python main.py                          # Full backtest + pattern discovery
    python main.py --symbols AAPL,TSLA     # Specific symbols
    python main.py --start 2020-01-01      # Custom date range
    python main.py --optimize              # Run parameter optimization
    python main.py --patterns-only          # Only run pattern discovery
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Ensure the project root is on the Python path for proper imports
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd  # noqa: E402
import numpy as np  # noqa: E402

# Core modules
from core.data_loader import DataLoader  # noqa: E402
from core.paper_broker import PaperBroker  # noqa: E402
from core.strategy_runner import StrategyRunner  # noqa: E402

# Strategies
from strategies.rsi_sma_strategy import PerSymbolRSISMAStrategy  # noqa: E402

# Pattern discovery
from patterns.detector import PatternDetector, Pattern  # noqa: E402

# Optimizer
from optimizer.grid_search import GridSearchOptimizer  # noqa: E402

# Reporting
from reporting.dashboard import Dashboard  # noqa: E402

logger = logging.getLogger("Harper.Main")


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler()],
    )
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def load_config(config_path: str = "config/backtest_config.json") -> Dict:
    """Load backtest configuration from JSON file."""
    # Default config
    default_config = {
        "symbols": ["AAPL", "TSLA", "NVDA", "GOOGL"],
        "start_date": "2020-01-01",
        "end_date": "2025-12-31",
        "interval": "1d",
        "initial_capital": 100000,
        "sma_period": 20,
        "rsi_period": 14,
        "rsi_buy_threshold": 30,
        "rsi_sell_threshold": 70,
        "stop_loss_pct": 0.02,
        "take_profit_pct": 0.05,
        "max_loss_pct": 0.05,
        "max_holding_days": 5,
        "max_exposure_pct": 0.1,
        "risk_pct": 0.01,
        "commission_per_share": 0.0,
        "slippage_pct": 0.0005,
        "per_symbol_settings": {},
        "optimization": {
            "enabled": False,
            "param_grid": {
                "rsi_buy_threshold": [25, 28, 30, 33, 35],
                "rsi_sell_threshold": [65, 70, 72, 75, 78],
                "stop_loss_pct": [0.01, 0.015, 0.02, 0.025, 0.03],
                "take_profit_pct": [0.03, 0.04, 0.05, 0.06, 0.08],
            },
        },
    }

    if os.path.exists(config_path):
        with open(config_path) as f:
            user_config = json.load(f)
            # Deep merge
            for key, value in user_config.items():
                if key in default_config and isinstance(default_config[key], dict):
                    default_config[key].update(value)
                else:
                    default_config[key] = value
        logger.info(f"Loaded config from {config_path}")
    else:
        # Write default config
        os.makedirs(os.path.dirname(config_path) or ".", exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(default_config, f, indent=2)
        logger.info(f"Created default config at {config_path}")

    return default_config


async def run_backtest(config: Dict, symbols: Optional[List[str]] = None) -> Dict:
    """
    Run the full backtest: fetch data, execute strategy, log trades.

    Returns dict of symbol -> results.
    """
    if symbols is None:
        symbols = config["symbols"]

    logger.info(f"Starting backtest for {len(symbols)} symbols: {symbols}")
    logger.info(f"Date range: {config['start_date']} → {config['end_date']}")

    # 1. Load data
    loader = DataLoader(
        cache_dir="data",
        api_key=os.getenv("APCA_API_KEY_ID"),
        secret_key=os.getenv("APCA_API_SECRET_KEY"),
    )
    data = await loader.fetch_batch(
        symbols=symbols,
        start_date=config["start_date"],
        end_date=config["end_date"],
        interval=config["interval"],
    )

    if not data:
        logger.error("No data loaded. Check symbols and date range.")
        return {}

    for sym, df in data.items():
        logger.info(f"  {sym}: {len(df)} bars, {df.iloc[0]['timestamp']} → {df.iloc[-1]['timestamp']}")

    # 2. Initialize strategy
    strategy = PerSymbolRSISMAStrategy(
        symbols=symbols,
        default_sma_period=config.get("sma_period", 20),
        default_rsi_period=config.get("rsi_period", 14),
        default_rsi_buy=config.get("rsi_buy_threshold", 30),
        default_rsi_sell=config.get("rsi_sell_threshold", 70),
        per_symbol_settings=config.get("per_symbol_settings", {}),
    )

    # 3. Initialize broker
    broker = PaperBroker(
        initial_capital=config.get("initial_capital", 100_000),
        commission_per_share=config.get("commission_per_share", 0.0),
        slippage_pct=config.get("slippage_pct", 0.0005),
    )

    # 4. Run strategy
    runner = StrategyRunner(
        broker=broker,
        strategy=strategy,
        stop_loss_pct=config.get("stop_loss_pct", 0.02),
        take_profit_pct=config.get("take_profit_pct", 0.05),
        max_loss_pct=config.get("max_loss_pct", 0.05),
        max_holding_days=config.get("max_holding_days", 5),
        max_exposure_pct=config.get("max_exposure_pct", 0.1),
        risk_pct=config.get("risk_pct", 0.01),
        allow_shorts=config.get("allow_shorts", True),
        logs_dir="logs",
    )

    results = runner.run_batch(data)
    return results


async def run_pattern_discovery(config: Dict, results: Dict, symbols: Optional[List[str]] = None) -> List[Pattern]:
    """
    Run pattern detection on all symbols' historical data.
    Can be called standalone or after backtest results.
    """
    if symbols is None:
        symbols = config["symbols"]

    logger.info(f"Running pattern discovery for {len(symbols)} symbols...")

    loader = DataLoader(cache_dir="data")
    detector = PatternDetector(min_occurrences=5, significance_level=0.05)
    all_patterns: List[Pattern] = []

    # Use cached data if available, otherwise fetch
    cached_symbols = loader.load_cached_symbols()
    symbols_to_fetch = [s for s in symbols if s in cached_symbols]
    symbols_need_fetch = [s for s in symbols if s not in cached_symbols]

    if symbols_need_fetch:
        logger.info(f"Fetching data for {len(symbols_need_fetch)} uncached symbols: {symbols_need_fetch}")
        data = await loader.fetch_batch(
            symbols=symbols_need_fetch,
            start_date=config["start_date"],
            end_date=config["end_date"],
            interval="1d",
        )
    else:
        data = {}

    # Load cached symbols
    data.update(await loader.fetch_batch(
        symbols=symbols_to_fetch,
        start_date=config["start_date"],
        end_date=config["end_date"],
        interval="1d",
    ))

    for sym, df in data.items():
        if df.empty:
            logger.warning(f"No data for {sym}, skipping pattern detection")
            continue
        patterns = detector.discover_all(df, sym)
        all_patterns.extend(patterns)
        logger.info(f"  {sym}: {len(patterns)} patterns found")

    # Sort by confidence
    all_patterns.sort(key=lambda p: p.confidence_score, reverse=True)
    logger.info(f"Total patterns discovered: {len(all_patterns)}")
    return all_patterns


async def run_optimization(config: Dict, symbols: Optional[List[str]] = None) -> Dict:
    """
    Run parameter grid search optimization across symbols.
    """
    if symbols is None:
        symbols = config["symbols"]

    opt_config = config.get("optimization", {})
    if not opt_config.get("enabled", False):
        logger.info("Optimization disabled in config. Use --optimize flag or set enabled:true.")
        return {}

    param_grid = opt_config.get("param_grid", {
        "rsi_buy_threshold": [25, 28, 30, 33, 35],
        "rsi_sell_threshold": [65, 70, 72, 75, 78],
        "stop_loss_pct": [0.01, 0.015, 0.02, 0.025, 0.03],
        "take_profit_pct": [0.03, 0.04, 0.05, 0.06, 0.08],
    })

    logger.info(f"Starting optimization for {len(symbols)} symbols with {np.prod([len(v) for v in param_grid.values()])} combinations")

    optimizer = GridSearchOptimizer(scoring_metric="composite")

    # For each symbol, run grid search
    for sym in symbols:
        logger.info(f"\n{'='*40}\nOptimizing {sym}\n{'='*40}")

        def backtest_fn(params: Dict) -> Dict:
            """Quick single-symbol backtest with given params."""
            loader = DataLoader(cache_dir="data")
            broker = PaperBroker(
                initial_capital=config.get("initial_capital", 100000),
                commission_per_share=config.get("commission_per_share", 0),
                slippage_pct=config.get("slippage_pct", 0.0005),
            )

            strategy = PerSymbolRSISMAStrategy(
                symbols=[sym],
                default_sma_period=config.get("sma_period", 20),
                default_rsi_period=config.get("rsi_period", 14),
                default_rsi_buy=params.get("rsi_buy_threshold", 30),
                default_rsi_sell=params.get("rsi_sell_threshold", 70),
                per_symbol_settings={
                    sym: {
                        "rsi_buy_threshold": params.get("rsi_buy_threshold", 30),
                        "rsi_sell_threshold": params.get("rsi_sell_threshold", 70),
                        "stop_loss_pct": params.get("stop_loss_pct", 0.02),
                        "take_profit_pct": params.get("take_profit_pct", 0.05),
                        "rsi_period": config.get("rsi_period", 14),
                    }
                },
            )

            runner = StrategyRunner(
                broker=broker,
                strategy=strategy,
                stop_loss_pct=params.get("stop_loss_pct", 0.02),
                take_profit_pct=params.get("take_profit_pct", 0.05),
                max_loss_pct=config.get("max_loss_pct", 0.05),
                max_holding_days=config.get("max_holding_days", 5),
                max_exposure_pct=config.get("max_exposure_pct", 0.1),
                risk_pct=config.get("risk_pct", 0.01),
                logs_dir="logs",
            )

            # Need to run synchronously inside async context
            df = loader._fetch_yahoo(
                sym, config["start_date"], config["end_date"], config["interval"]
            )
            if df.empty:
                return {"error": "no_data"}

            return runner.run(sym, df)

        run_result = optimizer.optimize(
            param_grid=param_grid,
            run_backtest_fn=backtest_fn,
            symbol=sym,
        )

        optimizer.save_results(run_result, f"logs/optimization_{sym}.json")
        logger.info(f"Best params for {sym}: {run_result.best_result.params if run_result.best_result else 'N/A'}")

    return {}


async def main(args):
    """Main entry point."""
    # Change to project root so all relative paths (data/, logs/, reports/) resolve correctly
    os.chdir(str(PROJECT_ROOT))

    setup_logging(args.verbose)

    # Resolve config path relative to project root
    config_path = str(PROJECT_ROOT / args.config) if not os.path.isabs(args.config) else args.config
    config = load_config(config_path)

    # Override symbols from CLI
    symbols = None
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",")]

    # Override dates from CLI
    if args.start:
        config["start_date"] = args.start
    if args.end:
        config["end_date"] = args.end

    results = {}
    patterns = []
    optimization_results = {}

    # Run optimization
    if args.optimize:
        config["optimization"]["enabled"] = True
        optimization_results = await run_optimization(config, symbols)

    # Run pattern discovery
    if args.patterns_only:
        patterns = await run_pattern_discovery(config, results, symbols)
    else:
        # Full backtest + patterns
        results = await run_backtest(config, symbols)
        patterns = await run_pattern_discovery(config, results, symbols)

    # Generate reports
    dashboard = Dashboard(output_dir="reports")
    dashboard.print_console_summary(results, patterns)
    dashboard.export_json(results, patterns, "results.json")
    html_path = dashboard.generate_html_dashboard(
        results, patterns, optimization_results, "dashboard.html"
    )

    print(f"\n[Dashboard] {Path(html_path).resolve()}")
    print(f"[JSON]       {Path('reports/results.json').resolve()}")
    print(f"[Trade Logs] {Path('logs').resolve()}")
    print(f"\nHarper analysis complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Harper — Woven Model Market Intelligence Platform"
    )
    parser.add_argument(
        "--config", default="config/backtest_config.json",
        help="Path to config JSON"
    )
    parser.add_argument(
        "--symbols", type=str,
        help="Comma-separated list of symbols (e.g., AAPL,TSLA,NVDA)"
    )
    parser.add_argument(
        "--start", type=str,
        help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end", type=str,
        help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--optimize", action="store_true",
        help="Run parameter optimization"
    )
    parser.add_argument(
        "--patterns-only", action="store_true",
        help="Only run pattern discovery (skip backtest)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose logging"
    )

    args = parser.parse_args()
    asyncio.run(main(args))
