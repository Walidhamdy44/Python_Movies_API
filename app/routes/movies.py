"""
Movies CRUD endpoints using MongoDB.
"""

import math
import asyncio
from fastapi import APIRouter, HTTPException, status, Depends, Query, BackgroundTasks
from typing import Optional, List
from bson import ObjectId
from pydantic import BaseModel
from datetime import datetime

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


class BulkMovieCreate(BaseModel):
    """Bulk movie creation - list of URLs to process."""
    urls: List[str]
    auto_extract: bool = True  # Auto extract info and download links


class BulkJobStatus(BaseModel):
    """Status of a bulk job."""
    job_id: str
    status: str  # pending, processing, completed, failed
    total: int
    processed: int
    successful: int
    failed: int
    results: List[dict] = []


class MoviesListResponse(BaseModel):
    movies: List[dict]
    total: int
    page: int
    per_page: int
    total_pages: int


# Store for bulk job status (in production, use Redis or DB)
bulk_jobs = {}


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
    limit: int = Query(10, ge=1, le=20, description="Max links to extract"),
    get_direct_links: bool = Query(True, description="Process host links to get direct CDN URLs"),
    admin: dict = Depends(get_current_admin),
):
    """Extract download links for a movie. Admin only."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from urllib.parse import urlparse
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
    
    movie_url = movie["movie_url"]
    
    # Auto-detect website type
    def is_wecima_url(url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return 'wecima' in host
    
    # Run extraction in thread pool to avoid blocking async loop
    def run_extraction():
        extractor = DownloadExtractor()
        # Use appropriate extraction method based on website
        if is_wecima_url(movie_url):
            return extractor.extract_wecima(movie_url, limit=limit, get_direct_links=get_direct_links)
        else:
            return extractor.extract(movie_url, limit=limit)
    
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


# ============== Bulk Operations ==============

async def process_single_movie(url: str, admin_id: str, auto_extract: bool = True) -> dict:
    """Process a single movie URL - extract info and create movie."""
    from concurrent.futures import ThreadPoolExecutor
    from urllib.parse import urlparse
    from app.services import DownloadExtractor
    
    db = get_database()
    result = {
        "url": url,
        "success": False,
        "movie_id": None,
        "error": None
    }
    
    # Auto-detect website type
    def is_wecima_url(u: str) -> bool:
        host = urlparse(u).netloc.lower()
        return 'wecima' in host
    
    try:
        # Extract movie info from URL
        def run_info_extraction():
            extractor = DownloadExtractor()
            if is_wecima_url(url):
                return extractor.extract_wecima_info_only(url)
            else:
                return extractor.extract_info_only(url)
        
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=1)
        extract_result = await loop.run_in_executor(executor, run_info_extraction)
        
        if not extract_result.success:
            result["error"] = f"Failed to extract info: {extract_result.message}"
            return result
        
        movie_info = extract_result.movie
        
        # For wecima, download links are already included in the info extraction
        download_links = []
        if extract_result.download_links:
            download_links = [link.model_dump() for link in extract_result.download_links]
        
        # Create the movie
        new_movie = movie_doc(
            name=movie_info.title if movie_info else "Unknown",
            movie_url=url,
            poster_url=movie_info.image if movie_info else None,
            year=movie_info.year if movie_info else None,
            quality=movie_info.quality if movie_info else None,
            rating=movie_info.rating if movie_info else None,
            duration=movie_info.duration if movie_info else None,
            genres=movie_info.genres if movie_info else [],
            created_by=admin_id,
        )
        
        # If we already have download links from wecima, add them
        if download_links:
            new_movie["download_links"] = download_links
        
        insert_result = await db.movies.insert_one(new_movie)
        movie_id = str(insert_result.inserted_id)
        
        result["success"] = True
        result["movie_id"] = movie_id
        result["title"] = movie_info.title if movie_info else "Unknown"
        
        # If we already got links from wecima, skip additional extraction
        if download_links:
            result["links_extracted"] = len(download_links)
            return result
        
        # Auto extract download links if requested (for egydead)
        if auto_extract:
            try:
                def run_link_extraction():
                    extractor = DownloadExtractor()
                    return extractor.extract(url, limit=10)
                
                link_result = await loop.run_in_executor(executor, run_link_extraction)
                
                if link_result.success and link_result.download_links:
                    await db.movies.update_one(
                        {"_id": insert_result.inserted_id},
                        {"$set": {"download_links": [link.model_dump() for link in link_result.download_links]}}
                    )
                    result["links_extracted"] = len(link_result.download_links)
            except Exception as e:
                result["links_error"] = str(e)
        
        return result
        
    except Exception as e:
        result["error"] = str(e)
        return result


async def process_bulk_job(job_id: str, urls: List[str], admin_id: str, auto_extract: bool):
    """Background task to process bulk movie uploads."""
    global bulk_jobs
    
    bulk_jobs[job_id]["status"] = "processing"
    
    for i, url in enumerate(urls):
        if not url.strip():
            continue
            
        url = url.strip()
        
        try:
            result = await process_single_movie(url, admin_id, auto_extract)
            
            bulk_jobs[job_id]["processed"] += 1
            bulk_jobs[job_id]["results"].append(result)
            
            if result["success"]:
                bulk_jobs[job_id]["successful"] += 1
            else:
                bulk_jobs[job_id]["failed"] += 1
                
        except Exception as e:
            bulk_jobs[job_id]["processed"] += 1
            bulk_jobs[job_id]["failed"] += 1
            bulk_jobs[job_id]["results"].append({
                "url": url,
                "success": False,
                "error": str(e)
            })
    
    bulk_jobs[job_id]["status"] = "completed"


@router.post("/bulk")
async def bulk_create_movies(
    data: BulkMovieCreate,
    background_tasks: BackgroundTasks,
    admin: dict = Depends(get_current_admin),
):
    """
    Bulk create movies from a list of URLs.
    Movies are processed asynchronously in the background.
    Returns a job ID to track progress.
    Admin only.
    """
    import uuid
    
    # Filter empty URLs
    urls = [url.strip() for url in data.urls if url.strip()]
    
    if not urls:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid URLs provided"
        )
    
    if len(urls) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 50 URLs allowed per batch"
        )
    
    # Create job
    job_id = str(uuid.uuid4())[:8]
    bulk_jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "total": len(urls),
        "processed": 0,
        "successful": 0,
        "failed": 0,
        "results": [],
        "created_at": datetime.utcnow().isoformat()
    }
    
    # Start background processing
    background_tasks.add_task(
        process_bulk_job, 
        job_id, 
        urls, 
        admin.get("id"),
        data.auto_extract
    )
    
    return {
        "message": f"Bulk job started for {len(urls)} movies",
        "job_id": job_id,
        "total": len(urls)
    }


@router.get("/bulk/{job_id}")
async def get_bulk_job_status(
    job_id: str,
    admin: dict = Depends(get_current_admin),
):
    """Get the status of a bulk upload job. Admin only."""
    if job_id not in bulk_jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return bulk_jobs[job_id]


@router.get("/bulk")
async def list_bulk_jobs(
    admin: dict = Depends(get_current_admin),
):
    """List all bulk jobs. Admin only."""
    return {
        "jobs": list(bulk_jobs.values())
    }
