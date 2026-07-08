"""License activation, validation, deactivation, transfer, and update-check endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user, get_optional_user
from app.models.user import User
from app.models.license import License, LicenseStatus
from app.models.product import Product
from app.schemas.license import (
    ActivateRequest, ValidateRequest, DeactivateRequest, TransferRequest,
    ActivateResponse, ValidateResponse, DeactivateResponse, TransferResponse,
    CheckUpdatesResponse, LicenseInfoResponse,
)
from app.services.license_service import (
    activate_license, validate_license, deactivate_license,
    transfer_license, renew_license,
)

router = APIRouter(tags=["Licensing"])


@router.post("/activate", response_model=ActivateResponse)
async def api_activate(
    body: ActivateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_user),
):
    # Support both: SDK sends "fingerprint" (string hash),
    # and direct API clients send "fingerprint_data" (dict).
    fp = getattr(body, "fingerprint", None)
    fp_data = getattr(body, "fingerprint_data", body.fingerprint_data)
    cert, error = await activate_license(
        db=db,
        license_key=body.license_key,
        fingerprint=fp,
        fingerprint_data=fp_data if not fp else None,
        ip_address=body.ip_address,
        application_version=body.application_version,
    )
    if error:
        return ActivateResponse(success=False, message=error)
    return ActivateResponse(success=True, message="License activated", certificate=cert)


@router.post("/validate", response_model=ValidateResponse)
async def api_validate(
    body: ValidateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_user),
):
    valid, message, cert = await validate_license(
        db=db,
        license_key=body.license_key,
        fingerprint=body.fingerprint,
        signature_b64=body.signature,
    )
    return ValidateResponse(valid=valid, message=message, certificate=cert)


@router.post("/deactivate", response_model=DeactivateResponse)
async def api_deactivate(
    body: DeactivateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_user),
):
    success, message = await deactivate_license(
        db=db,
        license_key=body.license_key,
        fingerprint=body.fingerprint,
    )
    return DeactivateResponse(success=success, message=message)


@router.post("/transfer", response_model=TransferResponse)
async def api_transfer(
    body: TransferRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_user),
):
    success, message, cert = await transfer_license(
        db=db,
        license_key=body.license_key,
        old_fingerprint=body.old_fingerprint,
        new_fingerprint_data=body.new_fingerprint_data,
    )
    return TransferResponse(success=success, message=message, certificate=cert)


@router.post("/renew")
async def api_renew(
    license_id: int,
    extra_days: int = 365,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    success, message = await renew_license(db, license_id, extra_days)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
    return {"success": True, "message": message}


@router.get("/check-updates", response_model=CheckUpdatesResponse)
async def api_check_updates(
    current_version: str = "0.0.0",
    product_code: str = "UNKNOWN",
    db: AsyncSession = Depends(get_db),
):
    """Check if a newer version is available for a product."""
    result = await db.execute(select(Product).where(Product.code == product_code))
    product = result.scalar_one_or_none()
    if product and product.version != current_version:
        return CheckUpdatesResponse(
            update_available=True,
            latest_version=product.version,
            download_url=f"https://downloads.wovenmodel.com/{product.code.lower()}/{product.version}",
            release_notes=f"Version {product.version} is available.",
            force_update=False,
        )
    return CheckUpdatesResponse(update_available=False)


@router.get("/license/{license_key}", response_model=LicenseInfoResponse)
async def api_get_license_info(
    license_key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(License).where(License.license_key == license_key))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License not found")
    if lic.user_id != current_user.id and current_user.role not in ("admin", "super_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    activations_list = []
    for act in lic.activations:
        activations_list.append({
            "id": act.id,
            "machine_fingerprint": act.machine.fingerprint_hash if act.machine else "",
            "machine_hostname": act.machine.hostname if act.machine else None,
            "status": act.status.value,
            "activation_date": act.activation_date.isoformat(),
            "last_validation": act.last_validation.isoformat() if act.last_validation else None,
        })
    return LicenseInfoResponse(
        id=lic.id,
        license_key=lic.license_key,
        license_type=lic.license_type.value,
        status=lic.status.value,
        product_id=lic.product_id,
        user_id=lic.user_id,
        expiration_date=lic.expiration_date,
        max_activations=lic.max_activations,
        current_activations=lic.current_activations,
        perpetual=lic.perpetual,
        offline_days=lic.offline_days,
        feature_flags=lic.feature_flags_json,
        created_at=lic.created_at,
        activations=activations_list,
    )
