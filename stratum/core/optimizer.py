"""Parameter Optimizer — Grid search for optimal strategy parameters."""
import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from itertools import product
from datetime import datetime
import numpy as np
import pandas as pd
import json

from .config_manager import ConfigManager, StrategyParams

logger = logging.getLogger("Stratum.Optimizer")


@dataclass
class OptimizationResult:
    params: Dict[str, Any]
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int
    total_pnl: float
    score: float


class Optimizer:
    """
    Grid search optimizer for strategy parameters.
    Uses composite scoring: Sharpe * (1 + return/100) * (1 - max_dd/100).
    """

    def __init__(self, config: ConfigManager):
        self.config = config

    def _score(self, perf: Dict, metric: str = "composite") -> float:
        sharpe = perf.get("sharpe_ratio", 0)
        ret = perf.get("total_return_pct", 0)
        dd = perf.get("max_drawdown_pct", 100)
        wr = perf.get("win_rate", 0) / 100

        if metric == "sharpe":
            return sharpe
        elif metric == "return":
            return ret
        elif metric == "win_rate":
            return wr
        elif metric == "profit_factor":
            return perf.get("pl_ratio", 0)
        else:  # composite
            return sharpe * (1 + ret / 100) * (1 - dd / 100)

    def optimize(
        self,
        engine_callable: Callable[[str, StrategyParams], Dict],
        symbol: str,
        param_grid: Optional[Dict[str, List]] = None,
        scoring_metric: str = "composite",
        maximize: bool = True,
    ) -> List[OptimizationResult]:
        """Run grid search for a symbol."""
        if param_grid is None:
            param_grid = self.config.config.get("optimization", {}).get("param_grid", {})
        scoring_metric = self.config.config.get("optimization", {}).get("scoring_metric", scoring_metric)

        # Build all combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        total = 1
        for vals in param_values:
            total *= len(vals)

        logger.info(f"Optimizing {symbol}: {total} combinations across {param_names}")
        results = []
        completed = 0

        for combo in product(*param_values):
            params_dict = dict(zip(param_names, combo))
            # Map grid param names to StrategyParams (new instance each iteration)
            sp = StrategyParams()
            for key, val in params_dict.items():
                if hasattr(sp, key):
                    setattr(sp, key, val)

            try:
                result = engine_callable(symbol, sp)
                if "error" in result:
                    completed += 1
                    continue
                perf = result.get("performance", {})
                score = self._score(perf, scoring_metric)

                results.append(OptimizationResult(
                    params=params_dict,
                    total_return_pct=perf.get("total_return_pct", 0),
                    sharpe_ratio=perf.get("sharpe_ratio", 0),
                    max_drawdown_pct=perf.get("max_drawdown_pct", 100),
                    win_rate=perf.get("win_rate", 0),
                    total_trades=perf.get("total_trades", 0),
                    total_pnl=perf.get("total_realized_pnl", 0),
                    score=score,
                ))
            except Exception as e:
                logger.debug(f"Combination failed: {params_dict}: {e}")

            completed += 1
            if completed % 10 == 0:
                logger.info(f"  Progress: {completed}/{total}")

        results.sort(key=lambda r: r.score, reverse=maximize)
        logger.info(f"Optimization complete for {symbol}: best score={results[0].score if results else 'N/A'}")
        return results

    def to_dataframe(self, results: List[OptimizationResult]) -> pd.DataFrame:
        rows = [{
            **r.params,
            "score": round(r.score, 3),
            "sharpe": round(r.sharpe_ratio, 3),
            "return_pct": round(r.total_return_pct, 2),
            "max_dd_pct": round(r.max_drawdown_pct, 2),
            "win_rate": round(r.win_rate, 2),
            "trades": r.total_trades,
            "total_pnl": round(r.total_pnl, 2),
        } for r in results]
        return pd.DataFrame(rows)

    def find_best_params(self, results: List[OptimizationResult]) -> Optional[Dict]:
        if not results:
            return None
        best = results[0]
        return {
            "params": best.params,
            "score": best.score,
            "sharpe": best.sharpe_ratio,
            "return_pct": best.total_return_pct,
            "max_dd_pct": best.max_drawdown_pct,
            "win_rate": best.win_rate,
            "trades": best.total_trades,
        }
