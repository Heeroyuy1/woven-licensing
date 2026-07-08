"""License service — activation, validation, deactivation, transfer."""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.license import License, LicenseType, LicenseStatus
from app.models.machine import Machine
from app.models.activation import LicenseActivation, ActivationStatus
from app.services.crypto import sign_license_certificate, verify_license_certificate
from app.services.fingerprint import generate_fingerprint

_KEY_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _generate_license_key() -> str:
    """Generate a license key in format XXXXX-XXXXX-XXXXX-XXXXX with checksum.
    
    Key structure: 19 random chars + 1 checksum char = 20 chars total,
    grouped as 4 groups of 5: XXXXX-XXXXX-XXXXX-XXXXX
    Checksum: (36 - (sum_of_all_char_values % 36)) % 36 ensures total % 36 == 0.
    """
    # Generate 19 random characters
    raw = "".join(secrets.choice(_KEY_CHARS) for _ in range(19))
    total = sum(_KEY_CHARS.index(c) for c in raw)
    checksum = _KEY_CHARS[(36 - (total % 36)) % 36]
    full = raw + checksum  # 20 characters
    # Split into 4 groups of 5
    key = "-".join(full[i:i+5] for i in range(0, 20, 5))
    return key


async def create_license(
    db: AsyncSession,
    product_id: int,
    user_id: int,
    license_type: LicenseType = LicenseType.PERPETUAL,
    max_activations: int = 1,
    max_devices: int = 1,
    expiration_days: Optional[int] = None,
    perpetual: bool = False,
    offline_days: int = 7,
    feature_flags: Optional[List[str]] = None,
    metadata: Optional[dict] = None,
    notes: Optional[str] = None,
) -> License:
    """Create a new license with a unique key."""
    for _ in range(10):
        license_key = _generate_license_key()
        existing = await db.execute(select(License).where(License.license_key == license_key))
        if not existing.scalar_one_or_none():
            break
    else:
        raise RuntimeError("Could not generate unique license key")

    expiration_date = None
    if expiration_days:
        expiration_date = datetime.now(timezone.utc) + timedelta(days=expiration_days)

    lic = License(
        license_key=license_key,
        product_id=product_id,
        user_id=user_id,
        license_type=license_type,
        status=LicenseStatus.ACTIVE,
        expiration_date=expiration_date,
        max_activations=max_activations,
        max_devices=max_devices,
        perpetual=perpetual,
        offline_days=offline_days,
        feature_flags_json=json.dumps(feature_flags) if feature_flags else None,
        metadata_json=json.dumps(metadata) if metadata else None,
        notes=notes,
    )
    db.add(lic)
    await db.flush()
    return lic


async def activate_license(
    db: AsyncSession,
    license_key: str,
    fingerprint_data: Optional[dict] = None,
    fingerprint: Optional[str] = None,
    ip_address: Optional[str] = None,
    application_version: Optional[str] = None,
) -> Tuple[Optional[dict], str]:
    """Activate a license on a machine.

    Accepts either a pre-computed fingerprint hash string or a dict of
    hardware identifiers from which the fingerprint is generated.
    Returns (certificate_data, error_message).
    """
    result = await db.execute(select(License).where(License.license_key == license_key))
    lic = result.scalar_one_or_none()
    if not lic:
        return None, "License key not found"
    if lic.status != LicenseStatus.ACTIVE:
        return None, f"License status is {lic.status.value}"
    if lic.expiration_date and lic.expiration_date < datetime.now(timezone.utc):
        return None, "License has expired"

    # Determine fingerprint
    if fingerprint:
        fp_hash = fingerprint
    elif fingerprint_data:
        fp_hash = generate_fingerprint(**fingerprint_data)
    else:
        return None, "Either 'fingerprint' or 'fingerprint_data' is required"

    result = await db.execute(select(Machine).where(Machine.fingerprint_hash == fp_hash))
    machine = result.scalar_one_or_none()

    if not machine:
        machine = Machine(
            fingerprint_hash=fp_hash,
            hostname=fingerprint_data.get("hostname") if fingerprint_data else None,
            operating_system=fingerprint_data.get("operating_system") if fingerprint_data else None,
            cpu_identifier=fingerprint_data.get("cpu_identifier") if fingerprint_data else None,
            motherboard_uuid=fingerprint_data.get("motherboard_uuid") if fingerprint_data else None,
            disk_serial=fingerprint_data.get("disk_serial") if fingerprint_data else None,
            bios_uuid=fingerprint_data.get("bios_uuid") if fingerprint_data else None,
            ip_address=ip_address,
        )
        db.add(machine)
        await db.flush()

    if machine.is_blacklisted:
        return None, "This machine has been blacklisted"

    # Check existing activation
    result = await db.execute(
        select(LicenseActivation).where(
            LicenseActivation.license_id == lic.id,
            LicenseActivation.machine_id == machine.id,
            LicenseActivation.status == ActivationStatus.ACTIVE,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.last_validation = datetime.now(timezone.utc)
        existing.ip_address = ip_address
        await db.flush()
        cert = _build_certificate(lic, machine, existing)
        return cert, ""

    # Check activation limit
    result = await db.execute(
        select(func.count(LicenseActivation.id)).where(
            LicenseActivation.license_id == lic.id,
            LicenseActivation.status == ActivationStatus.ACTIVE,
        )
    )
    active_count = result.scalar() or 0
    if active_count >= lic.max_activations:
        return None, f"Maximum activations ({lic.max_activations}) reached. Deactivate another device first."

    activation = LicenseActivation(
        license_id=lic.id,
        machine_id=machine.id,
        status=ActivationStatus.ACTIVE,
        activation_date=datetime.now(timezone.utc),
        last_validation=datetime.now(timezone.utc),
        ip_address=ip_address,
        application_version=application_version,
    )
    db.add(activation)
    lic.current_activations = lic.current_activations + 1
    await db.flush()

    cert = _build_certificate(lic, machine, activation)
    return cert, ""


async def validate_license(
    db: AsyncSession,
    license_key: str,
    fingerprint: str,
    signature_b64: Optional[str] = None,
) -> Tuple[bool, str, Optional[dict]]:
    """Validate a license activation.

    If signature_b64 is provided, try offline verification first.
    Returns (is_valid, message, certificate_data).
    """
    if signature_b64:
        if verify_license_certificate(
            {"license_key": license_key, "fingerprint": fingerprint},
            signature_b64,
        ):
            return True, "Valid (offline certificate verified)", None

    result = await db.execute(select(License).where(License.license_key == license_key))
    lic = result.scalar_one_or_none()
    if not lic:
        return False, "License key not found", None
    if lic.status != LicenseStatus.ACTIVE:
        return False, f"License status is {lic.status.value}", None
    if lic.expiration_date and lic.expiration_date < datetime.now(timezone.utc):
        return False, "License has expired", None

    result = await db.execute(select(Machine).where(Machine.fingerprint_hash == fingerprint))
    machine = result.scalar_one_or_none()
    if not machine:
        return False, "Machine not registered with this license", None
    if machine.is_blacklisted:
        return False, "Machine is blacklisted", None

    result = await db.execute(
        select(LicenseActivation).where(
            LicenseActivation.license_id == lic.id,
            LicenseActivation.machine_id == machine.id,
            LicenseActivation.status == ActivationStatus.ACTIVE,
        )
    )
    activation = result.scalar_one_or_none()
    if not activation:
        return False, "No active activation found for this machine", None

    activation.last_validation = datetime.now(timezone.utc)
    machine.last_seen = datetime.now(timezone.utc)
    cert = _build_certificate(lic, machine, activation)
    return True, "Valid", cert


async def deactivate_license(
    db: AsyncSession,
    license_key: str,
    fingerprint: str,
) -> Tuple[bool, str]:
    """Deactivate a license on a specific machine."""
    result = await db.execute(select(License).where(License.license_key == license_key))
    lic = result.scalar_one_or_none()
    if not lic:
        return False, "License key not found"

    result = await db.execute(select(Machine).where(Machine.fingerprint_hash == fingerprint))
    machine = result.scalar_one_or_none()
    if not machine:
        return False, "Machine not found"

    result = await db.execute(
        select(LicenseActivation).where(
            LicenseActivation.license_id == lic.id,
            LicenseActivation.machine_id == machine.id,
            LicenseActivation.status == ActivationStatus.ACTIVE,
        )
    )
    activation = result.scalar_one_or_none()
    if not activation:
        return False, "No active activation found"

    activation.status = ActivationStatus.DEACTIVATED
    activation.deactivation_date = datetime.now(timezone.utc)
    lic.current_activations = max(0, lic.current_activations - 1)
    return True, "Deactivated"


async def transfer_license(
    db: AsyncSession,
    license_key: str,
    old_fingerprint: str,
    new_fingerprint_data: dict,
) -> Tuple[bool, str, Optional[dict]]:
    """Transfer a license from one machine to another."""
    ok, msg = await deactivate_license(db, license_key, old_fingerprint)
    if not ok:
        return False, f"Deactivation failed: {msg}", None
    cert, err = await activate_license(db, license_key, fingerprint_data=new_fingerprint_data)
    if err:
        return False, f"Re-activation failed: {err}", None
    return True, "License transferred", cert


async def renew_license(db: AsyncSession, license_id: int, extra_days: int = 365) -> Tuple[bool, str]:
    """Renew/extend a license."""
    result = await db.execute(select(License).where(License.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        return False, "License not found"
    if lic.expiration_date:
        new_exp = lic.expiration_date + timedelta(days=extra_days)
    else:
        new_exp = datetime.now(timezone.utc) + timedelta(days=extra_days)
    lic.expiration_date = new_exp
    if lic.status == LicenseStatus.EXPIRED:
        lic.status = LicenseStatus.ACTIVE
    return True, f"License renewed to {new_exp.date().isoformat()}"


def _build_certificate(lic: License, machine: Machine, activation: LicenseActivation) -> dict:
    """Build a signed license certificate for the client."""
    data = {
        "license_key": lic.license_key,
        "license_type": lic.license_type.value,
        "status": lic.status.value,
        "product_id": lic.product_id,
        "user_id": lic.user_id,
        "expiration_date": lic.expiration_date.isoformat() if lic.expiration_date else None,
        "perpetual": lic.perpetual,
        "offline_days": lic.offline_days,
        "max_activations": lic.max_activations,
        "current_activations": lic.current_activations,
        "feature_flags": json.loads(lic.feature_flags_json) if lic.feature_flags_json else [],
        "machine_fingerprint": machine.fingerprint_hash,
        "machine_hostname": machine.hostname,
        "activation_date": activation.activation_date.isoformat(),
        "last_validation": datetime.now(timezone.utc).isoformat(),
        "metadata": json.loads(lic.metadata_json) if lic.metadata_json else {},
        "issued_by": "Woven Model Licensing Server",
    }
    signature = sign_license_certificate(data)
    return {"certificate": data, "signature": signature}
