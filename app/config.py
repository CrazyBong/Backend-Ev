from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr
from functools import lru_cache
from typing import List

class Settings(BaseSettings):
    # App
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    SECRET_KEY: SecretStr
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "exp://"]

    # Database (Supabase)
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: SecretStr
    DATABASE_URL: str        # PostgreSQL DSN with PostGIS
    DATABASE_URL_ASYNC: str  # Async DSN

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # JWT
    JWT_ALGORITHM: str = "RS256"
    JWT_PRIVATE_KEY: str     # PEM — stored in env, not file
    JWT_PUBLIC_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # OTP
    OTP_LENGTH: int = 6
    OTP_EXPIRE_SECONDS: int = 300
    OTP_MAX_ATTEMPTS: int = 5
    OTP_RATE_LIMIT_WINDOW: int = 600  # 10 minutes

    # Razorpay
    RAZORPAY_KEY_ID: str
    RAZORPAY_KEY_SECRET: str
    RAZORPAY_WEBHOOK_SECRET: str

    # Google Maps
    GOOGLE_MAPS_API_KEY: str

    # Expo Notifications
    EXPO_ACCESS_TOKEN: str

    # Slot Locking
    SLOT_LOCK_TTL_SECONDS: int = 120   # 2 minutes

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
