from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Dict

# Project imports
from app.db.session import get_db
from app.db.models.reseller import Reseller as ResellerModel # SQLAlchemy model
from app.schemas.transaction import TransactionRead
from app.schemas.payment_receipt import PaymentReceiptCreate, PaymentReceiptRead
from app.services import transaction_service, payment_receipt_service
from app.api.v1.endpoints.reseller_auth import get_current_active_reseller # Dependency

router = APIRouter()

@router.get("/balance", response_model=Dict[str, float]) # Using float for balance in response for simplicity
def get_reseller_wallet_balance(
    current_reseller: ResellerModel = Depends(get_current_active_reseller)
):
    """
    Get current reseller's wallet balance.
    """
    # Convert Decimal to float for JSON response if not automatically handled by FastAPI's encoder
    return {"wallet_balance": float(current_reseller.wallet_balance)}


@router.get("/transactions", response_model=List[TransactionRead])
def list_reseller_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200), # Max 200 transactions per page
    current_reseller: ResellerModel = Depends(get_current_active_reseller),
    db: Session = Depends(get_db)
):
    """
    List transactions for the current reseller.
    """
    transactions = transaction_service.get_transactions_for_reseller(
        db=db, reseller_id=current_reseller.id, skip=skip, limit=limit
    )
    return transactions


@router.post("/receipts", response_model=PaymentReceiptRead, status_code=status.HTTP_201_CREATED)
def submit_payment_receipt(
    receipt_in: PaymentReceiptCreate, # Reseller provides amount and reference
    current_reseller: ResellerModel = Depends(get_current_active_reseller),
    db: Session = Depends(get_db)
):
    """
    Submit a new payment receipt for wallet top-up.
    The reseller_id from the payload will be ignored; authenticated reseller's ID is used.
    """
    # Create a new PaymentReceiptCreate instance if you want to ensure reseller_id from token is used
    # and not one from a potentially malicious payload.
    # However, create_receipt_for_reseller service function already takes reseller_id as a separate param.
    
    # The service function `create_receipt_for_reseller` will set reseller_id from current_reseller.id
    created_receipt = payment_receipt_service.create_receipt_for_reseller(
        db=db, 
        receipt_in=receipt_in, # Pass the original payload
        reseller_id=current_reseller.id # Explicitly pass authenticated reseller's ID
    )
    return created_receipt


@router.get("/receipts", response_model=List[PaymentReceiptRead])
def list_reseller_payment_receipts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_reseller: ResellerModel = Depends(get_current_active_reseller),
    db: Session = Depends(get_db)
):
    """
    List payment receipts submitted by the current reseller.
    """
    # Using the existing service function (previously named get_all_receipts_for_reseller)
    receipts = payment_receipt_service.get_all_receipts_for_reseller( # Ensure this is the correct name
        db=db, reseller_id=current_reseller.id, skip=skip, limit=limit
    )
    return receipts
