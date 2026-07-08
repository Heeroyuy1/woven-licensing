# Stratum — Customer Summary

**AI Trading Strategy Analyzer | Powered by Woven Model**

---

## What Is Stratum?

Stratum is a Windows desktop application that answers one question: **"Would this trading strategy have made money on this stock?"**

It takes historical market data, simulates a trading strategy bar-by-bar, and tells you exactly how it would have performed — including profit/loss, win rate, drawdown, and dozens of other metrics.

---

## What It Does

| Capability | Description |
|------------|-------------|
| **Backtesting** | Replays years of market data to see how a strategy would have performed |
| **AI Analysis** | Rates each symbol 0-100 and recommends whether to trade it, proceed with caution, or avoid it |
| **Parameter Optimization** | Tests hundreds of parameter combinations to find the best settings for each symbol |
| **Multi-Symbol Comparison** | Analyze 1-20+ symbols at once and compare results side by side |
| **Reporting** | Export professional reports in PDF, Excel, CSV, or JSON |

---

## Who It's For

- **Algorithmic traders** — Validate strategies before going live
- **Retail investors** — Find which stocks work best with your approach
- **Trading bot developers** — Optimize configuration values for your bots
- **Quantitative analysts** — Data-driven strategy evaluation
- **Financial researchers** — Historical pattern analysis

---

## The Strategy

The application simulates an **RSI + SMA** mean-reversion strategy:

1. **Buy** when a stock is oversold (RSI drops below a threshold) — anticipating a bounce
2. **Sell (short)** when a stock is overbought (RSI rises above a threshold) — anticipating a pullback
3. **Exit** when take-profit, stop-loss, or max-holding conditions are met

All parameters are fully configurable. You can also set **different parameters for each symbol** — because what works for AAPL may not work for TSLA.

---

## Key Metrics You Get

After running a backtest, you see:

- **Total Return %** — How much the simulated account grew
- **Sharpe Ratio** — Return relative to risk (higher = smoother returns)
- **Max Drawdown** — The worst peak-to-trough drop
- **Win Rate** — Percentage of profitable trades
- **Total Trades** — How many trades were executed
- **P&L** — Total profit or loss in dollars
- **Trade History** — Every trade with entry, exit, P&L, and reason
- **Equity Curve** — Account value over time

Plus **AI-powered ratings** that combine all metrics into a single 0-100 score with a clear recommendation.

---

## Sample Output

Using default settings on 5 major stocks over 2020-2025:

```
Symbol    Return%    Sharpe    MaxDD%    WinRate%    Trades    P&L
AAPL      +0.96%     0.23      18.43%    50.0%       20        $960
TSLA      +2.50%     0.15      22.10%    45.0%       22        $2,500
NVDA      +7.25%     0.35      15.80%    55.0%       18        $7,250
GOOGL     -1.20%     0.10      20.50%    42.0%       19        -$1,200
AMD       +3.40%     0.28      17.20%    52.0%       21        $3,400

AI Analysis:
  Best Overall: NVDA (Score: 72/100 — Recommended to Trade)
  Most Stable: AAPL
  Most Volatile: TSLA
```

---

## Getting Started

```
1. Install Python 3.10+
2. pip install -r requirements.txt
3. python app.py
4. Start your 24-hour free trial
5. Enter symbols → Click "Run Backtest" → Get results
```

---

## Support

**Woven Model** — Building Intelligent Systems That Scale

- **Email**: jude@wovenmodel.com
- **Web**: https://wovenmodel.com

*Stratum v1.1.0 | This software is a decision-support tool. It does not place trades. Past performance does not guarantee future results.*
