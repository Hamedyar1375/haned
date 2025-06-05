from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import date # For query parameter type hinting

# Project imports
from app.db.session import get_db
from app.db.models.reseller import Reseller as ResellerModel # For current_reseller type hint
from app.services import transaction_service # Service functions
from app.schemas.reports import ( # Pydantic schemas for response
    SalesSummary,
    DailySale,
    MonthlySale,
)
from app.api.v1.endpoints.reseller_auth import get_current_active_reseller # Dependency

router = APIRouter()

@router.get("/reports/sales/summary", response_model=SalesSummary)
def get_reseller_sales_summary_report(
    start_date: date = Query(..., description="Start date for the report period (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date for the report period (YYYY-MM-DD)"),
    current_reseller: ResellerModel = Depends(get_current_active_reseller),
    db: Session = Depends(get_db),
):
    """
    Get sales summary for the current authenticated reseller.
    """
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Start date cannot be after end date.")
        
    summary_data = transaction_service.get_sales_summary_by_period(
        db=db, 
        start_date=start_date, 
        end_date=end_date, 
        reseller_id=current_reseller.id # Automatically apply current reseller's ID
    )
    return SalesSummary(**summary_data)


@router.get("/reports/sales/daily-trend", response_model=List[DailySale])
def get_reseller_daily_sales_trend_report(
    start_date: date = Query(..., description="Start date for the trend (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date for the trend (YYYY-MM-DD)"),
    current_reseller: ResellerModel = Depends(get_current_active_reseller),
    db: Session = Depends(get_db),
):
    """
    Get daily sales trend for the current authenticated reseller.
    """
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Start date cannot be after end date.")

    trend_data = transaction_service.get_daily_sales_trend(
        db=db, 
        start_date=start_date, 
        end_date=end_date, 
        reseller_id=current_reseller.id # Automatically apply current reseller's ID
    )
    return [DailySale(**item) for item in trend_data]


@router.get("/reports/sales/monthly-trend", response_model=List[MonthlySale])
def get_reseller_monthly_sales_trend_report(
    start_year: int = Query(..., description="Start year for the trend (YYYY)"),
    end_year: int = Query(..., description="End year for the trend (YYYY)"),
    current_reseller: ResellerModel = Depends(get_current_active_reseller),
    db: Session = Depends(get_db),
):
    """
    Get monthly sales trend for the current authenticated reseller.
    """
    if start_year > end_year:
        raise HTTPException(status_code=400, detail="Start year cannot be after end year.")
        
    trend_data = transaction_service.get_monthly_sales_trend(
        db=db, 
        start_year=start_year, 
        end_year=end_year, 
        reseller_id=current_reseller.id # Automatically apply current reseller's ID
    )
    return [MonthlySale(**item) for item in trend_data]
