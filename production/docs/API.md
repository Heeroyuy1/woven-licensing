# Woven Model Licensing Server — API Reference

**Version 1.3.0 | REST API | JSON**

Base URL: `http://localhost:8000/api/v1` (or your deployed domain)

---

## Authentication

Most endpoints require a JWT Bearer token in the `Authorization` header.

### POST `/api/v1/auth/login`

Authenticate with email and password.

**Request:**
```json
{
    "email": "admin@wovenmodel.com",
    "password": "your-password"
}
```

**Response (200):**
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 1800,
    "user": {
        "id": 1,
        "email": "admin@wovenmodel.com",
        "role": "admin"
    }
}
```

**curl example:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@wovenmodel.com", "password": "admin123!"}'
```

### POST `/api/v1/auth/register`

Register a new user account.

**Request:**
```json
{
    "email": "user@example.com",
    "password": "secure-password",
    "name": "User Name"
}
```

**Response (201):**
```json
{
    "id": 2,
    "email": "user@example.com",
    "name": "User Name",
    "role": "user",
    "created_at": "2026-07-07T12:00:00Z"
}
```

### POST `/api/v1/auth/refresh`

Refresh an expired token.

**Request:**
```json
{
    "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response (200):**
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 1800
}
```

---

## Licensing Endpoints

### POST `/api/v1/activate`

Activate a license key on a machine. This is the endpoint called by the
Stratum desktop app when the user enters their license key.

**Request:**
```json
{
    "license_key": "ABCDE-FGHIJ-KLMNO-PQRST",
    "fingerprint": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    "fingerprint_data": {
        "machine_guid": "550e8400-e29b-41d4-a716-446655440000",
        "hostname": "DESKTOP-ABC123",
        "operating_system": "Windows 11 Pro",
        "cpu_identifier": "Intel64 Family 6 Model 186",
        "motherboard_uuid": "12345678-1234-1234-1234-123456789abc",
        "disk_serial": "WD-WCC4E5HV6V7S",
        "bios_uuid": "87654321-4321-4321-4321-cba987654321"
    },
    "ip_address": "192.168.1.100",
    "application_version": "1.3.0"
}
```

Either `fingerprint` (pre-computed hash) or `fingerprint_data` is required.
If both are provided, `fingerprint` takes precedence.

**Response (200):**
```json
{
    "success": true,
    "message": "License activated successfully",
    "certificate": {
        "certificate": {
            "license_key": "ABCDE-FGHIJ-KLMNO-PQRST",
            "license_type": "perpetual",
            "status": "active",
            "product_id": 1,
            "user_id": 1,
            "expiration_date": null,
            "perpetual": true,
            "offline_days": 7,
            "max_activations": 3,
            "current_activations": 1,
            "feature_flags": ["all"],
            "machine_fingerprint": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            "machine_hostname": "DESKTOP-ABC123",
            "activation_date": "2026-07-07T12:00:00",
            "last_validation": "2026-07-07T12:00:00",
            "metadata": {},
            "issued_by": "Woven Model Licensing Server"
        },
        "signature": "R29vZCBqb2IhIEhlcmUgaXMgdGhlIHNpZ25lZCBjZXJ0aWZpY2F0ZSBkYXRhLi4u"
    }
}
```

**curl example:**
```bash
curl -X POST http://localhost:8000/api/v1/activate \
  -H "Content-Type: application/json" \
  -d '{
    "license_key": "ABCDE-FGHIJ-KLMNO-PQRST",
    "fingerprint": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
  }'
```

### POST `/api/v1/validate`

Validate an active license on a machine.

**Request:**
```json
{
    "license_key": "ABCDE-FGHIJ-KLMNO-PQRST",
    "fingerprint": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    "signature_b64": "optional-signed-certificate-for-offline-validation"
}
```

**Response (200):**
```json
{
    "valid": true,
    "message": "Valid",
    "certificate": {
        "certificate": {
            "license_key": "ABCDE-FGHIJ-KLMNO-PQRST",
            ...
        },
        "signature": "..."
    }
}
```

**Response when invalid:**
```json
{
    "valid": false,
    "message": "License key not found",
    "certificate": null
}
```

**curl example:**
```bash
curl -X POST http://localhost:8000/api/v1/validate \
  -H "Content-Type: application/json" \
  -d '{
    "license_key": "ABCDE-FGHIJ-KLMNO-PQRST",
    "fingerprint": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
  }'
```

### POST `/api/v1/deactivate`

Deactivate a license on a specific machine, freeing an activation slot.

**Request:**
```json
{
    "license_key": "ABCDE-FGHIJ-KLMNO-PQRST",
    "fingerprint": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
}
```

**Response (200):**
```json
{
    "success": true,
    "message": "Deactivated"
}
```

**curl example:**
```bash
curl -X POST http://localhost:8000/api/v1/deactivate \
  -H "Content-Type: application/json" \
  -d '{
    "license_key": "ABCDE-FGHIJ-KLMNO-PQRST",
    "fingerprint": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
  }'
```

### POST `/api/v1/transfer`

Transfer a license from one machine to another.

**Request:**
```json
{
    "license_key": "ABCDE-FGHIJ-KLMNO-PQRST",
    "old_fingerprint": "old-machine-fingerprint-hash",
    "new_fingerprint_data": {
        "machine_guid": "new-machine-uuid",
        "hostname": "NEW-PC",
        "operating_system": "Windows 11 Pro",
        "cpu_identifier": "...",
        "disk_serial": "..."
    }
}
```

**Response (200):**
```json
{
    "success": true,
    "message": "License transferred",
    "certificate": {
        "certificate": { ... },
        "signature": "..."
    }
}
```

### POST `/api/v1/renew`

Extend the expiration of a license.

**Request:**
```json
{
    "license_id": 1,
    "extra_days": 365
}
```

**Response (200):**
```json
{
    "success": true,
    "message": "License renewed to 2027-07-07"
}
```

### GET `/api/v1/check-updates`

Check if a newer version of an application is available.

**Query parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `current_version` | string | Version string (e.g. "1.2.0") |
| `product_code` | string | Product identifier (e.g. "STRATUM") |

**Response (200):**
```json
{
    "update_available": true,
    "current_version": "1.2.0",
    "latest_version": "1.3.0",
    "release_date": "2026-07-01",
    "download_url": "https://wovenmodel.com/downloads/stratum-1.3.0.msi",
    "release_notes": "Bug fixes, performance improvements"
}
```

**curl example:**
```bash
curl "http://localhost:8000/api/v1/check-updates?current_version=1.2.0&product_code=STRATUM"
```

### GET `/api/v1/license/{key}`

Get detailed license information by key.

**Response (200):**
```json
{
    "id": 1,
    "license_key": "ABCDE-FGHIJ-KLMNO-PQRST",
    "product_code": "STRATUM",
    "license_type": "perpetual",
    "status": "active",
    "user_id": 1,
    "user_email": "admin@wovenmodel.com",
    "expires_at": null,
    "perpetual": true,
    "max_activations": 3,
    "current_activations": 1,
    "feature_flags": ["all"],
    "activations": [
        {
            "id": 1,
            "machine_fingerprint": "a1b2...",
            "hostname": "DESKTOP-ABC123",
            "activated_at": "2026-07-07T12:00:00",
            "last_validation": "2026-07-07T12:00:00"
        }
    ],
    "created_at": "2026-07-07T12:00:00",
    "notes": null
}
```

---

## Admin Endpoints

All admin endpoints require the `Authorization: Bearer <token>` header
with a valid admin JWT.

### GET `/api/v1/admin/stats`

Get dashboard statistics.

**Response (200):**
```json
{
    "total_users": 1,
    "total_licenses": 5,
    "active_licenses": 5,
    "total_machines": 3,
    "total_activations": 3,
    "recent_activity": [
        {
            "description": "License activated: ABCDE-12345",
            "timestamp": "2026-07-07T12:00:00Z",
            "type": "activation"
        }
    ]
}
```

### GET `/api/v1/admin/users`

List all users.

**Response (200):**
```json
[
    {
        "id": 1,
        "email": "admin@wovenmodel.com",
        "name": "Admin",
        "role": "admin",
        "is_active": true,
        "created_at": "2026-07-01T00:00:00Z",
        "license_count": 5
    }
]
```

### POST `/api/v1/admin/users`

Create a new user.

**Request:**
```json
{
    "email": "user@example.com",
    "password": "secure-password",
    "name": "User Name",
    "role": "user"
}
```

### GET `/api/v1/admin/users/{id}`

Get user details.

### PUT `/api/v1/admin/users/{id}`

Update user details (email, name, role, is_active).

### GET `/api/v1/admin/machines`

List all registered machines.

**Response (200):**
```json
[
    {
        "id": 1,
        "fingerprint_hash": "a1b2c3...",
        "hostname": "DESKTOP-ABC123",
        "operating_system": "Windows 11 Pro",
        "cpu_identifier": "Intel64 Family 6 Model 186",
        "motherboard_uuid": "12345678-1234-1234-1234-123456789abc",
        "disk_serial": "WD-WCC4E5HV6V7S",
        "bios_uuid": "87654321-4321-4321-4321-cba987654321",
        "ip_address": "192.168.1.100",
        "last_seen": "2026-07-07T12:00:00Z",
        "is_blacklisted": false,
        "activation_count": 2
    }
]
```

### POST `/api/v1/admin/machines/{id}/blacklist`

Toggle machine blacklist status.

**Request:**
```json
{
    "is_blacklisted": true
}
```

### POST `/api/v1/admin/licenses/generate`

Generate a new license key.

**Request:**
```json
{
    "product_code": "STRATUM",
    "user_id": 1,
    "license_type": "perpetual",
    "max_activations": 3,
    "perpetual": true,
    "feature_flags": ["all"],
    "expiration_days": null,
    "offline_days": 7,
    "notes": "Customer license"
}
```

**Response (200):**
```json
{
    "id": 6,
    "license_key": "ABC12-DEF34-GHI56-JKL78",
    "product_code": "STRATUM",
    "user_id": 1,
    "license_type": "perpetual",
    "status": "active",
    "expires_at": null,
    "perpetual": true,
    "max_activations": 3,
    "feature_flags": ["all"],
    "created_at": "2026-07-07T12:00:00Z"
}
```

**curl example:**
```bash
curl -X POST http://localhost:8000/api/v1/admin/licenses/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "product_code": "STRATUM",
    "user_id": 1,
    "license_type": "perpetual"
  }'
```

### POST `/api/v1/admin/licenses/{id}/revoke`

Revoke a license (mark as inactive).

### POST `/api/v1/admin/licenses/{id}/reset-activations`

Reset all activations for a license, allowing re-activation.

### GET `/api/v1/admin/logs`

View server activity logs.

| Query Param | Description |
|-------------|-------------|
| `limit` | Number of log entries (default: 50) |
| `severity` | Filter by severity (DEBUG, INFO, WARNING, ERROR) |

### GET `/api/v1/admin/export`

Export data as JSON.

| Query Param | Values |
|-------------|--------|
| `export_type` | `licenses`, `users`, `machines`, `activations`, `all` |

**Response:** Array of JSON objects matching the requested type.

---

## Product Endpoints

### GET `/api/v1/products/`

List all registered products.

**Response (200):**
```json
[
    {
        "id": 1,
        "name": "Stratum",
        "code": "STRATUM",
        "description": "AI Trading Strategy Analyzer",
        "is_active": true,
        "created_at": "2026-07-01T00:00:00Z"
    },
    {
        "id": 2,
        "name": "Backtesting Bot",
        "code": "BACKTESTING_BOT",
        "description": "Automated backtesting bot",
        "is_active": true,
        "created_at": "2026-07-01T00:00:00Z"
    }
]
```

---

## System Endpoints

### GET `/health`

Server health check.

**Response (200):**
```json
{
    "status": "healthy",
    "version": "1.3.0"
}
```

---

## Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad request (missing/invalid fields) |
| 401 | Unauthorized (missing/invalid token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Resource not found |
| 409 | Conflict (e.g., max activations reached) |
| 422 | Unprocessable entity (validation error) |
| 429 | Too many requests (rate limited) |
| 500 | Internal server error |

---

## Error Response Format

```json
{
    "detail": "Human-readable error message",
    "code": "ERROR_CODE",
    "status": 400
}
```

---

## Python Client Example

```python
import requests

BASE_URL = "http://localhost:8000"
API = f"{BASE_URL}/api/v1"

# Login
resp = requests.post(f"{API}/auth/login", json={
    "email": "admin@wovenmodel.com",
    "password": "admin123!",
})
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Generate license
resp = requests.post(f"{API}/admin/licenses/generate",
    headers=headers,
    json={
        "product_code": "STRATUM",
        "user_id": 1,
        "license_type": "perpetual",
    })
key = resp.json()["license_key"]
print(f"License key: {key}")

# Activate
fingerprint = "test-fingerprint-hash"
resp = requests.post(f"{API}/activate", json={
    "license_key": key,
    "fingerprint": fingerprint,
    "fingerprint_data": {
        "machine_guid": "test-machine",
        "hostname": "test-pc",
    },
})
print(f"Activated: {resp.json()['success']}")

# Validate
resp = requests.post(f"{API}/validate", json={
    "license_key": key,
    "fingerprint": fingerprint,
})
print(f"Valid: {resp.json()['valid']}")

# Deactivate
resp = requests.post(f"{API}/deactivate", json={
    "license_key": key,
    "fingerprint": fingerprint,
})
print(f"Deactivated: {resp.json()['success']}")
```

---

*Woven Model Licensing Server v1.3.0 | © Woven Model. All rights reserved.*
*Support: jude@wovenmodel.com*
