"""
Application configuration and settings.
"""

import os
from typing import List


class Settings:
    """Application settings loaded from environment variables."""
    
    # API Settings
    APP_NAME: str = "Download Link Extractor API"
    APP_VERSION: str = "2.0.0"
    APP_DESCRIPTION: str = "Extract download links from Arabic streaming websites (bypasses Cloudflare)"
    
    # Database - MongoDB
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "moviehub")
    
    # JWT Authentication
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
    
    # API Key (optional)
    API_KEY: str = os.getenv("API_KEY", "")
    API_KEY_HEADER: str = "X-API-Key"
    AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "false").lower() == "true"
    
    # CORS Settings
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")
    
    # Extraction Settings
    MAX_WORKERS: int = int(os.getenv("MAX_WORKERS", "3"))
    DEFAULT_LIMIT: int = int(os.getenv("DEFAULT_LIMIT", "10"))
    MAX_LIMIT: int = int(os.getenv("MAX_LIMIT", "50"))
    
    # Selenium Timeouts (seconds)
    PAGE_LOAD_WAIT: int = int(os.getenv("PAGE_LOAD_WAIT", "4"))
    CLOUDFLARE_WAIT: int = int(os.getenv("CLOUDFLARE_WAIT", "10"))
    CLOUDFLARE_EXTRA_WAIT: int = int(os.getenv("CLOUDFLARE_EXTRA_WAIT", "15"))
    BUTTON_CLICK_WAIT: int = int(os.getenv("BUTTON_CLICK_WAIT", "4"))


settings = Settings()
