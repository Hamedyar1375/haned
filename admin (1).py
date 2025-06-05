from pydantic import BaseModel, EmailStr
from datetime import datetime

class AdminBase(BaseModel):
    username: str
    email: EmailStr # Retaining email for now, though not in DB model yet. Can be removed later.

class AdminCreate(BaseModel): # Modified: username and password only for creation
    username: str
    password: str

class AdminRead(AdminBase): # Modified: Reflects DB model more closely
    id: int
    username: str # username is already in AdminBase
    # email: EmailStr # Email is not in the Admin DB model
    created_at: datetime
    updated_at: datetime
    # is_active: bool # is_active is not in the Admin DB model yet

    class Config:
        orm_mode = True

# Optional: Schema for internal use, including hashed password
class AdminInDB(AdminRead):
    password_hash: str
