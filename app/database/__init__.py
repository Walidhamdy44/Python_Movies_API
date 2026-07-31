"""
Database module - MongoDB
"""

from app.database.mongodb import connect_db, close_db, get_database
from app.database.mongo_models import (
    user_doc,
    movie_doc,
    serialize_doc,
    hash_password,
    verify_password,
)

__all__ = [
    "connect_db",
    "close_db", 
    "get_database",
    "user_doc",
    "movie_doc",
    "serialize_doc",
    "hash_password",
    "verify_password",
]
