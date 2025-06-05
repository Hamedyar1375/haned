from sqlalchemy import Column, Integer, String, TIMESTAMP, func, DECIMAL, TEXT, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
# Import Transaction model for the relationship, ensure no circular dependency issues at runtime
# by using string for ForeignKey and being careful with relationship population.
# from .transaction import Transaction # Not strictly needed here if using string in relationship()

class PaymentReceipt(Base):
    __tablename__ = "payment_receipts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    reseller_id = Column(Integer, ForeignKey("resellers.id", ondelete="CASCADE"), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    receipt_reference = Column(String(255), nullable=False) # URL or transaction ID
    status = Column(String(50), default='pending', nullable=False, index=True) # 'pending', 'approved', 'rejected'
    admin_notes = Column(TEXT, nullable=True)
    submitted_at = Column(TIMESTAMP, server_default=func.now(), nullable=False, index=True)
    reviewed_at = Column(TIMESTAMP, nullable=True)

    # Relationships
    reseller = relationship("Reseller", back_populates="payment_receipts")
    
    # Relationship to Transaction: One receipt leads to one transaction (for top-up)
    transaction = relationship(
        "Transaction",
        # foreign_keys="Transaction.payment_receipt_id", # Not needed if primaryjoin is used or clear from FK
        primaryjoin="PaymentReceipt.id == foreign(Transaction.payment_receipt_id)", # Correct join condition
        back_populates="payment_receipt", # Corresponds to Transaction.payment_receipt
        uselist=False # One-to-one
    )

# Update Reseller model to have 'payment_receipts' relationship
# This will be done in the Reseller model file.
