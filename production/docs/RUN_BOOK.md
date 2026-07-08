# Woven Model Licensing Server — Operations Run Book

**Version 1.3.0 | Stratum + Licensing Platform**

The run book contains procedures that operations staff follow to keep the
licensing server running, diagnose issues, and perform maintenance.

---

## 1. System Overview

### Architecture

```
                    ┌──────────────────────┐
                    │   Internet / VPN      │
                    └──────┬───────────────┘
                           │ Port 80/443
                    ┌──────▼───────────────┐
                    │   Nginx (Reverse      │
                    │   Proxy + SSL)        │
                    └──────┬───────────────┘
                           │ upstream
                    ┌──────▼───────────────┐
                    │  FastAPI / Uvicorn    │
                    │  (Licensing API)      │
                    └──────┬───────────────┘
                           │
                    ┌──────▼───────────────┐
                    │  SQLite / aiiosqlite  │
                    │  (woven_licensing.db) │
                    └──────────────────────┘
```

### Services

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| **app** | `licensing-app` | 8000 | FastAPI licensing API |
| **nginx** | `licensing-nginx` | 80/443 | Reverse proxy, SSL, rate limiting |

### Data Flow

1. **Stratum Desktop** sends activation request to `/api/v1/activate`
2. **Nginx** rate-limits the request (30 req/min for activation)
3. **FastAPI** validates the license key against the database
4. **Server** generates a machine fingerprint, creates activation record
5. **Server** signs an Ed25519 certificate and returns it
6. **Stratum** caches the certificate for offline validation

### Key Locations (Container)

| Path | Purpose |
|------|---------|
| `/app/` | Application code |
| `/app/data/woven_licensing.db` | SQLite database |
| `/app/data/signing_private.pem` | Ed25519 private key |
| `/app/data/signing_public.pem` | Ed25519 public key |
| `/var/log/` | System logs |
| `/etc/nginx/conf.d/` | Nginx config |

---

## 2. Starting & Stopping the Server

### Start All Services

```bash
cd /opt/woven-licensing
docker compose --env-file .env.production up -d
```

### Stop All Services

```bash
docker compose down
```

### Stop and Remove Volumes (destructive)

```bash
docker compose down -v
# Deletes all database data! Only use for testing.
```

### Restart a Single Service

```bash
docker compose restart app
docker compose restart nginx
```

### Check Status

```bash
docker compose ps
docker compose logs --tail=50 -f
```

---

## 3. Monitoring Health Checks

### Automated Health Check

The server exposes a health endpoint that should be polled every 30 seconds:

```
GET /health
```

**Expected response:**
```json
{
    "status": "healthy",
    "version": "1.3.0"
}
```

### Docker Container Health

```bash
# Check container health status
docker inspect --format='{{json .State.Health}}' licensing-app

# Watch health status
watch -n 5 docker ps --filter name=licensing
```

### Uptime Monitoring

Configure external monitoring (e.g., UptimeRobot, Pingdom, Grafana) to:

1. **HTTP check**: `https://yourdomain.com/health` — expect 200
2. **SSL check**: Ensure certificate > 30 days from expiry
3. **Response time**: Alert if > 2 seconds

### Log Monitoring

Watch for these patterns in logs:

```bash
# Real-time error monitoring
docker compose logs -f app | grep -E "(ERROR|CRITICAL|WARNING)"

# Activation failures (possible brute force)
docker compose logs -f nginx | grep "429"

# Database errors
docker compose logs -f app | grep "database"
```

---

## 4. Viewing Logs

### Application Logs

```bash
# All app logs
docker compose logs app

# Last 100 lines
docker compose logs --tail=100 app

# Follow (streaming)
docker compose logs -f app

# Filter by log level
docker compose logs app | grep -E "(INFO|WARNING|ERROR)"
```

### Nginx Access Logs

```bash
docker compose logs nginx

# Watch for 4xx/5xx errors
docker compose logs -f nginx | grep -E '" 4[0-9]{2} |" 5[0-9]{2} '

# Rate limiting hits
docker compose logs -f nginx | grep "limiting requests"
```

### Query Logs by Date

```bash
# Logs from the last 15 minutes
docker compose logs --since=15m app
```

---

## 5. Backup & Restore

### Automated Daily Backup

The recommended backup procedure uses SQLite's `.backup` command,
which is safe for in-use databases.

**Backup script** (`/usr/local/bin/backup-licensing.sh`):

```bash
#!/bin/bash
BACKUP_DIR="/var/backups/woven-licensing"
DB_PATH="/var/lib/docker/volumes/woven-licensing_licensing_db/_data/woven_licensing.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Verify DB exists
if [ ! -f "$DB_PATH" ]; then
    echo "ERROR: Database not found at $DB_PATH"
    exit 1
fi

# Backup with compression
sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/woven_licensing_$TIMESTAMP.db'"
gzip "$BACKUP_DIR/woven_licensing_$TIMESTAMP.db"

# Keep last 30 days, remove older
find "$BACKUP_DIR" -name "*.db.gz" -mtime +30 -delete

echo "OK: Backup saved to $BACKUP_DIR/woven_licensing_$TIMESTAMP.db.gz"
```

**Cron schedule** (`/etc/cron.d/woven-licensing-backup`):

```
0 2 * * * root /usr/local/bin/backup-licensing.sh
```

### Manual Backup

```bash
# Stop the app (keeps nginx running for static portal)
docker compose stop app

# Backup DB
cp /var/lib/docker/volumes/woven-licensing_licensing_db/_data/woven_licensing.db \
   /backup/woven_licensing_$(date +%Y%m%d).db

# Also backup .env and signing keys
cp /opt/woven-licensing/.env.production /backup/
cp /opt/woven-licensing/signing_private.pem /backup/

# Restart app
docker compose start app
```

### Restore from Backup

```bash
# Stop all services
docker compose down

# Restore database to the docker volume location
cp /backup/woven_licensing_20260706.db \
   /var/lib/docker/volumes/woven-licensing_licensing_db/_data/woven_licensing.db

# Restart
docker compose --env-file .env.production up -d

# Verify
curl http://localhost:8000/health
```

---

## 6. Adding a New Product

Products define what license keys can be generated for. To add a new product:

### Via Admin API

```bash
curl -X POST http://localhost:8000/api/v1/admin/products \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <admin-token>" \
  -d '{
    "name": "My New Product",
    "code": "NEW_PRODUCT",
    "description": "Description of the product"
  }'
```

Alternatively, use the seed script:

```bash
python production/scripts/seed_admin.py --seed-products
```

Edit `product/scripts/seed_admin.py` and add your product to the `DEFAULT_PRODUCTS` list.

---

## 7. Creating a License for a Customer

### Via Admin API

```bash
curl -X POST http://localhost:8000/api/v1/admin/licenses/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <admin-token>" \
  -d '{
    "product_code": "STRATUM",
    "user_id": 1,
    "license_type": "perpetual",
    "max_activations": 3,
    "feature_flags": ["all"]
  }'
```

### Via CLI

```bash
python production/scripts/license_cli.py generate \
  --product STRATUM \
  --user 1 \
  --type perpetual
```

### Via Portal

1. Log in to the management portal
2. Go to **Licenses** tab
3. Click **Generate License**
4. Select product, enter user ID, choose type
5. Click **Generate License**
6. Copy the key and send to the customer

---

## 8. Revoking / Resetting Activations

### Revoke a License (permanently disable)

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/admin/licenses/1/revoke \
  -H "Authorization: Bearer <admin-token>"

# Via CLI
python production/scripts/license_cli.py revoke <key>
```

### Reset Activations (unlock max activation limit)

```bash
curl -X POST http://localhost:8000/api/v1/admin/licenses/1/reset-activations \
  -H "Authorization: Bearer <admin-token>"
```

This sets `current_activations` to 0, allowing the customer to activate again.

---

## 9. Blacklisting a Machine

Use this if a customer's machine is compromised or involved in abuse.

### Via API

```bash
curl -X POST http://localhost:8000/api/v1/admin/machines/1/blacklist \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <admin-token>" \
  -d '{"is_blacklisted": true}'
```

### Via Portal

1. Go to **Machines** tab in the portal
2. Find the machine by fingerprint or hostname
3. Toggle the blacklist switch

### Effects

- Blacklisted machines cannot activate any licenses
- Existing activations on blacklisted machines will fail validation
- The machine will receive error messages indicating it is blacklisted

---

## 10. Exporting Data

### Via API

```bash
# Export all licenses as JSON
curl -H "Authorization: Bearer <admin-token>" \
  http://localhost:8000/api/v1/admin/export?export_type=licenses

# Export users
curl -H "Authorization: Bearer <admin-token>" \
  http://localhost:8000/api/v1/admin/export?export_type=users
```

### Via Portal

1. Go to **Settings** tab
2. Click **Export Data**
3. Choose: Licenses, Users, Machines, or All Data
4. A JSON file will be downloaded

### Manual Database Export

```bash
# Dump entire database to SQL
sqlite3 /path/to/woven_licensing.db .dump > /backup/export_$(date +%Y%m%d).sql

# Export specific table to CSV
sqlite3 /path/to/woven_licensing.db -header -csv \
  "SELECT * FROM licenses;" > /backup/licenses.csv
```

---

## 11. Emergency Procedures

### Database Corruption

**Symptom:** Health check returns `database: disconnected` or API calls return 500 with SQL errors.

**Procedure:**
1. Stop the server: `docker compose stop app`
2. Attempt to run integrity check:
   ```bash
   sqlite3 /path/to/woven_licensing.db "PRAGMA integrity_check;"
   ```
3. If corruption is detected, restore from the latest backup (see section 5)
4. If no backup exists, try to recover with `.recover`:
   ```bash
   sqlite3 /path/to/woven_licensing.db ".recover" | sqlite3 /path/to/recovered.db
   ```
5. Start the server with the recovered database
6. Conduct a full audit of all licenses after recovery

### Server Overload

**Symptom:** High response times, connection timeouts.

**Procedure:**
1. Check active connections:
   ```bash
   docker compose logs --tail=100 app | grep "connected"
   ```
2. Check resource usage:
   ```bash
   docker stats licensing-app
   ```
3. Increase worker count in docker-compose.yml
4. If sustained, add a caching layer (Redis) between nginx and FastAPI
5. Consider scaling horizontally with multiple app instances

### Security Breach (Signing Key Compromised)

**Symptom:** Suspicious activity, counterfeit license certificates.

**Procedure:**
1. **Immediately** generate new signing keys:
   ```bash
   python scripts/generate_keys.py --force
   ```
2. Restart the server to pick up new keys:
   ```bash
   docker compose restart app
   ```
3. **All existing offline certificates are now invalid.** Users must re-activate.
4. Audit for forged certificates by checking activation timestamps
5. Rotate all admin passwords
6. Investigate the breach vector

### Rate Limit Lockout

**Symptom:** Legitimate users getting 429 Too Many Requests.

**Procedure:**
1. Check nginx rate limit logs:
   ```bash
   docker compose logs nginx | grep "limiting requests"
   ```
2. Temporarily increase limits in nginx.conf:
   ```
   limit_req_zone $binary_remote_addr zone=activate:10m rate=60r/m;
   ```
3. Reload nginx: `docker compose exec nginx nginx -s reload`
4. Investigate the cause of traffic surge
5. If legitimate, update the rate limit permanently
6. If malicious, identify and block the offending IPs via firewall

---

## 12. Support Escalation

| Severity | Definition | Response Time | Contact |
|----------|-----------|--------------|---------|
| **SEV-1** | Complete outage, all licensing fails | 1 hour | jude@wovenmodel.com + phone |
| **SEV-2** | Partial outage, key features impacted | 4 hours | jude@wovenmodel.com |
| **SEV-3** | Minor issues, workaround available | 24 hours | jude@wovenmodel.com |
| **SEV-4** | Feature requests, non-urgent | Next release | https://wovenmodel.com |

### Before Escalating

1. Have you checked the health endpoint? `curl http://localhost:8000/health`
2. Have you checked the logs? `docker compose logs --tail=50 app`
3. Have you checked the database? `sqlite3 /path/to/db "PRAGMA integrity_check;"`
4. Have you restored from backup? See section 5
5. Have you restarted the service? `docker compose restart app`

---

*Woven Model Licensing Server v1.3.0 | © Woven Model. All rights reserved.*
*Support: jude@wovenmodel.com*
