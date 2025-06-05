from sqlalchemy import (
    Column, Integer, String, TIMESTAMP, func, Boolean, TEXT, ForeignKey,
    UniqueConstraint, JSON
)
from sqlalchemy.orm import relationship
from app.db.base import Base

class MarzbanUser(Base):
    __tablename__ = "marzban_users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    marzban_username = Column(String(255), nullable=False, index=True)
    marzban_panel_id = Column(Integer, ForeignKey("marzban_panels.id", ondelete="CASCADE"), nullable=False)
    reseller_id = Column(Integer, ForeignKey("resellers.id", ondelete="CASCADE"), nullable=False, index=True)
    
    created_by_new_panel = Column(Boolean, default=False, nullable=False) # True if created by this system
    notes = Column(TEXT, nullable=True)
    
    last_synced_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    api_response_data = Column(JSON, nullable=True) # Store raw API response for this user

    # Relationships
    marzban_panel = relationship("MarzbanPanel", back_populates="marzban_users")
    reseller = relationship("Reseller", back_populates="marzban_users")
    
    # Back-populate to Transactions (one MarzbanUser can have many transactions)
    transactions = relationship("Transaction", back_populates="marzban_user")


    __table_args__ = (
        UniqueConstraint("marzban_username", "marzban_panel_id", name="uq_marzban_user_panel_username"),
    )

# Relationships to be added in other models:
# In MarzbanPanel: marzban_users = relationship("MarzbanUser", back_populates="marzban_panel")
# In Reseller: marzban_users = relationship("MarzbanUser", back_populates="reseller")
# In Transaction: marzban_user = relationship("MarzbanUser", back_populates="transactions") (already planned)
