"""
Pydantic models for API requests and responses.
"""

from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# ============== Download/Extract Models ==============

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
    database: str


# ============== User/Auth Models ==============

class UserCreate(BaseModel):
    """Create a new user."""
    email: str
    username: str
    password: str


class UserLogin(BaseModel):
    """User login request."""
    email: str
    password: str


class UserResponse(BaseModel):
    """User response (no password)."""
    id: str
    email: str
    username: str
    role: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str
    success: bool = True


# ============== Movie Models ==============

class MovieCreate(BaseModel):
    """Create a new movie."""
    name: str
    name_ar: Optional[str] = None
    poster_url: Optional[str] = None
    movie_url: str
    year: Optional[str] = None
    quality: Optional[str] = None
    rating: Optional[str] = None
    duration: Optional[str] = None
    genres: List[str] = []
    description: Optional[str] = None
    description_ar: Optional[str] = None


class MovieUpdate(BaseModel):
    """Update a movie."""
    name: Optional[str] = None
    name_ar: Optional[str] = None
    poster_url: Optional[str] = None
    movie_url: Optional[str] = None
    year: Optional[str] = None
    quality: Optional[str] = None
    rating: Optional[str] = None
    duration: Optional[str] = None
    genres: Optional[List[str]] = None
    description: Optional[str] = None
    description_ar: Optional[str] = None
    download_links: Optional[List[DownloadLink]] = None


class MovieResponse(BaseModel):
    """Movie response model."""
    id: str
    name: str
    name_ar: Optional[str] = None
    poster_url: str
    movie_url: str
    year: Optional[str] = None
    quality: Optional[str] = None
    rating: Optional[str] = None
    duration: Optional[str] = None
    genres: List[str] = []
    description: Optional[str] = None
    description_ar: Optional[str] = None
    download_links: List[DownloadLink] = []
    views: str = "0"
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class MoviesListResponse(BaseModel):
    """List of movies with pagination."""
    movies: List[MovieResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
