from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.models.marzban_panel import MarzbanPanel
from app.schemas.marzban_panel import MarzbanPanelCreate, MarzbanPanelUpdate
from app.utils.encryption import encrypt_data, decrypt_data

def create_panel(db: Session, panel_in: MarzbanPanelCreate) -> MarzbanPanel:
    encrypted_password = encrypt_data(panel_in.admin_password)
    db_panel = MarzbanPanel(
        name=panel_in.name,
        api_url=str(panel_in.api_url), # Ensure HttpUrl is converted to string for DB
        admin_username=panel_in.admin_username,
        encrypted_admin_password=encrypted_password
    )
    db.add(db_panel)
    db.commit()
    db.refresh(db_panel)
    return db_panel

def get_panel(db: Session, panel_id: int) -> Optional[MarzbanPanel]:
    return db.query(MarzbanPanel).filter(MarzbanPanel.id == panel_id).first()

def get_panels(db: Session, skip: int = 0, limit: int = 100) -> List[MarzbanPanel]:
    return db.query(MarzbanPanel).offset(skip).limit(limit).all()

def update_panel(db: Session, panel_id: int, panel_in: MarzbanPanelUpdate) -> Optional[MarzbanPanel]:
    db_panel = get_panel(db, panel_id)
    if not db_panel:
        return None
    
    update_data = panel_in.dict(exclude_unset=True)
    
    if "admin_password" in update_data and update_data["admin_password"] is not None:
        encrypted_password = encrypt_data(update_data["admin_password"])
        db_panel.encrypted_admin_password = encrypted_password
        del update_data["admin_password"] # Avoid trying to set it directly on the model

    if "api_url" in update_data and update_data["api_url"] is not None:
        db_panel.api_url = str(update_data["api_url"]) # Ensure HttpUrl is converted to string
        del update_data["api_url"]

    for key, value in update_data.items():
        setattr(db_panel, key, value)
        
    db.add(db_panel)
    db.commit()
    db.refresh(db_panel)
    return db_panel

def delete_panel(db: Session, panel_id: int) -> Optional[MarzbanPanel]:
    db_panel = get_panel(db, panel_id)
    if db_panel:
        db.delete(db_panel)
        db.commit()
    return db_panel

def get_panel_decrypted_password(db: Session, panel_id: int) -> Optional[str]:
    db_panel = get_panel(db, panel_id)
    if db_panel and db_panel.encrypted_admin_password:
        try:
            return decrypt_data(db_panel.encrypted_admin_password)
        except ValueError: # Or more specific InvalidToken from encryption util
            # Log error or handle appropriately if decryption fails
            return None 
    return None
