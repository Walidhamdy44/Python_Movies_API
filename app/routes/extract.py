"""
Download link extraction endpoints.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from urllib.parse import urlparse

from app.models import ExtractResponse
from app.services import DownloadExtractor
from app.auth import verify_api_key
from app.config import settings

router = APIRouter(tags=["Extraction"])

# Thread pool for running blocking Selenium code
executor = ThreadPoolExecutor(max_workers=settings.MAX_WORKERS)


def is_wecima_url(url: str) -> bool:
    """Check if URL is from wecima.cx domain."""
    host = urlparse(url).netloc.lower()
    return 'wecima' in host


def is_egydead_url(url: str) -> bool:
    """Check if URL is from egydead domain."""
    host = urlparse(url).netloc.lower()
    return 'egydead' in host


@router.get("/extract/info", response_model=ExtractResponse)
async def extract_info_only(
    url: str = Query(..., description="Movie page URL to extract info from"),
    api_key: str = Depends(verify_api_key)
):
    """
    FAST: Extract movie info only (title, year, poster, quality).
    Automatically detects website (egydead, wecima) and uses appropriate handler.
    
    - **url**: The movie page URL (e.g., https://tv10.egydead.live/... or https://wecima.cx/watch/...)
    
    Returns movie info. For wecima, also includes decoded download links.
    Use this for the Add Movie form to quickly get movie metadata.
    
    **Authentication**: Requires X-API-Key header if AUTH_ENABLED=true
    """
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    if url.startswith('view-source:'):
        url = url.replace('view-source:', '')
    
    def run_extraction():
        extractor = DownloadExtractor()
        # Auto-detect website and use appropriate handler
        if is_wecima_url(url):
            return extractor.extract_wecima_info_only(url)
        else:
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
    include_watch_servers: Optional[bool] = Query(
        False,
        description="For wecima: also include streaming server URLs"
    ),
    get_direct_links: Optional[bool] = Query(
        True,
        description="Process host links to get direct CDN URLs (slower but gives actual download links)"
    ),
    api_key: str = Depends(verify_api_key)
):
    """
    FULL: Extract download links from a movie page.
    Automatically detects website (egydead, wecima) and uses appropriate handler.
    
    - **url**: The movie page URL (e.g., https://tv10.egydead.live/... or https://wecima.cx/watch/...)
    - **limit**: Optional limit on number of download links to process
    - **include_watch_servers**: (wecima only) Also include streaming server URLs
    - **get_direct_links**: Process each host link to get direct CDN URLs (default: true)
    
    For egydead: Slow (2-5 min) - processes each download link to get direct CDN links.
    For wecima: Fast with get_direct_links=false, Slow with get_direct_links=true.
    
    **Authentication**: Requires X-API-Key header if AUTH_ENABLED=true
    """
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    if url.startswith('view-source:'):
        url = url.replace('view-source:', '')
    
    def run_extraction():
        extractor = DownloadExtractor()
        # Auto-detect website and use appropriate handler
        if is_wecima_url(url):
            return extractor.extract_wecima(
                url, 
                include_watch_servers=include_watch_servers, 
                limit=limit,
                get_direct_links=get_direct_links
            )
        else:
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
    include_watch_servers: Optional[bool] = False,
    api_key: str = Depends(verify_api_key)
):
    """
    POST endpoint for extract (same as GET).
    
    **Authentication**: Requires X-API-Key header if AUTH_ENABLED=true
    """
    return await extract_links(url=url, limit=limit, include_watch_servers=include_watch_servers, api_key=api_key)


# ============== WECIMA-SPECIFIC ENDPOINTS ==============

@router.get("/extract/wecima", response_model=ExtractResponse)
async def extract_wecima_links(
    url: str = Query(..., description="Wecima movie page URL"),
    limit: Optional[int] = Query(None, description="Limit number of links", ge=1, le=50),
    include_watch_servers: bool = Query(False, description="Also include streaming server URLs"),
    get_direct_links: bool = Query(True, description="Process host links to get direct CDN URLs"),
    api_key: str = Depends(verify_api_key)
):
    """
    Extract download links from wecima.cx page.
    
    - **url**: The wecima movie page URL (e.g., https://wecima.cx/watch/...)
    - **limit**: Optional limit on number of download links
    - **include_watch_servers**: Also include streaming server URLs
    - **get_direct_links**: Process each host to get direct CDN URLs (default: true, slower)
    
    With get_direct_links=true: Processes each host (dhcplay, hgcloud, etc.) to get actual CDN links.
    With get_direct_links=false: Returns intermediate host URLs only (fast).
    
    **Authentication**: Requires X-API-Key header if AUTH_ENABLED=true
    """
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    if not is_wecima_url(url):
        raise HTTPException(
            status_code=400, 
            detail="URL must be from wecima.cx domain. Use /extract for other sites."
        )
    
    def run_extraction():
        extractor = DownloadExtractor()
        return extractor.extract_wecima(
            url, 
            include_watch_servers=include_watch_servers, 
            limit=limit,
            get_direct_links=get_direct_links
        )
    
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, run_extraction)
    
    if not result.success:
        raise HTTPException(status_code=500, detail=result.message)
    
    return result


@router.get("/extract/wecima/info", response_model=ExtractResponse)
async def extract_wecima_info_only(
    url: str = Query(..., description="Wecima movie page URL"),
    api_key: str = Depends(verify_api_key)
):
    """
    FAST: Extract movie info from wecima.cx (includes decoded download links).
    
    - **url**: The wecima movie page URL (e.g., https://wecima.cx/watch/...)
    
    Returns movie info with decoded download links.
    Since wecima links are base64-encoded in the HTML, we can decode them without 
    additional page navigation.
    
    **Authentication**: Requires X-API-Key header if AUTH_ENABLED=true
    """
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    if not is_wecima_url(url):
        raise HTTPException(
            status_code=400, 
            detail="URL must be from wecima.cx domain. Use /extract/info for other sites."
        )
    
    def run_extraction():
        extractor = DownloadExtractor()
        return extractor.extract_wecima_info_only(url)
    
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, run_extraction)
    
    if not result.success:
        raise HTTPException(status_code=500, detail=result.message)
    
    return result
