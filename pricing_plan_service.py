from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.models.pricing_plan import PricingPlan
from app.schemas.pricing_plan import PricingPlanCreate, PricingPlanUpdate

def create_plan(db: Session, plan_in: PricingPlanCreate) -> PricingPlan:
    db_plan = PricingPlan(
        name=plan_in.name,
        data_limit_gb=plan_in.data_limit_gb,
        duration_days=plan_in.duration_days,
        price=plan_in.price,
        is_active=plan_in.is_active
    )
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    return db_plan

def get_plan(db: Session, plan_id: int) -> Optional[PricingPlan]:
    return db.query(PricingPlan).filter(PricingPlan.id == plan_id).first()

def get_plan_by_name(db: Session, name: str) -> Optional[PricingPlan]:
    return db.query(PricingPlan).filter(PricingPlan.name == name).first()

def get_plans(db: Session, skip: int = 0, limit: int = 100, active_only: bool = False) -> List[PricingPlan]:
    query = db.query(PricingPlan)
    if active_only:
        query = query.filter(PricingPlan.is_active == True)
    return query.offset(skip).limit(limit).all()

def update_plan(db: Session, plan_id: int, plan_in: PricingPlanUpdate) -> Optional[PricingPlan]:
    db_plan = get_plan(db, plan_id)
    if not db_plan:
        return None
    
    update_data = plan_in.dict(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_plan, key, value)
        
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    return db_plan

def delete_plan(db: Session, plan_id: int) -> Optional[PricingPlan]:
    db_plan = get_plan(db, plan_id)
    if db_plan:
        # Consider implications: if plan is in use, simple deletion might cause issues.
        # For now, hard delete as per subtask.
        # Future: Soft delete (db_plan.is_active = False) or check dependencies.
        db.delete(db_plan)
        db.commit()
    return db_plan
