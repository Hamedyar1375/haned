from sqlalchemy import Column, Integer, String, TIMESTAMP, func, DECIMAL, TEXT, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    reseller_id = Column(Integer, ForeignKey("resellers.id", ondelete="CASCADE"), nullable=False)
    transaction_type = Column(String(50), nullable=False, index=True)
    amount = Column(DECIMAL(10, 2), nullable=False)
    
    # Changed from marzban_user_username to marzban_user_id
    marzban_user_id = Column(Integer, ForeignKey("marzban_users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    pricing_plan_id = Column(Integer, ForeignKey("pricing_plans.id", ondelete="SET NULL"), nullable=True)
    reseller_pricing_id = Column(Integer, ForeignKey("reseller_pricings.id", ondelete="SET NULL"), nullable=True)
    
    description = Column(TEXT, nullable=True)
    
    # Link to the payment receipt if this transaction is a result of a top-up
    payment_receipt_id = Column(Integer, ForeignKey("payment_receipts.id", ondelete="SET NULL"), nullable=True, unique=True) 
    # unique=True assumes one transaction per receipt. If a receipt could result in multiple transactions, remove unique.
    # For top-up, it's usually one-to-one.

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False, index=True)

    # Relationships
    reseller = relationship("Reseller", back_populates="transactions")
    pricing_plan = relationship("PricingPlan")
    reseller_pricing = relationship("ResellerPricing")
    payment_receipt = relationship(
        "PaymentReceipt",
        foreign_keys=[payment_receipt_id],
        back_populates="transaction",
        uselist=False
    )
    marzban_user = relationship("MarzbanUser", back_populates="transactions") # New relationship

# Update Reseller model to have 'transactions' relationship
# This will be done in the Reseller model file.
