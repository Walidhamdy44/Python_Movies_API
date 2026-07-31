"""
Pydantic models for API requests and responses.
"""

from pydantic import BaseModel
from typing import Optional, List


class DownloadLink(BaseModel):
    """Represents a download link from a host."""
    host: str
    quality: Optional[str] = None
    direct_link: str
    is_direct: bool


class MovieInfo(BaseModel):
    """Movie metadata extracted from the page."""
    title: str
    year: Optional[str] = None
    image: Optional[str] = None
    quality: Optional[str] = None
    rating: Optional[str] = None
    duration: Optional[str] = None
    genres: List[str] = []


class ExtractResponse(BaseModel):
    """Response model for extraction endpoint."""
    success: bool
    message: str
    url: str
    movie: Optional[MovieInfo] = None
    download_links: List[DownloadLink] = []
    total_links: int = 0
    direct_links_count: int = 0


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""
    status: str
    seleniumbase: bool
    auth_enabled: bool
