# Harper

**Intelligent Woven Model Platform for Market Intelligence**

Harper transforms historical market data into actionable insights through advanced backtesting, pattern recognition, and predictive analytics. Built on the [Woven Model](https://heeroyuy1.github.io/Heeroyuy1.github.ai/) ecosystem.

---

## Overview

Harper is a comprehensive historical backtesting and market pattern analysis platform, refactored from a live trading bot into a research-grade analytical tool. It supports multi-year historical data processing, paper trading simulation, strategy validation, and automated pattern discovery — all within a unified architecture.

### Key Capabilities

- **AI-Powered Pattern Discovery** — Automatically identifies statistically significant recurring market patterns (seasonal, day-of-week, volume spikes, technical setups)
- **Historical Backtesting** — Replay strategies across 5+ years of market data with virtual money
- **Predictive Analytics** — Generate probability-based forecasts with confidence scores
- **Strategy Optimization** — Grid search across thousands of parameter combinations
- **Interactive Dashboard** — Visual reports with performance metrics, equity curves, and pattern rankings

---

## Architecture

```
harper/
├── config/                 # Configuration files
│   └── backtest_config.json
├── core/                   # Core engine
│   ├── data_loader.py      # Historical data fetching & caching
│   ├── paper_broker.py     # Simulated brokerage (virtual money)
│   └── strategy_runner.py  # Strategy execution against historical data
├── strategies/             # Trading strategies
│   ├── base_strategy.py    # Abstract strategy interface
│   └── rsi_sma_strategy.py # RSI/SMA strategy
├── patterns/               # Pattern discovery engine
│   └── detector.py         # Statistical pattern finder
├── optimizer/              # Strategy parameter optimization
│   └── grid_search.py      # Grid search optimizer
├── reporting/              # Dashboards & reports
│   └── dashboard.py        # Harper-branded dashboard
├── logs/                   # Trade & pattern logs
├── data/                   # Cached historical data
├── reports/                # Generated reports & dashboards
└── main.py                 # Entry point
```

---

## Quick Start

### Prerequisites

```bash
pip install -r requirements.txt
```

### Run

```bash
# Full backtest + pattern discovery + dashboard
python main.py

# Specific symbols
python main.py --symbols AAPL,TSLA,NVDA

# Custom date range
python main.py --start 2020-01-01 --end 2025-12-31

# Pattern discovery only (uses cached data)
python main.py --patterns-only

# Run parameter optimization
python main.py --optimize --symbols AAPL
```

### Output

| File | Description |
|---|---|
| `reports/dashboard.html` | Interactive Harper dashboard |
| `reports/results.json` | Full JSON export |
| `logs/trades_*.csv` | Every simulated trade |
| `logs/signals_*.csv` | Every signal generated |
| `logs/daily_*.csv` | Daily equity snapshots |
| `data/*.parquet` | Cached OHLCV data (5+ years) |

---

## Strategy

Harper implements the RSI/SMA strategy with configurable per-symbol parameters:

- **Entry**: RSI below buy threshold (oversold) or above sell threshold (overbought)
- **Exit**: Stop-loss, take-profit, max holding period, or max loss
- **Risk Management**: Position sizing based on equity percentage and stop distance
- **Metrics**: Sharpe ratio, maximum drawdown, win rate, P/L ratio

---

## Pattern Discovery Engine

Harper automatically searches for statistically significant recurring patterns:

| Pattern Type | Detection Method | Statistical Test |
|---|---|---|
| Seasonal (monthly) | Monthly return distributions | Binomial test |
| Day-of-week | Daily return by weekday | t-test |
| Volume spikes | 2x average volume events | Forward return analysis |
| RSI extremes | RSI < 30 / RSI > 70 setups | Binomial test on forward returns |

Each pattern includes:
- Confidence score (0-1)
- Probability of occurrence
- Historical win rate
- Average gain/loss
- p-value (statistical significance)

---

## Configuration

Edit `config/backtest_config.json`:

```json
{
  "symbols": ["AAPL", "TSLA", "NVDA", "GOOGL"],
  "start_date": "2020-01-01",
  "end_date": "2025-12-31",
  "initial_capital": 100000,
  "sma_period": 20,
  "rsi_buy_threshold": 30,
  "rsi_sell_threshold": 70,
  "stop_loss_pct": 0.02,
  "take_profit_pct": 0.05,
  "max_holding_days": 5,
  "per_symbol_settings": { ... }
}
```

---

## Brand

Harper is part of the **Woven Model** ecosystem — building intelligent systems that scale.

> *"Harper is an intelligent Woven Model platform designed to transform historical market data into actionable insights through advanced backtesting, pattern recognition, and predictive analytics."*

### Design System

| Element | Value |
|---|---|
| Primary Background | `#0a0f1c` (Deep Navy) |
| Card Background | `#111827` |
| Accent | `#14b8a6` (Teal) |
| Positive | `#10b981` (Emerald) |
| Typography | Inter, SF Pro, Segoe UI (system stack) |

---

## Disclaimer

⚠️ **Past performance does not guarantee future results.** All patterns are statistical correlations identified in historical data. Harper does not provide financial advice. Use findings for research and analysis purposes only.

---

**Harper** · Woven Model Market Intelligence Platform
