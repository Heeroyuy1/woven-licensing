#!/usr/bin/env python3
"""
Woven Model Licensing Server — License CLI
===========================================
Command-line tool for managing licenses via the licensing server API.

Usage:
    python license_cli.py generate --product STRATUM --user 1 --type perpetual
    python license_cli.py list
    python license_cli.py info KEY
    python license_cli.py revoke KEY
    python license_cli.py activate KEY --machine machine-id
    python license_cli.py deactivate KEY

Environment variables:
    LICENSE_API_URL  — API base URL (default: http://localhost:8000)
    LICENSE_API_KEY  — Admin API key / bearer token
"""

import os
import sys
import argparse
import json
import textwrap
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

# ── ANSI colors for rich terminal output ──────────────────────
COLORS = {
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "magenta": "\033[95m",
    "cyan": "\033[96m",
    "white": "\033[97m",
    "reset": "\033[0m",
}


def c(text, *names):
    """Colorize text with ANSI codes."""
    codes = "".join(COLORS.get(n, "") for n in names)
    return f"{codes}{text}{COLORS['reset']}"


def print_header(title):
    """Print a formatted header."""
    width = 60
    print()
    print(c("=" * width, "bold", "cyan"))
    print(c(f"  {title}", "bold", "white"))
    print(c("=" * width, "bold", "cyan"))
    print()


def print_table(rows, headers=None):
    """Print a simple ASCII table with colored headers."""
    if not rows:
        print(c("  (empty)", "dim"))
        return

    # Calculate column widths
    col_widths = []
    for row in rows:
        while len(col_widths) < len(row):
            col_widths.append(0)
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    # Print headers
    if headers:
        for i, h in enumerate(headers):
            width = col_widths[i] if i < len(col_widths) else 20
            print(c(f"  {h.ljust(width)}", "bold", "cyan"), end="")
        print()
        print(c("  " + "-" * (sum(col_widths) + len(col_widths) * 2 - 2), "dim"))

    # Print rows
    for row in rows:
        for i, cell in enumerate(row):
            width = col_widths[i] if i < len(col_widths) else 20
            print(f"  {str(cell).ljust(width)}", end="")
        print()
    print()


# ── API Client ─────────────────────────────────────────────────
class LicenseAPI:
    """Minimal HTTP client for the licensing server API (no external deps)."""

    def __init__(self, base_url=None, api_key=None):
        self.base_url = (base_url or os.environ.get("LICENSE_API_URL", "http://localhost:8000")).rstrip("/")
        self.api_key = api_key or os.environ.get("LICENSE_API_KEY", "")

    def _request(self, method, path, data=None):
        """Make an HTTP request and return parsed JSON."""
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        body = json.dumps(data).encode("utf-8") if data else None

        req = Request(url, data=body, headers=headers, method=method)

        try:
            with urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                if raw:
                    return json.loads(raw)
                return {}
        except HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            try:
                error_data = json.loads(error_body)
                msg = error_data.get("detail", error_data.get("message", str(e)))
            except (json.JSONDecodeError, AttributeError):
                msg = error_body or str(e)
            raise RuntimeError(f"API Error ({e.code}): {msg}") from e
        except URLError as e:
            raise RuntimeError(f"Connection failed: {e.reason}") from e

    def get(self, path):
        return self._request("GET", path)

    def post(self, path, data=None):
        return self._request("POST", path, data)

    def put(self, path, data=None):
        return self._request("PUT", path, data)

    def delete(self, path):
        return self._request("DELETE", path)


# ── CLI Commands ───────────────────────────────────────────────
def cmd_generate(api, args):
    """Generate a new license."""
    print_header("Generate License")

    payload = {
        "product_code": args.product,
        "user_id": args.user,
        "license_type": args.type,
    }
    if args.expires:
        payload["expires_at"] = args.expires
    if args.machine:
        payload["machine_id"] = args.machine

    result = api.post("/api/v1/licenses/generate", payload)

    print(c("  License generated successfully!", "bold", "green"))
    print()
    rows = [
        (c("Key:", "bold"), c(result.get("key", ""), "yellow")),
        ("Product:", result.get("product_code", args.product)),
        ("Type:", result.get("license_type", args.type)),
        ("User ID:", str(result.get("user_id", args.user))),
        ("Active:", c("Yes", "green") if result.get("is_active", True) else c("No", "red")),
    ]
    if result.get("expires_at"):
        rows.append(("Expires:", result["expires_at"]))
    print_table(rows)
    return result


def cmd_list(api, args):
    """List all licenses."""
    print_header("License List")

    result = api.get("/api/v1/licenses")
    licenses = result if isinstance(result, list) else result.get("licenses", result.get("data", [result]))

    if not licenses:
        print(c("  No licenses found.", "yellow"))
        return []

    rows = []
    for lic in licenses:
        active = c("Yes", "green") if lic.get("is_active", True) else c("No", "red")
        rows.append((
            str(lic.get("id", "?")),
            lic.get("key", "?"),
            lic.get("product_code", lic.get("product", "?")),
            lic.get("license_type", "?"),
            active,
        ))

    print_table(rows, headers=["ID", "License Key", "Product", "Type", "Active"])
    print(c(f"  Total: {len(licenses)} license(s)", "dim"))
    return licenses


def cmd_info(api, args):
    """Show detailed info about a specific license."""
    print_header(f"License Info: {args.key}")

    result = api.get(f"/api/v1/licenses/{args.key}")

    rows = [
        (c("Key:", "bold"), c(result.get("key", args.key), "yellow")),
        ("ID:", str(result.get("id", "?"))),
        ("Product:", result.get("product_code", result.get("product", "?"))),
        ("Type:", result.get("license_type", "?")),
        ("User ID:", str(result.get("user_id", "?"))),
        ("Active:", c("Yes", "green") if result.get("is_active", True) else c("No", "red")),
        ("Machine ID:", result.get("machine_id", "-")),
    ]
    if result.get("issued_at"):
        rows.append(("Issued:", result["issued_at"]))
    if result.get("expires_at"):
        rows.append(("Expires:", result["expires_at"]))
    if result.get("activated_at"):
        rows.append(("Activated:", result["activated_at"]))

    print_table(rows)

    # Show activations if present
    activations = result.get("activations", result.get("license_activations", []))
    if activations:
        print(c("  Activations:", "bold"))
        act_rows = []
        for act in activations:
            act_rows.append((
                str(act.get("id", "?")),
                act.get("machine_id", "?"),
                act.get("activated_at", "?"),
            ))
        print_table(act_rows, headers=["ID", "Machine ID", "Activated At"])

    return result


def cmd_revoke(api, args):
    """Revoke a license (deactivate it)."""
    print_header(f"Revoke License: {args.key}")

    result = api.post(f"/api/v1/licenses/{args.key}/revoke")

    rows = [
        (c("Key:", "bold"), c(args.key, "yellow")),
        ("Status:", c("Revoked", "red") if result.get("is_active") is False else c("Unknown", "yellow")),
    ]
    if result.get("message"):
        rows.append(("Message:", result["message"]))
    print_table(rows)
    print(c("  License revoked.", "bold", "red"))
    return result


def cmd_activate(api, args):
    """Activate a license on a machine."""
    print_header(f"Activate License: {args.key}")

    payload = {"machine_id": args.machine}
    result = api.post(f"/api/v1/licenses/{args.key}/activate", payload)

    rows = [
        (c("Key:", "bold"), c(args.key, "yellow")),
        ("Machine:", args.machine),
        ("Status:", c("Activated", "green")),
    ]
    if result.get("message"):
        rows.append(("Message:", result["message"]))
    print_table(rows)
    print(c("  License activated.", "bold", "green"))
    return result


def cmd_deactivate(api, args):
    """Deactivate a license from a machine."""
    print_header(f"Deactivate License: {args.key}")

    payload = {"machine_id": args.machine} if args.machine else {}
    result = api.post(f"/api/v1/licenses/{args.key}/deactivate", payload)

    rows = [
        (c("Key:", "bold"), c(args.key, "yellow")),
        ("Status:", c("Deactivated", "yellow")),
    ]
    if result.get("message"):
        rows.append(("Message:", result["message"]))
    print_table(rows)
    print(c("  License deactivated.", "bold", "yellow"))
    return result


# ── Main CLI ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Woven Model Licensing Server — License Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python license_cli.py generate --product STRATUM --user 1 --type perpetual
              python license_cli.py list
              python license_cli.py info ABCDE-12345-FGHIJ-67890
              python license_cli.py revoke ABCDE-12345-FGHIJ-67890
              python license_cli.py activate ABCDE-12345-FGHIJ-67890 --machine worker-01
              python license_cli.py deactivate ABCDE-12345-FGHIJ-67890 --machine worker-01
        """),
    )
    parser.add_argument("--api-url", help="API base URL (default: from LICENSE_API_URL env or http://localhost:8000)")
    parser.add_argument("--api-key", help="Admin API key (default: from LICENSE_API_KEY env)")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # generate
    gen_parser = subparsers.add_parser("generate", help="Generate a new license")
    gen_parser.add_argument("--product", "-p", required=True, help="Product code (e.g. STRATUM)")
    gen_parser.add_argument("--user", "-u", required=True, type=int, help="User ID")
    gen_parser.add_argument("--type", "-t", required=True, choices=["perpetual", "subscription", "trial", "node-locked", "floating"], help="License type")
    gen_parser.add_argument("--expires", "-e", help="Expiration date (ISO format)")
    gen_parser.add_argument("--machine", "-m", help="Machine ID for node-locked licenses")

    # list
    subparsers.add_parser("list", help="List all licenses")

    # info
    info_parser = subparsers.add_parser("info", help="Show license details")
    info_parser.add_argument("key", help="License key")

    # revoke
    revoke_parser = subparsers.add_parser("revoke", help="Revoke a license")
    revoke_parser.add_argument("key", help="License key")

    # activate
    act_parser = subparsers.add_parser("activate", help="Activate a license on a machine")
    act_parser.add_argument("key", help="License key")
    act_parser.add_argument("--machine", "-m", required=True, help="Machine ID")

    # deactivate
    deact_parser = subparsers.add_parser("deactivate", help="Deactivate a license")
    deact_parser.add_argument("key", help="License key")
    deact_parser.add_argument("--machine", "-m", help="Machine ID (optional)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Build API client
    api = LicenseAPI(base_url=args.api_url, api_key=args.api_key)

    try:
        if args.command == "generate":
            cmd_generate(api, args)
        elif args.command == "list":
            cmd_list(api, args)
        elif args.command == "info":
            cmd_info(api, args)
        elif args.command == "revoke":
            cmd_revoke(api, args)
        elif args.command == "activate":
            cmd_activate(api, args)
        elif args.command == "deactivate":
            cmd_deactivate(api, args)
        else:
            print(c(f"Unknown command: {args.command}", "red"))
            return 1
    except RuntimeError as e:
        print(c(f"\n  Error: {e}", "bold", "red"), file=sys.stderr)
        return 1
    except Exception as e:
        print(c(f"\n  Unexpected error: {e}", "bold", "red"), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())