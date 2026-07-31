"""
SQLAlchemy database models.
"""

from sqlalchemy import Column, String, Text, Boolean, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.sql import func
from datetime import datetime
import enum
import uuid

from app.database.connection import Base


def generate_uuid():
    """Generate a unique ID."""
    return str(uuid.uuid4())


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"


class User(Base):
    """User model for authentication."""
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default=UserRole.USER.value)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Movie(Base):
    """Movie model."""
    __tablename__ = "movies"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    
    # Basic info
    name = Column(String(255), nullable=False)
    name_ar = Column(String(255), nullable=True)  # Arabic name
    poster_url = Column(Text, nullable=True)  # Made optional
    movie_url = Column(Text, nullable=False)
    
    # Metadata
    year = Column(String(10), nullable=True)
    quality = Column(String(20), nullable=True)
    rating = Column(String(10), nullable=True)
    duration = Column(String(50), nullable=True)
    genres = Column(JSON, default=list)  # List of genres
    
    # Descriptions
    description = Column(Text, nullable=True)
    description_ar = Column(Text, nullable=True)  # Arabic description
    
    # Download links (extracted from our API)
    download_links = Column(JSON, default=list)  # List of {host, quality, direct_link, is_direct}
    
    # Tracking
    created_by = Column(String(36), nullable=True)  # Admin user ID
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Views counter
    views = Column(String(20), default="0")


class ExtractionLog(Base):
    """Log of URL extractions."""
    __tablename__ = "extraction_logs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    url = Column(Text, nullable=False)
    movie_id = Column(String(36), nullable=True)  # If linked to a movie
    status = Column(String(20), nullable=False)  # success, failed
    links_found = Column(String(10), default="0")
    direct_links = Column(String(10), default="0")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
