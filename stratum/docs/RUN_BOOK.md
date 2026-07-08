# Stratum Run Book

**Operational Guide for Stratum — AI Trading Strategy Analyzer**

*Document Version: 1.3 | Woven Model*

---

## 1. System Overview

Stratum is a Windows desktop application that analyzes historical market data using an RSI + SMA trading strategy, generates performance statistics, AI-powered recommendations, and parameter optimization results. It integrates with the Woven Model Licensing Server for online license activation and validation.

### 1.1 Tab Reference

The application has nine tabs, arranged left-to-right in the navigation bar:

| # | Tab | Purpose |
|---|-----|---------|
| 1 | **📊 Dashboard** | High-level KPIs, quick actions, last analysis summary |
| 2 | **🔍 Backtest** | Run backtests — symbol entry, date range, capital, results table |
| 3 | **🤖 AI Analysis** | Symbol ratings (0-100), recommendations, rankings |
| 4 | **⚙ Optimize** | Grid-search parameter optimization |
| 5 | **⚙ Config** | Strategy profiles, per-symbol settings, parameter configuration |
| 6 | **👁 Watchlist** | Symbol watchlist management with checkboxes |
| 7 | **📊 Reports** | Export to PDF, Excel, CSV, JSON, Trades CSV |
| 8 | **🔑 License** | License activation, deactivation, status |
| 9 | **⚙ Settings** | Commission, slippage, cache clearing, factory reset |

### 1.2 Architecture

```
User Interface (PyQt6)
    │
    ├── Config Manager → profiles/*.json (JSON on disk)
    ├── Data Loader → Yahoo Finance / Parquet cache (stratum/data/*.parquet)
    ├── Strategy Engine → Paper Broker → results
    ├── AI Analysis → ratings & recommendations
    ├── Optimizer → grid search results
    ├── Reporting → PDF / Excel / CSV / JSON
    └── License Manager ──▶ Licensing Server (REST API)
                              │
                              ├── /api/v1/activate
                              ├── /api/v1/validate
                              ├── /api/v1/deactivate
                              └── /api/v1/transfer
```

### 1.3 Data Flow

1. User enters symbols + date range + parameters in **Backtest** tab
2. Config is saved to the active profile (`profiles/default.json`)
3. `LicenseManager.check_license()` verifies license status (online via SDK, or fallback)
4. Data Loader fetches from Yahoo Finance, caches as Parquet in `stratum/data/`
5. Strategy Engine replays bars sequentially, executing simulated trades through the Paper Broker
6. Results feed into AI Analysis for symbol ratings (0-100)
7. All data displayed in UI tables and available for export via **Reports** tab

---

## 2. Licensing System

### 2.1 Architecture

Stratum now integrates with the **Woven Model Licensing Server** — a central REST API that manages all license activations. On each launch, Stratum attempts to validate its license with the server and falls back to a locally cached certificate (signed with Ed25519) when offline.

```
Stratum Desktop                        Licensing Server
    │                                        │
    ├── check_license() ────────────▶ POST /health
    │   (online verification)        │
    │   ◀───────────────────────────  200 OK
    │                                        │
    ├── activate(key) ──────────────▶ POST /api/v1/activate
    │   (machine fingerprint + key)  │
    │   ◀───────────────────────────  {certificate, signature}
    │                                        │
    ├── validate() ─────────────────▶ POST /api/v1/validate
    │   (fingerprint hash)           │
    │   ◀───────────────────────────  {valid, certificate}
    │                                        │
    └── deactivate() ───────────────▶ POST /api/v1/deactivate
        (license key + fingerprint)   │
        ◀───────────────────────────  {success}
```

### 2.2 Trial Mode (24-Hour Free Trial)

On first launch, the application checks for an existing license. If none is found, a **License Dialog** appears offering two options:

1. **Start 24-Hour Free Trial** — unlocks limited features for 24 hours
2. **Enter License Key** — full permanent activation (validated against the licensing server)

The trial timer is stored in `stratum/.trial` as a JSON file containing the start timestamp.

**Trial limitations:**

| Feature | Trial (24h) | Licensed |
|---------|:-----------:|:--------:|
| Backtest — up to 2 symbols | ✅ | ✅ |
| Backtest — unlimited symbols | ❌ | ✅ |
| Watchlist management | ✅ | ✅ |
| Load saved profiles | ✅ | ✅ |
| Save profiles | ❌ | ✅ |
| AI Analysis & recommendations | ❌ | ✅ |
| Parameter optimization (grid search) | ❌ | ✅ |
| Export reports (PDF/Excel/CSV/JSON) | ❌ | ✅ |
| Per-symbol parameter customization | ❌ | ✅ |

### 2.3 License Activation

License keys use the format `XXXXX-XXXXX-XXXXX-XXXXX` where each character is from the set `A-Z` and `0-9` (excludes ambiguous `0`, `O`, `1`, `I`, `L`). The key includes a modulo-36 checksum: the sum of all 20 character values must be divisible by 36.

**To activate:**

1. Obtain a license key from the Woven Model Licensing Server admin panel
2. Open Stratum → **🔑 License** tab
3. Enter the key in the input field
4. Click **Activate**

**What happens under the hood:**

1. Stratum collects the machine fingerprint (HMAC-SHA256 of hardware IDs)
2. Sends `POST /api/v1/activate` to the licensing server with license key + fingerprint
3. Server validates the key, creates machine + activation records in the database
4. Server returns a **signed certificate** (Ed25519 signature) containing license details
5. Stratum caches the certificate locally as `stratum/license.lic` (encrypted)
6. On deactivation, `POST /api/v1/deactivate` is sent to release the activation slot

**Status indicators:**

- `🔒 Licensed` — verified with the licensing server (online)
- `🔐 Licensed` — activated locally (offline fallback)
- `Trial` — 24-hour free trial active

### 2.4 License Key Generator (Server-Side)

License keys are generated via the admin API:

```bash
# From the licensing server admin panel
curl -X POST https://licensing.wovenmodel.com/api/v1/admin/licenses/generate \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "product_code": "STRATUM",
    "user_id": 1,
    "license_type": "perpetual",
    "max_activations": 2,
    "expiration_days": 365
  }'
```

### 2.5 Feature Comparison (Full)

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

### 2.6 License File Locations

| File | Purpose |
|------|---------|
| `stratum/license.lic` | Encrypted local license file (Fernet + PBKDF2) |
| `stratum/.trial` | Trial timer (JSON with start timestamp) |
| `stratum/cache/license/` | Signed certificate cache from licensing server |

To reset licensing: delete `license.lic` and `.trial`, then restart.

### 2.7 License Deactivation

To move a license to a new machine:

1. Open Stratum → **🔑 License** tab on the old machine
2. Click **Deactivate License** — sends `POST /api/v1/deactivate` to server
3. On the new machine, enter the same license key

### 2.8 Licensing Server Configuration

The licensing server URL defaults to `http://localhost:8000` for development. Point to production:

```json
// In profiles/default.json or config:
{
  "licensing_server_url": "https://licensing.wovenmodel.com"
}
```

---

## 3. Installation

### 3.1 Requirements

- **OS**: Windows 10 or 11 (64-bit)
- **Python**: 3.10 or higher
- **Disk**: 500 MB minimum (more for cached data)
- **RAM**: 4 GB minimum, 8 GB recommended
- **Network**: Internet required for data fetching (Yahoo Finance) and license validation

### 3.2 Dependencies

```bash
pip install PyQt6 PyQt6-Charts pyqtgraph numpy pandas \
  yfinance scipy reportlab openpyxl cryptography
```

The Woven License SDK is bundled with Stratum and auto-detected from:
- `../licensing-server/client-sdk/` (development)
- Installed as `woven-license` package (production)

### 3.3 First Launch

```bash
cd stratum
python app.py
```

On first launch the application will:

1. Prompt for license activation or start **24-hour free trial** via the License Dialog
2. Initialize the License Manager with the licensing server SDK
3. Create default configuration profile at `stratum/profiles/default.json`
4. Create `stratum/data/`, `stratum/logs/`, `stratum/reports/` directories
5. Show the **📊 Dashboard** tab ready for use

### 3.4 Portable Build (Single EXE)

```bash
python build_portable.py --portable
```

Output: `dist/Stratum.exe` — a single-file portable executable. No Python installation required.

### 3.5 Licensing Server Setup

For development, run the licensing server locally:

```bash
cd ../licensing-server/backend
pip install -r ../requirements.txt
python ../scripts/generate_keys.py   # Generate Ed25519 keys
# Add SIGNING_PRIVATE_KEY and SIGNING_PUBLIC_KEY to .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Then Stratum will connect to `http://localhost:8000` automatically.

---

## 4. Daily Operations

### 4.1 Running a Standard Backtest

1. Navigate to **🔍 Backtest** tab
2. Enter symbols in the text field (e.g., `AAPL, TSLA, NVDA, GOOGL, AMD`)
3. Set date range using the date pickers (e.g., 2020-01-01 to 2025-12-31)
4. Set initial capital ($100,000 default)
5. Check/uncheck **"Allow Short Selling"**
6. Click **▶ Run Backtest**
7. Monitor progress bar in the status bar and log output
8. Results populate automatically in the results table, Dashboard, and AI Analysis

### 4.2 Analyzing Results

After a backtest completes, inspect these tabs in order:

1. **📊 Dashboard** — KPI overview cards: Best Return, Total Trades, Avg Sharpe, Win Rate
2. **🔍 Backtest** — Table of all symbols with return %, Sharpe, max drawdown %, P&L
3. **🤖 AI Analysis** — Symbol ratings (0-100), recommendations, rankings
4. **⚙ Optimize** — Grid search optimization results per symbol

### 4.3 AI Analysis Tab

1. Navigate to **🤖 AI Analysis** tab after a backtest completes
2. Review the **summary** text at the top for a quick takeaway
3. Inspect the **ratings table** — each symbol scored 0-100 with recommendation, volatility, return, Sharpe, max drawdown
4. Check the **rankings** panel:

   - **Best Overall** — highest-scoring symbols
   - **Best Return** — highest absolute return
   - **Best Sharpe** — best risk-adjusted returns
   - **Lowest Drawdown** — safest performers
   - **Most Stable / Most Volatile** — volatility classification
5. Use the **recommendation** column:

   - ✅ **Recommended to Trade** — score 70+
   - ⚠️ **Trade with Caution** — score 45-69
   - ❌ **Avoid Trading** — score < 45

### 4.4 Watchlist Tab

1. Navigate to **👁 Watchlist** tab
2. **Add symbols** by typing and clicking **Add to Watchlist**
3. Each symbol has a **checkbox** — only checked symbols are analyzed
4. **Remove** symbols by selecting them and clicking **Remove Selected**
5. **Analyze Watchlist** sets checked symbols in the Backtest tab and switches to it
6. Watchlist is **persisted across sessions** via the active profile

### 4.5 Exporting Reports

1. Run a backtest first (no data = nothing to export)
2. Navigate to **📊 Reports** tab
3. Click desired export format:

   - **📄 Export as PDF** — Professional report with tables
   - **📗 Export as Excel** — Multi-sheet workbook (Performance, Trades, AI Analysis, Equity Curves)
   - **📊 Export as CSV** — Summary data per symbol
   - **📋 Export as JSON** — Full data export
   - **📉 Export Trades CSV** — Individual trade logs only
4. Choose save location in file dialog

---

## 5. Configuration Management

### 5.1 Saving a Profile

1. Go to **⚙ Config** tab
2. Adjust strategy parameters
3. Enter profile name in "New profile name" field
4. Click **Save As...**

### 5.2 Loading a Profile

1. Select profile from dropdown
2. Click **Load**
3. Parameters are applied immediately to the UI controls

### 5.3 Parameters Available

| Widget | Config Key | Default | Range |
|--------|-----------|---------|-------|
| SMA Period | `sma_period` | 20 | 5-200 |
| RSI Period | `rsi_period` | 14 | 5-50 |
| RSI Buy Threshold | `rsi_buy_threshold` | 30 | 10-45 |
| RSI Sell Threshold | `rsi_sell_threshold` | 70 | 55-90 |
| Stop Loss % | `stop_loss_pct` | 2% | 0.5%-10% |
| Take Profit % | `take_profit_pct` | 5% | 1%-50% |
| Max Holding Bars | `max_holding_bars` | 5 | 1-50 |
| Max Exposure % | `max_exposure_pct` | 10% | 1%-50% |
| Risk % Per Trade | `risk_pct` | 1% | 0.1%-5% |

Note: Stop Loss, Take Profit, Max Exposure, and Risk Per Trade are displayed as percentages (e.g., 2.0) but stored as decimals (e.g., 0.02) in the config file.

---

## 6. Settings Tab

### 6.1 General Settings

- **Commission per Share ($)** — Default: 0.0. Adds a per-share commission cost to each fill.
- **Slippage %** — Default: 0.05% (0.0005). Simulates market impact.

### 6.2 Maintenance Actions

- **Clear All Cached Data** — Deletes all downloaded Parquet files from `stratum/data/`. Next backtest will re-fetch from Yahoo Finance.
- **Reset to Defaults** — Restores all configuration and strategy parameters to factory defaults. Does not affect license activation.

---

## 7. Performance Optimization

### 7.1 Improving Backtest Speed

- First-time data fetching is slow (downloads from Yahoo Finance)
- Subsequent runs use cached Parquet files and are much faster
- Limit date range for quicker iterations
- Fewer symbols = faster results

### 7.2 Optimization Performance

Optimization runs 625 combinations per symbol (5 × 5 × 5 × 5 parameter grid).
- Reduce parameter grid size for faster runs
- Limit to 1-2 symbols during tuning
- Expect ~30-60 seconds per symbol at default grid size

---

## 8. Troubleshooting

### 8.1 "No data loaded" Error

**Causes**: Invalid symbols, no internet, Yahoo Finance rate limiting

**Solutions**:
- Verify symbol exists (e.g., `AAPL` not `APPL`)
- Check internet connection
- Wait 60 seconds and retry
- Try a smaller date range

### 8.2 Application won't start

**Causes**: Missing dependencies, Python version too old

**Solutions**:
- Run: `pip install -r requirements.txt`
- Verify Python 3.10+ with: `python --version`
- Check logs in: `stratum/logs/stratum_YYYYMMDD.log`

### 8.3 License errors

**Causes**: Corrupted `license.lic`, machine change, expired license, licensing server unreachable

**Solutions**:
- Delete `stratum/license.lic` and restart (triggers License Dialog)
- Delete `stratum/.trial` to reset trial
- Ensure licensing server is running at the configured URL
- Check `stratum/logs/` for `Stratum.Licensing` log entries
- Contact jude@wovenmodel.com for license reissue

### 8.4 Licensing Server Unreachable

If the licensing server is unavailable, Stratum falls back gracefully:
- **First activation**: fails with message "Server unreachable. Try again later."
- **Already activated**: uses the locally cached `license.lic` file
- **Status bar**: shows `🔐 Licensed` (offline fallback)

To resolve:
1. Check that the licensing server is running at `http://localhost:8000` (dev) or `https://licensing.wovenmodel.com` (prod)
2. Verify network connectivity
3. Check server logs for errors

### 8.5 Optimization is slow

**Causes**: 625 combinations per symbol at default grid size

**Solutions**:
- Reduce parameter grid size in `profiles/default.json`
- Limit optimization to 1-2 symbols

### 8.6 AI Analysis shows no data

**Causes**: No backtest results loaded, feature locked in trial mode

**Solutions**:
- Run a backtest first
- Activate a license key
- Check that at least one symbol has trade data

### 8.7 Trial expired

**Causes**: The 24-hour trial period has elapsed

**Solutions**:
- Enter a valid license key in the **🔑 License** tab
- Contact jude@wovenmodel.com to obtain a key
- After activation all features restore immediately

---

## 9. Monitoring & Logs

### 9.1 Viewing Logs

- Click **Log** button in the status bar to toggle the log panel
- Full logs saved to: `stratum/logs/stratum_YYYYMMDD.log`

### 9.2 Log Sources

| Prefix | Module |
|--------|--------|
| `Stratum` | App entry point |
| `Stratum.UI` | Main window UI |
| `Stratum.Engine` | Strategy engine |
| `Stratum.Broker` | Paper broker |
| `Stratum.Data` | Data loader |
| `Stratum.AI` | AI analysis |
| `Stratum.Optimizer` | Parameter optimizer |
| `Stratum.Config` | Config manager |
| `Stratum.Reporting` | Export engine |
| `Stratum.Licensing` | License manager |
| `woven_license` | License SDK client |

---

## 10. Security

### 10.1 Data Security

- All market data fetched over HTTPS (Yahoo Finance API)
- No user data transmitted to external servers (fully offline analysis)
- License data encrypted with Fernet (symmetric encryption using PBKDF2-derived key)
- Machine ID generated from SHA-256 hash of hostname, processor, system, and MAC address
- License certificates are signed with Ed25519 (public key verified offline)

### 10.2 License Integrity

| Component | Mechanism |
|-----------|-----------|
| License key | Modulo-36 checksum validation |
| Machine binding | HMAC-SHA256 fingerprint hash |
| Certificate | Ed25519 digital signature |
| Storage | Fernet (AES-128-CBC) encrypted file |
| Online validation | POST to licensing server |

---

## 11. File Reference

### 11.1 Directory Structure

```
stratum/
├── app.py                        # Application entry point
├── build_portable.py             # PyInstaller build script
├── generate_license_key.py       # Legacy local key generator
├── README.md                     # Customer-facing README
├── core/
│   ├── __init__.py
│   ├── config_manager.py         # Profile/parameter management
│   ├── data_loader.py            # Yahoo Finance + Parquet
│   ├── broker.py                 # Paper trading broker
│   ├── strategy_engine.py        # RSI+SMA backtest engine
│   ├── optimizer.py              # Grid search optimizer
│   ├── ai_analysis.py            # AI recommendation engine
│   ├── reporting.py              # PDF/Excel/CSV/JSON export
│   ├── licensing.py              # License manager (server-aware)
│   └── logger.py                 # Logging system
├── ui/
│   ├── __init__.py
│   └── main_window.py            # PyQt6 desktop interface
├── docs/
│   ├── RUN_BOOK.md               # This document
│   ├── PLAYBOOK.md               # Strategy & tactics guide
│   └── SUMMARY.md                # Customer-facing summary
├── data/                         # Cached market data (Parquet)
├── logs/                         # Application logs
├── reports/                      # Exported reports
├── profiles/                     # Saved strategy profiles
├── cache/                        # License certificate cache
├── assets/                       # Icons and assets
├── license.lic                   # Encrypted license binding
└── .trial                        # Trial timer file
```

---

## 12. Support Contacts

| Issue | Contact |
|-------|---------|
| License activation | jude@wovenmodel.com |
| Bug reports | jude@wovenmodel.com |
| Custom development | jude@wovenmodel.com |
| General inquiries | https://wovenmodel.com |

---

*Stratum v1.3.0 | © Woven Model. All rights reserved. | This software is a decision-support tool. It does not place trades. Past performance does not guarantee future results.*
