from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.schemas.pricing_plan import (
    PricingPlanCreate,
    PricingPlanUpdate,
    PricingPlanRead,
)
from app.services import pricing_plan_service
from app.api.v1.endpoints.auth import get_current_admin
from app.db.models.admin import Admin as AdminModel # For type hinting get_current_admin
from sqlalchemy.exc import IntegrityError # To catch unique constraint violations for name

router = APIRouter()

@router.post("/", response_model=PricingPlanRead, status_code=status.HTTP_201_CREATED)
def create_pricing_plan(
    plan_in: PricingPlanCreate,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    existing_plan = pricing_plan_service.get_plan_by_name(db, name=plan_in.name)
    if existing_plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pricing plan with name '{plan_in.name}' already exists."
        )
    try:
        return pricing_plan_service.create_plan(db=db, plan_in=plan_in)
    except IntegrityError: # Should be caught by the service check, but as a fallback
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pricing plan with name '{plan_in.name}' already exists (database integrity error)."
        )


@router.get("/", response_model=List[PricingPlanRead])
def read_pricing_plans(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False, # Query parameter to filter active plans
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    plans = pricing_plan_service.get_plans(db=db, skip=skip, limit=limit, active_only=active_only)
    return plans

@router.get("/{plan_id}", response_model=PricingPlanRead)
def read_pricing_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    db_plan = pricing_plan_service.get_plan(db=db, plan_id=plan_id)
    if db_plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pricing plan not found")
    return db_plan

@router.put("/{plan_id}", response_model=PricingPlanRead)
def update_pricing_plan(
    plan_id: int,
    plan_in: PricingPlanUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    if plan_in.name: # If name is being updated, check for uniqueness
        existing_plan = pricing_plan_service.get_plan_by_name(db, name=plan_in.name)
        # Ensure the found plan is not the current plan being updated
        if existing_plan and existing_plan.id != plan_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Pricing plan with name '{plan_in.name}' already exists."
            )
    
    updated_plan = pricing_plan_service.update_plan(db=db, plan_id=plan_id, plan_in=plan_in)
    if updated_plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pricing plan not found")
    
    # The service layer (update_plan) already handles commit and refresh.
    # If IntegrityError for name uniqueness needs to be caught here after service call,
    # it implies the service didn't fully handle the check before its own commit,
    # or a race condition occurred. The primary check is done before calling update_plan.
    # For now, assuming service layer's commit is sufficient.
    # If a very specific race condition for name update needs to be caught,
    # the service would need to not commit, return the object, let endpoint commit, and handle error.
    # This usually means the service check + DB constraint is the primary guard.
    return updated_plan

@router.delete("/{plan_id}", response_model=PricingPlanRead)
def delete_pricing_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    # Consider adding a check here: if plan is assigned to any active subscriptions, prevent deletion.
    # For now, direct delete.
    deleted_plan = pricing_plan_service.delete_plan(db=db, plan_id=plan_id)
    if deleted_plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pricing plan not found")
    return deleted_plan
