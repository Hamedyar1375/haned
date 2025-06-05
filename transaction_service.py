from sqlalchemy.orm import Session, selectinload, joinedload
from typing import List, Optional

from app.db.models.transaction import Transaction
from app.schemas.transaction import TransactionCreate # For type hinting

def create_transaction(db: Session, transaction_in: TransactionCreate) -> Transaction:
    """
    Creates a new transaction.
    This function will be called by other services (e.g., PaymentReceiptService, UserManagement services).
    Wallet balance updates for the reseller should happen in the calling service
    as this function only records the transaction itself.
    """
    db_transaction = Transaction(**transaction_in.dict())
    db.add(db_transaction)
    # The commit will typically be handled by the calling service to ensure atomicity
    # with other operations like wallet balance update.
    # However, if this service is meant to be atomic for transaction creation itself:
    # db.commit()
    # db.refresh(db_transaction)
    # For now, assuming calling service handles commit. (Decision reversed for better atomicity in calling services)
    # The calling service (e.g. PaymentReceiptService) will handle the commit
    # to ensure atomicity with other operations like wallet balance update.
    # db.commit() # Removed commit
    # db.refresh(db_transaction) # Removed refresh, calling service can refresh if needed after its commit
    return db_transaction

def get_transaction(db: Session, transaction_id: int) -> Optional[Transaction]:
    return db.query(Transaction).options(
        selectinload(Transaction.reseller),
        selectinload(Transaction.pricing_plan),
        selectinload(Transaction.reseller_pricing),
        selectinload(Transaction.payment_receipt) # To populate payment_receipt field in TransactionRead
    ).filter(Transaction.id == transaction_id).first()

def get_transactions_for_reseller(
    db: Session, reseller_id: int, skip: int = 0, limit: int = 100
) -> List[Transaction]:
    return db.query(Transaction).options(
        selectinload(Transaction.reseller), # May be redundant if already filtered by reseller_id but good for consistency
        selectinload(Transaction.pricing_plan),
        selectinload(Transaction.reseller_pricing),
        selectinload(Transaction.payment_receipt)
    ).filter(Transaction.reseller_id == reseller_id).order_by(Transaction.created_at.desc()).offset(skip).limit(limit).all()

def get_all_transactions(db: Session, skip: int = 0, limit: int = 100) -> List[Transaction]:
    return db.query(Transaction).options(
        selectinload(Transaction.reseller),
        selectinload(Transaction.pricing_plan),
        selectinload(Transaction.reseller_pricing),
        selectinload(Transaction.payment_receipt)
    ).order_by(Transaction.created_at.desc()).offset(skip).limit(limit).all()

# --- Reporting Enhancements ---
from sqlalchemy import func, Date, cast
from sqlalchemy.sql.expression import extract
from datetime import date, timedelta
from decimal import Decimal

# Define sales transaction types
SALES_TRANSACTION_TYPES = ['user_creation_cost', 'user_renewal_cost']

def get_sales_summary_by_period(
    db: Session, start_date: date, end_date: date, reseller_id: Optional[int] = None
) -> dict:
    """
    Calculates total sales amount and number of sales transactions within a period.
    Sales are reported as positive values.
    """
    # Ensure end_date is inclusive by adding one day to the range for timestamp comparisons
    query_end_date = end_date + timedelta(days=1)

    query = db.query(
        # Sum of amounts (convert to positive)
        func.sum(Transaction.amount * -1).label("total_sales_amount"),
        func.count(Transaction.id).label("transaction_count")
    ).filter(
        Transaction.transaction_type.in_(SALES_TRANSACTION_TYPES),
        Transaction.created_at >= start_date,
        Transaction.created_at < query_end_date # Use exclusive end for timestamp
    )

    if reseller_id is not None:
        query = query.filter(Transaction.reseller_id == reseller_id)

    result = query.one()
    
    return {
        "total_sales_amount": result.total_sales_amount or Decimal('0.00'),
        "transaction_count": result.transaction_count or 0
    }

def get_daily_sales_trend(
    db: Session, start_date: date, end_date: date, reseller_id: Optional[int] = None
) -> List[dict]:
    """
    Aggregates sales transaction amounts per day.
    Sales are reported as positive values.
    """
    query_end_date = end_date + timedelta(days=1)
    
    # Use func.date for MariaDB/MySQL to extract date part from datetime field
    # For other DBs like PostgreSQL, func.date or cast(Transaction.created_at, Date) might be used.
    # SQLAlchemy's func.date should work for MariaDB.
    date_group = func.date(Transaction.created_at).label("sale_date")

    query = db.query(
        date_group,
        func.sum(Transaction.amount * -1).label("total_sales"),
        func.count(Transaction.id).label("transaction_count")
    ).filter(
        Transaction.transaction_type.in_(SALES_TRANSACTION_TYPES),
        Transaction.created_at >= start_date,
        Transaction.created_at < query_end_date
    ).group_by(
        date_group
    ).order_by(
        date_group
    )

    if reseller_id is not None:
        query = query.filter(Transaction.reseller_id == reseller_id)
        
    results = query.all()
    
    # Format results
    trend_data = []
    for row in results:
        trend_data.append({
            "date_str": row.sale_date.strftime("%Y-%m-%d"), # row.sale_date is already a date object
            "total_sales": row.total_sales or Decimal('0.00'),
            "transaction_count": row.transaction_count or 0
        })
    return trend_data


def get_monthly_sales_trend(
    db: Session, start_year: int, end_year: int, reseller_id: Optional[int] = None
) -> List[dict]:
    """
    Aggregates sales transaction amounts per month.
    Sales are reported as positive values.
    """
    # Construct date range for filtering
    # Start of the first month of start_year
    start_date_filter = date(start_year, 1, 1)
    # End of the last month of end_year (exclusive for the next year's first day)
    end_date_filter = date(end_year + 1, 1, 1)

    # For MariaDB/MySQL, use strftime or YEAR() and MONTH()
    # Using YEAR and MONTH for grouping
    year_group = func.year(Transaction.created_at).label("sale_year")
    month_group = func.month(Transaction.created_at).label("sale_month")
    
    query = db.query(
        year_group,
        month_group,
        func.sum(Transaction.amount * -1).label("total_sales"),
        func.count(Transaction.id).label("transaction_count")
    ).filter(
        Transaction.transaction_type.in_(SALES_TRANSACTION_TYPES),
        Transaction.created_at >= start_date_filter,
        Transaction.created_at < end_date_filter
    ).group_by(
        year_group,
        month_group
    ).order_by(
        year_group,
        month_group
    )

    if reseller_id is not None:
        query = query.filter(Transaction.reseller_id == reseller_id)
        
    results = query.all()
    
    # Format results
    trend_data = []
    for row in results:
        trend_data.append({
            "month_str": f"{row.sale_year:04d}-{row.sale_month:02d}",
            "total_sales": row.total_sales or Decimal('0.00'),
            "transaction_count": row.transaction_count or 0
        })
    return trend_data
