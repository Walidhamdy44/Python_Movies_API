"""
MongoDB connection and database operations.
Using Motor for async MongoDB operations.
"""

import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

# Global database client
client: Optional[AsyncIOMotorClient] = None
db = None


async def connect_db():
    """Connect to MongoDB."""
    global client, db
    
    try:
        client = AsyncIOMotorClient(settings.MONGODB_URI)
        db = client[settings.MONGODB_DB_NAME]
        
        # Test connection
        await client.admin.command('ping')
        logger.info(f"✓ Connected to MongoDB: {settings.MONGODB_DB_NAME}")
        
        # Create indexes
        await create_indexes()
        
        return db
    except Exception as e:
        logger.error(f"✗ Failed to connect to MongoDB: {e}")
        raise


async def close_db():
    """Close MongoDB connection."""
    global client
    if client:
        client.close()
        logger.info("MongoDB connection closed")


async def create_indexes():
    """Create database indexes for better performance."""
    global db
    
    # Users indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index("username", unique=True)
    
    # Movies indexes
    await db.movies.create_index("name")
    await db.movies.create_index("created_at", DESCENDING)
    await db.movies.create_index([("name", "text"), ("name_ar", "text")])
    
    logger.info("Database indexes created")


def get_db():
    """Get database instance."""
    global db
    return db


# Collections helpers
def get_users_collection():
    """Get users collection."""
    return db.users


def get_movies_collection():
    """Get movies collection."""
    return db.movies
