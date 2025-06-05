from sqlalchemy.orm import Session, selectinload, joinedload
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from app.db.models.payment_receipt import PaymentReceipt
from app.db.models.reseller import Reseller
from app.db.models.transaction import Transaction # Needed for type hinting if returned by a method
from app.schemas.transaction import TransactionCreate
from app.services.transaction_service import create_transaction # To log the transaction

class PaymentReceiptServiceError(Exception):
    pass

def get_receipt(db: Session, receipt_id: int) -> Optional[PaymentReceipt]:
    return db.query(PaymentReceipt).options(
        selectinload(PaymentReceipt.reseller),
        selectinload(PaymentReceipt.transaction) # To populate transaction in PaymentReceiptRead if needed
    ).filter(PaymentReceipt.id == receipt_id).first()

def get_receipts_by_status(
    db: Session, status: str, skip: int = 0, limit: int = 100
) -> List[PaymentReceipt]:
    return db.query(PaymentReceipt).options(
        selectinload(PaymentReceipt.reseller)
    ).filter(PaymentReceipt.status == status).order_by(PaymentReceipt.submitted_at.asc()).offset(skip).limit(limit).all()

def get_all_receipts_for_reseller( # New function that might be useful for reseller view
    db: Session, reseller_id: int, skip: int = 0, limit: int = 100
) -> List[PaymentReceipt]:
     return db.query(PaymentReceipt).options(
        selectinload(PaymentReceipt.reseller) # Redundant if filtered by reseller_id but good for consistency
    ).filter(PaymentReceipt.reseller_id == reseller_id).order_by(PaymentReceipt.submitted_at.desc()).offset(skip).limit(limit).all()


def approve_receipt(
    db: Session, receipt_id: int, admin_id: int, admin_notes: Optional[str] = None
) -> PaymentReceipt:
    """
    Approves a payment receipt.
    - Updates receipt status to 'approved'.
    - Creates a 'wallet_top_up' transaction.
    - Updates reseller's wallet_balance.
    All in a single database transaction.
    """
    db_receipt = get_receipt(db, receipt_id)
    if not db_receipt:
        raise PaymentReceiptServiceError(f"Payment receipt with ID {receipt_id} not found.")
    
    if db_receipt.status != 'pending':
        raise PaymentReceiptServiceError(f"Receipt is not pending. Current status: {db_receipt.status}.")

    db_reseller = db.query(Reseller).filter(Reseller.id == db_receipt.reseller_id).first()
    if not db_reseller:
        # Should not happen if DB constraints are fine, but good check
        raise PaymentReceiptServiceError(f"Reseller with ID {db_receipt.reseller_id} not found for receipt.")

    try:
        db_receipt.status = 'approved'
        db_receipt.reviewed_at = datetime.utcnow()
        db_receipt.admin_notes = admin_notes
        # admin_id can be logged here if a field for reviewed_by_admin_id is added to PaymentReceipt model

        # 2. Create a 'wallet_top_up' transaction
        transaction_data = TransactionCreate(
            reseller_id=db_receipt.reseller_id,
            transaction_type='wallet_top_up',
            amount=db_receipt.amount, # Positive amount for top-up
            description=f"Wallet top-up from approved receipt ID: {db_receipt.id}. Admin ID: {admin_id}.",
            payment_receipt_id=db_receipt.id
        )
        # Note: create_transaction will commit itself. For full atomicity of approve_receipt,
        # create_transaction should not commit, and the commit should happen here.
        # Let's modify create_transaction to not commit, or make a version that doesn't.
        # For now, assuming create_transaction commits is a slight break in full atomicity if subsequent lines fail.
        # To fix: transaction_service.create_transaction_no_commit(db, transaction_data)
        # then db.commit() at the end here.
        # For simplicity of this subtask, we'll proceed with create_transaction committing itself.
        # A more robust solution would use a unit of work pattern or pass session around.
        
        # Let's refine: create_transaction should NOT commit.
        # The service method orchestrating multiple DB changes should handle the commit.
        # I will need to go back and modify transaction_service.create_transaction.
        # For now, I will write it as if create_transaction does not commit.
        
        created_tx = Transaction(**transaction_data.dict())
        db.add(created_tx)
        # db_receipt.transaction_id = created_tx.id # Not needed if using FK on transaction table.

        # 3. Update reseller's wallet_balance
        db_reseller.wallet_balance = (db_reseller.wallet_balance or Decimal('0.0')) + db_receipt.amount
        
        db.add(db_receipt)
        db.add(db_reseller)
        
        db.commit() # Commit all changes: receipt status, new transaction, wallet balance
        
        db.refresh(db_receipt)
        db.refresh(db_reseller)
        # db.refresh(created_tx) # If created_tx is used after commit
        
        return db_receipt
    except Exception as e:
        db.rollback()
        raise PaymentReceiptServiceError(f"Error approving receipt: {str(e)}")


def reject_receipt(
    db: Session, receipt_id: int, admin_id: int, admin_notes: Optional[str] = None
) -> PaymentReceipt:
    """
    Rejects a payment receipt.
    - Updates receipt status to 'rejected'.
    """
    db_receipt = get_receipt(db, receipt_id)
    if not db_receipt:
        raise PaymentReceiptServiceError(f"Payment receipt with ID {receipt_id} not found.")

    if db_receipt.status != 'pending':
        raise PaymentReceiptServiceError(f"Receipt is not pending. Current status: {db_receipt.status}.")

    try:
        db_receipt.status = 'rejected'
        db_receipt.reviewed_at = datetime.utcnow()
        db_receipt.admin_notes = admin_notes if admin_notes else "Receipt rejected by admin."
        # Log admin_id if field exists

        db.add(db_receipt)
        db.commit()
        db.refresh(db_receipt)
        return db_receipt

# --- Reseller-facing functions ---

def create_receipt_for_reseller(
    db: Session, receipt_in: PaymentReceiptCreate, reseller_id: int
) -> PaymentReceipt:
    """
    Creates a new payment receipt for a given reseller with 'pending' status.
    """
    # Ensure the reseller_id from the token overrides any in payload
    db_receipt = PaymentReceipt(
        reseller_id=reseller_id,
        amount=receipt_in.amount,
        receipt_reference=receipt_in.receipt_reference,
        status='pending' # Initial status
        # submitted_at is handled by server_default in model
    )
    db.add(db_receipt)
    db.commit()
    db.refresh(db_receipt)
    return db_receipt
    except Exception as e:
        db.rollback()
        raise PaymentReceiptServiceError(f"Error rejecting receipt: {str(e)}")
