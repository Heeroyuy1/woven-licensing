# Woven Model Licensing Server — Deployment Guide

**Version 1.3.0 | Stratum + Licensing Platform**

This guide covers production deployment of the Woven Model Licensing Server and the Stratum desktop application.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Option A: Docker Compose (Recommended)](#2-option-a-docker-compose-recommended)
3. [Option B: Bare Metal Installation](#3-option-b-bare-metal-installation)
4. [Generating Signing Keys](#4-generating-signing-keys)
5. [Environment Configuration](#5-environment-configuration)
6. [SSL / HTTPS Setup](#6-ssl--https-setup)
7. [Database Backup](#7-database-backup)
8. [Monitoring & Logging](#8-monitoring--logging)
9. [Upgrading](#9-upgrading)
10. [Security Checklist](#10-security-checklist)
11. [Performance Tuning](#11-performance-tuning)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Prerequisites

### Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4 cores |
| RAM | 2 GB | 4 GB |
| Disk | 10 GB | 20 GB (SSD) |
| Network | 100 Mbps | 1 Gbps |

### Software Requirements

- **Docker** 24.0+ and **Docker Compose** v2.20+ (for Option A)
- **Python** 3.10–3.12 (for Option B or bare-metal scripts)
- **Git** 2.30+
- **OpenSSL** 1.1+ or **certbot** (for SSL)

### Supported OS

- **Linux**: Ubuntu 22.04+, Debian 12+, RHEL 9+, Fedora 38+
- **macOS**: Ventura+ (development only — Docker Desktop)
- **Windows**: Server 2022+ (Docker Desktop + WSL2), or Windows 10/11 Pro for Docker

### Network Requirements

- Port **80** (HTTP) — accessible for ACME HTTP-01 challenges
- Port **443** (HTTPS) — production API and portal access
- Port **8000** (optional) — direct API access behind firewall
- Outbound access to package repositories (PyPI, Docker Hub)

---

## 2. Option A: Docker Compose (Recommended)

This is the fastest path to production.

### Step 1: Clone the Repository

```bash
git clone https://github.com/wovenmodel/licensing-server.git
cd licensing-server
```

### Step 2: Deploy with Docker Compose

```bash
# Deploy for production
docker compose -f docker-compose.yml --env-file .env.production up -d

# Check that everything is running
docker compose ps

# View logs
docker compose logs -f
```

### Step 3: Run the Deployment Script

Alternatively, use the deployment script from the `production/scripts/` directory:

**Linux/macOS:**
```bash
cd production/scripts/
chmod +x deploy.sh
./deploy.sh
```

**Windows:**
```cmd
cd production\scripts\
deploy.bat
```

The script will:
1. Check for Docker and Docker Compose
2. Create `.env.production` if missing
3. Generate signing keys
4. Prompt for domain name (for SSL)
5. Start the services
6. Seed the admin user

### Step 4: Seed Admin User

```bash
cd production/scripts/
python seed_admin.py --seed-products
```

If `ADMIN_PASSWORD` is not set, the script generates a random password and prints it.
**Save this password immediately.**

---

## 3. Option B: Bare Metal Installation

For environments where Docker is not available or you need direct control.

### Step 1: Set Up Python Environment

```bash
# Clone the repository
git clone https://github.com/wovenmodel/licensing-server.git
cd licensing-server/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Generate Signing Keys

```bash
cd ../scripts
python generate_keys.py
cd ../backend
```

### Step 3: Configure Environment

```bash
# Copy environment config
cp ../.env.example .env

# Edit with production values
nano .env  # or vi .env, or code .env
```

Key settings to change:
- `DATABASE_URL` — path to SQLite file (recommend `/var/lib/woven-licensing/data.db`)
- `SECRET_KEY` — long random string (use `openssl rand -hex 32`)
- `JWT_SECRET_KEY` — another long random string (use `openssl rand -hex 32`)
- `ADMIN_EMAIL` and `ADMIN_PASSWORD` — your admin credentials

### Step 4: Initialize Database

```bash
# Run the seed script
python scripts/seed_admin.py --seed-products
```

### Step 5: Start the Server

```bash
# Development (single worker, auto-reload)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Production (multiple workers)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 \
    --proxy-headers --forwarded-allow-ips "*" \
    --log-level info
```

### Step 6: Run as a Systemd Service (Linux)

Create `/etc/systemd/system/woven-licensing.service`:

```ini
[Unit]
Description=Woven Model Licensing Server
After=network.target

[Service]
User=woven
Group=woven
WorkingDirectory=/opt/woven-licensing/backend
EnvironmentFile=/opt/woven-licensing/backend/.env
ExecStart=/opt/woven-licensing/backend/venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 --port 8000 --workers 4 \
    --proxy-headers --forwarded-allow-ips "*"
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable woven-licensing
sudo systemctl start woven-licensing
sudo systemctl status woven-licensing
```

### Step 7: Set Up Nginx Reverse Proxy

Install nginx and copy the production config:

```bash
sudo apt install nginx
sudo cp production/licensing-server/nginx.conf /etc/nginx/conf.d/woven-licensing.conf
sudo systemctl restart nginx
```

---

## 4. Generating Signing Keys

The licensing server uses **Ed25519** cryptographic keys to sign license certificates.

### Using the Script

```bash
cd licensing-server/scripts
python generate_keys.py
```

This writes private and public keys to your `.env` file automatically.

### Manual Generation (OpenSSL)

```bash
# Generate private key
openssl genpkey -algorithm ed25519 -out private.pem

# Extract public key
openssl pkey -in private.pem -pubout -out public.pem

# Copy into .env
SIGNING_PRIVATE_KEY="$(cat private.pem | base64 -w0)"
SIGNING_PUBLIC_KEY="$(cat public.pem | base64 -w0)"
```

**Important:** The private key must be kept secret. If it is compromised, all existing
license certificates can be forged. Rotate compromised keys immediately by
generating new ones — this will invalidate all existing offline certificate caches.

---

## 5. Environment Configuration

The `.env.production` file controls all server behaviour. Key variables:

| Variable | Purpose | Default | Recommended |
|----------|---------|---------|-------------|
| `ENVIRONMENT` | Runtime mode | `development` | `production` |
| `DEBUG` | Verbose logging | `true` | `false` |
| `SECRET_KEY` | Session signing | auto-generated | 64-char random hex |
| `DATABASE_URL` | SQLite location | local file | `/app/data/woven_licensing.db` |
| `JWT_SECRET_KEY` | Token signing | auto-generated | 64-char random hex |
| `JWT_ALGORITHM` | Token algorithm | `HS256` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token TTL | `30` | `15` |
| `SIGNING_PRIVATE_KEY` | Ed25519 private key | (none) | from generate_keys.py |
| `SIGNING_PUBLIC_KEY` | Ed25519 public key | (none) | from generate_keys.py |
| `CORS_ORIGINS` | Allowed origins | `*` | Your domains |
| `DB_POOL_SIZE` | DB connections | `5` | `10` |
| `ADMIN_EMAIL` | Admin login email | `admin@wovenmodel.com` | Your email |
| `ADMIN_PASSWORD` | Admin login password | `admin` | Strong password |

### Environment File Template

```bash
cp .env.example .env.production
nano .env.production
```

---

## 6. SSL / HTTPS Setup

### Using Let's Encrypt + Certbot

```bash
# Install certbot (Ubuntu/Debian)
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d licensing.yourdomain.com --agree-tos -m jude@wovenmodel.com

# Auto-renewal is configured automatically
# Test renewal:
sudo certbot renew --dry-run
```

### Using the Deployment Script

```bash
cd production/scripts/
./deploy.sh
```

When prompted, enter your domain name and choose "Yes" for SSL setup.

### Manual Certificate Placement

Place your certificate files at:

```
/etc/letsencrypt/live/yourdomain.com/
├── fullchain.pem
├── privkey.pem
└── chain.pem
```

Then uncomment the HTTPS server block in `nginx.conf` and restart nginx:

```bash
sudo systemctl restart nginx
```

---

## 7. Database Backup

The licensing server stores data in a single SQLite file. Backups are critical.

### Automatic Backup Script

```bash
#!/bin/bash
# /usr/local/bin/backup-licensing.sh

BACKUP_DIR="/var/backups/woven-licensing"
DB_PATH="/var/lib/woven-licensing/data/woven_licensing.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# SQLite backup (safe for in-use databases)
sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/woven_licensing_$TIMESTAMP.db'"

# Compress
gzip "$BACKUP_DIR/woven_licensing_$TIMESTAMP.db"

# Keep last 30 days
find "$BACKUP_DIR" -name "*.db.gz" -mtime +30 -delete

echo "Backup completed: woven_licensing_$TIMESTAMP.db.gz"
```

### Schedule with Cron

```cron
# Run backup daily at 2 AM
0 2 * * * /usr/local/bin/backup-licensing.sh
```

### Restore from Backup

```bash
# Stop the server
docker compose down

# Restore database
cp /var/backups/woven-licensing/woven_licensing_20260701_020000.db \
   /var/lib/woven-licensing/data/woven_licensing.db

# Start the server
docker compose up -d
```

---

## 8. Monitoring & Logging

### Health Check Endpoint

```
GET /health
```

Response:
```json
{
    "status": "healthy",
    "version": "1.3.0",
    "uptime": "7d 12h 34m",
    "database": "connected",
    "last_backup": "2026-07-07T02:00:00Z"
}
```

### Logging

Docker Compose logs to stdout:
```bash
docker compose logs -f app
docker compose logs -f nginx
```

Log levels:
- `DEBUG` — Full detail (development only)
- `INFO` — Standard operations
- `WARNING` — Suspicious activity
- `ERROR` — Operational failures
- `CRITICAL` — System failures requiring immediate attention

### Prometheus Integration (Optional)

The server exposes `GET /metrics` if the `prometheus-client` package is installed.

### Typical Log Messages

| Message | Severity | Meaning |
|---------|----------|---------|
| `License activated: ABCDE-12345` | INFO | New activation |
| `Validation failed: machine not found` | WARNING | Possible misuse |
| `Database connection lost, reconnecting` | ERROR | SQLite locked or disk full |
| `Rate limit exceeded for IP 192.168.1.100` | WARNING | Possible brute-force attempt |

---

## 9. Upgrading

### Docker Compose Upgrade

```bash
# Pull latest images and restart
docker compose pull
docker compose up -d --force-recreate

# Check for issues
docker compose logs -f --tail=50
```

### Database Migrations

The server uses SQLAlchemy ORM with auto-migration on startup.
In production, always back up the database before upgrading:

```bash
sqlite3 /path/to/woven_licensing.db ".backup /backups/pre_upgrade_$(date +%Y%m%d).db"
```

### Version Checks

Run the health endpoint to verify the new version:

```bash
curl http://localhost:8000/health | python -m json.tool
```

---

## 10. Security Checklist

- [ ] **Change default admin password** — never use `admin` in production
- [ ] **Generate strong `SECRET_KEY`** — at least 64 hex characters
- [ ] **Generate strong `JWT_SECRET_KEY`** — at least 64 hex characters
- [ ] **Restrict `CORS_ORIGINS`** — only your known domains
- [ ] **Enable HTTPS** — use Let's Encrypt or your own certificate
- [ ] **Set `DEBUG=false`** — never expose debug info in production
- [ ] **Use `ADMIN_PASSWORD` env var** — set your own, don't rely on auto-generation
- [ ] **Protect signing keys** — the `SIGNING_PRIVATE_KEY` must never be leaked
- [ ] **Rate limiting** — nginx config limits activation attempts
- [ ] **Database backups** — automated daily or more frequent
- [ ] **Monitor logs** — watch for repeated failed validation attempts
- [ ] **Keep secrets out of git** — `.env.production` is in `.gitignore`
- [ ] **Use non-root user** — Docker container runs as `woven` user
- [ ] **Regular updates** — keep Docker images and OS patched

---

## 11. Performance Tuning

### SQLite Optimization

```sql
PRAGMA journal_mode=WAL;           -- Write-Ahead Logging for concurrent reads
PRAGMA synchronous=NORMAL;         -- Balance safety and performance
PRAGMA cache_size=-64000;          -- 64 MB page cache
PRAGMA foreign_keys=ON;            -- Enforce relationships
PRAGMA busy_timeout=5000;          -- Wait up to 5 seconds when locked
```

These are set automatically on startup.

### Uvicorn Workers

```bash
# Number of workers = 2 × (number of CPU cores) + 1
uvicorn app.main:app --workers 9  # for a 4-core machine
```

### Nginx Tuning

The production nginx config sets:
- `gzip` compression for API responses
- `keepalive` connections to the upstream
- Proxy buffering to reduce backend load

### Connection Pool

Adjust based on expected concurrent users:

```ini
DB_POOL_SIZE=10        # Steady state connections
DB_MAX_OVERFLOW=20     # Max connections under load
```

### Load Testing

```bash
# Using Apache Bench (ab)
ab -n 1000 -c 10 http://localhost:8000/health

# Using hey
hey -n 1000 -c 10 http://localhost:8000/health
```

Expected throughput: 500+ requests/second on a 4-core machine.

---

## 12. Troubleshooting

### Server Won't Start

| Symptom | Cause | Solution |
|---------|-------|----------|
| `Address already in use` | Port 8000 busy | `sudo lsof -i :8000` then kill process |
| `No module named 'app'` | Wrong working directory | `cd /path/to/backend` then run |
| `Cannot open database` | SQLite directory missing | `mkdir -p /app/data` |
| `Invalid signing key` | Keys not generated | Run `python scripts/generate_keys.py` |

### Docker Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| `docker: command not found` | Docker not installed | Install Docker Desktop |
| `Permission denied` | User not in docker group | `sudo usermod -aG docker $USER` |
| `Port already allocated` | Port conflict | Change host port in docker-compose.yml |
| `Container exits immediately` | Startup error | `docker compose logs app` |

### Authentication Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| `401 Unauthorized` | Wrong credentials | Check `ADMIN_EMAIL`/`ADMIN_PASSWORD` in `.env` |
| `Token expired` | Long idle time | Refresh token or re-login |
| `Session invalid` | Server restart | Tokens invalidated, re-login |

### Licensing Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| `License key not found` | Wrong key | Generate a new key for the correct product |
| `Maximum activations reached` | Too many devices | Deactivate one or increase max_activations |
| `Machine blacklisted` | Abuse detection | Unblacklist via admin API |
| `Certificate expired` | Clock skew | Check server time, NTP sync |

### Getting Help

If the above doesn't resolve your issue:

| Resource | Contact |
|----------|---------|
| **Email** | jude@wovenmodel.com |
| **Web** | https://wovenmodel.com |
| **Bug Reports** | Include full logs from `docker compose logs` |

---

*Woven Model Licensing Server v1.3.0 | © Woven Model. All rights reserved.*
*Support: jude@wovenmodel.com*
