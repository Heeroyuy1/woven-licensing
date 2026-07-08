"""AI Analysis Engine — Intelligent recommendations based on backtest results."""
import logging
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from datetime import datetime

logger = logging.getLogger("Stratum.AI")


class AIAnalysis:
    """
    Analyzes backtest results and generates intelligent recommendations.
    Answers questions like:
    - Best symbols for this strategy
    - Poor-performing / volatile / stable symbols
    - Recommended watchlist
    - Suggested risk levels, stop-loss, take-profit, RSI settings
    - Overall confidence score
    """

    RECOMMENDATION_TRADE = "Recommended to Trade"
    RECOMMENDATION_CAUTION = "Trade with Caution"
    RECOMMENDATION_AVOID = "Avoid Trading"

    def __init__(self):
        self.results: Dict[str, Dict] = {}
        self.symbol_ratings: Dict[str, Dict] = {}

    def analyze(self, results: Dict[str, Dict]) -> Dict:
        """Run full AI analysis on backtest results."""
        self.results = results
        self.symbol_ratings = {}

        for sym, result in results.items():
            if "performance" not in result:
                continue
            self._rate_symbol(sym, result)

        return {
            "symbol_ratings": self.symbol_ratings,
            "rankings": self._generate_rankings(),
            "recommendations": self._generate_recommendations(),
            "watchlist": self._generate_watchlist(),
            "suggested_params": self._suggest_params(),
            "summary": self._generate_summary(),
            "generated_at": datetime.now().isoformat(),
        }

    def _rate_symbol(self, symbol: str, result: Dict) -> Dict:
        """Rate a single symbol on multiple dimensions (0-100 scale)."""
        perf = result["performance"]
        trades = result.get("trades", [])

        # Profitability score
        ret = perf.get("total_return_pct", 0)
        if ret > 100:
            profit_score = 100
        elif ret > 50:
            profit_score = 90
        elif ret > 20:
            profit_score = 75
        elif ret > 0:
            profit_score = 60
        elif ret > -20:
            profit_score = 30
        elif ret > -50:
            profit_score = 15
        else:
            profit_score = 0

        # Risk score (inverse of drawdown)
        dd = perf.get("max_drawdown_pct", 100)
        if dd < 5:
            risk_score = 95
        elif dd < 10:
            risk_score = 85
        elif dd < 20:
            risk_score = 70
        elif dd < 30:
            risk_score = 50
        elif dd < 50:
            risk_score = 30
        else:
            risk_score = 10

        # Consistency score (Sharpe)
        sharpe = perf.get("sharpe_ratio", 0)
        if sharpe > 2:
            consistency_score = 95
        elif sharpe > 1.5:
            consistency_score = 85
        elif sharpe > 1.0:
            consistency_score = 70
        elif sharpe > 0.5:
            consistency_score = 55
        elif sharpe > 0:
            consistency_score = 40
        else:
            consistency_score = 15

        # Win rate score
        wr = perf.get("win_rate", 0)
        win_rate_score = min(100, wr)

        # Trade frequency
        n_trades = perf.get("total_trades", 0)
        if n_trades >= 50:
            freq_score = 90
        elif n_trades >= 20:
            freq_score = 70
        elif n_trades >= 10:
            freq_score = 50
        elif n_trades >= 5:
            freq_score = 30
        else:
            freq_score = 10

        # Volatility (P&L std deviation)
        pnls = [t.get("pnl", 0) for t in trades]
        if pnls and len(pnls) > 1:
            vol = float(np.std(pnls))
            avg_abs_pnl = float(np.mean([abs(p) for p in pnls]))
            vol_ratio = vol / avg_abs_pnl if avg_abs_pnl > 0 else 0
            if vol_ratio < 0.5:
                volatility = "Low"
                vol_score = 85
            elif vol_ratio < 1.0:
                volatility = "Moderate"
                vol_score = 60
            elif vol_ratio < 2.0:
                volatility = "High"
                vol_score = 35
            else:
                volatility = "Extreme"
                vol_score = 10
        else:
            volatility = "Unknown"
            vol_score = 50

        # Overall confidence (weighted average)
        weights = {"profit": 0.30, "risk": 0.20, "consistency": 0.20, "win_rate": 0.15, "frequency": 0.15}
        overall = (
            profit_score * weights["profit"]
            + risk_score * weights["risk"]
            + consistency_score * weights["consistency"]
            + win_rate_score * weights["win_rate"]
            + freq_score * weights["frequency"]
        )

        # Recommendation
        if overall >= 70:
            recommendation = self.RECOMMENDATION_TRADE
        elif overall >= 45:
            recommendation = self.RECOMMENDATION_CAUTION
        else:
            recommendation = self.RECOMMENDATION_AVOID

        rating = {
            "symbol": symbol,
            "overall_score": round(overall, 1),
            "profitability_score": round(profit_score, 1),
            "risk_score": round(risk_score, 1),
            "consistency_score": round(consistency_score, 1),
            "win_rate_score": round(win_rate_score, 1),
            "frequency_score": round(freq_score, 1),
            "volatility": volatility,
            "volatility_score": round(vol_score, 1),
            "recommendation": recommendation,
            "total_return_pct": perf.get("total_return_pct", 0),
            "sharpe_ratio": perf.get("sharpe_ratio", 0),
            "max_drawdown_pct": perf.get("max_drawdown_pct", 0),
            "win_rate": perf.get("win_rate", 0),
            "total_trades": perf.get("total_trades", 0),
            "total_pnl": perf.get("total_realized_pnl", 0),
        }
        self.symbol_ratings[symbol] = rating
        return rating

    def _generate_rankings(self) -> Dict:
        """Generate best/worst symbol rankings."""
        ratings = list(self.symbol_ratings.values())
        if not ratings:
            return {}

        sorted_by_score = sorted(ratings, key=lambda r: r["overall_score"], reverse=True)
        sorted_by_return = sorted(ratings, key=lambda r: r["total_return_pct"], reverse=True)
        sorted_by_sharpe = sorted(ratings, key=lambda r: r["sharpe_ratio"], reverse=True)
        sorted_by_dd = sorted(ratings, key=lambda r: r["max_drawdown_pct"])
        sorted_by_vol = sorted(ratings, key=lambda r: r.get("volatility_score", 50))

        return {
            "best_overall": [r["symbol"] for r in sorted_by_score[:3]],
            "worst_overall": [r["symbol"] for r in sorted_by_score[-3:]],
            "best_return": [r["symbol"] for r in sorted_by_return[:3]],
            "best_sharpe": [r["symbol"] for r in sorted_by_sharpe[:3]],
            "lowest_drawdown": [r["symbol"] for r in sorted_by_dd[:3]],
            "most_stable": [r["symbol"] for r in sorted_by_vol[-3:]] if sorted_by_vol else [],
            "most_volatile": [r["symbol"] for r in sorted_by_vol[:3]] if sorted_by_vol else [],
        }

    def _generate_recommendations(self) -> Dict:
        """Generate categorized trade recommendations."""
        ratings = list(self.symbol_ratings.values())
        if not ratings:
            return {}

        return {
            "recommended_to_trade": [
                r for r in ratings if r["recommendation"] == self.RECOMMENDATION_TRADE
            ],
            "trade_with_caution": [
                r for r in ratings if r["recommendation"] == self.RECOMMENDATION_CAUTION
            ],
            "avoid_trading": [
                r for r in ratings if r["recommendation"] == self.RECOMMENDATION_AVOID
            ],
        }

    def _generate_watchlist(self) -> List[str]:
        """Generate a recommended watchlist of top symbols."""
        ratings = list(self.symbol_ratings.values())
        if not ratings:
            return []
        sorted_scores = sorted(ratings, key=lambda r: r["overall_score"], reverse=True)
        return [r["symbol"] for r in sorted_scores[:10] if r["overall_score"] >= 50]

    def _suggest_params(self) -> Dict:
        """Suggest optimized parameter values based on results."""
        ratings = list(self.symbol_ratings.values())
        if not ratings:
            return {}

        # Simple heuristic suggestions
        winning_symbols = [r for r in ratings if r["total_return_pct"] > 0]
        losing_symbols = [r for r in ratings if r["total_return_pct"] <= 0]

        suggestions = {}

        # General confidence
        win_ratio = len(winning_symbols) / len(ratings) if ratings else 0
        if win_ratio >= 0.7:
            suggestions["confidence"] = "High — strategy performs well on most symbols"
        elif win_ratio >= 0.4:
            suggestions["confidence"] = "Moderate — strategy selective, test on your symbols"
        else:
            suggestions["confidence"] = "Low — strategy underperforms on many symbols"
        suggestions["profitable_symbol_ratio"] = f"{win_ratio:.0%}"

        # For each symbol, best params are handled by the optimizer.
        # AI-level suggestions about overall strategy:
        avg_sharpe = np.mean([r["sharpe_ratio"] for r in ratings]) if ratings else 0
        if avg_sharpe > 1.0:
            suggestions["risk_assessment"] = "Strategy shows strong risk-adjusted returns"
        elif avg_sharpe > 0.5:
            suggestions["risk_assessment"] = "Strategy shows adequate risk-adjusted returns"
        else:
            suggestions["risk_assessment"] = "Strategy may need tighter risk controls"

        suggestions["analysis_summary"] = {
            "total_symbols_analyzed": len(ratings),
            "profitable_symbols": len(winning_symbols),
            "losing_symbols": len(losing_symbols),
            "avg_return_across_symbols": round(np.mean([r["total_return_pct"] for r in ratings]), 2) if ratings else 0,
            "avg_sharpe_across_symbols": round(avg_sharpe, 2),
            "avg_max_drawdown": round(np.mean([r["max_drawdown_pct"] for r in ratings]), 2) if ratings else 0,
        }

        return suggestions

    def _generate_summary(self) -> str:
        """Generate a human-readable summary of the analysis."""
        ratings = list(self.symbol_ratings.values())
        if not ratings:
            return "No data available for AI analysis."

        profitable = sum(1 for r in ratings if r["total_return_pct"] > 0)
        total = len(ratings)
        best = max(ratings, key=lambda r: r["overall_score"])
        worst = min(ratings, key=lambda r: r["overall_score"])

        return (
            f"Analyzed {total} symbols. "
            f"Strategy performed well on {profitable}/{total} symbols ({profitable/total*100:.0f}% win rate across symbols). "
            f"Best performer: {best['symbol']} (score: {best['overall_score']:.0f}/100, return: {best['total_return_pct']:+.2f}%). "
            f"Worst performer: {worst['symbol']} (score: {worst['overall_score']:.0f}/100, return: {worst['total_return_pct']:+.2f}%). "
        )

    def get_symbol_rating(self, symbol: str) -> Optional[Dict]:
        """Get AI rating for a specific symbol."""
        return self.symbol_ratings.get(symbol)
