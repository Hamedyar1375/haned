from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.db.session import get_db
from app.services import marzban_user_service
from app.services.marzban_user_service import MarzbanUserServiceError # Custom service error
from app.services.marzban_panel_service import get_panel # To fetch panel
from app.services.reseller_service import get_reseller # To fetch reseller
from app.api.v1.endpoints.auth import get_current_admin
from app.db.models.admin import Admin as AdminModel # For type hinting current_admin

router = APIRouter()

@router.post("/reseller/{reseller_id}/panel/{panel_id}", response_model=Dict[str, Any])
def sync_marzban_users_for_panel_and_reseller(
    reseller_id: int,
    panel_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    db_reseller = get_reseller(db, reseller_id)
    if not db_reseller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseller not found.")
    
    db_panel = get_panel(db, panel_id)
    if not db_panel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marzban Panel not found.")

    if db_reseller.marzban_admin_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Reseller {db_reseller.username} (ID: {reseller_id}) does not have a Marzban Admin ID configured. Sync cannot proceed."
        )

    try:
        sync_summary = marzban_user_service.sync_marzban_users_for_reseller_panel(
            db=db, reseller=db_reseller, panel=db_panel
        )
        if sync_summary.get("errors"):
            # You might want to return a different status code if there are partial errors
            # For now, returning 200 with errors in the summary.
            # Or, if any error is critical, raise HTTPException here.
            # e.g., if "Authentication failed" or "Could not retrieve/decrypt password".
            if any("Authentication failed" in err for err in sync_summary["errors"]) or \
               any("Could not retrieve/decrypt password" in err for err in sync_summary["errors"]):
                 raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Critical error during sync: {sync_summary['errors']}")

        return sync_summary
    except MarzbanUserServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Log the exception e for server-side details
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected server error occurred during sync: {str(e)}")
