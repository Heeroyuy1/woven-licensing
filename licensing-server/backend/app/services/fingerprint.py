"""Machine fingerprinting — hash hardware identifiers into a secure fingerprint."""
from __future__ import annotations

import hashlib
import hmac
from typing import Dict, Optional


def generate_fingerprint(
    machine_guid: Optional[str] = None,
    motherboard_uuid: Optional[str] = None,
    cpu_identifier: Optional[str] = None,
    disk_serial: Optional[str] = None,
    bios_uuid: Optional[str] = None,
    mac_address: Optional[str] = None,
    hostname: Optional[str] = None,
    salt: Optional[str] = None,
) -> str:
    """
    Generate a secure machine fingerprint from hardware identifiers.
    Uses SHA-256 HMAC with an optional salt to prevent rainbow table attacks.
    Never stores raw hardware identifiers.
    """
    raw_parts = []
    for val in [machine_guid, motherboard_uuid, cpu_identifier, disk_serial, bios_uuid, mac_address, hostname]:
        if val:
            raw_parts.append(val.strip().lower())

    if not raw_parts:
        raise ValueError("At least one hardware identifier is required")

    concatenated = "|".join(sorted(raw_parts))
    key = (salt or "WovenModelFingerprintSalt2024").encode("utf-8")
    digest = hmac.new(key, concatenated.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest


def normalize_machine_guid(raw: str) -> str:
    """Normalize a Windows MachineGUID."""
    return raw.strip().lower().replace("{", "").replace("}", "").replace("-", "")


def normalize_uuid(raw: str) -> str:
    """Normalize a UUID by removing separators and lowercasing."""
    return raw.strip().lower().replace("-", "").replace("{", "").replace("}", "")


def normalize_disk_serial(raw: str) -> str:
    """Normalize a disk serial number."""
    return raw.strip().lower().replace(" ", "")
