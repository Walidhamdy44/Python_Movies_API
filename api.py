"""
Download Link Extractor - FastAPI
Extracts movie info and download links from Arabic streaming websites.
Uses SeleniumBase UC mode to bypass Cloudflare protection.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import re
import logging
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from contextlib import asynccontextmanager
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Thread pool for running blocking Selenium code
executor = ThreadPoolExecutor(max_workers=3)

# SeleniumBase import
try:
    from seleniumbase import SB
    SELENIUMBASE_AVAILABLE = True
except ImportError:
    SELENIUMBASE_AVAILABLE = False


# ============== Response Models ==============

class DownloadLink(BaseModel):
    host: str
    quality: Optional[str] = None
    direct_link: str
    is_direct: bool


class MovieInfo(BaseModel):
    title: str
    year: Optional[str] = None
    image: Optional[str] = None
    quality: Optional[str] = None
    rating: Optional[str] = None
    duration: Optional[str] = None
    genres: List[str] = []


class ExtractResponse(BaseModel):
    success: bool
    message: str
    url: str
    movie: Optional[MovieInfo] = None
    download_links: List[DownloadLink] = []
    total_links: int = 0
    direct_links_count: int = 0


class HealthResponse(BaseModel):
    status: str
    seleniumbase: bool


# ============== Extractor Class ==============

class DownloadExtractor:
    """Extracts download links using SeleniumBase UC mode for Cloudflare bypass."""
    
    def __init__(self):
        pass
    
    def _extract_movie_info(self, html: str, url: str) -> MovieInfo:
        """Extract movie information from page."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Title from URL
        title = ""
        url_path = urlparse(url).path.strip('/')
        if url_path:
            title_from_url = url_path.replace('-', ' ')
            title_from_url = re.sub(r'\b(1080p|720p|480p|bluray|webrip|hdtv|cam)\b', '', title_from_url, flags=re.I)
            title = ' '.join(title_from_url.split()).strip().title()
        
        if not title:
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                title = og_title['content']
        
        if not title:
            page_title = soup.find('title')
            if page_title:
                title = page_title.get_text(strip=True).split('|')[0].strip()
        
        # Year
        year = None
        year_match = re.search(r'(19|20)\d{2}', url + title)
        if year_match:
            year = year_match.group(0)
        
        # Image
        image = None
        img_selectors = [
            '.single-thumb img', '.movie-thumb img', '.thumb img',
            'img.poster', '.poster img', '.movie-poster img',
            'img[itemprop="image"]', 'article img', '.featured-img img'
        ]
        for selector in img_selectors:
            img = soup.select_one(selector)
            if img:
                src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                if src and 'logo' not in src.lower():
                    image = urljoin(url, src)
                    break
        
        # Quality
        quality = None
        quality_elem = soup.select_one('.quality, .qlty, span.quality, .label-quality')
        if quality_elem:
            quality = quality_elem.get_text(strip=True)
        else:
            q_match = re.search(r'(1080p|720p|480p|4k)', url, re.I)
            if q_match:
                quality = q_match.group(1).upper()
        
        # Rating
        rating = None
        rating_elem = soup.select_one('.rating .num, .imdb-rating, [class*="rating"] span')
        if rating_elem:
            rating_text = rating_elem.get_text(strip=True)
            r_match = re.search(r'[\d.]+', rating_text)
            if r_match:
                rating = r_match.group(0)
        
        # Duration
        duration = None
        duration_elem = soup.select_one('.runtime, .duration, [class*="duration"], .time')
        if duration_elem:
            duration = duration_elem.get_text(strip=True)
        
        # Genres
        genres = []
        genre_selectors = ['.genres a', '.genre a', 'a[href*="/genre/"]', '.cats a']
        for selector in genre_selectors:
            genre_links = soup.select(selector)
            for g in genre_links[:5]:
                text = g.get_text(strip=True)
                if text and len(text) < 30 and 'افلام' not in text.lower():
                    genres.append(text)
            if genres:
                break
        
        return MovieInfo(
            title=title or "Unknown",
            year=year,
            image=image,
            quality=quality,
            rating=rating,
            duration=duration,
            genres=list(set(genres))[:5]
        )
    
    def _find_download_links(self, html: str) -> list:
        """Find all حمل الان download links with ser-link class."""
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        
        # Method 1: Find links with class 'ser-link' containing حمل الان
        for a_tag in soup.find_all('a', class_='ser-link'):
            href = a_tag.get('href')
            if href and not href.startswith('#') and not href.startswith('javascript'):
                links.append(href)
        
        # Method 2: Find any link with حمل الان text
        if not links:
            for a_tag in soup.find_all('a', href=True):
                text = a_tag.get_text(strip=True)
                if 'حمل الان' in text:
                    href = a_tag['href']
                    if href and not href.startswith('#') and not href.startswith('javascript'):
                        links.append(href)
        
        return links
    
    def _extract_megaup_link(self, sb, url: str) -> tuple:
        """Extract direct download link from megaup using SeleniumBase UC mode."""
        try:
            sb.open(url)
            sb.sleep(10)
            
            html = sb.get_page_source()
            title = sb.get_title()
            
            if 'Just a moment' in html or 'Just a moment' in title:
                sb.sleep(15)
                html = sb.get_page_source()
            
            # Look for megadl download link (the final CDN link)
            matches = re.findall(r'https?://megadl[^"\'<>\s]+', html)
            if matches:
                return (matches[0], True)
            
            # Try finding via element
            try:
                link = sb.find_element('a[href*="megadl"]')
                href = link.get_attribute('href')
                if href:
                    return (href, True)
            except:
                pass
            
            # Look for download.megaup.net redirect link
            matches = re.findall(r'https?://download\.megaup\.net[^"\'<>\s]+', html)
            if matches:
                sb.open(matches[0])
                sb.sleep(10)
                
                html = sb.get_page_source()
                
                if 'Just a moment' in html:
                    sb.sleep(15)
                    html = sb.get_page_source()
                
                megadl_matches = re.findall(r'https?://megadl[^"\'<>\s]+', html)
                if megadl_matches:
                    return (megadl_matches[0], True)
            
            return (url, False)
        except Exception as e:
            logger.error(f"megaup extraction failed: {e}")
            return (url, False)
    
    def _extract_streamruby_link(self, sb, url: str) -> tuple:
        """Extract direct download link from streamruby."""
        try:
            sb.open(url)
            sb.sleep(10)
            
            html = sb.get_page_source()
            
            if 'Just a moment' in html:
                sb.sleep(15)
                html = sb.get_page_source()
            
            # Look for streamruby CDN link directly
            matches = re.findall(r'https?://[a-z0-9]+\.streamruby\.net[^"\'<>\s]+\.mp4[^"\'<>\s]*', html, re.I)
            if matches:
                return (matches[0], True)
            
            # Try clicking the download button
            try:
                btns = sb.find_elements('a.btn-primary, a.download-btn, a[class*="download"]')
                for btn in btns:
                    text = btn.text.lower()
                    if 'download' in text:
                        href = btn.get_attribute('href')
                        if href and 'streamruby.net' in href:
                            return (href, True)
                        btn.click()
                        sb.sleep(6)
                        break
                
                html = sb.get_page_source()
                matches = re.findall(r'https?://[a-z0-9]+\.streamruby\.net[^"\'<>\s]+\.mp4[^"\'<>\s]*', html, re.I)
                if matches:
                    return (matches[0], True)
                
                current_url = sb.get_current_url()
                if 'streamruby.net' in current_url and '.mp4' in current_url:
                    return (current_url, True)
                    
            except:
                pass
            
            return (url, False)
        except Exception as e:
            logger.error(f"streamruby extraction failed: {e}")
            return (url, False)
    
    def _extract_hgcloud_link(self, sb, url: str) -> tuple:
        """Extract direct download link from hgcloud/premilkyway."""
        try:
            sb.open(url)
            sb.sleep(10)
            
            html = sb.get_page_source()
            
            if 'Just a moment' in html:
                sb.sleep(15)
                html = sb.get_page_source()
            
            # Look for premilkyway CDN link
            matches = re.findall(r'https?://[a-z0-9]+\.premilkyway\.com[^"\'<>\s]+\.mp4[^"\'<>\s]*', html, re.I)
            if matches:
                return (matches[0], True)
            
            # Try clicking download button
            try:
                btns = sb.find_elements('a.submit-btn, a.btn-gr, a.download-btn, a[class*="download"]')
                for btn in btns:
                    href = btn.get_attribute('href')
                    if href and 'premilkyway' in href:
                        return (href, True)
                    
                    text = btn.text.lower()
                    if 'download' in text:
                        btn.click()
                        sb.sleep(6)
                        break
                
                html = sb.get_page_source()
                matches = re.findall(r'https?://[a-z0-9]+\.premilkyway\.com[^"\'<>\s]+\.mp4[^"\'<>\s]*', html, re.I)
                if matches:
                    return (matches[0], True)
                    
            except:
                pass
            
            return (url, False)
        except Exception as e:
            logger.error(f"hgcloud extraction failed: {e}")
            return (url, False)
    
    def _extract_final_link_with_sb(self, sb, url: str) -> tuple:
        """Extract final download link using SeleniumBase. Returns (link, is_direct)."""
        host = urlparse(url).netloc.lower()
        
        # Route to specific handler based on host
        if 'megaup' in host:
            return self._extract_megaup_link(sb, url)
        elif 'streamruby' in host:
            return self._extract_streamruby_link(sb, url)
        elif 'hgcloud' in host or 'premilkyway' in host:
            return self._extract_hgcloud_link(sb, url)
        else:
            # Generic extraction
            try:
                sb.open(url)
                sb.sleep(6)
                
                html = sb.get_page_source()
                
                if 'Just a moment' in html:
                    sb.sleep(10)
                    html = sb.get_page_source()
                
                # Look for common CDN patterns
                cdn_patterns = [
                    r'https?://[a-z0-9]+\.premilkyway\.com[^"\'<>\s]+\.mp4[^"\'<>\s]*',
                    r'https?://[a-z0-9]+\.streamruby\.net[^"\'<>\s]+\.mp4[^"\'<>\s]*',
                    r'https?://megadl[^"\'<>\s]+',
                    r'https?://[^"\'<>\s]*cdn[^"\'<>\s]*\.mp4[^"\'<>\s]*',
                ]
                
                for pattern in cdn_patterns:
                    matches = re.findall(pattern, html, re.I)
                    if matches:
                        return (matches[0], True)
                
                return (url, False)
            except Exception as e:
                logger.error(f"generic extraction failed: {e}")
                return (url, False)
    
    def extract(self, url: str, limit: int = None) -> ExtractResponse:
        """Main extraction method using SeleniumBase UC mode."""
        if not SELENIUMBASE_AVAILABLE:
            return ExtractResponse(
                success=False,
                message="SeleniumBase not installed",
                url=url
            )
        
        try:
            with SB(uc=True, headless=True) as sb:
                logger.info(f"Loading: {url}")
                
                # Load the movie page
                sb.open(url)
                sb.sleep(4)
                
                # Get page HTML for movie info
                html = sb.get_page_source()
                movie_info = self._extract_movie_info(html, url)
                logger.info(f"Movie: {movie_info.title}")
                
                # Click the watch/download button (المشاهده والتحميل)
                try:
                    buttons = sb.find_elements("button")
                    for btn in buttons:
                        text = btn.text
                        if 'المشاهده' in text or 'التحميل' in text:
                            btn.click()
                            sb.sleep(4)
                            break
                except Exception as e:
                    logger.warning(f"Button click failed: {e}")
                
                # Get page HTML after clicking
                html = sb.get_page_source()
                
                # Find all download links
                download_urls = self._find_download_links(html)
                logger.info(f"Found {len(download_urls)} download links")
                
                if not download_urls:
                    return ExtractResponse(
                        success=False,
                        message="No download links found on page",
                        url=url,
                        movie=movie_info
                    )
                
                if limit:
                    download_urls = download_urls[:limit]
                
                # Process each download link
                download_links = []
                
                for dl_url in download_urls:
                    try:
                        host = urlparse(dl_url).netloc or "unknown"
                        logger.info(f"Processing: {host}")
                        
                        # Extract final link with Cloudflare bypass
                        final_link, is_direct = self._extract_final_link_with_sb(sb, dl_url)
                        
                        download_links.append(DownloadLink(
                            host=host,
                            direct_link=final_link,
                            is_direct=is_direct
                        ))
                        
                    except Exception as e:
                        logger.error(f"Error processing {dl_url}: {e}")
                        download_links.append(DownloadLink(
                            host=urlparse(dl_url).netloc or "unknown",
                            direct_link=dl_url,
                            is_direct=False
                        ))
                
                direct_count = sum(1 for d in download_links if d.is_direct)
                
                return ExtractResponse(
                    success=True,
                    message=f"Extracted {len(download_links)} links ({direct_count} direct)",
                    url=url,
                    movie=movie_info,
                    download_links=download_links,
                    total_links=len(download_links),
                    direct_links_count=direct_count
                )
                
        except Exception as e:
            logger.exception(f"Extraction failed: {e}")
            return ExtractResponse(
                success=False,
                message=f"Error: {str(e)}",
                url=url
            )


# ============== FastAPI App ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("🚀 Download Extractor API starting...")
    logger.info(f"   SeleniumBase: {'✓' if SELENIUMBASE_AVAILABLE else '✗'}")
    yield
    logger.info("👋 Shutting down...")


app = FastAPI(
    title="Download Link Extractor API",
    description="Extract download links from Arabic streaming websites (bypasses Cloudflare)",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        seleniumbase=SELENIUMBASE_AVAILABLE
    )


@app.get("/extract", response_model=ExtractResponse)
async def extract_links(
    url: str = Query(..., description="Movie page URL to extract from"),
    limit: Optional[int] = Query(None, description="Limit number of links to process", ge=1, le=50)
):
    """
    Extract download links from a movie page.
    
    - **url**: The movie page URL (e.g., https://tv10.egydead.live/movie-name/)
    - **limit**: Optional limit on number of download links to process
    
    Returns movie info and all available download links with Cloudflare bypass.
    """
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    if url.startswith('view-source:'):
        url = url.replace('view-source:', '')
    
    # Run blocking Selenium code in thread pool
    def run_extraction():
        extractor = DownloadExtractor()
        return extractor.extract(url, limit=limit)
    
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, run_extraction)
    
    if not result.success:
        raise HTTPException(status_code=500, detail=result.message)
    
    return result


@app.post("/extract", response_model=ExtractResponse)
async def extract_links_post(
    url: str,
    limit: Optional[int] = None
):
    """POST endpoint for extract (same as GET)."""
    return await extract_links(url=url, limit=limit)


# ============== Run Server ==============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
