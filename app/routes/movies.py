"""
Movies CRUD endpoints using MongoDB.
"""

import math
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, List
from bson import ObjectId
from pydantic import BaseModel

from app.database import get_database, movie_doc, serialize_doc
from app.routes.auth import get_current_admin

router = APIRouter(prefix="/movies", tags=["Movies"])


# Request/Response models
class MovieCreate(BaseModel):
    name: str
    movie_url: str
    name_ar: Optional[str] = None
    poster_url: Optional[str] = None
    year: Optional[str] = None
    quality: Optional[str] = None
    rating: Optional[str] = None
    duration: Optional[str] = None
    genres: Optional[List[str]] = None
    description: Optional[str] = None
    description_ar: Optional[str] = None


class MovieUpdate(BaseModel):
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
    download_links: Optional[List[dict]] = None


class MoviesListResponse(BaseModel):
    movies: List[dict]
    total: int
    page: int
    per_page: int
    total_pages: int


@router.get("", response_model=MoviesListResponse)
async def list_movies(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by name"),
):
    """List all movies with pagination."""
    db = get_database()
    
    # Build query - ignore "undefined" string from frontend
    query = {}
    if search and search.lower() not in ["undefined", "null", ""]:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"name_ar": {"$regex": search, "$options": "i"}}
        ]
    
    # Get total count
    total = await db.movies.count_documents(query)
    
    # Pagination
    total_pages = math.ceil(total / per_page) if total > 0 else 1
    skip = (page - 1) * per_page
    
    # Fetch movies
    cursor = db.movies.find(query).sort("created_at", -1).skip(skip).limit(per_page)
    movies = await cursor.to_list(length=per_page)
    
    return MoviesListResponse(
        movies=[serialize_doc(m) for m in movies],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.get("/{movie_id}")
async def get_movie(movie_id: str):
    """Get a single movie by ID."""
    db = get_database()
    
    try:
        oid = ObjectId(movie_id)
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid movie ID"
        )
    
    movie = await db.movies.find_one({"_id": oid})
    
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found"
        )
    
    # Increment views
    await db.movies.update_one(
        {"_id": oid},
        {"$inc": {"views": 1}}
    )
    
    return serialize_doc(movie)


@router.post("")
async def create_movie(
    movie_data: MovieCreate,
    admin: dict = Depends(get_current_admin),
):
    """Create a new movie. Admin only."""
    db = get_database()
    
    new_movie = movie_doc(
        name=movie_data.name,
        movie_url=movie_data.movie_url,
        name_ar=movie_data.name_ar,
        poster_url=movie_data.poster_url,
        year=movie_data.year,
        quality=movie_data.quality,
        rating=movie_data.rating,
        duration=movie_data.duration,
        genres=movie_data.genres,
        description=movie_data.description,
        description_ar=movie_data.description_ar,
        created_by=admin.get("id"),
    )
    
    result = await db.movies.insert_one(new_movie)
    new_movie["_id"] = result.inserted_id
    
    return serialize_doc(new_movie)


@router.put("/{movie_id}")
async def update_movie(
    movie_id: str,
    movie_data: MovieUpdate,
    admin: dict = Depends(get_current_admin),
):
    """Update a movie. Admin only."""
    db = get_database()
    
    try:
        oid = ObjectId(movie_id)
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid movie ID"
        )
    
    movie = await db.movies.find_one({"_id": oid})
    
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found"
        )
    
    # Build update
    update_data = movie_data.model_dump(exclude_unset=True)
    if update_data:
        from datetime import datetime
        update_data["updated_at"] = datetime.utcnow()
        
        await db.movies.update_one(
            {"_id": oid},
            {"$set": update_data}
        )
    
    # Return updated movie
    movie = await db.movies.find_one({"_id": oid})
    return serialize_doc(movie)


@router.delete("/{movie_id}")
async def delete_movie(
    movie_id: str,
    admin: dict = Depends(get_current_admin),
):
    """Delete a movie. Admin only."""
    db = get_database()
    
    try:
        oid = ObjectId(movie_id)
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid movie ID"
        )
    
    result = await db.movies.delete_one({"_id": oid})
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found"
        )
    
    return {"message": "Movie deleted successfully"}


@router.post("/{movie_id}/extract")
async def extract_movie_links(
    movie_id: str,
    limit: int = Query(5, ge=1, le=10, description="Max links to extract"),
    admin: dict = Depends(get_current_admin),
):
    """Extract download links for a movie. Admin only."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from app.services import DownloadExtractor
    
    db = get_database()
    
    try:
        oid = ObjectId(movie_id)
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid movie ID"
        )
    
    movie = await db.movies.find_one({"_id": oid})
    
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found"
        )
    
    # Run extraction in thread pool to avoid blocking async loop
    def run_extraction():
        extractor = DownloadExtractor()
        return extractor.extract(movie["movie_url"], limit=limit)
    
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=1)
    result = await loop.run_in_executor(executor, run_extraction)
    
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {result.message}"
        )
    
    # Update movie with extracted links
    update_data = {
        "download_links": [link.model_dump() for link in result.download_links]
    }
    
    # Update metadata if extracted
    if result.movie:
        if result.movie.year and not movie.get("year"):
            update_data["year"] = result.movie.year
        if result.movie.quality and not movie.get("quality"):
            update_data["quality"] = result.movie.quality
        if result.movie.rating and not movie.get("rating"):
            update_data["rating"] = result.movie.rating
    
    await db.movies.update_one({"_id": oid}, {"$set": update_data})
    
    # Return updated movie
    movie = await db.movies.find_one({"_id": oid})
    return serialize_doc(movie)
