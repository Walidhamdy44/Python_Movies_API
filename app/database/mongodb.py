"""
MongoDB connection using Motor (async driver).
"""

import os
import certifi
from motor.motor_asyncio import AsyncIOMotorClient

# MongoDB connection string
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "moviehub")

# Global client instance
client: AsyncIOMotorClient = None
db = None


async def connect_db():
    """Connect to MongoDB."""
    global client, db
    
    print(f"Connecting to MongoDB...")
    
    # Use certifi for SSL certificates (fixes SSL issues on some platforms)
    client = AsyncIOMotorClient(
        MONGODB_URL,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
    )
    
    # Test connection
    try:
        await client.admin.command('ping')
        print("✅ Connected to MongoDB!")
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        raise e
    
    db = client[DATABASE_NAME]
    
    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.movies.create_index("created_at")
    
    return db


async def close_db():
    """Close MongoDB connection."""
    global client
    if client:
        client.close()
        print("MongoDB connection closed")


def get_database():
    """Get database instance."""
    return db
