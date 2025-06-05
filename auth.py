from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from app.db.session import get_db
from app.schemas.token import Token
from app.utils.security import create_access_token, verify_password
from app.db.models.admin import Admin as AdminModel # Renamed to avoid conflict
from app.core.config import settings
from app.schemas.admin import AdminRead
from app.services.admin_service import get_admin_by_username # Import from service

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


# get_admin_by_username is now imported from admin_service

@router.post("/token", response_model=Token)
async def login_for_access_token(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
):
    admin = get_admin_by_username(db, username=form_data.username)
    if not admin or not verify_password(form_data.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=admin.username, expires_delta=access_token_expires # Use subject consistently
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Dependency to get current admin
async def get_current_admin(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> AdminModel:
    username = decode_token(token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    admin = get_admin_by_username(db, username=username)
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return admin

# Example protected route (optional, for testing)
# @router.get("/users/me", response_model=AdminRead)
# async def read_users_me(current_admin: AdminModel = Depends(get_current_admin)):
#     return current_admin
