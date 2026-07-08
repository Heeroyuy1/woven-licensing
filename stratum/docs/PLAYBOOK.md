# Stratum Playbook

**Strategy & Tactics Guide for Traders and Analysts**

*Document Version: 1.2 | Woven Model*

---

## 1. Introduction

This playbook provides tactical guidance on how to use Stratum effectively for different trading scenarios. It covers strategy configuration, signal interpretation, optimization workflows, and practical trading decisions based on historical analysis.

---

## 2. The Core Strategy: RSI + SMA

### 2.1 How It Works

Stratum's strategy engine replicates the RSI (Relative Strength Index) + SMA (Simple Moving Average) approach:

| Component | Purpose | Typical Setting |
|-----------|---------|-----------------|
| **SMA(20)** | Trend filter — identifies overall direction | 20 periods |
| **RSI(14)** | Momentum oscillator — measures speed/change of price | 14 periods |
| **Buy Signal** | RSI drops below threshold = oversold = potential bounce | < 30 |
| **Sell Signal** | RSI rises above threshold = overbought = potential pullback | > 70 |

### 2.2 The Logic

```
IF RSI < rsi_buy_threshold:
    → BUY (anticipate oversold reversal)
ELSE IF RSI > rsi_sell_threshold:
    → SELL (short) (anticipate overbought reversal)
ELSE:
    → HOLD (no signal)
```

### 2.3 Exit Conditions (priority order)
1. **Take Profit** — Gain exceeds target → close
2. **Stop Loss** — Loss exceeds threshold → close
3. **Max Loss** — Catastrophic loss cap → close
4. **Max Holding** — Position held too long → close

---

## 3. Full Parameter Reference

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `sma_period` | 20 | 5–200 | Number of bars for the SMA trend filter |
| `rsi_period` | 14 | 5–50 | Number of bars for RSI calculation |
| `rsi_buy_threshold` | 30 | 10–45 | RSI level below which a BUY signal fires |
| `rsi_sell_threshold` | 70 | 55–90 | RSI level above which a SELL (short) signal fires |
| `stop_loss_pct` | 0.02 (2%) | 0.5%–10% | Maximum loss per trade before forced exit |
| `take_profit_pct` | 0.05 (5%) | 1%–50% | Profit target per trade |
| `max_loss_pct` | 0.05 (5%) | 1%–20% | Catastrophic loss cap — overrides stop loss at wider distance |
| `max_holding_bars` | 5 | 1–50 | Maximum bars a position is held before forced exit |
| `max_exposure_pct` | 0.10 (10%) | 1%–50% | Maximum fraction of equity allocated to any single position |
| `risk_pct` | 0.01 (1%) | 0.1%–5% | Fraction of equity risked per trade (used in position sizing) |

---

## 4. Parameter Configuration Playbook

### 4.1 Conservative Settings (Low Risk)
```
RSI Buy Threshold: 25      (requires extreme oversold)
RSI Sell Threshold: 75      (requires extreme overbought)
Stop Loss: 1.5%             (tight stop)
Take Profit: 4%             (moderate target)
Max Loss: 4%                (cap on catastrophic loss)
Max Holding: 5 bars         (exit after 5 days if not triggered)
Max Exposure: 5%            (small allocation per position)
Risk Per Trade: 0.5%        (small position size)
```
**Best for**: Blue chips, low volatility, capital preservation

### 4.2 Aggressive Settings (High Risk)
```
RSI Buy Threshold: 35       (more buy signals)
RSI Sell Threshold: 65      (more sell signals)
Stop Loss: 3%               (wider stop)
Take Profit: 8%             (larger target)
Max Loss: 8%                (higher catastrophic cap)
Max Holding: 10 bars        (hold longer)
Max Exposure: 15%           (larger allocation per position)
Risk Per Trade: 2%          (larger position size)
```
**Best for**: High volatility, small caps, momentum trading

### 4.3 Balanced Settings (Medium Risk)
```
RSI Buy Threshold: 30       (standard oversold)
RSI Sell Threshold: 70      (standard overbought)
Stop Loss: 2%               (moderate stop)
Take Profit: 5%             (moderate target)
Max Loss: 5%                (moderate catastrophic cap)
Max Holding: 5 bars         (standard hold)
Max Exposure: 10%           (standard allocation per position)
Risk Per Trade: 1%          (standard position size)
```
**Best for**: Most equities, general purpose

### 4.4 Short-Only Settings
```
Allow Shorts: ON
RSI Sell Threshold: 68      (trigger shorts earlier)
Stop Loss: 2%               (tight on shorts)
Take Profit: 4%
Max Loss: 4%
Max Holding: 5 bars
```
**Best for**: Bear markets, overvalued sectors

---

## 5. Per-Symbol Customization

Different stocks behave differently. The application supports **per-symbol parameter overrides**, which take precedence over the global strategy parameters when a specific symbol is backtested.

### 5.1 High Volatility Symbols (TSLA, NVDA, crypto)
```
stop_loss_pct: 0.03         (wider stop for volatile swings)
take_profit_pct: 0.08       (larger profit targets)
max_loss_pct: 0.10          (wider catastrophic loss cap)
rsi_buy_threshold: 25       (wait for deeper oversold)
rsi_sell_threshold: 75      (wait for extreme overbought)
```

### 5.2 Low Volatility Symbols (AAPL, MSFT, JPM)
```
stop_loss_pct: 0.015        (tighter stop)
take_profit_pct: 0.04       (smaller profit targets)
max_loss_pct: 0.04          (tighter catastrophic cap)
rsi_buy_threshold: 28       (slightly earlier entry)
rsi_sell_threshold: 72      (slightly earlier exit)
```

### 5.3 Small Cap / Speculative (BB, PLUG, KULR)
```
stop_loss_pct: 0.05         (very wide for explosive moves)
take_profit_pct: 0.15       (let winners run)
max_loss_pct: 0.10          (cap total downside)
risk_pct: 0.005             (very small position sizing)
max_exposure_pct: 0.05      (tight allocation limit)
```

---

## 6. Optimization Tactics

### 6.1 Finding the Best Parameters
1. Run **Optimize** tab on 1-2 representative symbols
2. Wait for grid search to complete (625 combinations per symbol)
3. Look at the "Best Params" column for each symbol
4. Identify the most common parameter values across symbols
5. Apply those as your new defaults
6. Re-run backtest to validate the new defaults

### 6.2 Scoring Metric Selection
| Metric | Use When |
|--------|----------|
| **composite** | General purpose — balances return, risk, and consistency |
| **sharpe** | You prioritize smooth returns over raw profit |
| **return** | You want maximum profit regardless of volatility |
| **win_rate** | You need a high percentage of winning trades |
| **profit_factor** | You care about the win/loss size ratio |

### 6.3 Composite Scoring Formula
```
score = sharpe × (1 + return_pct / 100) × (1 - max_dd_pct / 100)
```

### 6.4 Grid Search Ranges
```yaml
rsi_buy_threshold: [22, 25, 28, 30, 33]
rsi_sell_threshold: [67, 70, 72, 75, 78]
stop_loss_pct: [0.01, 0.015, 0.02, 0.025, 0.03]
take_profit_pct: [0.03, 0.04, 0.05, 0.06, 0.08]
```

### 6.5 Position Sizing Logic
```
qty_risk = equity × risk_pct / (price × stop_loss_pct)
qty_cap  = equity × max_exposure_pct / price
qty      = min(qty_risk, qty_cap)
```

---

## 7. Interpreting AI Analysis

### 7.1 Score Ranges

| Score | Meaning | Action |
|-------|---------|--------|
| **70-100** | Strong historical performance | Recommended to Trade |
| **45-69** | Moderate performance | Trade with Caution |
| **0-44** | Poor performance | Avoid Trading |

### 7.2 Score Components
- **Profitability (30%)** — Higher raw returns = better score
- **Risk (20%)** — Lower drawdown = better score
- **Consistency (20%)** — Higher Sharpe = better score
- **Win Rate (15%)** — Higher win % = better score
- **Frequency (15%)** — More trades = more statistical confidence

### 7.3 Rankings to Watch
- **Best Overall** — Top candidates for the strategy
- **Most Stable** — Lowest volatility, predictable results
- **Most Volatile** — High risk, potentially high reward
- **Lowest Drawdown** — Safest performers

---

## 8. Workflows by Use Case

### 8.1 Building a Watchlist
1. Start with 10-20 candidate symbols
2. Run backtest on all symbols
3. Go to **AI Analysis** tab
4. Note symbols with "Recommended to Trade"
5. Add those to your watchlist
6. Run optimization on watchlist symbols for best params
7. Apply the best params as per-symbol overrides via the Config tab

### 8.2 Comparing Multiple Symbols
1. Run backtest with all symbols at once
2. Use the **Backtest** results table to sort by different metrics
3. Check equity curves in exported Excel for visual comparison

### 8.3 Pre-Trade Checklist
- [ ] Has the symbol been backtested over at least 2 years?
- [ ] Does it have at least 20 trades in the backtest?
- [ ] Is the AI score above 50?
- [ ] Is the win rate above 40%?
- [ ] Is the max drawdown acceptable for your risk tolerance?
- [ ] Has the symbol's volatility been assessed?
- [ ] Are per-symbol parameters configured?

---

## 9. Common Patterns & What They Mean

| Scenario | Interpretation |
|----------|---------------|
| High return, high drawdown | Profitable but risky — use smaller position sizing |
| High win rate, low return | Many small wins, occasional large losses — check profit factor |
| Low win rate, high return | Few big winners outweigh many small losers — can work with patience |
| High Sharpe, low return | Very consistent but limited upside — good for conservative portfolios |
| Many trades (100+) | High statistical confidence in results |
| Few trades (<10) | Results may not be statistically meaningful |

---

## 10. Risk Management Framework

### 10.1 Position Sizing Formula
```python
position_size = min(
    equity × risk_pct / (price × stop_loss_pct),   # Risk-based sizing
    equity × max_exposure_pct / price               # Max exposure cap
)
```

### 10.2 Recommended Limits
| Account Size | Risk Per Trade | Max Exposure | Max Drawdown |
|-------------|---------------|--------------|--------------|
| $10,000 | $50 (0.5%) | $1,000 (10%) | 10% |
| $50,000 | $250 (0.5%) | $5,000 (10%) | 10% |
| $100,000 | $500 (0.5%) | $10,000 (10%) | 10% |
| $500,000 | $2,500 (0.5%) | $50,000 (10%) | 10% |

---

## 11. Licensing & Feature Gating

### 11.1 Integration with Licensing Server

Stratum validates licenses against the **Woven Model Licensing Server** at startup. The license flow:

1. **Startup**: `LicenseManager.check_license()` checks for `license.lic`
2. **If found**: Validates locally (encrypted file + machine binding), then re-validates online via the SDK
3. **If not found**: Shows the License Dialog with trial or activation options
4. **Activation**: Sends `POST /api/v1/activate` with license key + machine fingerprint
5. **Validation**: Each launch re-validates via `POST /api/v1/validate` (with offline certificate fallback)
6. **Deactivation**: Sends `POST /api/v1/deactivate` to release the activation slot

### 11.2 Trial vs Licensed Feature Matrix

| Feature | Trial (24h) | Licensed |
|---------|:-----------:|:--------:|
| Backtest up to 2 symbols | ✅ | ✅ |
| Backtest unlimited symbols | ❌ | ✅ |
| Watchlist management | ✅ | ✅ |
| Load saved profiles | ✅ | ✅ |
| Save profiles | ❌ | ✅ |
| AI Analysis & recommendations | ❌ | ✅ |
| Parameter optimization (grid search) | ❌ | ✅ |
| Export reports (PDF/Excel/CSV/JSON) | ❌ | ✅ |
| Per-symbol parameter customization | ❌ | ✅ |

### 11.3 Activating a License

1. Run the licensing server: `cd ../licensing-server/backend && uvicorn app.main:app --port 8000`
2. Generate a license via admin API (see RUN_BOOK.md)
3. Open Stratum → **🔑 License** tab
4. Paste the key and click **Activate**

### 11.4 What Happens After Activation

- `POST /api/v1/activate` sends license key + machine fingerprint to server
- Server validates the key, creates machine + activation DB records
- Server returns a **signed Ed25519 certificate** with expiry and feature flags
- Stratum caches the certificate to `stratum/cache/license/` and `stratum/license.lic`
- Trial timer file (`.trial`) is deleted
- Status bar updates: `🔒 Licensed | Key: ABCDE... | Expires: 2027-01-01`

### 11.5 Offline Fallback Behavior

| Scenario | Behavior |
|----------|----------|
| Server online, license valid | `🔒 Licensed` — full features |
| Server offline, cached cert valid | `🔐 Licensed` — full features (offline) |
| Server offline, no cached cert | Shows trial or activation prompt |
| License expired on server | Blocks features, prompts renewal |

### 11.6 Status Indicators in Header

| Indicator | Meaning |
|-----------|---------|
| `🔒 Licensed` | Verified with licensing server (online) |
| `🔐 Licensed` | Valid local cache (offline fallback) |
| `Trial | 12h 34m remaining` | 24-hour trial active |
| `Trial expired` | Trial period over, license needed |

---

## 12. Support Escalation

| Level | Contact | Response Time |
|-------|---------|---------------|
| L1: Application usage | This playbook + Run Book | Self-service |
| L2: Technical issues | jude@wovenmodel.com | 24 hours |
| L3: License server issues | jude@wovenmodel.com | 24 hours |
| L4: Custom development | https://wovenmodel.com | Per agreement |

---

*Stratum v1.2.0 | © Woven Model. All rights reserved. | This document does not constitute financial advice. Always perform your own due diligence before making trading decisions.*
