from sqlalchemy import Column, Integer, String, TIMESTAMP, func
from sqlalchemy.orm import relationship # Import relationship
from app.db.base import Base

class MarzbanPanel(Base):
    __tablename__ = "marzban_panels"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    api_url = Column(String(255), nullable=False)
    admin_username = Column(String(255), nullable=False)
    encrypted_admin_password = Column(String(512), nullable=False) # Increased length for encrypted data
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationship to Reseller via ResellerPanelAccess
    resellers = relationship(
        "Reseller",
        secondary="reseller_panel_accesses",
        back_populates="panels",
        lazy="selectin"
    )

    # Relationship to MarzbanUser
    marzban_users = relationship(
        "MarzbanUser",
        back_populates="marzban_panel",
        cascade="all, delete-orphan", # If a panel is deleted, its synced users are also deleted.
        lazy="selectin"
    )
