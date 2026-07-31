"""
Download link extraction endpoints.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional

from app.models import ExtractResponse
from app.services import DownloadExtractor
from app.auth import verify_api_key
from app.config import settings

router = APIRouter(tags=["Extraction"])

# Thread pool for running blocking Selenium code
executor = ThreadPoolExecutor(max_workers=settings.MAX_WORKERS)


@router.get("/extract/info", response_model=ExtractResponse)
async def extract_info_only(
    url: str = Query(..., description="Movie page URL to extract info from"),
    api_key: str = Depends(verify_api_key)
):
    """
    FAST: Extract movie info only (title, year, poster, quality).
    Does NOT process download links - much faster (~30-60 sec vs 3-5 min).
    
    - **url**: The movie page URL (e.g., https://tv10.egydead.live/movie-name/)
    
    Returns movie info without processing download links.
    Use this for the Add Movie form to quickly get movie metadata.
    
    **Authentication**: Requires X-API-Key header if AUTH_ENABLED=true
    """
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    if url.startswith('view-source:'):
        url = url.replace('view-source:', '')
    
    def run_extraction():
        extractor = DownloadExtractor()
        return extractor.extract_info_only(url)
    
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, run_extraction)
    
    if not result.success:
        raise HTTPException(status_code=500, detail=result.message)
    
    return result


@router.get("/extract", response_model=ExtractResponse)
async def extract_links(
    url: str = Query(..., description="Movie page URL to extract from"),
    limit: Optional[int] = Query(
        None, 
        description="Limit number of links to process", 
        ge=1, 
        le=settings.MAX_LIMIT
    ),
    api_key: str = Depends(verify_api_key)
):
    """
    FULL: Extract download links from a movie page (SLOW - 2-5 min).
    
    - **url**: The movie page URL (e.g., https://tv10.egydead.live/movie-name/)
    - **limit**: Optional limit on number of download links to process
    
    Returns movie info and all available download links with Cloudflare bypass.
    Note: This is slow because it processes each download link.
    
    **Authentication**: Requires X-API-Key header if AUTH_ENABLED=true
    """
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    if url.startswith('view-source:'):
        url = url.replace('view-source:', '')
    
    def run_extraction():
        extractor = DownloadExtractor()
        return extractor.extract(url, limit=limit)
    
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, run_extraction)
    
    if not result.success:
        raise HTTPException(status_code=500, detail=result.message)
    
    return result


@router.post("/extract", response_model=ExtractResponse)
async def extract_links_post(
    url: str,
    limit: Optional[int] = None,
    api_key: str = Depends(verify_api_key)
):
    """
    POST endpoint for extract (same as GET).
    
    **Authentication**: Requires X-API-Key header if AUTH_ENABLED=true
    """
    return await extract_links(url=url, limit=limit, api_key=api_key)
