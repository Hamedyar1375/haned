from sqlalchemy import (
    Column, Integer, String, TIMESTAMP, func, DECIMAL, TEXT, ForeignKey,
    UniqueConstraint, CheckConstraint
)
from sqlalchemy.orm import relationship
from app.db.base import Base

class ResellerPricing(Base):
    __tablename__ = "reseller_pricings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    reseller_id = Column(Integer, ForeignKey("resellers.id", ondelete="CASCADE"), nullable=False)
    # ondelete="SET NULL" for pricing_plan_id: if a plan is deleted, this config doesn't get deleted,
    # but the link is nullified. Admin might need to update it.
    pricing_plan_id = Column(Integer, ForeignKey("pricing_plans.id", ondelete="SET NULL"), nullable=True)
    custom_price_per_gb = Column(DECIMAL(10, 2), nullable=True)
    # ondelete="CASCADE": if a panel is deleted, this specific pricing for that panel is also deleted.
    marzban_panel_id = Column(Integer, ForeignKey("marzban_panels.id", ondelete="CASCADE"), nullable=True)
    notes = Column(TEXT, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationships
    reseller = relationship("Reseller", back_populates="pricing_configs")
    pricing_plan = relationship("PricingPlan") # No back_populates needed if PricingPlan doesn't need to list ResellerPricings
    marzban_panel = relationship("MarzbanPanel") # No back_populates needed if MarzbanPanel doesn't need to list ResellerPricings

    __table_args__ = (
        # Ensures a reseller has only one pricing configuration per panel.
        # A NULL marzban_panel_id means a generic configuration for that reseller.
        # If marzban_panel_id is part of the key, then (reseller_id, NULL) is different from (reseller_id, 1)
        UniqueConstraint("reseller_id", "marzban_panel_id", name="uq_reseller_panel_pricing"),
        # DB-level check constraint for pricing_plan_id XOR custom_price_per_gb can be added for extra safety,
        # but primary enforcement will be in the service layer as requested.
        # Example: CheckConstraint(
        #    "(pricing_plan_id IS NOT NULL AND custom_price_per_gb IS NULL) OR "
        #    "(pricing_plan_id IS NULL AND custom_price_per_gb IS NOT NULL)",
        #    name="chk_pricing_type"
        # )
        # For now, focusing on service layer validation for this specific rule.
    )

# Now, update Reseller model to have 'pricing_configs' relationship
# from app.db.models.reseller import Reseller # This would cause circular import if done here
# Reseller.pricing_configs = relationship("ResellerPricing", back_populates="reseller")
# This kind of reverse relationship setup is better done directly in the Reseller model file.
