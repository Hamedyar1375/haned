from pydantic import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+pymysql://user:password@host/db_name"
    SECRET_KEY: str = "your-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    MARZBAN_PANEL_FERNET_KEY: Optional[str] = None # Allow it to be None initially

    class Config:
        env_file = ".env"

settings = Settings()

# Generate and set MARZBAN_PANEL_FERNET_KEY if not provided via environment
# This is a simplified approach for this subtask.
# In production, the key should ideally be set via environment variable and be persistent.
if settings.MARZBAN_PANEL_FERNET_KEY is None:
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    settings.MARZBAN_PANEL_FERNET_KEY = key.decode()
    print(f"Generated new MARZBAN_PANEL_FERNET_KEY: {settings.MARZBAN_PANEL_FERNET_KEY}")
    print("IMPORTANT: Store this key securely, e.g., in your .env file for persistence.")
    # In a real app, you might write this to a .env file or require it to be set.
