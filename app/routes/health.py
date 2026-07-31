"""
Health check endpoint.
"""

import os
from fastapi import APIRouter
from app.models import HealthResponse
from app.services import SELENIUMBASE_AVAILABLE
from app.config import settings

router = APIRouter(tags=["Health"])


@router.get("/", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns API status and configuration info.
    """
    # Determine database type
    db_url = os.getenv("DATABASE_URL", "sqlite:///./moviehub.db")
    if "postgresql" in db_url or "postgres" in db_url:
        db_type = "PostgreSQL"
    else:
        db_type = "SQLite"
    
    return HealthResponse(
        status="ok",
        seleniumbase=SELENIUMBASE_AVAILABLE,
        auth_enabled=settings.AUTH_ENABLED,
        database=db_type,
    )
