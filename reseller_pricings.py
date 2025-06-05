from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.schemas.reseller_pricing import (
    ResellerPricingCreate,
    ResellerPricingUpdate,
    ResellerPricingRead,
)
from app.services import reseller_pricing_service
from app.api.v1.endpoints.auth import get_current_admin
from app.db.models.admin import Admin as AdminModel
from sqlalchemy.exc import IntegrityError # To catch DB unique constraint violations

router = APIRouter()

@router.post("/", response_model=ResellerPricingRead, status_code=status.HTTP_201_CREATED)
def create_reseller_pricing_config(
    pricing_in: ResellerPricingCreate,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    try:
        return reseller_pricing_service.create_reseller_pricing(db=db, pricing_in=pricing_in)
    except ValueError as e: # Catch validation errors from service
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except IntegrityError as e: # Catch DB unique constraint violations (e.g. uq_reseller_panel_pricing)
        db.rollback()
        # Attempt to provide a more specific message based on common constraints
        if "uq_reseller_panel_pricing" in str(e.orig).lower():
            detail = "A pricing configuration for this reseller and Marzban panel (or generic) already exists."
        else:
            detail = "Database integrity error. This pricing configuration might conflict with an existing one."
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


@router.get("/", response_model=List[ResellerPricingRead])
def read_reseller_pricing_configs(
    reseller_id: Optional[int] = Query(None),
    marzban_panel_id: Optional[int] = Query(None), # Allows filtering by panel
    skip: int = Query(0),
    limit: int = Query(100),
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    # This endpoint might need more sophisticated filtering logic in the service if many params
    if reseller_id is not None:
        # If marzban_panel_id is also provided, service handles it. If not, service gets all for reseller.
        # The -1 hack in service is not ideal for API. Let's pass None or actual ID.
        pricings = reseller_pricing_service.get_reseller_pricings_for_reseller(
            db=db, reseller_id=reseller_id, 
            marzban_panel_id=marzban_panel_id if marzban_panel_id is not None else -1 # Re-evaluate this -1
        )
    else:
        # Basic get all if no reseller_id, service might need a get_all_pricings function
        # For now, this will be empty if reseller_id is None.
        # A proper get_all_pricings or more advanced filtering in service would be better.
        # Let's assume for now this requires at least a reseller_id for meaningful data.
        # OR: create a get_all_reseller_pricings in service. For now, limiting scope.
        # Returning empty list if no reseller_id is probably not what user expects for a general GET /.
    # If reseller_id is provided, filter by it. Otherwise, list all (requires new/modified service).
    # For now, if reseller_id is None, we return an empty list as get_reseller_pricings_for_reseller needs it.
    # A proper implementation would be a service.get_all_pricings(reseller_id=reseller_id, ...)
    pricings = []
    if reseller_id is not None:
        effective_panel_id = marzban_panel_id if marzban_panel_id is not None else -1 # -1 for service "all for this reseller"
        pricings = reseller_pricing_service.get_reseller_pricings_for_reseller(
            db=db, reseller_id=reseller_id, marzban_panel_id=effective_panel_id
        )
    else:
        # TODO: Implement service reseller_pricing_service.get_all_reseller_pricings(db, skip, limit)
        # For now, returning empty or could raise 501 Not Implemented
        pass # Returns empty list

    return pricings

@router.get("/{pricing_id}", response_model=ResellerPricingRead)
def read_reseller_pricing_config(
    pricing_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    db_pricing = reseller_pricing_service.get_reseller_pricing(db=db, pricing_id=pricing_id)
    if db_pricing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseller pricing configuration not found")
    return db_pricing

@router.put("/{pricing_id}", response_model=ResellerPricingRead)
def update_reseller_pricing_config(
    pricing_id: int,
    pricing_in: ResellerPricingUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    try:
        updated_pricing = reseller_pricing_service.update_reseller_pricing(
            db=db, pricing_id=pricing_id, pricing_in=pricing_in
        )
        if updated_pricing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseller pricing configuration not found")
        return updated_pricing
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except IntegrityError as e: # Catch DB unique constraint violations
        db.rollback()
        if "uq_reseller_panel_pricing" in str(e.orig).lower():
            detail = "Updating this configuration would conflict with an existing one for the same reseller and Marzban panel."
        else:
            detail = "Database integrity error during update."
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


@router.delete("/{pricing_id}", response_model=ResellerPricingRead)
def delete_reseller_pricing_config(
    pricing_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    deleted_pricing = reseller_pricing_service.delete_reseller_pricing(db=db, pricing_id=pricing_id)
    if deleted_pricing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseller pricing configuration not found")
    return deleted_pricing

# Path adjusted to be /reseller-pricings/for-reseller/{reseller_id}
@router.get("/for-reseller/{reseller_id}", response_model=List[ResellerPricingRead], tags=["Reseller Pricings"])
def read_pricings_for_specific_reseller( # Renamed function for clarity
    reseller_id: int,
    marzban_panel_id: Optional[int] = Query(None, description="Filter by specific Marzban panel ID. If not provided, returns all for reseller."),
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin)
):
    # If marzban_panel_id is None from query, pass -1 to service to get all for reseller.
    # If marzban_panel_id is a value, pass that value to get specific panel pricing.
    # If marzban_panel_id should target generic (NULL in DB), API could define a specific value like 0 or "generic"
    # or service `get_reseller_pricings_for_reseller` could be modified to take `None` for generic.
    # Current service: marzban_panel_id = -1 means no panel filter (all for reseller)
    #                  marzban_panel_id = value means filter by that panel_id (value can be None for generic if DB stores it as NULL)
    
    effective_panel_filter = -1 # Default to "all for reseller"
    if marzban_panel_id is not None: # User specified a panel filter
        effective_panel_filter = marzban_panel_id 
        # If user wants to query for generic pricing (marzban_panel_id IS NULL in DB),
        # they would pass marzban_panel_id= (empty) or a conventional value like 0 if API defines it.
        # For now, if marzban_panel_id query param is an int, it targets that panel.
        # If marzban_panel_id query param is NOT given, it means "all for reseller" (-1 to service).

    pricings = reseller_pricing_service.get_reseller_pricings_for_reseller(
        db=db, reseller_id=reseller_id, marzban_panel_id=effective_panel_filter
    )
    # An empty list is a valid response if no pricings match.
    return pricings
