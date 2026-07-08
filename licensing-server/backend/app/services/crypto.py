"""Cryptographic services — Ed25519 signing, verification, key generation."""
from __future__ import annotations

import json
import base64
from typing import Optional, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.exceptions import InvalidSignature

from app.config import settings


def generate_signing_keypair() -> Tuple[str, str]:
    """Generate a new Ed25519 keypair. Returns (private_hex, public_hex)."""
    private_key = Ed25519PrivateKey.generate()
    private_hex = private_key.private_bytes_raw().hex()
    public_hex = private_key.public_key().public_bytes_raw().hex()
    return private_hex, public_hex


def get_signing_key() -> Optional[Ed25519PrivateKey]:
    """Load the signing private key from settings."""
    if not settings.SIGNING_PRIVATE_KEY:
        return None
    raw = bytes.fromhex(settings.SIGNING_PRIVATE_KEY)
    return Ed25519PrivateKey.from_private_bytes(raw)


def get_verification_key() -> Optional[Ed25519PublicKey]:
    """Load the verification public key from settings."""
    if not settings.SIGNING_PUBLIC_KEY:
        return None
    raw = bytes.fromhex(settings.SIGNING_PUBLIC_KEY)
    return Ed25519PublicKey.from_public_bytes(raw)


def sign_license_certificate(license_data: dict) -> str:
    """
    Sign a license certificate payload with the server's Ed25519 private key.
    Returns a base64-encoded signature.
    """
    private_key = get_signing_key()
    if not private_key:
        raise RuntimeError("SIGNING_PRIVATE_KEY not configured on server")

    payload = json.dumps(license_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = private_key.sign(payload)
    return base64.b64encode(signature).decode("utf-8")


def verify_license_certificate(license_data: dict, signature_b64: str) -> bool:
    """
    Verify a license certificate signature using the embedded public key.
    Returns True if the signature is valid.
    """
    public_key = get_verification_key()
    if not public_key:
        raise RuntimeError("SIGNING_PUBLIC_KEY not configured")

    payload = json.dumps(license_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    try:
        signature = base64.b64decode(signature_b64)
        public_key.verify(signature, payload)
        return True
    except (InvalidSignature, ValueError, Exception):
        return False


def sign_arbitrary(data: bytes) -> str:
    """Sign arbitrary bytes with the server's private key."""
    private_key = get_signing_key()
    if not private_key:
        raise RuntimeError("SIGNING_PRIVATE_KEY not configured on server")
    signature = private_key.sign(data)
    return base64.b64encode(signature).decode("utf-8")


def verify_arbitrary(data: bytes, signature_b64: str) -> bool:
    """Verify arbitrary bytes against a base64 signature."""
    public_key = get_verification_key()
    if not public_key:
        raise RuntimeError("SIGNING_PUBLIC_KEY not configured")
    try:
        signature = base64.b64decode(signature_b64)
        public_key.verify(signature, data)
        return True
    except (InvalidSignature, ValueError, Exception):
        return False
