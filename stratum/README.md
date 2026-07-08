# Stratum — AI Trading Strategy Analyzer

**Powered by Woven Model**

Stratum is a professional desktop application that analyzes historical market data to determine whether a trading strategy would have been profitable under different market conditions. It provides intelligent recommendations, optimized configuration values, and comprehensive performance reports.

---

## Quick Start

### Prerequisites
- Windows 10/11
- Python 3.10+
- Internet connection (for market data)

### Install & Run
```bash
cd stratum
pip install -r requirements.txt
python app.py
```

On first launch, you can start a **24-hour free trial** or enter a license key.

### First Analysis
1. Go to the **Backtest** tab
2. Enter symbols (e.g., `AAPL, TSLA, NVDA`)
3. Set a date range
4. Click **▶ Run Backtest**
5. Results appear automatically — Dashboard, AI Analysis, and tables update in real time

---

## Features

### 📊 Dashboard
High-level KPI cards (best return, total trades, average Sharpe, win rate) and quick action buttons.

### 🔍 Backtesting
Run RSI + SMA strategy simulations on any stock symbols over configurable date ranges. Supports per-symbol parameter overrides matching the reference bot's behavior.

### 🤖 AI Analysis
Intelligent symbol ratings on a 0–100 scale across five dimensions: profitability, risk, consistency, win rate, and trade frequency. Each symbol gets one of three recommendations:
- ✅ **Recommended to Trade** — strong historical performance
- ⚠️ **Trade with Caution** — moderate results, selective
- ❌ **Avoid Trading** — poor historical performance

### ⚙ Parameter Optimization
Grid search across strategy parameters (RSI thresholds, stop-loss, take-profit) to find the best configuration for each symbol. Scoring metrics: composite, Sharpe, return, win rate, or profit factor.

### ⚙ Configuration
Save and load strategy profiles. Configure SMA period, RSI period/buy/sell thresholds, stop-loss, take-profit, max holding bars, exposure, and risk per trade.

### 👁 Watchlist
Manage a personal watchlist of symbols with checkboxes. Batch-analyze your watchlist in one click.

### 📊 Reports & Export
Export results as:
- **PDF** — Professional formatted report with tables
- **Excel** — Multi-sheet workbook (Performance, Trades, AI Analysis, Equity Curves)
- **CSV** — Performance summary and individual trade logs
- **JSON** — Full data export

### 🔑 Licensing
- 24-hour free trial on first launch
- License activation via XXXXX-XXXXX-XXXXX-XXXXX format key
- Encrypted license storage with machine binding
- One-year license duration

---

## Strategy Logic

The backtest engine replicates the RSI + SMA strategy from the reference bot:

| Condition | Action |
|-----------|--------|
| RSI < `rsi_buy_threshold` | **BUY** (oversold bounce) |
| RSI > `rsi_sell_threshold` | **SELL / Short** (overbought pullback) |
| `gain_pct >= take_profit_pct` | Exit: Take Profit |
| `gain_pct <= -stop_loss_pct` | Exit: Stop Loss |
| `gain_pct < -max_loss_pct` | Exit: Max Loss |
| Holding period exceeded | Exit: Max Holding |

Position sizing uses risk-based calculation: `equity × risk_pct / (price × stop_loss_pct)`, capped by `max_exposure_pct`.

---

## Architecture

```
stratum/
├── app.py                  # Application entry point
├── core/                   # Engine modules
│   ├── config_manager.py   # Profiles & per-symbol settings
│   ├── data_loader.py      # Yahoo Finance + Parquet cache
│   ├── broker.py           # Paper trading engine
│   ├── strategy_engine.py  # Bar-by-bar backtest engine
│   ├── optimizer.py        # Grid search optimizer
│   ├── ai_analysis.py      # AI recommendation engine
│   ├── reporting.py        # PDF/Excel/CSV/JSON export
│   ├── licensing.py        # License management
│   └── logger.py           # Logging system
├── ui/
│   └── main_window.py      # PyQt6 desktop interface
├── data/                   # Cached market data (Parquet)
├── logs/                   # Application logs
├── reports/                # Exported reports
└── profiles/               # Saved strategy profiles
```

---

## Support

For licensing, support, or custom development inquiries:
- **Email**: jude@wovenmodel.com
- **Web**: https://wovenmodel.com

© Woven Model. All rights reserved.
