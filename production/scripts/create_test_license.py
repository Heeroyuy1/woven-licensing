#!/usr/bin/env python3
"""
Woven Model Licensing Server — Create Test Licenses
====================================================
Standalone script that connects to a running licensing server,
logs in as admin, and generates test licenses for STRATUM and BACKTESTING_BOT.

No external dependencies beyond stdlib + urllib.

Usage:
    python create_test_license.py
    python create_test_license.py --email admin@wovenmodel.com
    python create_test_license.py --email admin@wovenmodel.com --password admin123
    python create_test_license.py --url http://localhost:8000

Environment variables:
    ADMIN_EMAIL     — Admin email (default: admin@wovenmodel.com)
    ADMIN_PASSWORD  — Admin password (default: admin)
    LICENSE_API_URL — Server URL (default: http://localhost:8000)

Exit code: 0 on success, 1 on failure.
"""

import os
import sys
import json
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin


# ── Constants ─────────────────────────────────────────────────
PRODUCTS = [
    {
        "code": "STRATUM",
        "name": "Stratum — AI Trading Strategy Analyzer",
        "description": "Perpetual license for the Stratum desktop application",
    },
    {
        "code": "BACKTESTING_BOT",
        "name": "Backtesting Bot",
        "description": "Perpetual license for the automated backtesting bot",
    },
]

DEFAULT_URL = "http://localhost:8000"
DEFAULT_EMAIL = "admin@wovenmodel.com"
DEFAULT_PASSWORD = "admin"


# ── Colored output ────────────────────────────────────────────
def color(text, *codes):
    """Apply ANSI color codes. Falls back to plain text if not a TTY."""
    if not sys.stdout.isatty():
        return text
    code_map = {
        "bold": "1",
        "red": "91",
        "green": "92",
        "yellow": "93",
        "blue": "94",
        "cyan": "96",
        "reset": "0",
    }
    prefix = "".join(f"\033[{code_map[c]}m" for c in codes if c in code_map)
    suffix = "\033[0m"
    return f"{prefix}{text}{suffix}"


def ok(msg):
    print(f"  {color('[OK]', 'green')} {msg}")

def warn(msg):
    print(f"  {color('[WARN]', 'yellow')} {msg}")

def fail(msg):
    print(f"  {color('[FAIL]', 'red')} {msg}", file=sys.stderr)


# ── HTTP helpers ──────────────────────────────────────────────
def http_request(method, url, headers=None, data=None):
    """Make an HTTP request. Returns (status_code, response_data_dict)."""
    if headers is None:
        headers = {}
    headers.setdefault("Content-Type", "application/json")
    headers.setdefault("Accept", "application/json")

    body = json.dumps(data).encode("utf-8") if data else None

    req = Request(url, data=body, headers=headers, method=method.upper())

    try:
        with urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            result = json.loads(raw) if raw else {}
            return resp.status, result
    except HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        try:
            error_data = json.loads(error_body)
            msg = error_data.get("detail", error_data.get("message", str(e)))
        except (json.JSONDecodeError, AttributeError):
            msg = error_body or str(e)
        return e.code, {"error": msg, "detail": msg}
    except URLError as e:
        return 0, {"error": f"Connection failed: {e.reason}"}
    except Exception as e:
        return 0, {"error": str(e)}


# ── Login ───────────────────────────────────────────────────────
def login(base_url, email, password):
    """Log in as admin and get an auth token."""
    url = urljoin(base_url.rstrip("/") + "/", "/api/v1/auth/login")
    payload = {"email": email, "password": password}

    status, data = http_request("POST", url, data=payload)

    if status == 200:
        token = data.get("access_token", data.get("token", ""))
        if token:
            ok(f"Logged in as {email}")
            return token
        else:
            fail(f"Login succeeded but no token in response: {json.dumps(data, indent=2)[:200]}")
            return None
    else:
        fail(f"Login failed (HTTP {status}): {data.get('error', data.get('detail', 'unknown error'))}")
        return None


def register_product(base_url, token, product):
    """Register a product if not already registered. Returns product ID."""
    headers = {"Authorization": f"Bearer {token}"}

    # Try to find existing product
    url = urljoin(base_url.rstrip("/") + "/", f"/api/v1/products/{product['code']}")
    status, data = http_request("GET", url, headers=headers)

    if status == 200 and data.get("id"):
        warn(f"Product '{product['code']}' already exists (id={data['id']})")
        return data["id"]

    # Create product
    url = urljoin(base_url.rstrip("/") + "/", "/api/v1/products")
    payload = {
        "code": product["code"],
        "name": product["name"],
        "description": product.get("description", ""),
    }
    status, data = http_request("POST", url, headers=headers, data=payload)

    if status in (200, 201):
        ok(f"Product '{product['code']}' created (id={data.get('id', '?')})")
        return data.get("id")
    else:
        warn(f"Could not register product '{product['code']}' (HTTP {status}): {data.get('error', '')}")
        return None


def generate_license(base_url, token, product_code, user_id=1):
    """Generate a perpetual license for the given product."""
    headers = {"Authorization": f"Bearer {token}"}
    url = urljoin(base_url.rstrip("/") + "/", "/api/v1/licenses/generate")
    payload = {
        "product_code": product_code,
        "user_id": user_id,
        "license_type": "perpetual",
    }

    status, data = http_request("POST", url, headers=headers, data=payload)

    if status == 200 and data.get("key"):
        ok(f"{product_code} license generated")
        return data["key"]
    else:
        fail(f"Failed to generate {product_code} license (HTTP {status}): {data.get('error', data.get('detail', 'unknown'))}")
        return None


def health_check(base_url):
    """Check if the server is reachable."""
    url = urljoin(base_url.rstrip("/") + "/", "/health")
    status, data = http_request("GET", url)
    return status == 200 or data.get("status") == "ok"


# ── Main ───────────────────────────────────────────────────────
def main():
    print()
    print(color("=" * 58, "bold", "cyan"))
    print(color("  Woven Model — Test License Generator", "bold", "white"))
    print(color("=" * 58, "bold", "cyan"))
    print()

    # Parse arguments
    import argparse
    parser = argparse.ArgumentParser(
        description="Generate test licenses for STRATUM and BACKTESTING_BOT"
    )
    parser.add_argument("--url", help=f"Server URL (default: from LICENSE_API_URL env or {DEFAULT_URL})")
    parser.add_argument("--email", help=f"Admin email (default: from ADMIN_EMAIL env or {DEFAULT_EMAIL})")
    parser.add_argument("--password", help=f"Admin password (default: from ADMIN_PASSWORD env or {DEFAULT_PASSWORD})")
    parser.add_argument("--user-id", type=int, default=1, help="User ID to assign licenses to (default: 1)")
    args = parser.parse_args()

    base_url = (args.url or os.environ.get("LICENSE_API_URL", DEFAULT_URL)).rstrip("/")
    email = args.email or os.environ.get("ADMIN_EMAIL", DEFAULT_EMAIL)
    password = args.password or os.environ.get("ADMIN_PASSWORD", DEFAULT_PASSWORD)
    user_id = args.user_id

    print(f"  Server:   {color(base_url, 'cyan')}")
    print(f"  Email:    {color(email, 'yellow')}")
    print(f"  User ID:  {color(str(user_id), 'yellow')}")
    print()

    # Step 1: Health check
    print(color("  [1/4] Checking server connectivity...", "bold"))
    if not health_check(base_url):
        fail(f"Cannot reach server at {base_url}")
        print()
        print(color("  Make sure the licensing server is running:", "yellow"))
        print(f"    cd licensing-server/backend")
        print(f"    uvicorn main:app --host 0.0.0.0 --port 8000")
        print(f"  Or with Docker:")
        print(f"    docker-compose up -d")
        print()
        return 1
    ok(f"Server reachable at {base_url}")
    print()

    # Step 2: Login
    print(color("  [2/4] Authenticating...", "bold"))
    token = login(base_url, email, password)
    if not token:
        print()
        fail("Authentication failed. Check your credentials.")
        print()
        return 1
    print()

    # Step 3: Register products
    print(color("  [3/4] Registering products...", "bold"))
    for product in PRODUCTS:
        register_product(base_url, token, product)
    print()

    # Step 4: Generate licenses
    print(color("  [4/4] Generating test licenses...", "bold"))
    results = []
    for product in PRODUCTS:
        key = generate_license(base_url, token, product["code"], user_id)
        if key:
            results.append((product["code"], key))
    print()

    # Summary
    if results:
        print(color("=" * 58, "bold", "green"))
        print(color("  Test Licenses Generated Successfully", "bold", "white"))
        print(color("=" * 58, "bold", "green"))
        print()
        for code, key in results:
            print(f"    {color(code.ljust(20), 'bold', 'cyan')} {color(key, 'yellow')}")
        print()
        print(color("  You can now use these keys with:", "dim"))
        print(color("    python license_cli.py info <key>", "dim"))
        print(color("    python license_cli.py activate <key> --machine <id>", "dim"))
        print()
        return 0
    else:
        fail("No licenses were generated.")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())