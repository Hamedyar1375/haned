from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta # For token expiry if customized per token type

# Project imports
from app.db.session import get_db
from app.schemas.token import Token
from app.utils import security # For password verification and token creation
from app.services import reseller_service # To get reseller by username
from app.db.models.reseller import Reseller as ResellerModel # SQLAlchemy model for type hinting
from app.core.config import settings # For token expiry minutes

router = APIRouter()

# Define OAuth2PasswordBearer for reseller authentication
# The tokenUrl should point to the token endpoint itself
oauth2_scheme_reseller = OAuth2PasswordBearer(tokenUrl="/api/v1/reseller/auth/token")

@router.post("/token", response_model=Token)
async def login_reseller_for_access_token(
    db: Session = Depends(get_db), 
    form_data: OAuth2PasswordRequestForm = Depends()
):
    reseller = reseller_service.get_reseller_by_username(db, username=form_data.username)
    
    if not reseller or not security.verify_password(form_data.password, reseller.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not reseller.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, # Or 401, but 403 seems more appropriate for inactive
            detail="This reseller account is inactive.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        subject=reseller.username, # Using username as the subject for the token
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


# Dependency to get the current reseller from a token
def get_current_reseller(
    token: str = Depends(oauth2_scheme_reseller), 
    db: Session = Depends(get_db)
) -> ResellerModel:
    username = security.decode_token(token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials (token invalid or expired)",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    reseller = reseller_service.get_reseller_by_username(db, username=username)
    if reseller is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reseller not found (user may have been deleted)",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return reseller

# Dependency to get the current *active* reseller
def get_current_active_reseller(
    current_reseller: ResellerModel = Depends(get_current_reseller)
) -> ResellerModel:
    if not current_reseller.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Inactive user. Please contact support."
        )
    return current_reseller
