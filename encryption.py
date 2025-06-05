from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings

# Ensure the key is bytes
try:
    key = settings.MARZBAN_PANEL_FERNET_KEY.encode()
    cipher_suite = Fernet(key)
except Exception as e:
    # This might happen if the key is somehow still None or invalid despite config logic
    # Or if Fernet(key) fails for other reasons (e.g. key not 32 url-safe base64-encoded bytes)
    print(f"CRITICAL ERROR: Could not initialize Fernet cipher. MARZBAN_PANEL_FERNET_KEY might be invalid or missing: {e}")
    # Fallback or raise an error to prevent app from running with non-functional encryption
    # For this subtask, we'll print and proceed, but a real app should handle this more robustly.
    # One option is to raise an ImproperlyConfigured exception.
    cipher_suite = None # Indicate that encryption/decryption will not work


def encrypt_data(data: str) -> str:
    if cipher_suite is None:
        raise ValueError("Encryption service is not initialized. Check MARZBAN_PANEL_FERNET_KEY.")
    if not data: # Handle empty string case if necessary
        return ""
    encrypted_bytes = cipher_suite.encrypt(data.encode())
    return encrypted_bytes.decode()

def decrypt_data(encrypted_data: str) -> str:
    if cipher_suite is None:
        raise ValueError("Decryption service is not initialized. Check MARZBAN_PANEL_FERNET_KEY.")
    if not encrypted_data: # Handle empty string case
        return ""
    try:
        decrypted_bytes = cipher_suite.decrypt(encrypted_data.encode())
        return decrypted_bytes.decode()
    except InvalidToken:
        # This error occurs if the token is invalid or corrupted
        # Or if the wrong key was used to decrypt
        print("Error: Failed to decrypt data. Token is invalid or key is incorrect.")
        # Depending on policy, either raise an error or return a specific value (e.g. empty string or None)
        # Raising an error is generally safer to alert to a potential issue.
        raise ValueError("Decryption failed: Invalid token or key.")
    except Exception as e:
        print(f"An unexpected error occurred during decryption: {e}")
        raise ValueError(f"Decryption failed due to an unexpected error: {e}")
