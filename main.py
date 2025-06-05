from fastapi import FastAPI

from app.db.base import Base
from app.db.session import engine
from app.api.v1.endpoints import auth
from app.api.v1.endpoints import marzban_panels
from app.api.v1.endpoints import resellers
from app.api.v1.endpoints import pricing_plans
from app.api.v1.endpoints import reseller_pricings
from app.api.v1.endpoints import admin_payment_receipts
from app.api.v1.endpoints import reports
from app.api.v1.endpoints import admin_sync
from app.api.v1.endpoints import reseller_auth
from app.api.v1.endpoints import reseller_profile
from app.api.v1.endpoints import reseller_wallet
from app.api.v1.endpoints import reseller_users
from app.api.v1.endpoints import reseller_reports # Import ResellerReports router
# Ensure all models are imported so Base knows about them for create_all
from app.db.models import admin, marzban_panel, reseller, reseller_panel_access, pricing_plan, reseller_pricing, transaction, payment_receipt, marzban_user

# Create database tables
# In a production app, you might want to use Alembic for migrations
Base.metadata.create_all(bind=engine)

# Import service and session to create initial admin
from app.services.admin_service import create_initial_admin
from app.db.session import SessionLocal

# Create initial admin user (call this function carefully)
db_startup = SessionLocal()
# Models are imported above, ensuring they are registered with Base before create_all
create_initial_admin(db_startup)
db_startup.close()


app = FastAPI(title="Admin Panel Backend", version="0.1.0")

# Mount routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(marzban_panels.router, prefix="/api/v1/marzban-panels", tags=["Marzban Panels"])
app.include_router(resellers.router, prefix="/api/v1/resellers", tags=["Resellers"])
app.include_router(pricing_plans.router, prefix="/api/v1/pricing-plans", tags=["Pricing Plans"])
app.include_router(reseller_pricings.router, prefix="/api/v1/reseller-pricings", tags=["Reseller Pricings"])
app.include_router(admin_payment_receipts.router, prefix="/api/v1/admin/payment-receipts", tags=["Admin Payment Receipts"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])
app.include_router(admin_sync.router, prefix="/api/v1/admin/sync", tags=["Admin Sync"])
app.include_router(reseller_auth.router, prefix="/api/v1/reseller/auth", tags=["Reseller Authentication"])
app.include_router(reseller_profile.router, prefix="/api/v1/reseller/profile", tags=["Reseller Profile"])
app.include_router(reseller_wallet.router, prefix="/api/v1/reseller/wallet", tags=["Reseller Wallet"])
app.include_router(reseller_users.router, prefix="/api/v1/reseller/users", tags=["Reseller User Management"])
app.include_router(reseller_reports.router, prefix="/api/v1/reseller", tags=["Reseller Reports"]) # Mounted at /api/v1/reseller


@app.get("/")
async def root():
    return {"message": "Panel Backend Running"}
