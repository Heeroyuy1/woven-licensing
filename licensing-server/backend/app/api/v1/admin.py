"""Admin API endpoints — user management, license generation, system administration."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.api.deps import get_current_admin, get_current_super_admin
from app.models.user import User, UserRole
from app.models.license import License, LicenseType, LicenseStatus
from app.models.product import Product
from app.models.machine import Machine
from app.models.activation import LicenseActivation, ActivationStatus
from app.models.audit import AuditLog
from app.schemas.admin import (
    AdminCreateUserRequest, AdminUpdateUserRequest,
    AdminGenerateLicenseRequest, AdminRevokeLicenseRequest,
    AdminUserResponse, AdminLicenseResponse, AdminMachineResponse,
    AdminStatsResponse, AdminLogEntry, AdminExportResponse,
    AdminCreateProductRequest, AdminProductResponse,
)
from app.services.auth_service import hash_password, create_user
from app.services.license_service import create_license

router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get("/users", response_model=list[AdminUserResponse])
async def admin_list_users(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    result = await db.execute(
        select(User).offset(skip).limit(limit).order_by(User.id)
    )
    users = result.scalars().all()
    resp = []
    for u in users:
        lic_count = await db.execute(
            select(func.count(License.id)).where(License.user_id == u.id)
        )
        resp.append(AdminUserResponse(
            id=u.id, email=u.email, name=u.name, role=u.role.value,
            is_active=u.is_active, company=u.company,
            email_verified=u.email_verified, last_login=u.last_login,
            created_at=u.created_at, license_count=lic_count.scalar() or 0,
        ))
    return resp


@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_user(
    body: AdminCreateUserRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    try:
        role = UserRole(body.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")
    try:
        user = await create_user(
            db=db, email=body.email, password=body.password,
            name=body.name, company=body.company, role=role,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return AdminUserResponse(
        id=user.id, email=user.email, name=user.name, role=user.role.value,
        is_active=user.is_active, company=user.company,
        email_verified=user.email_verified, last_login=user.last_login,
        created_at=user.created_at, license_count=0,
    )


@router.get("/users/{user_id}", response_model=AdminUserResponse)
async def admin_get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    lic_count = await db.execute(
        select(func.count(License.id)).where(License.user_id == user.id)
    )
    return AdminUserResponse(
        id=user.id, email=user.email, name=user.name, role=user.role.value,
        is_active=user.is_active, company=user.company,
        email_verified=user.email_verified, last_login=user.last_login,
        created_at=user.created_at, license_count=lic_count.scalar() or 0,
    )


@router.put("/users/{user_id}", response_model=AdminUserResponse)
async def admin_update_user(
    user_id: int,
    body: AdminUpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.name is not None:
        user.name = body.name
    if body.role is not None:
        try:
            user.role = UserRole(body.role)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.company is not None:
        user.company = body.company
    await db.flush()
    lic_count = await db.execute(
        select(func.count(License.id)).where(License.user_id == user.id)
    )
    return AdminUserResponse(
        id=user.id, email=user.email, name=user.name, role=user.role.value,
        is_active=user.is_active, company=user.company,
        email_verified=user.email_verified, last_login=user.last_login,
        created_at=user.created_at, license_count=lic_count.scalar() or 0,
    )


@router.post("/licenses/generate", response_model=AdminLicenseResponse)
async def admin_generate_license(
    body: AdminGenerateLicenseRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    # Validate product
    result = await db.execute(
        select(Product).where(Product.code == body.product_code)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product '{body.product_code}' not found")

    # Validate user
    result = await db.execute(select(User).where(User.id == body.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        lic_type = LicenseType(body.license_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid license type: {body.license_type}")

    lic = await create_license(
        db=db,
        product_id=product.id,
        user_id=user.id,
        license_type=lic_type,
        max_activations=body.max_activations,
        max_devices=body.max_devices,
        expiration_days=body.expiration_days,
        perpetual=body.perpetual,
        offline_days=body.offline_days,
        feature_flags=body.feature_flags,
        notes=body.notes,
    )
    return AdminLicenseResponse(
        id=lic.id,
        license_key=lic.license_key,
        license_type=lic.license_type.value,
        status=lic.status.value,
        product_code=product.code,
        user_email=user.email,
        user_name=user.name,
        max_activations=lic.max_activations,
        current_activations=lic.current_activations,
        expiration_date=lic.expiration_date,
        perpetual=lic.perpetual,
        created_at=lic.created_at,
    )


@router.post("/licenses/{license_id}/revoke")
async def admin_revoke_license(
    license_id: int,
    body: AdminRevokeLicenseRequest = AdminRevokeLicenseRequest(),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    result = await db.execute(select(License).where(License.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    lic.status = LicenseStatus.REVOKED
    lic.notes = (lic.notes or "") + f"\nRevoked by admin: {body.reason}"
    return {"success": True, "message": f"License {lic.license_key} revoked"}


@router.post("/licenses/{license_id}/reset-activations")
async def admin_reset_activations(
    license_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    result = await db.execute(select(License).where(License.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    result = await db.execute(
        select(LicenseActivation).where(
            LicenseActivation.license_id == license_id,
            LicenseActivation.status == ActivationStatus.ACTIVE,
        )
    )
    activations = result.scalars().all()
    for act in activations:
        act.status = ActivationStatus.DEACTIVATED
        act.deactivation_date = datetime.now(timezone.utc)
    lic.current_activations = 0
    return {
        "success": True,
        "message": f"Reset {len(activations)} activation(s) for license {lic.license_key}",
    }


@router.get("/machines", response_model=list[AdminMachineResponse])
async def admin_list_machines(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    result = await db.execute(
        select(Machine).offset(skip).limit(limit).order_by(Machine.last_seen.desc())
    )
    machines = result.scalars().all()
    resp = []
    for m in machines:
        act_count = await db.execute(
            select(func.count(LicenseActivation.id))
            .where(LicenseActivation.machine_id == m.id)
        )
        resp.append(AdminMachineResponse(
            id=m.id, fingerprint_hash=m.fingerprint_hash[:20] + "...",
            hostname=m.hostname, operating_system=m.operating_system,
            is_blacklisted=m.is_blacklisted,
            first_seen=m.first_seen, last_seen=m.last_seen,
            activation_count=act_count.scalar() or 0,
        ))
    return resp


@router.post("/machines/{machine_id}/blacklist")
async def admin_blacklist_machine(
    machine_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    result = await db.execute(select(Machine).where(Machine.id == machine_id))
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    machine.is_blacklisted = not machine.is_blacklisted
    status_text = "blacklisted" if machine.is_blacklisted else "unblacklisted"
    return {"success": True, "message": f"Machine {machine_id} {status_text}"}


@router.get("/stats", response_model=AdminStatsResponse)
async def admin_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    total_licenses = (await db.execute(select(func.count(License.id)))).scalar() or 0
    active_licenses = (
        await db.execute(
            select(func.count(License.id)).where(License.status == LicenseStatus.ACTIVE)
        )
    ).scalar() or 0
    total_machines = (await db.execute(select(func.count(Machine.id)))).scalar() or 0
    total_activations = (await db.execute(select(func.count(LicenseActivation.id)))).scalar() or 0
    total_products = (await db.execute(select(func.count(Product.id)))).scalar() or 0

    # By type
    lic_types_result = await db.execute(
        select(License.license_type, func.count(License.id))
        .group_by(License.license_type)
    )
    licenses_by_type = {k.value: v for k, v in lic_types_result}

    # By status
    lic_status_result = await db.execute(
        select(License.status, func.count(License.id))
        .group_by(License.status)
    )
    licenses_by_status = {k.value: v for k, v in lic_status_result}

    # Recent activations (24h)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent = (
        await db.execute(
            select(func.count(LicenseActivation.id))
            .where(LicenseActivation.activation_date >= cutoff)
        )
    ).scalar() or 0

    return AdminStatsResponse(
        total_users=total_users,
        total_licenses=total_licenses,
        active_licenses=active_licenses,
        total_machines=total_machines,
        total_activations=total_activations,
        total_products=total_products,
        licenses_by_type=licenses_by_type,
        licenses_by_status=licenses_by_status,
        recent_activations_24h=recent,
    )


@router.post("/products", response_model=AdminProductResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_product(
    body: AdminCreateProductRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Create a new product in the licensing system."""
    # Check for duplicate code
    result = await db.execute(select(Product).where(Product.code == body.code))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product with code '{body.code}' already exists",
        )
    product = Product(
        code=body.code,
        name=body.name,
        version=body.version,
        description=body.description,
        active=body.active,
    )
    db.add(product)
    await db.flush()
    return AdminProductResponse(
        id=product.id,
        code=product.code,
        name=product.name,
        version=product.version,
        description=product.description,
        active=product.active,
        created_at=product.created_at,
    )


@router.get("/logs", response_model=list[AdminLogEntry])
async def admin_logs(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    action: Optional[str] = Query(None),
):
    query = select(AuditLog).order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit)
    if action:
        query = query.where(AuditLog.action == action)
    result = await db.execute(query)
    logs = result.scalars().all()
    resp = []
    for log_entry in logs:
        user_email = log_entry.user.email if log_entry.user else None
        resp.append(AdminLogEntry(
            id=log_entry.id,
            timestamp=log_entry.timestamp,
            action=log_entry.action,
            user_email=user_email,
            resource_type=log_entry.resource_type,
            resource_id=log_entry.resource_id,
            success=log_entry.success,
            details=log_entry.details,
        ))
    return resp


@router.get("/export", response_model=AdminExportResponse)
async def admin_export(
    export_type: str = Query("licenses", description="licenses, users, machines, activations"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if export_type == "licenses":
        result = await db.execute(
            select(License).options(joinedload(License.user), joinedload(License.product))
        )
        records = result.scalars().all()
        data = [
            {
                "id": l.id, "license_key": l.license_key,
                "type": l.license_type.value, "status": l.status.value,
                "product_code": l.product.code if l.product else "",
                "user_email": l.user.email if l.user else "",
                "created_at": l.created_at.isoformat(),
                "expiration_date": l.expiration_date.isoformat() if l.expiration_date else "",
            }
            for l in records
        ]
    elif export_type == "users":
        result = await db.execute(select(User))
        records = result.scalars().all()
        data = [
            {
                "id": u.id, "email": u.email, "name": u.name,
                "role": u.role.value, "is_active": u.is_active,
                "created_at": u.created_at.isoformat(),
            }
            for u in records
        ]
    elif export_type == "machines":
        result = await db.execute(select(Machine))
        records = result.scalars().all()
        data = [
            {
                "id": m.id, "fingerprint": m.fingerprint_hash[:20] + "...",
                "hostname": m.hostname, "os": m.operating_system,
                "is_blacklisted": m.is_blacklisted,
                "first_seen": m.first_seen.isoformat(),
                "last_seen": m.last_seen.isoformat(),
            }
            for m in records
        ]
    elif export_type == "activations":
        result = await db.execute(
            select(LicenseActivation).options(
                joinedload(LicenseActivation.license),
                joinedload(LicenseActivation.machine),
            )
        )
        records = result.scalars().all()
        data = [
            {
                "id": a.id,
                "license_key": a.license.license_key if a.license else "",
                "machine_fingerprint": a.machine.fingerprint_hash[:20] + "..." if a.machine else "",
                "status": a.status.value,
                "activation_date": a.activation_date.isoformat(),
                "last_validation": a.last_validation.isoformat() if a.last_validation else "",
            }
            for a in records
        ]
    else:
        raise HTTPException(status_code=400, detail=f"Unknown export type: {export_type}")

    return AdminExportResponse(
        export_type=export_type,
        record_count=len(data),
        filename=f"{export_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        data=data,
    )
