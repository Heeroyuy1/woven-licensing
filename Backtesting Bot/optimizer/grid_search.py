"""
Strategy Parameter Optimizer — Grid search across parameter combinations
to find the best risk-adjusted returns.
"""
import logging
from typing import Dict, List, Any, Callable, Optional, Tuple
from dataclasses import dataclass, field
from itertools import product
from datetime import datetime
import pandas as pd
import numpy as np
import json

logger = logging.getLogger("Harper.Optimizer")


@dataclass
class OptimizationResult:
    """Single parameter combination result."""
    params: Dict[str, Any]
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int
    total_pnl: float
    score: float  # Composite score (higher = better)


@dataclass
class OptimizationRun:
    """Complete optimization run summary."""
    symbol: str
    strategy_name: str
    total_combinations: int
    completed: int
    best_result: Optional[OptimizationResult]
    all_results: List[OptimizationResult]
    run_time_seconds: float
    started_at: str
    param_grid: Dict[str, List]


class GridSearchOptimizer:
    """
    Runs backtests across all combinations of strategy parameters.
    Uses a composite scoring function: Sharpe * (1 + return_pct/100) * (1 - max_dd/100)
    """

    def __init__(self, scoring_metric: str = "composite"):
        """
        Args:
            scoring_metric: 'sharpe', 'return', 'composite', or 'win_rate'
        """
        self.scoring_metric = scoring_metric

    def _score(self, result: Dict) -> float:
        """Compute composite score from performance metrics."""
        perf = result.get("performance", {})
        sharpe = perf.get("sharpe_ratio", 0)
        total_return = perf.get("total_return_pct", 0)
        max_dd = perf.get("max_drawdown_pct", 100)
        win_rate = perf.get("win_rate", 0) / 100

        if self.scoring_metric == "sharpe":
            return sharpe
        elif self.scoring_metric == "return":
            return total_return
        elif self.scoring_metric == "win_rate":
            return win_rate
        else:  # composite
            # Reward high Sharpe and returns, penalize drawdown
            return sharpe * (1 + total_return / 100) * (1 - max_dd / 100)

    def optimize(
        self,
        param_grid: Dict[str, List],
        run_backtest_fn: Callable[[Dict], Dict],
        symbol: str,
        maximize: bool = True,
    ) -> OptimizationRun:
        """
        Run grid search optimization.

        Args:
            param_grid: Dict of param_name -> list of values to test
            run_backtest_fn: Function(params_dict) -> backtest_result_dict
            symbol: Stock ticker for context
            maximize: True = higher score is better

        Returns:
            OptimizationRun with all results
        """
        start_time = datetime.now()
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        total = 1
        for vals in param_values:
            total *= len(vals)

        logger.info(
            f"Starting grid search for {symbol}: "
            f"{total} combinations across {param_names}"
        )

        all_results = []
        completed = 0

        for combo in product(*param_values):
            params = dict(zip(param_names, combo))
            try:
                result = run_backtest_fn(params)
                if "error" in result:
                    logger.warning(f"Params {params} failed: {result['error']}")
                    completed += 1
                    continue

                perf = result.get("performance", {})
                score = self._score(result)

                opt_result = OptimizationResult(
                    params=params,
                    total_return_pct=perf.get("total_return_pct", 0),
                    sharpe_ratio=perf.get("sharpe_ratio", 0),
                    max_drawdown_pct=perf.get("max_drawdown_pct", 100),
                    win_rate=perf.get("win_rate", 0),
                    total_trades=perf.get("total_trades", 0),
                    total_pnl=perf.get("total_realized_pnl", 0),
                    score=score,
                )
                all_results.append(opt_result)

            except Exception as e:
                logger.exception(f"Backtest failed for params {params}: {e}")

            completed += 1
            if completed % 10 == 0:
                logger.info(f"  Progress: {completed}/{total}")

        elapsed = (datetime.now() - start_time).total_seconds()
        all_results.sort(key=lambda r: r.score, reverse=maximize)
        best = all_results[0] if all_results else None

        logger.info(
            f"Optimization complete for {symbol}: {len(all_results)}/{total} successful, "
            f"{elapsed:.1f}s. Best score: {best.score if best else 'N/A'}"
        )

        return OptimizationRun(
            symbol=symbol,
            strategy_name="RSI_SMA",
            total_combinations=total,
            completed=len(all_results),
            best_result=best,
            all_results=all_results,
            run_time_seconds=elapsed,
            started_at=start_time.isoformat(),
            param_grid=param_grid,
        )

    def optimize_multi_symbol(
        self,
        param_grid: Dict[str, List],
        run_backtest_fn: Callable[[str, Dict], Dict],
        symbols: List[str],
    ) -> Dict[str, OptimizationRun]:
        """Run grid search across multiple symbols."""
        results = {}
        for sym in symbols:
            logger.info(f"--- Optimizing {sym} ---")
            # Wrap to pass symbol through
            def wrapped(params):
                return run_backtest_fn(sym, params)

            results[sym] = self.optimize(param_grid, wrapped, sym)
        return results

    def to_dataframe(self, run: OptimizationRun) -> pd.DataFrame:
        """Convert optimization results to a DataFrame for analysis."""
        if not run.all_results:
            return pd.DataFrame()
        rows = [
            {
                **r.params,
                "score": round(r.score, 3),
                "sharpe": round(r.sharpe_ratio, 3),
                "return_pct": round(r.total_return_pct, 2),
                "max_dd_pct": round(r.max_drawdown_pct, 2),
                "win_rate": round(r.win_rate, 2),
                "trades": r.total_trades,
                "total_pnl": round(r.total_pnl, 2),
            }
            for r in run.all_results
        ]
        return pd.DataFrame(rows)

    def save_results(self, run: OptimizationRun, path: str):
        """Save optimization results to JSON."""
        output = {
            "symbol": run.symbol,
            "strategy": run.strategy_name,
            "total_combinations": run.total_combinations,
            "completed": run.completed,
            "run_time_seconds": run.run_time_seconds,
            "started_at": run.started_at,
            "param_grid": run.param_grid,
            "best": {
                "params": run.best_result.params,
                "score": run.best_result.score,
                "sharpe": run.best_result.sharpe_ratio,
                "return_pct": run.best_result.total_return_pct,
                "max_dd_pct": run.best_result.max_drawdown_pct,
                "win_rate": run.best_result.win_rate,
                "trades": run.best_result.total_trades,
                "total_pnl": run.best_result.total_pnl,
            } if run.best_result else None,
            "top_10": [
                {
                    "params": r.params,
                    "score": r.score,
                    "sharpe": r.sharpe_ratio,
                    "return_pct": r.total_return_pct,
                    "max_dd_pct": r.max_drawdown_pct,
                }
                for r in run.all_results[:10]
            ],
        }
        with open(path, "w") as f:
            json.dump(output, f, indent=2)
        logger.info(f"Optimization results saved to {path}")
