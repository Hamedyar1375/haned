from sqlalchemy import Column, Integer, String, TIMESTAMP, func
from sqlalchemy.sql import expression
from app.db.base import Base

class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    # Use server_default for MariaDB/MySQL specific functions
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now(), # This handles ON UPDATE CURRENT_TIMESTAMP
        nullable=False
    )
