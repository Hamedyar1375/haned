from sqlalchemy.orm import Session, joinedload, selectinload
from typing import List, Optional

from app.db.models.reseller_pricing import ResellerPricing
from app.db.models.reseller import Reseller
from app.db.models.pricing_plan import PricingPlan
from app.db.models.marzban_panel import MarzbanPanel
from app.schemas.reseller_pricing import ResellerPricingCreate, ResellerPricingUpdate
from sqlalchemy.exc import IntegrityError


def _validate_pricing_input(pricing_in: ResellerPricingCreate | ResellerPricingUpdate, db_pricing: Optional[ResellerPricing] = None):
    """
    Validates that either pricing_plan_id or custom_price_per_gb is set, but not both.
    If db_pricing is provided (for updates), it considers existing values.
    """
    plan_id = pricing_in.pricing_plan_id
    custom_gb_price = pricing_in.custom_price_per_gb

    if isinstance(pricing_in, ResellerPricingUpdate):
        # For updates, if a field is not in the payload, use existing value from db_pricing
        if pricing_in.pricing_plan_id is None and 'pricing_plan_id' not in pricing_in.dict(exclude_unset=True):
            plan_id = db_pricing.pricing_plan_id if db_pricing else None
        if pricing_in.custom_price_per_gb is None and 'custom_price_per_gb' not in pricing_in.dict(exclude_unset=True):
            custom_gb_price = db_pricing.custom_price_per_gb if db_pricing else None
    
    if plan_id is not None and custom_gb_price is not None:
        raise ValueError("Cannot set both pricing_plan_id and custom_price_per_gb. Choose one.")
    if plan_id is None and custom_gb_price is None:
        # This condition should not be hit if validator in schema is working for ResellerPricingCreate
        # For ResellerPricingUpdate, it's possible if user tries to unset both, which should be disallowed.
        raise ValueError("Either pricing_plan_id or custom_price_per_gb must be set.")


def create_reseller_pricing(db: Session, pricing_in: ResellerPricingCreate) -> ResellerPricing:
    _validate_pricing_input(pricing_in)

    # Check for existing config for this reseller and panel (if panel_id is provided)
    # The UniqueConstraint on the model (`uq_reseller_panel_pricing`) handles this at DB level.
    # A pre-check can provide a friendlier error.
    existing_q = db.query(ResellerPricing).filter(
        ResellerPricing.reseller_id == pricing_in.reseller_id,
        ResellerPricing.marzban_panel_id == pricing_in.marzban_panel_id
    )
    if existing_q.first():
        panel_msg = f"for panel ID {pricing_in.marzban_panel_id}" if pricing_in.marzban_panel_id else "generically"
        raise IntegrityError(
            f"Reseller already has a pricing configuration {panel_msg}.",
            params=None, orig=None # Mimic IntegrityError structure if caught by endpoint
        )

    db_pricing = ResellerPricing(**pricing_in.dict())
    db.add(db_pricing)
    db.commit()
    db.refresh(db_pricing)
    return db_pricing

def get_reseller_pricing(db: Session, pricing_id: int) -> Optional[ResellerPricing]:
    return db.query(ResellerPricing).options(
        selectinload(ResellerPricing.reseller),
        selectinload(ResellerPricing.pricing_plan),
        selectinload(ResellerPricing.marzban_panel)
    ).filter(ResellerPricing.id == pricing_id).first()

def get_reseller_pricings_for_reseller(
    db: Session, reseller_id: int, marzban_panel_id: Optional[int] = -1 # Use -1 to signify not filtering by panel
) -> List[ResellerPricing]:
    query = db.query(ResellerPricing).options(
        selectinload(ResellerPricing.reseller),
        selectinload(ResellerPricing.pricing_plan),
        selectinload(ResellerPricing.marzban_panel)
    ).filter(ResellerPricing.reseller_id == reseller_id)
    
    if marzban_panel_id != -1: # If marzban_panel_id is provided (None or an actual ID)
        query = query.filter(ResellerPricing.marzban_panel_id == marzban_panel_id)
        
    return query.all()

def update_reseller_pricing(
    db: Session, pricing_id: int, pricing_in: ResellerPricingUpdate
) -> Optional[ResellerPricing]:
    db_pricing = get_reseller_pricing(db, pricing_id)
    if not db_pricing:
        return None

    update_data = pricing_in.dict(exclude_unset=True)
    
    # Apply the same validation logic for pricing type
    # Create a temporary merged state for validation
    temp_pricing_state = db_pricing.__dict__.copy()
    temp_pricing_state.update(update_data)
    
    # Convert to a Pydantic model like structure for the validator if needed, or adapt validator
    # For simplicity, directly check conditions based on update_data and db_pricing
    
    final_plan_id = update_data.get('pricing_plan_id', db_pricing.pricing_plan_id)
    final_custom_price = update_data.get('custom_price_per_gb', db_pricing.custom_price_per_gb)

    if 'pricing_plan_id' in update_data and update_data['pricing_plan_id'] is not None:
        final_custom_price = None # Nullify custom_price if plan_id is being set
        if 'custom_price_per_gb' not in update_data: # Ensure it's explicitly set to None in DB
             update_data['custom_price_per_gb'] = None
    elif 'custom_price_per_gb' in update_data and update_data['custom_price_per_gb'] is not None:
        final_plan_id = None # Nullify plan_id if custom_price is being set
        if 'pricing_plan_id' not in update_data: # Ensure it's explicitly set to None in DB
            update_data['pricing_plan_id'] = None

    if final_plan_id is not None and final_custom_price is not None:
         raise ValueError("Cannot set both pricing_plan_id and custom_price_per_gb. Choose one.")
    if final_plan_id is None and final_custom_price is None:
         # This check is important for updates if user tries to nullify both pricing mechanisms
         raise ValueError("Either pricing_plan_id or custom_price_per_gb must be set.")


    # Check for unique constraint (reseller_id, marzban_panel_id) if marzban_panel_id is changing
    if 'marzban_panel_id' in update_data and update_data['marzban_panel_id'] != db_pricing.marzban_panel_id:
        existing_q = db.query(ResellerPricing).filter(
            ResellerPricing.reseller_id == db_pricing.reseller_id, # reseller_id doesn't change
            ResellerPricing.marzban_panel_id == update_data['marzban_panel_id'],
            ResellerPricing.id != pricing_id # Exclude the current record
        )
        if existing_q.first():
            panel_msg = f"for panel ID {update_data['marzban_panel_id']}" if update_data['marzban_panel_id'] else "generically"
            raise IntegrityError(
                f"Reseller already has a pricing configuration {panel_msg}.",
                params=None, orig=None
            )
            
    for key, value in update_data.items():
        setattr(db_pricing, key, value)
    
    db.add(db_pricing)
    db.commit()
    db.refresh(db_pricing)
    return db_pricing

def delete_reseller_pricing(db: Session, pricing_id: int) -> Optional[ResellerPricing]:
    db_pricing = get_reseller_pricing(db, pricing_id)
    if db_pricing:
        db.delete(db_pricing)
        db.commit()
    return db_pricing

def get_active_pricing_for_reseller(
    db: Session, reseller_id: int, marzban_panel_id: Optional[int] = None
) -> Optional[ResellerPricing]:
    """
    Fetches the active pricing for a reseller.
    If marzban_panel_id is provided, it first looks for panel-specific pricing.
    If not found, or if marzban_panel_id is None, it looks for generic pricing for the reseller.
    """
    pricing = None
    if marzban_panel_id is not None:
        # Try to find panel-specific pricing
        pricing = db.query(ResellerPricing).options(
            selectinload(ResellerPricing.pricing_plan) # Load plan for cost calculation
        ).filter(
            ResellerPricing.reseller_id == reseller_id,
            ResellerPricing.marzban_panel_id == marzban_panel_id
        ).first()

    if pricing:
        return pricing

    # If no panel-specific pricing or no panel_id given, try to find generic pricing
    return db.query(ResellerPricing).options(
        selectinload(ResellerPricing.pricing_plan)
    ).filter(
        ResellerPricing.reseller_id == reseller_id,
        ResellerPricing.marzban_panel_id == None # Generic configuration
    ).first()
