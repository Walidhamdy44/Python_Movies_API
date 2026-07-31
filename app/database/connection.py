"""
Database connection using SQLite (local) or PostgreSQL (production).
SQLite is file-based - no shutdown, no external service needed.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Get database URL from environment
# Default: SQLite file in the app directory (never shuts down!)
# Production: Set DATABASE_URL to PostgreSQL connection string
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./moviehub.db")

# Handle Railway/Render PostgreSQL URL format
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create engine
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}  # Required for SQLite
    )
else:
    engine = create_engine(DATABASE_URL)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    from app.database.models import User, Movie  # Import models
    Base.metadata.create_all(bind=engine)
