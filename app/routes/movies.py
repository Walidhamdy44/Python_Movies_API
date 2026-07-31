"""
Movies CRUD endpoints.
"""

import math
from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db, Movie, User
from app.models import (
    MovieCreate, 
    MovieUpdate, 
    MovieResponse, 
    MoviesListResponse,
    MessageResponse,
    DownloadLink,
)
from app.auth import get_current_admin, get_optional_user

router = APIRouter(prefix="/movies", tags=["Movies"])


def movie_to_response(movie: Movie) -> MovieResponse:
    """Convert database movie to response model."""
    return MovieResponse(
        id=movie.id,
        name=movie.name,
        name_ar=movie.name_ar,
        poster_url=movie.poster_url,
        movie_url=movie.movie_url,
        year=movie.year,
        quality=movie.quality,
        rating=movie.rating,
        duration=movie.duration,
        genres=movie.genres or [],
        description=movie.description,
        description_ar=movie.description_ar,
        download_links=[DownloadLink(**link) for link in (movie.download_links or [])],
        views=movie.views or "0",
        created_at=movie.created_at,
        updated_at=movie.updated_at,
    )


@router.get("", response_model=MoviesListResponse)
async def list_movies(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by name"),
    db: Session = Depends(get_db),
):
    """
    List all movies with pagination.
    Public endpoint - no authentication required.
    """
    query = db.query(Movie)
    
    # Search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Movie.name.ilike(search_term)) | 
            (Movie.name_ar.ilike(search_term))
        )
    
    # Get total count
    total = query.count()
    
    # Pagination
    total_pages = math.ceil(total / per_page) if total > 0 else 1
    offset = (page - 1) * per_page
    
    movies = query.order_by(Movie.created_at.desc()).offset(offset).limit(per_page).all()
    
    return MoviesListResponse(
        movies=[movie_to_response(m) for m in movies],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.get("/{movie_id}", response_model=MovieResponse)
async def get_movie(
    movie_id: str,
    db: Session = Depends(get_db),
):
    """
    Get a single movie by ID.
    Also increments view count.
    """
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found"
        )
    
    # Increment views
    try:
        current_views = int(movie.views or "0")
        movie.views = str(current_views + 1)
        db.commit()
    except:
        pass
    
    return movie_to_response(movie)


@router.post("", response_model=MovieResponse)
async def create_movie(
    movie_data: MovieCreate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Create a new movie.
    Admin only.
    """
    movie = Movie(
        name=movie_data.name,
        name_ar=movie_data.name_ar,
        poster_url=movie_data.poster_url,
        movie_url=movie_data.movie_url,
        year=movie_data.year,
        quality=movie_data.quality,
        rating=movie_data.rating,
        duration=movie_data.duration,
        genres=movie_data.genres,
        description=movie_data.description,
        description_ar=movie_data.description_ar,
        created_by=current_user.id,
    )
    
    db.add(movie)
    db.commit()
    db.refresh(movie)
    
    return movie_to_response(movie)


@router.put("/{movie_id}", response_model=MovieResponse)
async def update_movie(
    movie_id: str,
    movie_data: MovieUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Update a movie.
    Admin only.
    """
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found"
        )
    
    # Update fields
    update_data = movie_data.model_dump(exclude_unset=True)
    
    # Convert download_links to dict format for JSON storage
    if "download_links" in update_data and update_data["download_links"]:
        update_data["download_links"] = [
            link.model_dump() if hasattr(link, 'model_dump') else link 
            for link in update_data["download_links"]
        ]
    
    for field, value in update_data.items():
        setattr(movie, field, value)
    
    db.commit()
    db.refresh(movie)
    
    return movie_to_response(movie)


@router.delete("/{movie_id}", response_model=MessageResponse)
async def delete_movie(
    movie_id: str,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Delete a movie.
    Admin only.
    """
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found"
        )
    
    db.delete(movie)
    db.commit()
    
    return MessageResponse(message="Movie deleted successfully")


@router.post("/{movie_id}/extract", response_model=MovieResponse)
async def extract_movie_links(
    movie_id: str,
    limit: int = Query(5, ge=1, le=10, description="Max links to extract"),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Extract download links for a movie using the extraction service.
    Updates the movie's download_links field.
    Admin only.
    """
    from app.services import DownloadExtractor
    
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found"
        )
    
    # Run extraction
    extractor = DownloadExtractor()
    result = extractor.extract(movie.movie_url, limit=limit)
    
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {result.message}"
        )
    
    # Update movie with extracted links
    movie.download_links = [link.model_dump() for link in result.download_links]
    
    # Update metadata if extracted
    if result.movie:
        if result.movie.year and not movie.year:
            movie.year = result.movie.year
        if result.movie.quality and not movie.quality:
            movie.quality = result.movie.quality
        if result.movie.rating and not movie.rating:
            movie.rating = result.movie.rating
    
    db.commit()
    db.refresh(movie)
    
    return movie_to_response(movie)
