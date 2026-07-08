"""Customer portal endpoints — profile, licenses, machines, activation history."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.license import License
from app.models.machine import Machine
from app.models.activation import LicenseActivation, ActivationStatus
from app.schemas.customer import (
    ProfileResponse, UpdateProfileRequest,
    CustomerLicenseResponse, CustomerActivationResponse,
    CustomerMachineResponse,
)

router = APIRouter(prefix="/customer", tags=["Customer Portal"])


@router.get("/profile", response_model=ProfileResponse)
async def customer_get_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ProfileResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        company=current_user.company,
        role=current_user.role.value,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )


@router.put("/profile", response_model=ProfileResponse)
async def customer_update_profile(
    body: UpdateProfileRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.name is not None:
        current_user.name = body.name
    if body.company is not None:
        current_user.company = body.company
    await db.flush()
    return ProfileResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        company=current_user.company,
        role=current_user.role.value,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )


@router.get("/licenses", response_model=list[CustomerLicenseResponse])
async def customer_list_licenses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(License)
        .options(joinedload(License.product))
        .where(License.user_id == current_user.id)
        .order_by(License.created_at.desc())
    )
    licenses = result.scalars().all()
    return [
        CustomerLicenseResponse(
            id=l.id,
            license_key=l.license_key,
            license_type=l.license_type.value,
            status=l.status.value,
            product_code=l.product.code if l.product else "",
            product_name=l.product.name if l.product else "",
            expiration_date=l.expiration_date,
            perpetual=l.perpetual,
            max_activations=l.max_activations,
            current_activations=l.current_activations,
            offline_days=l.offline_days,
            created_at=l.created_at,
        )
        for l in licenses
    ]


@router.get("/licenses/{license_id}/activations", response_model=list[CustomerActivationResponse])
async def customer_list_activations(
    license_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(License).where(
            License.id == license_id,
            License.user_id == current_user.id,
        )
    )
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")

    result = await db.execute(
        select(LicenseActivation)
        .options(joinedload(LicenseActivation.machine))
        .where(LicenseActivation.license_id == license_id)
        .order_by(LicenseActivation.activation_date.desc())
    )
    activations = result.scalars().all()
    return [
        CustomerActivationResponse(
            id=a.id,
            machine_fingerprint=a.machine.fingerprint_hash[:20] + "..." if a.machine else "",
            machine_hostname=a.machine.hostname if a.machine else None,
            machine_os=a.machine.operating_system if a.machine else None,
            status=a.status.value,
            activation_date=a.activation_date,
            last_validation=a.last_validation,
        )
        for a in activations
    ]


@router.get("/machines", response_model=list[CustomerMachineResponse])
async def customer_list_machines(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return machines that have activated one of the user's licenses."""
    result = await db.execute(
        select(License.id).where(License.user_id == current_user.id)
    )
    license_ids = [row[0] for row in result.all()]
    if not license_ids:
        return []

    result = await db.execute(
        select(Machine)
        .join(LicenseActivation)
        .where(
            LicenseActivation.license_id.in_(license_ids),
        )
        .distinct()
        .order_by(Machine.last_seen.desc())
    )
    machines = result.scalars().all()
    return [
        CustomerMachineResponse(
            id=m.id,
            fingerprint_hash=m.fingerprint_hash[:20] + "...",
            hostname=m.hostname,
            operating_system=m.operating_system,
            first_seen=m.first_seen,
            last_seen=m.last_seen,
        )
        for m in machines
    ]
