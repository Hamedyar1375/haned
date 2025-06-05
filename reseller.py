from sqlalchemy import Column, Integer, String, TIMESTAMP, func, Boolean, DECIMAL
from sqlalchemy.orm import relationship
from sqlalchemy.sql import expression # Moved import to the top
from app.db.base import Base

class Reseller(Base):
    __tablename__ = "resellers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    marzban_admin_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    wallet_balance = Column(DECIMAL(10, 2), nullable=False, server_default="0.00") # Correct
    is_active = Column(Boolean, nullable=False, server_default=expression.true()) # Correct
    allow_negative_balance = Column(Boolean, nullable=False, server_default=expression.false()) # Correct
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationship to MarzbanPanel via ResellerPanelAccess
    # The 'secondary' argument points to the association table.
    panels = relationship(
        "MarzbanPanel",
        secondary="reseller_panel_accesses",
        back_populates="resellers",
        lazy="selectin"
    )

    # Relationship to ResellerPricing
    pricing_configs = relationship(
        "ResellerPricing",
        back_populates="reseller",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    # Relationship to Transaction
    transactions = relationship(
        "Transaction",
        back_populates="reseller",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    # Relationship to PaymentReceipt
    payment_receipts = relationship(
        "PaymentReceipt",
        back_populates="reseller",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    # Relationship to MarzbanUser
    marzban_users = relationship(
        "MarzbanUser",
        back_populates="reseller",
        cascade="all, delete-orphan", # If a reseller is deleted, their associated Marzban users are also deleted.
        lazy="selectin"
    )
# Removed the redundant import from the bottom
