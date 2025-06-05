from sqlalchemy import Column, Integer, String, TIMESTAMP, func, Boolean, DECIMAL
from sqlalchemy.sql import expression
from app.db.base import Base

class PricingPlan(Base):
    __tablename__ = "pricing_plans"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    data_limit_gb = Column(Integer, nullable=True) # Nullable if unlimited or not applicable
    duration_days = Column(Integer, nullable=False)
    price = Column(DECIMAL(10, 2), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default=expression.true())
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
