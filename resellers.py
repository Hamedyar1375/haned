from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.schemas.reseller import (
    ResellerCreate,
    ResellerUpdate,
    ResellerRead,
    ResellerPanelAccessRequest,
)
from app.schemas.marzban_panel import MarzbanPanelRead # For response model
from app.services import reseller_service
from app.api.v1.endpoints.auth import get_current_admin
from app.db.models.admin import Admin as AdminModel # For type hinting get_current_admin
from sqlalchemy.exc import IntegrityError # To catch unique constraint violations

router = APIRouter()

@router.post("/", response_model=ResellerRead, status_code=status.HTTP_201_CREATED)
def create_reseller(
    reseller_in: ResellerCreate,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    # Check for uniqueness of marzban_admin_id and username at service or here
    existing_by_username = reseller_service.get_reseller_by_username(db, username=reseller_in.username)
    if existing_by_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{reseller_in.username}' already registered."
        )
    existing_by_marzban_id = reseller_service.get_reseller_by_marzban_admin_id(db, marzban_admin_id=reseller_in.marzban_admin_id)
    if existing_by_marzban_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Marzban Admin ID '{reseller_in.marzban_admin_id}' is already in use."
        )
    try:
        return reseller_service.create_reseller(db=db, reseller_in=reseller_in)
    except IntegrityError as e: # Catch DB level unique constraint violations if any race conditions
        db.rollback()
        # A more specific error message could be constructed by parsing e.orig
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A reseller with this username or Marzban Admin ID or email already exists.",
        )


@router.get("/", response_model=List[ResellerRead])
def read_resellers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    return reseller_service.get_resellers(db=db, skip=skip, limit=limit)

@router.get("/{reseller_id}", response_model=ResellerRead)
def read_reseller(
    reseller_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    db_reseller = reseller_service.get_reseller(db=db, reseller_id=reseller_id)
    if db_reseller is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseller not found")
    return db_reseller

@router.put("/{reseller_id}", response_model=ResellerRead)
def update_reseller(
    reseller_id: int,
    reseller_in: ResellerUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    # Add checks for uniqueness if username/email were updatable and changed
    updated_reseller = reseller_service.update_reseller(db=db, reseller_id=reseller_id, reseller_in=reseller_in)
    if updated_reseller is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseller not found")
    return updated_reseller

@router.delete("/{reseller_id}", response_model=ResellerRead) # Or 204
def delete_reseller(
    reseller_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    deleted_reseller = reseller_service.delete_reseller(db=db, reseller_id=reseller_id)
    if deleted_reseller is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseller not found")
    return deleted_reseller

@router.get("/{reseller_id}/panels", response_model=List[MarzbanPanelRead])
def get_reseller_panels(
    reseller_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    panels = reseller_service.get_reseller_panel_access(db=db, reseller_id=reseller_id)
    if panels is None: # get_reseller_panel_access returns [] if reseller not found, so this check might be redundant
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseller not found or no panels assigned")
    return panels

@router.put("/{reseller_id}/panels", response_model=ResellerRead) # Returns the updated reseller with new panel list
def update_reseller_panels(
    reseller_id: int,
    panel_access_request: ResellerPanelAccessRequest,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    updated_reseller = reseller_service.update_reseller_panel_access(
        db=db, reseller_id=reseller_id, panel_ids=panel_access_request.marzban_panel_ids
    )
    if updated_reseller is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseller not found")
    return updated_reseller
