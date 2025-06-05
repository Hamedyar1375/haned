from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.schemas.marzban_panel import (
    MarzbanPanelCreate,
    MarzbanPanelUpdate,
    MarzbanPanelRead,
)
from app.services import marzban_panel_service
from app.api.v1.endpoints.auth import get_current_admin # For authentication
from app.db.models.admin import Admin as AdminModel # For type hinting get_current_admin

router = APIRouter()

@router.post("/", response_model=MarzbanPanelRead, status_code=status.HTTP_201_CREATED)
def create_marzban_panel(
    panel_in: MarzbanPanelCreate,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    return marzban_panel_service.create_panel(db=db, panel_in=panel_in)

@router.get("/", response_model=List[MarzbanPanelRead])
def read_marzban_panels(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    panels = marzban_panel_service.get_panels(db=db, skip=skip, limit=limit)
    return panels

@router.get("/{panel_id}", response_model=MarzbanPanelRead)
def read_marzban_panel(
    panel_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    db_panel = marzban_panel_service.get_panel(db=db, panel_id=panel_id)
    if db_panel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marzban Panel not found")
    return db_panel

@router.put("/{panel_id}", response_model=MarzbanPanelRead)
def update_marzban_panel(
    panel_id: int,
    panel_in: MarzbanPanelUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    updated_panel = marzban_panel_service.update_panel(db=db, panel_id=panel_id, panel_in=panel_in)
    if updated_panel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marzban Panel not found")
    return updated_panel

@router.delete("/{panel_id}", response_model=MarzbanPanelRead) # Or return a 204 No Content
def delete_marzban_panel(
    panel_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    deleted_panel = marzban_panel_service.delete_panel(db=db, panel_id=panel_id)
    if deleted_panel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marzban Panel not found")
    return deleted_panel
