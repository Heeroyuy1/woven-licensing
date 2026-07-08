#!/usr/bin/env python3
"""Generate Ed25519 signing keypair for license certificate signing."""
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main():
    private_key = Ed25519PrivateKey.generate()
    private_hex = private_key.private_bytes_raw().hex()
    public_hex = private_key.public_key().public_bytes_raw().hex()

    print("=" * 60)
    print("ED25519 SIGNING KEYPAIR")
    print("=" * 60)
    print(f"\nPRIVATE KEY (add to .env as SIGNING_PRIVATE_KEY):")
    print(f"  {private_hex}")
    print(f"\nPUBLIC KEY (add to .env as SIGNING_PUBLIC_KEY):")
    print(f"  {public_hex}")
    print("\nStore the private key securely. The public key can be embedded")
    print("in desktop applications for offline certificate verification.")
    print("=" * 60)


if __name__ == "__main__":
    main()
