"""
Authentication endpoints using MongoDB.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
from bson import ObjectId

from app.database import get_database, user_doc, serialize_doc, hash_password, verify_password
from app.auth.jwt_handler import create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


# Request/Response models
class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    is_admin: bool


@router.post("/register", response_model=TokenResponse)
async def register(data: RegisterRequest):
    """Register a new user. First user becomes admin."""
    db = get_database()
    
    # Check if email exists
    existing = await db.users.find_one({"email": data.email.lower()})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # First user is admin
    user_count = await db.users.count_documents({})
    is_admin = user_count == 0
    
    # Create user
    new_user = user_doc(
        email=data.email,
        username=data.username,
        password=data.password,
        is_admin=is_admin
    )
    
    result = await db.users.insert_one(new_user)
    new_user["_id"] = result.inserted_id
    
    # Generate token
    token = create_access_token({"sub": str(result.inserted_id)})
    
    user_data = serialize_doc(new_user)
    del user_data["password_hash"]
    
    return TokenResponse(
        access_token=token,
        user=user_data
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest):
    """Login with email and password."""
    db = get_database()
    
    # Find user
    user = await db.users.find_one({"email": data.email.lower()})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Generate token
    token = create_access_token({"sub": str(user["_id"])})
    
    user_data = serialize_doc(user)
    del user_data["password_hash"]
    
    return TokenResponse(
        access_token=token,
        user=user_data
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user_id: str = Depends(get_current_user_id)):
    """Get current user info."""
    db = get_database()
    
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=str(user["_id"]),
        email=user["email"],
        username=user["username"],
        is_admin=user.get("is_admin", False)
    )


# Dependency to get current user ID from token
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.auth.jwt_handler import decode_access_token

security = HTTPBearer()


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Extract user ID from JWT token."""
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    return payload.get("sub")


async def get_current_admin(
    user_id: str = Depends(get_current_user_id)
) -> dict:
    """Get current user and verify admin status."""
    db = get_database()
    
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return serialize_doc(user)
