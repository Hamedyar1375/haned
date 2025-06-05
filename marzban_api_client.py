import requests
from typing import List, Dict, Optional, Any

class MarzbanAPIError(Exception):
    """Custom exception for Marzban API client errors."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code

def get_marzban_access_token(panel_url: str, username: str, password: str) -> Optional[str]:
    """Fetches access token from Marzban API."""
    try:
        # Ensure panel_url ends with a slash for proper joining
        if not panel_url.endswith('/'):
            panel_url += '/'
        
        login_url = f"{panel_url}api/admin/token"
        payload = {
            "username": username,
            "password": password
        }
        response = requests.post(login_url, data=payload, timeout=10) # 10s timeout
        response.raise_for_status() # Raises HTTPError for bad responses (4XX or 5XX)
        
        token_data = response.json()
        return token_data.get("access_token")

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        try:
            detail = e.response.json().get("detail", e.response.text)
        except requests.exceptions.JSONDecodeError:
            detail = e.response.text
        raise MarzbanAPIError(f"Failed to get Marzban token (HTTP {status_code}): {detail}", status_code=status_code)
    except requests.exceptions.RequestException as e:
        # Includes connection errors, timeouts, etc.
        raise MarzbanAPIError(f"Request failed while getting Marzban token: {str(e)}")
    except Exception as e: # Catch any other unexpected errors
        raise MarzbanAPIError(f"An unexpected error occurred while getting Marzban token: {str(e)}")


def get_marzban_users(
    panel_url: str, token: str, admin_id: Optional[int] = None
) -> Optional[List[Dict[str, Any]]]:
    """
    Fetches users from Marzban API.
    Optionally filters by admin_id (creator_admin_id in Marzban).
    """
    try:
        if not panel_url.endswith('/'):
            panel_url += '/'
        
        users_url = f"{panel_url}api/users"
        headers = {
            "Authorization": f"Bearer {token}"
        }
        params = {}
        if admin_id is not None:
            # Marzban user list can be filtered by `creator_admin_id`
            # Assuming `admin_id` here refers to the ID of the admin who created users in Marzban.
            # If it's a different parameter, this needs adjustment.
            # For now, let's assume it's not a direct filter in Marzban's /api/users
            # and we might need to filter client-side or adjust if Marzban supports it.
            # The standard Marzban /api/users does not seem to support creator_admin_id filter directly.
            # It returns all users. We will fetch all and filter client-side if admin_id is for that.
            # However, the subtask mentions "filtering by admin_id if provided".
            # This implies the Marzban API should support it or it's a misunderstanding of Marzban's API.
            # For now, let's assume Marzban's API does NOT filter by admin_id for the /users endpoint.
            # The admin_id in Marzban user object is `creator_admin_id`.
            # If the goal is to get users *created by* a specific admin (our Reseller.marzban_admin_id),
            # we'll have to fetch all and then filter.
            pass # No direct API filter for creator_admin_id on /users

        response = requests.get(users_url, headers=headers, params=params, timeout=15) # 15s timeout
        response.raise_for_status()
        
        users_data = response.json()
        
        # Client-side filtering if admin_id is provided (creator_admin_id)
        # This is inefficient for large user bases on Marzban.
        # A better approach would be if Marzban API supported server-side filtering.
        if admin_id is not None:
            filtered_users = [
                user for user in users_data.get("users", []) 
                if user.get("creator_admin_id") == admin_id
            ]
            return filtered_users
        else:
            return users_data.get("users", [])

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        try:
            detail = e.response.json().get("detail", e.response.text)
        except requests.exceptions.JSONDecodeError:
            detail = e.response.text
        raise MarzbanAPIError(f"Failed to get Marzban users (HTTP {status_code}): {detail}", status_code=status_code)
    except requests.exceptions.RequestException as e:
        raise MarzbanAPIError(f"Request failed while getting Marzban users: {str(e)}")
    except Exception as e:
        raise MarzbanAPIError(f"An unexpected error occurred while getting Marzban users: {str(e)}")


def create_marzban_user(
    panel_url: str,
    token: str,
    username: str,
    admin_id: Optional[int] = None, # creator_admin_id in Marzban
    proxies: Optional[Dict[str, Any]] = None,
    inbounds: Optional[Dict[str, List[str]]] = None,
    expire_timestamp: Optional[int] = None, # Unix timestamp for expiration
    data_limit_bytes: Optional[int] = None, # Data limit in bytes
    telegram_id: Optional[str] = None,
    note: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Creates a new user in Marzban.
    Marzban API /api/user expects:
    - username: str
    - proxies: dict (e.g., {"vless": {"flow": "xtls-rprx-vision"}})
    - inbounds: dict (e.g., {"vless": ["VLESS TCP REALITY"]})
    - expire: int (Unix timestamp)
    - data_limit: int (bytes)
    - admin_id: int (creator_admin_id)
    - tg_id: str
    - note: str
    """
    try:
        if not panel_url.endswith('/'):
            panel_url += '/'
        
        create_user_url = f"{panel_url}api/user" # Note: Marzban's path is /api/user for creation
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {"username": username}
        if proxies is not None:
            payload["proxies"] = proxies
        if inbounds is not None:
            payload["inbounds"] = inbounds
        if expire_timestamp is not None:
            payload["expire"] = expire_timestamp
        if data_limit_bytes is not None:
            payload["data_limit"] = data_limit_bytes
        if admin_id is not None:
            payload["admin_id"] = admin_id # This should be the creator_admin_id
        if telegram_id is not None:
            payload["tg_id"] = telegram_id
        if note is not None:
            payload["note"] = note
            
        response = requests.post(create_user_url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        try:
            detail = e.response.json().get("detail", e.response.text)
        except requests.exceptions.JSONDecodeError: # If Marzban returns non-JSON error
            detail = e.response.text
        # Marzban might return specific errors in detail, e.g., if username exists
        if isinstance(detail, dict) and "username" in detail :
             detail_message = detail["username"][0] if isinstance(detail["username"], list) else detail["username"]
             error_message = f"Failed to create Marzban user (HTTP {status_code}): Username - {detail_message}"
        elif isinstance(detail, str): # Standard error string
            error_message = f"Failed to create Marzban user (HTTP {status_code}): {detail}"
        else: # Other structured error
            error_message = f"Failed to create Marzban user (HTTP {status_code}): {str(detail)}"

        raise MarzbanAPIError(error_message, status_code=status_code)
    except requests.exceptions.RequestException as e:
        raise MarzbanAPIError(f"Request failed while creating Marzban user: {str(e)}")
    except Exception as e:
        raise MarzbanAPIError(f"An unexpected error occurred while creating Marzban user: {str(e)}")


def update_marzban_user(
    panel_url: str, 
    token: str, 
    username: str, 
    update_payload: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Updates an existing user in Marzban using PATCH request.
    `update_payload` should contain only the fields to be updated.
    e.g., {"expire": new_timestamp, "data_limit": new_data_limit_bytes}
    """
    try:
        if not panel_url.endswith('/'):
            panel_url += '/'
        
        update_user_url = f"{panel_url}api/user/{username}" # Note: /api/user/{username} for PATCH
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "accept": "application/json" # Explicitly accept JSON
        }
        
        # Filter out None values from payload, as Marzban might interpret explicit nulls as "unset"
        # or it might be required by API. For PATCH, usually only send what changes.
        # Marzban's PATCH might be sensitive to `null` vs missing field.
        # For now, assume we send what's in update_payload.
        # If a field needs to be UNSET, Marzban API docs should specify how (e.g. sending null or specific value).
        # Example: payload `{"expire": null}` might unset expiry.
        
        response = requests.patch(update_user_url, headers=headers, json=update_payload, timeout=15)
        response.raise_for_status()
        return response.json() # Return the updated user data from Marzban

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        try:
            detail = e.response.json().get("detail", e.response.text)
        except requests.exceptions.JSONDecodeError:
            detail = e.response.text
        raise MarzbanAPIError(f"Failed to update Marzban user '{username}' (HTTP {status_code}): {detail}", status_code=status_code)
    except requests.exceptions.RequestException as e:
        raise MarzbanAPIError(f"Request failed while updating Marzban user '{username}': {str(e)}")
    except Exception as e:
        raise MarzbanAPIError(f"An unexpected error occurred while updating Marzban user '{username}': {str(e)}")


def get_marzban_user_usage(
    panel_url: str, 
    token: str, 
    username: str
) -> Optional[Dict[str, Any]]:
    """
    Fetches a user's usage data from Marzban API.
    Marzban endpoint: /api/user/{username}/usage
    Returns a dictionary like:
    {
        "download": 0,
        "upload": 0,
        "total": 0,
        "remaining": 0, // if data_limit > 0
        "data_limit":0
    }
    """
    try:
        if not panel_url.endswith('/'):
            panel_url += '/'
        
        usage_url = f"{panel_url}api/user/{username}/usage"
        headers = {
            "Authorization": f"Bearer {token}",
            "accept": "application/json"
        }
        
        response = requests.get(usage_url, headers=headers, timeout=10)
        response.raise_for_status() # Raises HTTPError for 4XX/5XX status codes
        return response.json()

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        try:
            detail = e.response.json().get("detail", e.response.text)
        except requests.exceptions.JSONDecodeError:
            detail = e.response.text
        # User not found on Marzban panel will likely be a 404
        if status_code == 404:
             error_message = f"User '{username}' not found on Marzban panel (HTTP {status_code}): {detail}"
        else:
            error_message = f"Failed to get usage for Marzban user '{username}' (HTTP {status_code}): {detail}"
        raise MarzbanAPIError(error_message, status_code=status_code)
    except requests.exceptions.RequestException as e:
        raise MarzbanAPIError(f"Request failed while getting usage for Marzban user '{username}': {str(e)}")
    except Exception as e:
        raise MarzbanAPIError(f"An unexpected error occurred while getting usage for Marzban user '{username}': {str(e)}")
