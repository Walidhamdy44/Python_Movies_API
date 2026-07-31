"""
Health check endpoint.
"""

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
    return HealthResponse(
        status="ok",
        seleniumbase=SELENIUMBASE_AVAILABLE,
        auth_enabled=settings.AUTH_ENABLED
    )
