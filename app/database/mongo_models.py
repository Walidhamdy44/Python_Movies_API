"""
MongoDB document helpers and utilities.
"""

from datetime import datetime
from typing import Optional, List
from bson import ObjectId
import bcrypt


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'), 
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False


def user_doc(email: str, username: str, password: str, is_admin: bool = False) -> dict:
    """Create a user document."""
    return {
        "email": email.lower(),
        "username": username,
        "password_hash": hash_password(password),
        "is_admin": is_admin,
        "created_at": datetime.utcnow(),
    }


def movie_doc(
    name: str,
    movie_url: str,
    name_ar: Optional[str] = None,
    poster_url: Optional[str] = None,
    year: Optional[str] = None,
    quality: Optional[str] = None,
    rating: Optional[str] = None,
    duration: Optional[str] = None,
    genres: Optional[List[str]] = None,
    description: Optional[str] = None,
    description_ar: Optional[str] = None,
    created_by: Optional[str] = None,
) -> dict:
    """Create a movie document."""
    return {
        "name": name,
        "name_ar": name_ar,
        "poster_url": poster_url,
        "movie_url": movie_url,
        "year": year,
        "quality": quality,
        "rating": rating,
        "duration": duration,
        "genres": genres or [],
        "description": description,
        "description_ar": description_ar,
        "download_links": [],
        "views": 0,
        "created_by": created_by,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


def serialize_doc(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict."""
    if doc is None:
        return None
    
    result = dict(doc)
    
    # Convert ObjectId to string
    if "_id" in result:
        result["id"] = str(result.pop("_id"))
    
    # Convert datetime to ISO string
    for key in ["created_at", "updated_at"]:
        if key in result and result[key]:
            result[key] = result[key].isoformat()
    
    return result
