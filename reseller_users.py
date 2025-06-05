from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

# Project imports
from app.db.session import get_db
from app.db.models.reseller import Reseller as ResellerModel
from app.db.models.marzban_user import MarzbanUser as MarzbanUserModel
from app.schemas.marzban_user import MarzbanUserRead, ResellerMarzbanUserCreateRequest # Added request schema
from app.services import marzban_user_service
from app.api.v1.endpoints.reseller_auth import get_current_active_reseller

router = APIRouter()

@router.get("/users", response_model=List[MarzbanUserRead])
def list_reseller_marzban_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200), # Max 200 users per page
    current_reseller: ResellerModel = Depends(get_current_active_reseller),
    db: Session = Depends(get_db)
):
    """
    List Marzban users associated with the current reseller.
    """
    users = marzban_user_service.get_marzban_users_for_reseller(
        db=db, reseller_id=current_reseller.id, skip=skip, limit=limit
    )
    return users


@router.get("/users/{marzban_user_id}", response_model=MarzbanUserRead)
def get_reseller_marzban_user_detail(
    marzban_user_id: int, # This is the local DB ID of the MarzbanUser record
    current_reseller: ResellerModel = Depends(get_current_active_reseller),
    db: Session = Depends(get_db)
):
    """
    Get details of a specific Marzban user belonging to the current reseller.
    """
    db_marzban_user = marzban_user_service.get_marzban_user_for_reseller(
        db=db, marzban_user_id=marzban_user_id, reseller_id=current_reseller.id
    )
    if db_marzban_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Marzban user not found or does not belong to this reseller."
        )
    return db_marzban_user


@router.patch("/{marzban_user_id}", response_model=MarzbanUserRead)
def modify_reseller_marzban_user_detail(
    marzban_user_id: int, # Local DB ID of the MarzbanUser record
    user_update_request: ResellerMarzbanUserUpdateRequest, # Corrected schema import name
    current_reseller: ResellerModel = Depends(get_current_active_reseller),
    db: Session = Depends(get_db)
):
    """
    Modify an existing Marzban user associated with the current reseller.
    Allows updating data limit, extending expiry, changing proxy/inbound settings, and local notes.
    """
    try:
        updated_marzban_user = marzban_user_service.modify_marzban_user_for_reseller(
            db=db, 
            reseller=current_reseller, 
            local_marzban_user_id=marzban_user_id, 
            user_update_request=user_update_request
        )
        # Similar to create, the service returns the ORM object.
        # Pydantic's orm_mode with relationships loaded by service (or via lazy='selectin') should handle serialization.
        return updated_marzban_user

    except marzban_user_service.MarzbanUserServiceError as e:
        error_detail = str(e)
        # Handling specific error messages to return appropriate HTTP status codes
        if "Insufficient wallet balance" in error_detail:
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=error_detail)
        elif "not found or does not belong" in error_detail:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail)
        elif "Reseller does not have access" in error_detail or \
             "No active pricing configuration" in error_detail or \
             "No suitable pricing plan found" in error_detail or \
             "does not match assigned plan duration" in error_detail or \
             "Cannot modify data_limit_gb: No custom GB pricing found" in error_detail or \
             "Nothing to update" in error_detail:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_detail)
        elif "Marzban API error" in error_detail:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Error communicating with Marzban panel: {error_detail}")
        elif "Database error after Marzban user modification" in error_detail:
            # logger.error(f"CRITICAL: {error_detail}") # Assuming logger
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save user data after modification on Marzban. Please contact support.")
        else:
            # Default for other MarzbanUserServiceErrors
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_detail)
    except Exception as e:
        # logger.error(f"Unexpected error in reseller user modification: {e}") # Assuming logger
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred during user modification.")


@router.post("/", response_model=MarzbanUserRead, status_code=status.HTTP_201_CREATED)
def create_marzban_user_by_reseller(
    user_create_request: ResellerMarzbanUserCreateRequest,
    current_reseller: ResellerModel = Depends(get_current_active_reseller),
    db: Session = Depends(get_db)
):
    """
    Create a new Marzban user on a specified panel for the current reseller.
    """
    try:
        # The service function create_marzban_user_for_reseller should return the ORM object
        # with relationships (like marzban_panel and reseller) already populated or configured
        # for lazy/selectin loading, which Pydantic's orm_mode can handle.
        new_marzban_user = marzban_user_service.create_marzban_user_for_reseller(
            db=db, reseller=current_reseller, user_create_request=user_create_request
        )
        return new_marzban_user

    except marzban_user_service.MarzbanUserServiceError as e:
        error_detail = str(e)
        if "Insufficient wallet balance" in error_detail:
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=error_detail)
        elif "Reseller does not have access" in error_detail or \
             "No active pricing configuration" in error_detail or \
             "Target Marzban panel ID" in error_detail or \
             "Could not retrieve credentials" in error_detail or \
             "Failed to authenticate with Marzban panel" in error_detail or \
             "Data limit (data_limit_gb) must be provided" in error_detail:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_detail)
        elif "Marzban API error" in error_detail:
            # Specific check for username conflict from Marzban API
            if "username already exists" in error_detail.lower() or \
               "username - already exists" in error_detail.lower(): # Check based on Marzban's actual error message
                 raise HTTPException(
                     status_code=status.HTTP_409_CONFLICT, 
                     detail=f"Marzban username '{user_create_request.username}' already exists on the panel."
                 )
            # Generic Marzban API error
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Error communicating with Marzban panel: {error_detail}")
        elif "Database error after Marzban user creation" in error_detail:
            # This is a critical error indicating inconsistency.
            # Log this error server-side for admin attention.
            # logger.error(f"CRITICAL: {error_detail}") # Assuming logger is configured
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save user data after creation on Marzban. Please contact support.")
        else:
            # Default for other MarzbanUserServiceErrors
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_detail)
    except Exception as e:
        # logger.error(f"Unexpected error in reseller user creation: {e}") # Assuming logger
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred during user creation.")


@router.get("/{marzban_user_id}/usage", response_model=Dict[str, Any])
def get_reseller_marzban_user_usage_data(
    marzban_user_id: int, # Local DB ID of the MarzbanUser record
    current_reseller: ResellerModel = Depends(get_current_active_reseller),
    db: Session = Depends(get_db)
):
    """
    Get live usage data for a specific Marzban user belonging to the current reseller
    from the Marzban panel.
    """
    try:
        usage_data = marzban_user_service.get_marzban_user_usage_for_reseller(
            db=db,
            reseller=current_reseller,
            local_marzban_user_id=marzban_user_id
        )
        return usage_data
    except marzban_user_service.MarzbanUserServiceError as e:
        error_detail = str(e)
        if "not found or does not belong" in error_detail:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail)
        elif "Could not retrieve credentials" in error_detail or \
             "Failed to authenticate with Marzban panel" in error_detail:
            # These suggest configuration or panel issues, potentially a 502 or 400.
            # Let's use 502 as it's an issue with an upstream service (Marzban panel auth).
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=error_detail)
        elif "Marzban API error when fetching usage" in error_detail:
            # This could be 404 if user not on panel, or other errors from Marzban.
            # The MarzbanAPIError from client includes status_code, which could be used here.
            # For simplicity, if it's a specific "User not found on Marzban panel" from client, make it 404.
            if "User not found on Marzban panel" in error_detail:
                 raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found on the Marzban panel.")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=error_detail)
        else: # Other service errors
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_detail)
    except Exception as e:
        # logger.error(f"Unexpected error fetching user usage: {e}") # Assuming logger
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred while fetching user usage.")
