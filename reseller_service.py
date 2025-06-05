from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from app.db.models.reseller import Reseller
from app.db.models.marzban_panel import MarzbanPanel
from app.db.models.reseller_panel_access import ResellerPanelAccess
from app.schemas.reseller import ResellerCreate, ResellerUpdate
from app.utils.security import create_password_hash # Reusing admin password hashing

def create_reseller(db: Session, reseller_in: ResellerCreate) -> Reseller:
    hashed_password = create_password_hash(reseller_in.password)
    db_reseller = Reseller(
        username=reseller_in.username,
        marzban_admin_id=reseller_in.marzban_admin_id,
        password_hash=hashed_password,
        full_name=reseller_in.full_name,
        email=reseller_in.email
        # wallet_balance, is_active, allow_negative_balance use defaults
    )
    db.add(db_reseller)
    db.commit()
    db.refresh(db_reseller)
    return db_reseller

def get_reseller(db: Session, reseller_id: int) -> Optional[Reseller]:
    # Use joinedload to efficiently fetch related panels
    return db.query(Reseller).options(joinedload(Reseller.panels)).filter(Reseller.id == reseller_id).first()

def get_reseller_by_username(db: Session, username: str) -> Optional[Reseller]:
    return db.query(Reseller).options(joinedload(Reseller.panels)).filter(Reseller.username == username).first()

def get_reseller_by_marzban_admin_id(db: Session, marzban_admin_id: int) -> Optional[Reseller]:
     return db.query(Reseller).options(joinedload(Reseller.panels)).filter(Reseller.marzban_admin_id == marzban_admin_id).first()

def get_resellers(db: Session, skip: int = 0, limit: int = 100) -> List[Reseller]:
    return db.query(Reseller).options(joinedload(Reseller.panels)).offset(skip).limit(limit).all()

def update_reseller(db: Session, reseller_id: int, reseller_in: ResellerUpdate) -> Optional[Reseller]:
    db_reseller = get_reseller(db, reseller_id) # This already loads panels if needed later
    if not db_reseller:
        return None

    update_data = reseller_in.dict(exclude_unset=True)

    if "password" in update_data and update_data["password"] is not None:
        hashed_password = create_password_hash(update_data["password"])
        db_reseller.password_hash = hashed_password
        del update_data["password"]

    for key, value in update_data.items():
        setattr(db_reseller, key, value)
    
    db.add(db_reseller)
    db.commit()
    db.refresh(db_reseller)
    # Refresh related panels if they were part of the update logic (not in this ResellerUpdate schema directly)
    # For this specific ResellerUpdate schema, only Reseller fields are updated.
    # If panels were updated, you might need db.refresh(db_reseller, attribute_names=['panels'])
    return db_reseller

def delete_reseller(db: Session, reseller_id: int) -> Optional[Reseller]:
    db_reseller = get_reseller(db, reseller_id)
    if db_reseller:
        # Related ResellerPanelAccess entries should be deleted due to "ondelete=CASCADE"
        db.delete(db_reseller)
        db.commit()
    return db_reseller

def update_reseller_panel_access(db: Session, reseller_id: int, panel_ids: List[int]) -> Optional[Reseller]:
    db_reseller = get_reseller(db, reseller_id)
    if not db_reseller:
        return None

    # Clear existing panel access for this reseller
    db.query(ResellerPanelAccess).filter(ResellerPanelAccess.reseller_id == reseller_id).delete()

    # Add new panel access
    for panel_id in panel_ids:
        # Optional: Check if panel_id exists in MarzbanPanel table before adding
        panel = db.query(MarzbanPanel).filter(MarzbanPanel.id == panel_id).first()
        if panel: # Only add if panel exists
            access_entry = ResellerPanelAccess(reseller_id=reseller_id, marzban_panel_id=panel_id)
            db.add(access_entry)
    
    db.commit()
    db.refresh(db_reseller) # Refresh to get the updated 'panels' relationship
    # Explicitly load panels again after commit if not automatically refreshed by relationship config
    db_reseller = db.query(Reseller).options(joinedload(Reseller.panels)).filter(Reseller.id == reseller_id).first()
    return db_reseller


def get_reseller_panel_access(db: Session, reseller_id: int) -> List[MarzbanPanel]:
    db_reseller = get_reseller(db, reseller_id) # This should already load panels due to joinedload
    if not db_reseller:
        return []
    return db_reseller.panels


def update_reseller_password(
    db: Session, reseller: Reseller, current_password: str, new_password: str
) -> bool:
    """
    Updates a reseller's password after verifying the current password.
    Returns True on success, False on current password mismatch.
    """
    if not verify_password(current_password, reseller.password_hash):
        return False
    
    new_hashed_password = create_password_hash(new_password)
    reseller.password_hash = new_hashed_password
    db.add(reseller)
    db.commit()
    # No db.refresh(reseller) needed here as we are not returning the reseller object directly,
    # and the change is committed. The caller might refresh if they hold onto the instance.
    return True
