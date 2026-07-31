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
    
    # Authentication
    API_KEY: str = os.getenv("API_KEY", "")  # Set via environment variable
    API_KEY_HEADER: str = "X-API-Key"
    AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "false").lower() == "true"
    
    # CORS Settings
    CORS_ORIGINS: List[str] = os.getenv("CORS_ORIGINS", "*").split(",")
    
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
