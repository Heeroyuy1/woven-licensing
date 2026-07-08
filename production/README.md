# Woven Model — Production Deployment

**AI Trading Strategy Analyzer + Licensing Platform**

This package contains everything needed to deploy **Stratum** (the desktop app) and the **Licensing Server** in production.

---

## Project Structure (Full)

```
C:\Woven Model\Development\AI & Automation\End Product\
│
├── Backtesting Bot/                         # Harper — Legacy backtesting engine (dev tool)
│   ├── core/                                # Data loading, strategy runner, paper broker
│   ├── strategies/                          # RSI+SMA, MACD, Bollinger, SMA crossover
│   ├── patterns/                            # Statistical pattern discovery engine
│   ├── optimizer/                           # Grid search parameter optimizer
│   ├── reporting/                           # Dashboard HTML generator
│   ├── reports/                             # Generated dashboard HTML + logo assets
│   ├── data/                                # Parquet market data cache
│   ├── logs/                                # Trade and signal logs
│   ├── main.py                              # CLI entry point for backtesting
│   └── server.py                            # Flask web server (port 5000)
│
├── stratum/                                 # ★ Stratum Desktop App (final product)
│   ├── app.py                               # Application entry point (PyQt6)
│   ├── assets/                              # Brand assets
│   │   ├── logo.png                         # Woven Model waveform logo
│   │   └── icon.ico                         # Windows application icon
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config_manager.py                # Strategy profiles & settings
│   │   ├── data_loader.py                   # Market data (Yahoo Finance + Parquet)
│   │   ├── broker.py                        # Paper trading engine
│   │   ├── strategy_engine.py               # Bar-by-bar backtest engine
│   │   ├── optimizer.py                     # Grid search optimizer
│   │   ├── ai_analysis.py                   # AI recommendation engine (0-100 scores)
│   │   ├── reporting.py                     # PDF, Excel, CSV, JSON export
│   │   ├── licensing.py                     # License key validation & activation
│   │   └── logger.py                        # Logging system
│   ├── ui/
│   │   └── main_window.py                   # PyQt6 desktop UI (all tabs)
│   ├── data/                                # Cached market data (Parquet)
│   ├── logs/                                # Application logs
│   ├── reports/                             # Generated reports & exports
│   └── profiles/                            # Saved strategy profiles (JSON)
│
├── licensing-server/                        # Licensing API (FastAPI backend)
│   ├── backend/
│   │   └── app/
│   │       ├── main.py                      # FastAPI entry point (port 8000)
│   │       ├── config.py                    # Environment-based configuration
│   │       ├── database.py                  # SQLAlchemy async engine
│   │       ├── models/                      # SQLAlchemy ORM models
│   │       │   ├── user.py                  # User accounts (admin/customer)
│   │       │   ├── product.py               # Software products
│   │       │   ├── license.py               # License keys & statuses
│   │       │   ├── machine.py               # Registered device fingerprints
│   │       │   ├── activation.py            # License-to-machine bindings
│   │       │   ├── subscription.py          # Recurring billing
│   │       │   ├── audit.py                 # Immutable audit log
│   │       │   └── api_token.py             # API access tokens
│   │       ├── schemas/                     # Pydantic validation schemas
│   │       │   ├── auth.py                  # Login/register/refresh
│   │       │   ├── license.py               # Activate/validate/deactivate
│   │       │   ├── admin.py                 # Admin operations
│   │       │   └── customer.py              # Customer portal
│   │       ├── services/                    # Business logic
│   │       │   ├── auth_service.py          # JWT auth, password hashing
│   │       │   ├── license_service.py       # License CRUD, activation logic
│   │       │   ├── crypto.py                # Ed25519 signing
│   │       │   └── fingerprint.py           # Machine fingerprinting
│   │       └── api/v1/                      # Route handlers
│   │           ├── auth.py                  # POST /auth/login, /register, /refresh
│   │           ├── licensing.py             # POST /activate, /validate, /deactivate
│   │           ├── admin.py                 # GET/POST admin endpoints
│   │           ├── customer.py              # Customer portal endpoints
│   │           └── products.py              # Product listing endpoints
│   ├── nginx/
│   │   └── nginx.conf                       # Production reverse proxy + SSL
│   ├── scripts/
│   │   ├── generate_keys.py                 # Ed25519 keypair generator
│   │   └── init_db.py                       # Database initialization
│   ├── alembic/                             # Database migrations
│   │   ├── env.py                           # Alembic environment
│   │   └── versions/                        # Migration scripts
│   ├── client-sdk/
│   │   └── woven_license/                   # Python SDK for desktop apps
│   ├── docs/
│   │   ├── RUN_BOOK.md                      # Operations run book
│   │   └── PLAYBOOK.md                      # Strategy & tactics guide
│   ├── requirements.txt
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── production/                              # ★ Production deployment
│   ├── README.md                            # This file
│   ├── stratum/                             # Stratum packaging
│   │   ├── build_msi.py                     # PyInstaller + WiX MSI builder
│   │   ├── stratum.wxs                      # WiX installer config
│   │   └── install_guide.md                 # Installation guide
│   ├── licensing-portal/                    # Web-based admin portal
│   │   ├── index.html                       # SPA admin dashboard
│   │   ├── login.html                       # Authentication page
│   │   ├── logo.png                         # Woven Model waveform logo
│   │   ├── favicon.ico                      # Browser tab icon
│   │   ├── css/
│   │   │   └── portal.css                   # Complete design system
│   │   ├── js/
│   │   │   ├── portal.js                    # Main app logic (SPA)
│   │   │   └── api.js                       # Licensing API client
│   │   ├── docker-compose.yml               # Full-stack (API + nginx + portal)
│   │   └── nginx.conf                       # Portal reverse proxy config
│   ├── licensing-server/                    # Server deployment files
│   │   ├── .env.production                  # Production environment config
│   │   ├── docker-compose.yml               # Server-only deployment
│   │   ├── Dockerfile                       # Production Docker build
│   │   └── nginx.conf                       # Production nginx config
│   ├── docs/
│   │   ├── RUN_BOOK.md                      # Operations run book
│   │   ├── PLAYBOOK.md                      # Strategy & tactics guide
│   │   ├── DEPLOYMENT.md                    # Deployment instructions
│   │   └── API.md                           # Full API reference
│   └── scripts/
│       ├── deploy.bat                       # Windows one-click deploy
│       ├── deploy.sh                        # Linux one-click deploy
│       ├── seed_admin.py                    # Admin user seed
│       ├── license_cli.py                   # License management CLI
│       └── create_test_license.py           # Test license generator
│
├── Back Testing Bot Based ON live/          # Reference trading bot (Conquest Engine)
│   ├── TradingBackTestingLIVE.py            # Live trading script
│   ├── config5.json / config6.json          # Trading configurations
│   └── Conquest_Config_Reference.pdf        # Original bot documentation
│
├── config/                                  # Shared backtest configs
│   └── backtest_config.json                 # Default configuration
├── data/                                    # Shared market data cache
├── logs/                                    # Shared trade logs
├── reports/                                 # Shared generated reports
├── show_logos.html                          # Logo comparison tester (temp)
└── run_stratum.bat                          # Stratum quick-launch script
```

---

## Component Overview

### Stratum Desktop App (`stratum/`)
The final end-user product — a PyQt6 desktop application for backtesting trading strategies with AI-powered analysis.

| Module | Purpose |
|--------|---------|
| `app.py` | Entry point; launches PyQt6 main window |
| `core/config_manager.py` | Load/save strategy profiles and per-symbol parameters |
| `core/data_loader.py` | Fetches market data from Yahoo Finance, caches as Parquet |
| `core/broker.py` | Paper trading engine with position sizing and risk management |
| `core/strategy_engine.py` | Bar-by-bar backtest simulator supporting multiple strategies |
| `core/optimizer.py` | Grid search across parameter space to find optimal settings |
| `core/ai_analysis.py` | Rates symbols 0-100 across 5 dimensions; generates recommendations |
| `core/reporting.py` | Exports results as PDF, Excel, CSV, JSON |
| `core/licensing.py` | Validates license keys, manages activations, enforces trial limits |
| `ui/main_window.py` | Complete desktop UI with 9 tabs (Dashboard, Backtest, AI, etc.) |
| `assets/logo.png` | **Woven Model waveform brand logo** |

### Licensing Server (`licensing-server/`)
FastAPI-based REST API that manages license activation, validation, and customer accounts. Deployed alongside the licensing portal.

| Endpoint | Purpose |
|----------|---------|
| `POST /auth/login` | User authentication, returns JWT tokens |
| `POST /auth/register` | Create new customer accounts |
| `POST /auth/refresh` | Refresh expired access tokens |
| `POST /activate` | Activate a license key on a machine |
| `POST /validate` | Validate an active license (online or offline) |
| `POST /deactivate` | Release a machine from a license |
| `POST /transfer` | Transfer license between machines |
| `GET /check-updates` | Check for newer product versions |
| `GET/POST /admin/*` | Admin CRUD for users, licenses, machines |

### Licensing Portal (`production/licensing-portal/`)
Browser-based admin dashboard for managing licenses, users, and machines. Serves as the frontend to the Licensing API.

| File | Purpose |
|------|---------|
| `index.html` | Single-page application (Dashboard, Licenses, Users, Machines, Logs, Settings) |
| `login.html` | Standalone authentication page |
| `logo.png` | **Woven Model waveform brand logo** |
| `css/portal.css` | Complete design system matching wovenmodel.com brand |
| `js/portal.js` | SPA logic: routing, data loading, CRUD operations |
| `js/api.js` | HTTP client for all Licensing API endpoints |

### Harper Engine (`Backtesting Bot/`)
Legacy backtesting and pattern discovery engine. Functionally superseded by Stratum, but still used independently for quick analysis and pattern detection.

| Module | Purpose |
|--------|---------|
| `main.py` | CLI entry point for backtest + pattern discovery |
| `server.py` | Flask web server (port 5000) for interactive dashboard |
| `core/strategy_runner.py` | Multi-strategy backtest runner |
| `core/paper_broker.py` | Paper trading with commissions & slippage |
| `core/data_loader.py` | Market data fetching and caching |
| `patterns/detector.py` | Statistical pattern discovery (seasonal, day-of-week, volume spikes) |
| `reporting/dashboard.py` | HTML dashboard generator with Chart.js |

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────┐
│                    Stratum Desktop                        │
│                   (PyQt6 Application)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │Backtest  │  │ AI       │  │Optimize  │  │ Reports  │  │
│  │Engine    │  │Analysis  │  │Engine    │  │Export    │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
│       │              │              │              │        │
│  ┌────▼──────────────▼──────────────▼──────────────▼────┐  │
│  │            Licensing Client (woven_license SDK)      │  │
│  └────────────────────────┬────────────────────────────┘  │
└───────────────────────────┼──────────────────────────────┘
                            │ HTTPS
                            ▼
┌───────────────────────────────────────────────────────────┐
│                   Nginx Reverse Proxy                      │
│              licensing.wovenmodel.com:443                  │
└────────────────────┬─────────────────────┬────────────────┘
                     │ /api/*               │ /*
                     ▼                      ▼
┌────────────────────────────┐  ┌──────────────────────────────┐
│    Licensing API Server    │  │    Licensing Portal           │
│    (FastAPI, port 8000)    │  │    (Static HTML/JS, nginx)   │
│  ┌──────────────────────┐  │  │  ┌─────────────────────────┐  │
│  │  Ed25519 Signing     │  │  │  │ Dashboard  │  Login     │  │
│  │  JWT Auth            │  │  │  │ Licenses   │  Settings  │  │
│  │  License CRUD        │  │  │  │ Users      │  Logs      │  │
│  │  Machine Binding     │  │  │  └─────────────────────────┘  │
│  └──────────────────────┘  │  └──────────────────────────────┘
│  ┌──────────────────────┐  │
│  │  SQLite/PostgreSQL   │  │
│  │  + Alembic Migrations│  │
│  └──────────────────────┘  │
└────────────────────────────┘
```

---

## Environment Overview

| Environment | Purpose | Ports |
|-------------|---------|-------|
| **Stratum Desktop** | Local desktop app (PyQt6) | N/A (GUI only) |
| **Licensing API** | REST API server | 8000 |
| **Licensing Portal** | Web admin dashboard | 3000 (dev) / 443 (prod) |
| **Harper Server** | Legacy backtest web UI | 5000 |

---

## Quick Start

### Development

```bash
# Stratum Desktop
cd stratum
pip install -r requirements.txt
python app.py

# Licensing API
cd licensing-server
pip install -r requirements.txt
cd backend
uvicorn app.main:app --reload --port 8000

# Licensing Portal (dev server)
cd production/licensing-portal
python -m http.server 3000

# Harper (legacy)
cd "Backtesting Bot"
pip install -r requirements.txt
python server.py    # Port 5000
```

### Production

```bash
# Full-stack licensing + portal
cd production/licensing-portal
docker-compose up -d

# Stratum MSI installer
cd production/stratum
python build_msi.py
```

---

## Brand Assets

The **Woven Model waveform logo** (`logo.png`) is used across all components:

| Location | Usage |
|----------|-------|
| `stratum/assets/logo.png` | Stratum desktop app header icon |
| `production/licensing-portal/logo.png` | Licensing portal login page + sidebar |
| `Backtesting Bot/reports/harper-logo.png` | Harper dashboard (legacy) |

All instances reference the same source: `C:\Woven Model\WebPage\assets\logo.png`

---

## Support

- **Email**: jude@wovenmodel.com
- **Web**: https://wovenmodel.com

*© Woven Model. All rights reserved. v1.3.0*
