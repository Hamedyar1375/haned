from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date # For query parameter type hinting

from app.db.session import get_db
from app.services import transaction_service
from app.schemas.reports import (
    SalesSummary,
    DailySale,
    MonthlySale,
    # ReportQueryFilters will be handled by individual query params
)
from app.api.v1.endpoints.auth import get_current_admin
from app.db.models.admin import Admin as AdminModel # For type hinting current_admin

router = APIRouter()

@router.get("/sales/summary", response_model=SalesSummary)
def get_sales_summary_report(
    start_date: date = Query(..., description="Start date for the report period (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date for the report period (YYYY-MM-DD)"),
    reseller_id: Optional[int] = Query(None, description="Optional Reseller ID to filter results"),
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    summary_data = transaction_service.get_sales_summary_by_period(
        db=db, start_date=start_date, end_date=end_date, reseller_id=reseller_id
    )
    return SalesSummary(**summary_data)


@router.get("/sales/daily-trend", response_model=List[DailySale])
def get_daily_sales_trend_report(
    start_date: date = Query(..., description="Start date for the trend (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date for the trend (YYYY-MM-DD)"),
    reseller_id: Optional[int] = Query(None, description="Optional Reseller ID to filter results"),
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    trend_data = transaction_service.get_daily_sales_trend(
        db=db, start_date=start_date, end_date=end_date, reseller_id=reseller_id
    )
    return [DailySale(**item) for item in trend_data]


@router.get("/sales/monthly-trend", response_model=List[MonthlySale])
def get_monthly_sales_trend_report(
    start_year: int = Query(..., description="Start year for the trend (YYYY)"),
    end_year: int = Query(..., description="End year for the trend (YYYY)"),
    reseller_id: Optional[int] = Query(None, description="Optional Reseller ID to filter results"),
    db: Session = Depends(get_db),
    current_admin: AdminModel = Depends(get_current_admin),
):
    if start_year > end_year:
        raise HTTPException(status_code=400, detail="Start year cannot be after end year.")
    trend_data = transaction_service.get_monthly_sales_trend(
        db=db, start_year=start_year, end_year=end_year, reseller_id=reseller_id
    )
    return [MonthlySale(**item) for item in trend_data]
