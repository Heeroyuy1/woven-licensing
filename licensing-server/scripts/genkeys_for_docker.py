#!/usr/bin/env python3
"""Generate Ed25519 keypair and write to .env file."""
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import os

k = Ed25519PrivateKey.generate()
pk = k.private_bytes_raw().hex()
pb = k.public_key().public_bytes_raw().hex()

env_path = "/app/.env"
with open(env_path, "a") as f:
    f.write(f"\nSIGNING_PRIVATE_KEY={pk}\n")
    f.write(f"SIGNING_PUBLIC_KEY={pb}\n")

print(f"Generated Ed25519 keypair and saved to {env_path}")
print(f"Public key: {pb[:20]}...")
