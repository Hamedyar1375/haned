from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# Project imports
from app.db.session import get_db
from app.db.models.reseller import Reseller as ResellerModel # SQLAlchemy model
from app.schemas.reseller import ResellerRead, ResellerPasswordUpdate # Pydantic schemas
from app.services import reseller_service # Service functions
from app.api.v1.endpoints.reseller_auth import get_current_active_reseller # Dependency

router = APIRouter()

@router.get("/me", response_model=ResellerRead)
def read_reseller_me(
    current_reseller: ResellerModel = Depends(get_current_active_reseller)
):
    """
    Get current reseller's profile information.
    """
    # The current_reseller object from the dependency is already loaded from DB.
    # The ResellerRead schema will handle serialization, including panels if loaded.
    # The get_reseller service function (used by get_reseller_by_username in auth flow)
    # already uses joinedload for panels.
    return current_reseller


@router.put("/me/password", status_code=status.HTTP_200_OK) # Or 204 No Content
def update_reseller_me_password(
    password_data: ResellerPasswordUpdate,
    db: Session = Depends(get_db),
    current_reseller: ResellerModel = Depends(get_current_active_reseller)
):
    """
    Update current reseller's password.
    """
    if password_data.current_password == password_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be the same as the current password."
        )
    
    success = reseller_service.update_reseller_password(
        db=db, 
        reseller=current_reseller, 
        current_password=password_data.current_password, 
        new_password=password_data.new_password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password."
        )
    
    return {"message": "Password updated successfully."} # Or just status 204 No Content
                                                        # and no response body. HTTP 200 with message is also fine.
