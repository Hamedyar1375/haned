from pydantic import BaseModel, condecimal
from typing import Optional, Text, Any
from datetime import datetime

# Assuming other Read schemas are available
from app.schemas.reseller import ResellerRead # Or a simpler ResellerInTransactionRead
from app.schemas.pricing_plan import PricingPlanRead
# For ResellerPricingRead, need to import it from its schema file
# from app.schemas.reseller_pricing import ResellerPricingRead # Assuming this path
# For PaymentReceiptRead:
from app.schemas.payment_receipt import PaymentReceiptRead


from app.schemas.marzban_user import MarzbanUserRead # For nesting

class TransactionBase(BaseModel):
    reseller_id: int
    transaction_type: str
    amount: condecimal(decimal_places=2)
    marzban_user_id: Optional[int] = None # Changed from marzban_user_username
    pricing_plan_id: Optional[int] = None
    reseller_pricing_id: Optional[int] = None
    description: Optional[Text] = None
    payment_receipt_id: Optional[int] = None # Link to the PaymentReceipt if it's a top-up

class TransactionCreate(TransactionBase):
    pass

class TransactionRead(TransactionBase):
    id: int
    created_at: datetime
    
    reseller: ResellerRead # Or a simpler version like ResellerBasicInfo
    pricing_plan: Optional[PricingPlanRead] = None
    # reseller_pricing: Optional[ResellerPricingRead] = None # If full object needed
    
    payment_receipt: Optional[PaymentReceiptRead] = None
    marzban_user: Optional[MarzbanUserRead] = None # Added nested MarzbanUser

    class Config:
        orm_mode = True
