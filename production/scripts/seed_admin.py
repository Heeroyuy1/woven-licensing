#!/usr/bin/env python3
"""
Woven Model Licensing Server — Admin Seeder
===========================================
Creates or updates the admin user in the SQLite database.
Also seeds default products if --seed-products flag is given.

Can be used standalone or imported as a module.

Usage:
    python seed_admin.py
    python seed_admin.py --email admin@example.com --password mypass
    python seed_admin.py --seed-products
    python seed_admin.py --db-path ./woven_licensing.db

Environment variables:
    DATABASE_URL  — SQLite database URL or path
    ADMIN_EMAIL   — Admin email address
    ADMIN_PASSWORD — Admin password (if omitted, random one is generated)
"""

import os
import sys
import argparse
import secrets
import string
from pathlib import Path

try:
    from passlib.hash import bcrypt
except ImportError:
    import subprocess
    print("[WARN] passlib not installed. Installing...", file=sys.stderr)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "passlib", "bcrypt"])
    from passlib.hash import bcrypt


# ── Default products to seed ───────────────────────────────────
DEFAULT_PRODUCTS = [
    {
        "name": "Stratum",
        "code": "STRATUM",
        "description": "AI Trading Strategy Analyzer — Desktop application for backtesting and analysis",
    },
    {
        "name": "Backtesting Bot",
        "code": "BACKTESTING_BOT",
        "description": "Automated backtesting bot for continuous strategy evaluation",
    },
    {
        "name": "Stratum Pro",
        "code": "STRATUM_PRO",
        "description": "Premium tier with AI-powered strategy generation and optimization",
    },
]


def get_db_path(db_url):
    """Extract file path from SQLite URL or return path as-is."""
    if db_url and db_url.startswith("sqlite:///"):
        return db_url[len("sqlite:///"):]
    return db_url or "./woven_licensing.db"


def get_sqlite_connection(db_path):
    """Create a connection to the SQLite database."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_tables(conn):
    """Create users and products tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            description TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            product_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            license_type TEXT NOT NULL,
            machine_id TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS license_activations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_id INTEGER NOT NULL,
            machine_id TEXT NOT NULL,
            activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (license_id) REFERENCES licenses(id)
        );
    """)
    conn.commit()


def create_admin(conn, email, password):
    """Create or update admin user. Returns True if created, False if already exists."""
    cur = conn.execute("SELECT id FROM users WHERE email = ?", (email,))
    existing = cur.fetchone()

    if existing:
        print(f"[INFO] Admin user '{email}' already exists (id={existing['id']}). Skipping creation.")
        return False

    password_hash = bcrypt.hash(password)
    conn.execute(
        "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
        (email, password_hash, "admin"),
    )
    conn.commit()
    print(f"[OK] Admin user created: {email}")
    return True


def seed_products(conn, products=None):
    """Seed default products if they don't exist. Prints status for each."""
    if products is None:
        products = DEFAULT_PRODUCTS

    created_count = 0
    skipped_count = 0

    for product in products:
        cur = conn.execute("SELECT id FROM products WHERE code = ?", (product["code"],))
        existing = cur.fetchone()
        if existing:
            print(f"[SKIP] Product '{product['code']}' already exists (id={existing['id']})")
            skipped_count += 1
        else:
            conn.execute(
                "INSERT INTO products (name, code, description) VALUES (?, ?, ?)",
                (product["name"], product["code"], product["description"]),
            )
            print(f"[OK] Product '{product['code']}' — {product['name']}")
            created_count += 1

    conn.commit()
    print(f"[DONE] Products seeded: {created_count} created, {skipped_count} skipped")
    return created_count


def generate_password(length=24):
    """Generate a strong random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main():
    parser = argparse.ArgumentParser(
        description="Seed admin user and default products for Woven Model Licensing Server"
    )
    parser.add_argument("--email", help="Admin email (overrides ADMIN_EMAIL env)")
    parser.add_argument("--password", help="Admin password (overrides ADMIN_PASSWORD env)")
    parser.add_argument("--db-path", help="SQLite database file path (overrides DATABASE_URL env)")
    parser.add_argument("--seed-products", action="store_true", help="Also seed default products")
    args = parser.parse_args()

    # Resolve database path
    db_url = args.db_path or os.environ.get("DATABASE_URL", "")
    db_path = get_db_path(db_url)
    db_path = os.path.abspath(db_path)
    print(f"[INFO] Database path: {db_path}")

    # Resolve credentials
    email = args.email or os.environ.get("ADMIN_EMAIL", "admin@wovenmodel.com")
    password = args.password or os.environ.get("ADMIN_PASSWORD", "")

    # Generate random password if not provided
    if not password:
        password = generate_password()
        print(f"[INFO] No password provided. Generated random password.")
        print(f"[INFO] ── ADMIN PASSWORD ──")
        print(f"[INFO]   Email:    {email}")
        print(f"[INFO]   Password: {password}")
        print(f"[INFO] ────────────────────")
        print(f"[WARN] Save this password! It will not be shown again.")
    else:
        print(f"[INFO] Using provided password for {email}")

    # Connect to database
    try:
        conn = get_sqlite_connection(db_path)
    except Exception as e:
        print(f"[ERROR] Could not connect to database at {db_path}: {e}", file=sys.stderr)
        return 1

    try:
        # Ensure tables exist
        ensure_tables(conn)

        # Create admin user
        create_admin(conn, email, password)

        # Seed products if requested
        if args.seed_products:
            print("[INFO] Seeding default products...")
            seed_products(conn)

        print("[DONE] Seed operation completed.")
        return 0

    except Exception as e:
        print(f"[ERROR] Seed failed: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())