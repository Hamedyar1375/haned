from sqlalchemy.orm import Session, selectinload
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.db.models.marzban_user import MarzbanUser
from app.db.models.reseller import Reseller
from app.db.models.marzban_panel import MarzbanPanel
from app.schemas.marzban_user import MarzbanUserCreate
from app.utils.marzban_api_client import get_marzban_access_token, get_marzban_users, MarzbanAPIError
from app.services.marzban_panel_service import get_panel_decrypted_password # To get panel credentials

class MarzbanUserServiceError(Exception):
    pass

def create_marzban_user(db: Session, user_in: MarzbanUserCreate, commit: bool = True) -> MarzbanUser:
    """
    Creates a local MarzbanUser record.
    If commit=False, the calling function is responsible for db.commit() and db.refresh().
    """
    db_user = MarzbanUser(**user_in.dict())
    db.add(db_user)
    if commit:
        db.commit()
        db.refresh(db_user)
    # If not committing, the caller should flush to get ID if needed, then commit, then refresh.
    return db_user

def get_marzban_user(db: Session, user_id: int) -> Optional[MarzbanUser]:
    return db.query(MarzbanUser).options(
        selectinload(MarzbanUser.marzban_panel),
        selectinload(MarzbanUser.reseller)
    ).filter(MarzbanUser.id == user_id).first()

def get_marzban_user_by_username_and_panel(
    db: Session, username: str, panel_id: int
) -> Optional[MarzbanUser]:
    return db.query(MarzbanUser).filter(
        MarzbanUser.marzban_username == username,
        MarzbanUser.marzban_panel_id == panel_id
    ).first()

def update_marzban_user_from_api_data( # Renamed for clarity
    db: Session, db_user: MarzbanUser, user_data_from_api: Dict[str, Any]
) -> MarzbanUser:
    """Updates an existing local MarzbanUser record with new data from API."""
    db_user.api_response_data = user_data_from_api
    db_user.last_synced_at = datetime.utcnow()
    # Potentially update other fields if they can change and are tracked, e.g., notes, status from Marzban
    # For now, primarily updating the raw API data and sync time.
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def sync_marzban_users_for_reseller_panel(
    db: Session, reseller: Reseller, panel: MarzbanPanel
) -> Dict[str, Any]:
    summary = {
        "synced_panel_id": panel.id,
        "reseller_id": reseller.id,
        "reseller_marzban_admin_id": reseller.marzban_admin_id,
        "total_users_from_api": 0,
        "newly_added_count": 0,
        "updated_count": 0,
        "errors": []
    }

    decrypted_password = get_panel_decrypted_password(db, panel.id)
    if not decrypted_password:
        summary["errors"].append(f"Could not retrieve/decrypt password for panel ID {panel.id}.")
        raise MarzbanUserServiceError(f"Missing credentials for panel ID {panel.id}.")

    try:
        token = get_marzban_access_token(panel.api_url, panel.admin_username, decrypted_password)
        if not token:
            summary["errors"].append(f"Failed to get access token for panel ID {panel.id}.")
            raise MarzbanUserServiceError(f"Authentication failed for panel ID {panel.id}.")

        # We need to fetch users created by the reseller's marzban_admin_id
        api_users = get_marzban_users(panel.api_url, token, admin_id=reseller.marzban_admin_id)
        if api_users is None: # Should not happen if get_marzban_users raises MarzbanAPIError
            summary["errors"].append(f"Failed to fetch users from Marzban panel ID {panel.id}.")
            return summary # Or raise error
        
        summary["total_users_from_api"] = len(api_users)

        for user_data in api_users:
            marzban_username = user_data.get("username")
            if not marzban_username:
                summary["errors"].append(f"User data from API missing username: {user_data}")
                continue

            db_marzban_user = get_marzban_user_by_username_and_panel(
                db, username=marzban_username, panel_id=panel.id
            )

            if db_marzban_user:
                # User exists, update it
                update_marzban_user_from_api_data(db, db_marzban_user, user_data)
                summary["updated_count"] += 1
            else:
                # User does not exist, create it
                user_create_schema = MarzbanUserCreate(
                    marzban_username=marzban_username,
                    marzban_panel_id=panel.id,
                    reseller_id=reseller.id,
                    created_by_new_panel=False, # Synced from existing
                    api_response_data=user_data,
                    notes=f"Synced from Marzban panel. Original creator admin ID: {reseller.marzban_admin_id}"
                )
                create_marzban_user(db, user_create_schema) # This commits one by one.
                summary["newly_added_count"] += 1
        
        # For better performance on many new users, could collect all new MarzbanUserCreate objects
        # and use db.add_all() followed by a single db.commit() and then refresh each object.
        # However, create_marzban_user already commits. This is a trade-off.
        # If create_marzban_user is changed not to commit, then a single commit here would be better.

    except MarzbanAPIError as e:
        summary["errors"].append(f"Marzban API Error: {str(e)}")
        # Depending on desired behavior, might re-raise or just return summary with error.
        # For a sync job, often returning summary is preferred.
    except Exception as e:
        summary["errors"].append(f"An unexpected error during sync: {str(e)}")
        # Consider db.rollback() here if a transaction was implicitly started and failed mid-way
        # But since create_marzban_user and update_marzban_user_from_api_data commit individually,
        # a rollback here might not be effective for already committed parts.
        # This highlights the complexity of partial commits in a loop.
    
    return summary


# --- Reseller-facing User Management Functions ---

def get_marzban_users_for_reseller(
    db: Session, reseller_id: int, skip: int = 0, limit: int = 100
) -> List[MarzbanUser]:
    """
    Fetches MarzbanUsers associated with a specific reseller, with panel details.
    """
    return db.query(MarzbanUser).options(
        selectinload(MarzbanUser.marzban_panel) # Ensure panel details are loaded
        # Reseller info is implicitly linked via reseller_id, but if full ResellerRead needed in schema,
        # it should be loaded too, though MarzbanUserRead schema might simplify it.
        # selectinload(MarzbanUser.reseller) # Already defined in MarzbanUserRead schema
    ).filter(MarzbanUser.reseller_id == reseller_id).order_by(MarzbanUser.marzban_username).offset(skip).limit(limit).all()


def get_marzban_user_for_reseller(
    db: Session, marzban_user_id: int, reseller_id: int
) -> Optional[MarzbanUser]:
    """
    Fetches a specific MarzbanUser by its local ID, ensuring it belongs to the given reseller.
    Includes panel and reseller details.
    """
    return db.query(MarzbanUser).options(
        selectinload(MarzbanUser.marzban_panel),
        selectinload(MarzbanUser.reseller) # Load reseller for potential use in schema or checks
    ).filter(
        MarzbanUser.id == marzban_user_id,
        MarzbanUser.reseller_id == reseller_id
    ).first()


# --- Reseller User Modification ---
from app.schemas.marzban_user import ResellerMarzbanUserUpdateRequest
from app.utils.marzban_api_client import update_marzban_user as update_marzban_user_on_panel

def modify_marzban_user_for_reseller(
    db: Session, 
    reseller: Reseller, 
    local_marzban_user_id: int, 
    user_update_request: ResellerMarzbanUserUpdateRequest
) -> MarzbanUser:

    local_db_user = get_marzban_user_for_reseller(db, marzban_user_id=local_marzban_user_id, reseller_id=reseller.id)
    if not local_db_user:
        raise MarzbanUserServiceError("Marzban user not found or does not belong to this reseller.")

    target_panel = local_db_user.marzban_panel # Already loaded by get_marzban_user_for_reseller
    if not target_panel: # Should not happen if data is consistent
        raise MarzbanUserServiceError("Marzban panel details not found for this user.")

    cost = Decimal("0.00")
    marzban_api_payload = {}
    transaction_description_parts = []
    pricing_plan_id_for_tx = None
    reseller_pricing_id_for_tx = None

    active_pricing = reseller_pricing_service.get_active_pricing_for_reseller(
        db, reseller_id=reseller.id, marzban_panel_id=target_panel.id
    )

    # Cost calculation for data_limit_gb
    if user_update_request.data_limit_gb is not None:
        if user_update_request.data_limit_gb <= 0:
             raise MarzbanUserServiceError("data_limit_gb must be positive if provided.")
        if not active_pricing or active_pricing.custom_price_per_gb is None:
            raise MarzbanUserServiceError(
                "Cannot modify data_limit_gb: No custom GB pricing found for this reseller on this panel."
            )
        reseller_pricing_id_for_tx = active_pricing.id
        # Cost is based on the new total data limit requested.
        # Marzban sets absolute data limit. If reseller wants to "add" 5GB, they input current_limit + 5GB.
        # The cost should be for the entire new package size if pricing is per GB package.
        # Or, if it's "additional GB", then cost is for the delta.
        # Subtask says "New total data limit". So cost is for this new total.
        # This interpretation might need refinement based on business logic (is it "top-up" or "change plan"?)
        # For now, assume cost is for the new total package size as per custom_price_per_gb.
        cost_data = (Decimal(str(user_update_request.data_limit_gb)) * active_pricing.custom_price_per_gb).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        cost += cost_data
        marzban_api_payload['data_limit'] = gb_to_bytes(user_update_request.data_limit_gb)
        transaction_description_parts.append(f"Set data to {user_update_request.data_limit_gb}GB (cost: {cost_data})")

    # Cost calculation for expire_days_to_add
    if user_update_request.expire_days_to_add is not None:
        if user_update_request.expire_days_to_add <= 0:
            raise MarzbanUserServiceError("expire_days_to_add must be positive if provided.")
        if not active_pricing or active_pricing.pricing_plan_id is None or not active_pricing.pricing_plan:
            raise MarzbanUserServiceError(
                "Cannot extend expiry: No suitable pricing plan found for renewal for this reseller on this panel."
            )
        
        # Simplification: Cost is applied if expire_days_to_add matches plan duration
        if active_pricing.pricing_plan.duration_days == user_update_request.expire_days_to_add:
            cost_renewal = active_pricing.pricing_plan.price
            cost += cost_renewal
            pricing_plan_id_for_tx = active_pricing.pricing_plan_id
            reseller_pricing_id_for_tx = active_pricing.id # Link the ResellerPricing entry
            transaction_description_parts.append(
                f"Added {user_update_request.expire_days_to_add} days (cost: {cost_renewal} using plan '{active_pricing.pricing_plan.name}')"
            )
            
            # Calculate new expiry date for Marzban API
            current_expire_ts = None
            if local_db_user.api_response_data and local_db_user.api_response_data.get('expire') is not None:
                current_expire_ts = int(local_db_user.api_response_data['expire'])
            
            current_expire_dt = datetime.utcnow() # Default to now if no current expiry
            if current_expire_ts and current_expire_ts > 0:
                 # Check if current_expire_ts is already in the past
                if datetime.utcfromtimestamp(current_expire_ts) > datetime.utcnow():
                    current_expire_dt = datetime.utcfromtimestamp(current_expire_ts)
            
            new_expire_dt = current_expire_dt + timedelta(days=user_update_request.expire_days_to_add)
            marzban_api_payload['expire'] = int(new_expire_dt.timestamp())
        else:
            raise MarzbanUserServiceError(
                f"Cannot extend expiry: Requested duration {user_update_request.expire_days_to_add} days does not match assigned plan duration {active_pricing.pricing_plan.duration_days} days."
            )

    # Other updatable fields (no direct cost)
    if user_update_request.proxies is not None:
        marzban_api_payload['proxies'] = user_update_request.proxies
        if not transaction_description_parts: transaction_description_parts.append("Updated proxies")
    if user_update_request.inbounds is not None: # Marzban might expect specific format
        marzban_api_payload['inbounds'] = user_update_request.inbounds
        if not transaction_description_parts: transaction_description_parts.append("Updated inbounds")


    if not marzban_api_payload and user_update_request.note is None:
        raise MarzbanUserServiceError("Nothing to update. Provide data for data_limit, expiry, proxies, inbounds, or note.")

    # Wallet Check (if cost was incurred)
    if cost > Decimal("0.00"):
        if reseller.wallet_balance < cost and not reseller.allow_negative_balance:
            raise MarzbanUserServiceError(
                f"Insufficient wallet balance for modification. Required: {cost}, Available: {reseller.wallet_balance}."
            )

    # Marzban API Call (if there's something to update in Marzban)
    updated_marzban_api_response = None
    if marzban_api_payload:
        decrypted_password = get_panel_decrypted_password(db, target_panel.id)
        if not decrypted_password:
            raise MarzbanUserServiceError(f"Could not retrieve credentials for panel {target_panel.name}.")
        marzban_token = get_marzban_access_token(target_panel.api_url, target_panel.admin_username, decrypted_password)
        if not marzban_token:
            raise MarzbanUserServiceError(f"Failed to authenticate with Marzban panel {target_panel.name}.")

        try:
            updated_marzban_api_response = update_marzban_user_on_panel(
                panel_url=target_panel.api_url,
                token=marzban_token,
                username=local_db_user.marzban_username,
                update_payload=marzban_api_payload
            )
        except MarzbanAPIError as e:
            raise MarzbanUserServiceError(f"Marzban API error during update: {str(e)}")
        
        if not updated_marzban_api_response: # Should be caught by MarzbanAPIError but as fallback
            raise MarzbanUserServiceError("Failed to update user on Marzban panel or received unexpected response.")


    # Database Updates
    try:
        if cost > Decimal("0.00"):
            reseller.wallet_balance -= cost
            db.add(reseller)

            transaction_type = "user_config_change_cost" # Generic type
            if "Set data to" in " ".join(transaction_description_parts) and "Added" in " ".join(transaction_description_parts) :
                 transaction_type = "user_data_renew_cost"
            elif "Set data to" in " ".join(transaction_description_parts):
                 transaction_type = "user_data_topup_cost"
            elif "Added" in " ".join(transaction_description_parts):
                 transaction_type = "user_renewal_cost"

            tx_description = (
                f"Cost for modifying Marzban user '{local_db_user.marzban_username}' on panel '{target_panel.name}'. "
                + "; ".join(transaction_description_parts)
            )
            tx_create_schema = TransactionCreate(
                reseller_id=reseller.id,
                transaction_type=transaction_type,
                amount= -cost, # Cost is negative for debits
                marzban_user_id=local_db_user.id,
                pricing_plan_id=pricing_plan_id_for_tx, # Captured if renewal via plan
                reseller_pricing_id=reseller_pricing_id_for_tx, # Captured if any cost incurred
                description=tx_description
            )
            db_transaction = Transaction(**tx_create_schema.dict())
            db.add(db_transaction)

        if updated_marzban_api_response: # If Marzban was updated
            local_db_user.api_response_data = updated_marzban_api_response
        local_db_user.last_synced_at = datetime.utcnow() # Always update sync time if API call made or note changed

        if user_update_request.note is not None:
            local_db_user.notes = user_update_request.note
        
        db.add(local_db_user)
        db.commit()
        
        db.refresh(local_db_user)
        if cost > Decimal("0.00"):
            db.refresh(reseller)
        
        return local_db_user
        
    except Exception as e_db:
        db.rollback()
        # TODO: Compensation logic if Marzban API call succeeded but DB failed.
        # This is more complex for PATCH as reverting specific fields in Marzban is tricky.
        # Flagging for admin might be the most practical approach.
        raise MarzbanUserServiceError(f"Database error after Marzban user modification: {str(e_db)}. Manual reconciliation may be needed for user '{local_db_user.marzban_username}' on panel '{target_panel.name}'.")


# --- Reseller User Usage Viewing ---
from app.utils.marzban_api_client import get_marzban_user_usage as get_usage_from_marzban_panel

def get_marzban_user_usage_for_reseller(
    db: Session, 
    reseller: Reseller, 
    local_marzban_user_id: int
) -> Dict[str, Any]:
    """
    Fetches usage data for a specific Marzban user belonging to the reseller from the Marzban panel.
    """
    local_db_user = get_marzban_user_for_reseller(db, marzban_user_id=local_marzban_user_id, reseller_id=reseller.id)
    if not local_db_user:
        raise MarzbanUserServiceError("Marzban user not found or does not belong to this reseller.")

    target_panel = local_db_user.marzban_panel
    if not target_panel:
        raise MarzbanUserServiceError("Marzban panel details not found for this user.")

    decrypted_password = get_panel_decrypted_password(db, target_panel.id)
    if not decrypted_password:
        raise MarzbanUserServiceError(f"Could not retrieve credentials for panel {target_panel.name}.")

    marzban_token = get_marzban_access_token(target_panel.api_url, target_panel.admin_username, decrypted_password)
    if not marzban_token:
        raise MarzbanUserServiceError(f"Failed to authenticate with Marzban panel {target_panel.name}.")

    try:
        usage_data = get_usage_from_marzban_panel(
            panel_url=target_panel.api_url,
            token=marzban_token,
            username=local_db_user.marzban_username
        )
        if usage_data is None: # Should be caught by MarzbanAPIError, but as a fallback.
            raise MarzbanUserServiceError("Failed to retrieve usage data from Marzban panel or user not found on panel.")
        
        # Optionally, update local_db_user.api_response_data or a part of it with this fresh usage
        # For now, just return the fetched usage.
        # Example: local_db_user.api_response_data['usage'] = usage_data 
        #          local_db_user.last_synced_at = datetime.utcnow()
        #          db.add(local_db_user)
        #          db.commit()
        # This would keep the local record somewhat updated with last known usage.
        # However, usage is very dynamic, so on-demand fetching is primary.

        return usage_data
    except MarzbanAPIError as e:
        # Re-raise as service error to be handled by API layer
        raise MarzbanUserServiceError(f"Marzban API error when fetching usage: {str(e)}")
    except Exception as e:
        # Catch any other unexpected errors
        raise MarzbanUserServiceError(f"An unexpected error occurred when fetching usage: {str(e)}")



# --- Reseller User Creation ---
from app.schemas.marzban_user import ResellerMarzbanUserCreateRequest
from app.services import reseller_pricing_service, transaction_service # For pricing and transactions
from app.db.models.transaction import Transaction # For creating transaction object
from app.schemas.transaction import TransactionCreate # For creating transaction Pydantic object
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta

# Helper to convert GB to bytes for Marzban API
def gb_to_bytes(gb: Optional[float]) -> Optional[int]:
    if gb is None:
        return None
    return int(gb * 1024 * 1024 * 1024)

# Helper to convert days to future timestamp for Marzban API
def days_to_timestamp(days: Optional[int]) -> Optional[int]:
    if days is None:
        return None
    return int((datetime.utcnow() + timedelta(days=days)).timestamp())


def create_marzban_user_for_reseller(
    db: Session, reseller: Reseller, user_create_request: ResellerMarzbanUserCreateRequest
) -> MarzbanUser:
    # Step 1: Panel Access Check
    panel_accessible = any(
        panel.id == user_create_request.marzban_panel_id for panel in reseller.panels
    )
    if not panel_accessible:
        raise MarzbanUserServiceError(
            f"Reseller does not have access to Marzban panel ID {user_create_request.marzban_panel_id}."
        )

    target_panel = db.query(MarzbanPanel).filter(MarzbanPanel.id == user_create_request.marzban_panel_id).first()
    if not target_panel: # Should not happen if panel_accessible check passed based on Reseller.panels
        raise MarzbanUserServiceError(f"Target Marzban panel ID {user_create_request.marzban_panel_id} not found.")

    # Step 2: Determine Cost
    active_pricing = reseller_pricing_service.get_active_pricing_for_reseller(
        db, reseller_id=reseller.id, marzban_panel_id=target_panel.id
    )

    cost = Decimal("0.00")
    pricing_plan_id_for_tx = None
    reseller_pricing_id_for_tx = None

    if not active_pricing:
        raise MarzbanUserServiceError(
            "No active pricing configuration found for this reseller and panel. Please contact admin."
        )
    
    reseller_pricing_id_for_tx = active_pricing.id
    if active_pricing.custom_price_per_gb is not None:
        if user_create_request.data_limit_gb is None or user_create_request.data_limit_gb <= 0:
            raise MarzbanUserServiceError(
                "Data limit (data_limit_gb) must be provided and positive for custom GB pricing."
            )
        # Round cost to 2 decimal places
        cost = (Decimal(str(user_create_request.data_limit_gb)) * active_pricing.custom_price_per_gb).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    elif active_pricing.pricing_plan_id is not None and active_pricing.pricing_plan:
        cost = active_pricing.pricing_plan.price
        pricing_plan_id_for_tx = active_pricing.pricing_plan_id
        # Optionally, override request's data_limit_gb and expire_days with plan's values if strict plan adherence is policy
        # For now, request values are used for Marzban user creation, plan just determines cost.
    else:
        # Should not be reached if ResellerPricing validation is correct (either plan or custom price)
        raise MarzbanUserServiceError("Invalid pricing configuration found. Contact admin.")

    # Step 3: Wallet Check
    if reseller.wallet_balance < cost and not reseller.allow_negative_balance:
        raise MarzbanUserServiceError(
            f"Insufficient wallet balance. Required: {cost}, Available: {reseller.wallet_balance}."
        )

    # Step 4: Marzban API Call
    decrypted_password = get_panel_decrypted_password(db, target_panel.id)
    if not decrypted_password:
        raise MarzbanUserServiceError(f"Could not retrieve credentials for panel {target_panel.name}.")

    marzban_token = get_marzban_access_token(target_panel.api_url, target_panel.admin_username, decrypted_password)
    if not marzban_token:
        raise MarzbanUserServiceError(f"Failed to authenticate with Marzban panel {target_panel.name}.")

    # Prepare Marzban user parameters
    data_limit_in_bytes = gb_to_bytes(user_create_request.data_limit_gb)
    expire_ts = days_to_timestamp(user_create_request.expire_days)

    try:
        marzban_user_api_response = create_marzban_user(
            panel_url=target_panel.api_url,
            token=marzban_token,
            username=user_create_request.username,
            admin_id=reseller.marzban_admin_id, # Pass reseller's Marzban admin ID as creator
            proxies=user_create_request.proxies,
            inbounds=user_create_request.inbounds,
            expire_timestamp=expire_ts,
            data_limit_bytes=data_limit_in_bytes,
            telegram_id=user_create_request.telegram_id,
            note=user_create_request.note
        )
    except MarzbanAPIError as e:
        # Specific error from Marzban API (e.g., username exists, validation error)
        raise MarzbanUserServiceError(f"Marzban API error: {str(e)}")
    
    if not marzban_user_api_response or not marzban_user_api_response.get("username"):
        # Fallback if create_marzban_user returns None or unexpected response without raising error
        raise MarzbanUserServiceError("Failed to create user on Marzban panel or received unexpected response.")

    # Step 5: Database Updates (Atomically)
    try:
        # Begin nested transaction or rely on caller to commit everything if this service is part of larger op.
        # For now, assuming this service method should be atomic for its operations.
        
        # 5.1 Update reseller wallet balance
        reseller.wallet_balance -= cost
        db.add(reseller)

        # 5.2 Create local MarzbanUser record
        # The service `create_marzban_user` (local one) commits itself.
        # This is problematic for atomicity. It should also not commit.
        # For now, I will call it and accept its commit, then create transaction.
        # Ideal: all DB ops added to session, then one commit at the end.
        
        local_user_create_schema = MarzbanUserCreate(
            marzban_username=marzban_user_api_response["username"], # Use username from Marzban response
            marzban_panel_id=target_panel.id,
            reseller_id=reseller.id,
            created_by_new_panel=True,
            api_response_data=marzban_user_api_response,
            notes=user_create_request.note # Or a system generated note
        )
        # Assume create_marzban_user (local) is modified not to commit, or use direct model creation.
        # db_local_marzban_user = create_marzban_user(db, local_user_create_schema) # if it doesn't commit
        db_local_marzban_user = MarzbanUser(**local_user_create_schema.dict())
        db.add(db_local_marzban_user)
        db.flush() # To get db_local_marzban_user.id for the transaction log, before commit.


        # 5.3 Create transaction log
        # transaction_service.create_transaction also commits itself. This needs to change.
        # Assuming it's changed not to commit:
        tx_create_schema = TransactionCreate(
            reseller_id=reseller.id,
            transaction_type='user_creation_cost',
            amount= -cost, # Cost is negative for debits
            marzban_user_id=db_local_marzban_user.id, # Link to local MarzbanUser ID
            pricing_plan_id=pricing_plan_id_for_tx,
            reseller_pricing_id=reseller_pricing_id_for_tx,
            description=(
                f"Cost for creating Marzban user '{marzban_user_api_response['username']}' "
                f"on panel '{target_panel.name}'. Data: {user_create_request.data_limit_gb or 'N/A'}GB, "
                f"Days: {user_create_request.expire_days or 'N/A'}."
            )
        )
        # transaction_service.create_transaction(db, tx_create_schema) # if it doesn't commit
        db_transaction = Transaction(**tx_create_schema.dict())
        db.add(db_transaction)
        
        db.commit() # Commit all changes: wallet, local user, transaction
        
        db.refresh(reseller)
        db.refresh(db_local_marzban_user)
        # db.refresh(db_transaction) # if needed

        return db_local_marzban_user

    except Exception as e_db:
        db.rollback()
        # TODO: Important! If Marzban user was created but DB ops failed, need a compensation mechanism.
        # This could involve trying to delete the user from Marzban, or flagging for admin.
        # For now, just raising the DB error.
        raise MarzbanUserServiceError(f"Database error after Marzban user creation: {str(e_db)}. Manual reconciliation may be needed for user '{marzban_user_api_response.get('username')}' on panel '{target_panel.name}'.")

