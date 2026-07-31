"""
API Key authentication module.
"""

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from app.config import settings

# API Key header definition
api_key_header = APIKeyHeader(
    name=settings.API_KEY_HEADER,
    auto_error=False,
    description="API Key for authentication"
)


def get_api_key_header():
    """Returns the API key header security scheme."""
    return api_key_header


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Verify the API key from request header.
    
    If AUTH_ENABLED is False, authentication is skipped.
    If AUTH_ENABLED is True, a valid API_KEY must be provided.
    
    Returns:
        The verified API key or empty string if auth disabled
        
    Raises:
        HTTPException: If authentication fails
    """
    # If auth is disabled, allow all requests
    if not settings.AUTH_ENABLED:
        return ""
    
    # Auth is enabled, validate the key
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key. Provide it in the X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    if api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key",
        )
    
    return api_key
