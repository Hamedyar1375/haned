from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.schemas.payment_receipt import PaymentReceiptRead, PaymentReceiptUpdateAdmin # For request body
from app.services import payment_receipt_service
from app.services.payment_receipt_service import PaymentReceiptServiceError # Custom exception
from app.api.v1.endpoints.auth import get_current_admin
from app.db.models.admin import Admin as AdminModel # For type hinting get_current_admin

router = APIRouter()

@router.get("/", response_model=List[PaymentReceiptRead])
def list_payment_receipts_by_status(
    status: str = "pending", # Default to 'pending', can be 'approved', 'rejected'
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    if status not in ['pending', 'approved', 'rejected']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status value. Allowed values are 'pending', 'approved', 'rejected'."
        )
    receipts = payment_receipt_service.get_receipts_by_status(db=db, status=status, skip=skip, limit=limit)
    return receipts

@router.post("/{receipt_id}/approve", response_model=PaymentReceiptRead)
def approve_payment_receipt(
    receipt_id: int,
    admin_notes_payload: Optional[dict] = Body(None, embed=True), # Making notes truly optional in payload
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    admin_notes = admin_notes_payload.get("admin_notes") if admin_notes_payload else None
    try:
        approved_receipt = payment_receipt_service.approve_receipt(
            db=db, receipt_id=receipt_id, admin_id=current_admin.id, admin_notes=admin_notes
        )
        return approved_receipt
    except PaymentReceiptServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e: # Catch any other unexpected errors
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {str(e)}")


@router.post("/{receipt_id}/reject", response_model=PaymentReceiptRead)
def reject_payment_receipt(
    receipt_id: int,
    admin_notes_payload: dict = Body(..., embed=True), # Making notes required for rejection in payload
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    admin_notes = admin_notes_payload.get("admin_notes")
    if not admin_notes: # Basic validation for required notes on rejection
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Admin notes are required for rejection.")
    try:
        rejected_receipt = payment_receipt_service.reject_receipt(
            db=db, receipt_id=receipt_id, admin_id=current_admin.id, admin_notes=admin_notes
        )
        return rejected_receipt
    except PaymentReceiptServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {str(e)}")
