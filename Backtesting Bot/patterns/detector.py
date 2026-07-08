"""
Pattern Discovery Engine — Searches for statistically significant recurring
patterns in historical data: seasonal, day-of-week, volume spikes, and
technical indicator setups.
"""
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger("Harper.PatternDetector")


@dataclass
class Pattern:
    """A discovered recurring market pattern."""
    pattern_id: str
    pattern_type: str  # 'seasonal', 'day_of_week', 'volume_spike', 'technical_setup'
    symbol: str
    description: str
    occurrence_count: int
    total_opportunities: int
    win_rate: float  # 0.0 - 1.0
    avg_gain_pct: float
    avg_loss_pct: float
    probability_of_occurrence: float  # 0.0 - 1.0
    confidence_score: float  # 0.0 - 1.0
    p_value: Optional[float] = None  # Statistical significance
    direction: str = "any"  # 'bullish', 'bearish', 'any'
    metadata: Dict = field(default_factory=dict)
    discovered_at: str = field(default_factory=lambda: datetime.now().isoformat())


class PatternDetector:
    """
    Searches historical data for statistically significant recurring patterns.
    """

    def __init__(self, min_occurrences: int = 5, significance_level: float = 0.05):
        self.min_occurrences = min_occurrences
        self.significance_level = significance_level

    def discover_all(self, df: pd.DataFrame, symbol: str) -> List[Pattern]:
        """Run all pattern detectors on a single symbol's data."""
        patterns = []
        patterns.extend(self.detect_seasonal_monthly(df, symbol))
        patterns.extend(self.detect_day_of_week(df, symbol))
        patterns.extend(self.detect_volume_spikes(df, symbol))
        patterns.extend(self.detect_rsi_extremes(df, symbol))
        return sorted(patterns, key=lambda p: p.confidence_score, reverse=True)

    def detect_seasonal_monthly(self, df: pd.DataFrame, symbol: str) -> List[Pattern]:
        """
        Detect monthly seasonal patterns:
        - Does the stock consistently go up/down in specific months?
        - e.g., "AAPL declines in September 7 of last 10 years"
        """
        if df.empty:
            return []

        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df["month"] = df["timestamp"].dt.month
        df["year"] = df["timestamp"].dt.year

        # Calculate monthly returns
        monthly = df.groupby(["year", "month"]).agg(
            open_price=("open", "first"),
            close_price=("close", "last"),
        ).reset_index()
        monthly["return_pct"] = (
            (monthly["close_price"] - monthly["open_price"]) / monthly["open_price"]
        ) * 100

        patterns = []
        month_names = [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
        ]

        for month in range(1, 13):
            month_data = monthly[monthly["month"] == month]
            if len(month_data) < self.min_occurrences:
                continue

            n_total = len(month_data)
            n_positive = (month_data["return_pct"] > 0).sum()
            n_negative = (month_data["return_pct"] < 0).sum()
            avg_return = month_data["return_pct"].mean()
            std_return = month_data["return_pct"].std()

            # Binomial test: is the proportion of positive months significant?
            if n_positive > n_negative and n_total >= self.min_occurrences:
                p_val = stats.binomtest(n_positive, n_total, p=0.5, alternative="greater").pvalue
                if p_val < self.significance_level:
                    confidence = 1.0 - p_val
                    patterns.append(Pattern(
                        pattern_id=f"{symbol}_monthly_bullish_{month:02d}",
                        pattern_type="seasonal",
                        symbol=symbol,
                        description=(
                            f"{symbol} tends to rally in {month_names[month-1]}: "
                            f"positive in {n_positive}/{n_total} years "
                            f"(avg +{avg_return:.2f}%)"
                        ),
                        occurrence_count=n_positive,
                        total_opportunities=n_total,
                        win_rate=n_positive / n_total,
                        avg_gain_pct=month_data[month_data["return_pct"] > 0]["return_pct"].mean() if n_positive > 0 else 0,
                        avg_loss_pct=abs(month_data[month_data["return_pct"] < 0]["return_pct"].mean()) if n_negative > 0 else 0,
                        probability_of_occurrence=n_positive / n_total,
                        confidence_score=round(confidence, 3),
                        p_value=round(p_val, 4),
                        direction="bullish",
                        metadata={
                            "month": month,
                            "month_name": month_names[month - 1],
                            "avg_return_pct": round(avg_return, 2),
                            "std_return_pct": round(std_return, 2),
                        },
                    ))

            if n_negative > n_positive and n_total >= self.min_occurrences:
                p_val = stats.binomtest(n_negative, n_total, p=0.5, alternative="greater").pvalue
                if p_val < self.significance_level:
                    confidence = 1.0 - p_val
                    patterns.append(Pattern(
                        pattern_id=f"{symbol}_monthly_bearish_{month:02d}",
                        pattern_type="seasonal",
                        symbol=symbol,
                        description=(
                            f"{symbol} tends to decline in {month_names[month-1]}: "
                            f"negative in {n_negative}/{n_total} years "
                            f"(avg {avg_return:.2f}%)"
                        ),
                        occurrence_count=n_negative,
                        total_opportunities=n_total,
                        win_rate=n_negative / n_total,
                        avg_gain_pct=abs(month_data[month_data["return_pct"] < 0]["return_pct"].mean()) if n_negative > 0 else 0,
                        avg_loss_pct=month_data[month_data["return_pct"] > 0]["return_pct"].mean() if n_positive > 0 else 0,
                        probability_of_occurrence=n_negative / n_total,
                        confidence_score=round(confidence, 3),
                        p_value=round(p_val, 4),
                        direction="bearish",
                        metadata={
                            "month": month,
                            "month_name": month_names[month - 1],
                            "avg_return_pct": round(avg_return, 2),
                            "std_return_pct": round(std_return, 2),
                        },
                    ))

        return patterns

    def detect_day_of_week(self, df: pd.DataFrame, symbol: str) -> List[Pattern]:
        """
        Detect day-of-week effects.
        - e.g., "Mondays outperform Fridays"
        """
        if df.empty:
            return []

        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df["day_of_week"] = df["timestamp"].dt.dayofweek  # 0=Mon, 6=Sun
        df["daily_return"] = df["close"].pct_change() * 100

        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        patterns = []

        # Group by day of week
        dow_groups = df.groupby("day_of_week")["daily_return"]
        overall_mean = df["daily_return"].mean()

        for dow in range(5):  # Mon-Fri only
            day_data = dow_groups.get_group(dow).dropna()
            if len(day_data) < self.min_occurrences:
                continue

            n_total = len(day_data)
            n_positive = (day_data > 0).sum()
            n_negative = (day_data < 0).sum()
            avg_return = day_data.mean()

            # t-test: is this day's mean return significantly different from overall?
            if n_total >= self.min_occurrences:
                t_stat, p_val = stats.ttest_1samp(day_data, 0)
                if p_val < self.significance_level:
                    direction = "bullish" if avg_return > 0 else "bearish"
                    confidence = 1.0 - p_val
                    patterns.append(Pattern(
                        pattern_id=f"{symbol}_dow_{direction}_{dow}",
                        pattern_type="day_of_week",
                        symbol=symbol,
                        description=(
                            f"{symbol} {day_names[dow]}s: avg {direction} "
                            f"{avg_return:.2f}% (positive {n_positive}/{n_total} days)"
                        ),
                        occurrence_count=n_positive if direction == "bullish" else n_negative,
                        total_opportunities=n_total,
                        win_rate=(n_positive if direction == "bullish" else n_negative) / n_total,
                        avg_gain_pct=day_data[day_data > 0].mean() if n_positive > 0 else 0,
                        avg_loss_pct=abs(day_data[day_data < 0].mean()) if n_negative > 0 else 0,
                        probability_of_occurrence=(n_positive if direction == "bullish" else n_negative) / n_total,
                        confidence_score=round(confidence, 3),
                        p_value=round(p_val, 4),
                        direction=direction,
                        metadata={
                            "day_of_week": dow,
                            "day_name": day_names[dow],
                            "avg_return_pct": round(avg_return, 2),
                            "t_statistic": round(t_stat, 3),
                        },
                    ))

        return patterns

    def detect_volume_spikes(self, df: pd.DataFrame, symbol: str) -> List[Pattern]:
        """
        Detect volume spike patterns — unusually high volume days and their
        subsequent price behavior.
        """
        if df.empty or "volume" not in df.columns:
            return []

        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df["volume_ma"] = df["volume"].rolling(20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_ma"]
        df["volume_spike"] = df["volume_ratio"] > 2.0  # 2x average volume

        # Forward returns after spikes
        df["fwd_return_1d"] = df["close"].shift(-1) / df["close"] - 1
        df["fwd_return_5d"] = df["close"].shift(-5) / df["close"] - 1

        spike_days = df[df["volume_spike"]].dropna(subset=["fwd_return_1d"])
        if len(spike_days) < self.min_occurrences:
            return []

        n_total = len(spike_days)
        n_positive_1d = (spike_days["fwd_return_1d"] > 0).sum()
        n_positive_5d = (spike_days["fwd_return_5d"] > 0).sum()
        avg_1d = spike_days["fwd_return_1d"].mean() * 100
        avg_5d = spike_days["fwd_return_5d"].mean() * 100

        patterns = []

        # 1-day after spike
        direction_1d = "bullish" if avg_1d > 0 else "bearish"
        n_success_1d = n_positive_1d if direction_1d == "bullish" else n_total - n_positive_1d
        patterns.append(Pattern(
            pattern_id=f"{symbol}_volspike_1d",
            pattern_type="volume_spike",
            symbol=symbol,
            description=(
                f"{symbol} volume spikes (>2x avg): next day avg "
                f"{avg_1d:.2f}% ({direction_1d}), "
                f"{n_success_1d}/{n_total} follow direction"
            ),
            occurrence_count=n_success_1d,
            total_opportunities=n_total,
            win_rate=n_success_1d / n_total,
            avg_gain_pct=spike_days[spike_days["fwd_return_1d"] > 0]["fwd_return_1d"].mean() * 100 if n_positive_1d > 0 else 0,
            avg_loss_pct=abs(spike_days[spike_days["fwd_return_1d"] < 0]["fwd_return_1d"].mean()) * 100 if n_total - n_positive_1d > 0 else 0,
            probability_of_occurrence=n_success_1d / n_total,
            confidence_score=round(min(1.0, n_total / 20), 3),  # higher with more data
            direction=direction_1d,
            metadata={
                "avg_forward_return_1d_pct": round(avg_1d, 2),
                "avg_forward_return_5d_pct": round(avg_5d, 2),
                "spike_threshold": "2x_20d_avg",
            },
        ))

        return patterns

    def detect_rsi_extremes(self, df: pd.DataFrame, symbol: str) -> List[Pattern]:
        """
        Detect technical indicator patterns — RSI extremes and subsequent
        price behavior.
        """
        if df.empty:
            return []

        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        closes = df["close"].values

        # Compute RSI
        rsi_vals = np.full(len(df), np.nan)
        period = 14
        for i in range(period + 1, len(df)):
            diffs = np.diff(closes[i - period - 1 : i + 1])
            gains = np.where(diffs > 0, diffs, 0)
            losses = np.where(diffs < 0, -diffs, 0)
            avg_gain = np.mean(gains)
            avg_loss = np.mean(losses)
            if avg_loss == 0:
                rsi_vals[i] = 100
            else:
                rs = avg_gain / avg_loss
                rsi_vals[i] = 100 - (100 / (1 + rs))

        df["rsi"] = rsi_vals
        df["rsi_oversold"] = df["rsi"] < 30
        df["rsi_overbought"] = df["rsi"] > 70

        patterns = []

        # Oversold → forward returns
        for label, col, threshold in [
            ("oversold", "rsi_oversold", "RSI<30"),
            ("overbought", "rsi_overbought", "RSI>70"),
        ]:
            mask = df[col].fillna(False)
            events = df[mask]
            if len(events) < self.min_occurrences:
                continue

            # Forward 5-day return
            fwd_returns = []
            for idx in events.index:
                if idx + 5 < len(df):
                    fwd = (df.iloc[idx + 5]["close"] - df.iloc[idx]["close"]) / df.iloc[idx]["close"]
                    fwd_returns.append(fwd)

            if len(fwd_returns) < self.min_occurrences:
                continue

            fwd_arr = np.array(fwd_returns) * 100
            n_total = len(fwd_arr)
            n_positive = (fwd_arr > 0).sum()
            avg_fwd = fwd_arr.mean()

            direction = "bullish" if avg_fwd > 0 else "bearish"
            n_success = n_positive if direction == "bullish" else n_total - n_positive

            p_val = stats.binomtest(n_success, n_total, p=0.5, alternative="greater").pvalue
            confidence = 1.0 - p_val if p_val < self.significance_level else 0.5

            patterns.append(Pattern(
                pattern_id=f"{symbol}_rsi_{label}",
                pattern_type="technical_setup",
                symbol=symbol,
                description=(
                    f"{symbol} {threshold}: 5-day forward avg "
                    f"{avg_fwd:.2f}% ({direction}), "
                    f"{n_success}/{n_total} follow direction"
                ),
                occurrence_count=n_success,
                total_opportunities=n_total,
                win_rate=n_success / n_total,
                avg_gain_pct=fwd_arr[fwd_arr > 0].mean() if n_positive > 0 else 0,
                avg_loss_pct=abs(fwd_arr[fwd_arr < 0].mean()) if n_total - n_positive > 0 else 0,
                probability_of_occurrence=n_success / n_total,
                confidence_score=round(confidence, 3),
                p_value=round(p_val, 4),
                direction=direction,
                metadata={
                    "rsi_condition": threshold,
                    "forward_period_days": 5,
                    "avg_fwd_return_pct": round(avg_fwd, 2),
                },
            ))

        return patterns
