"""
Download Link Extractor - FastAPI
Extracts movie info and download links from Arabic streaming websites.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional, List
import re
import time
import base64
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from contextlib import asynccontextmanager

# Selenium imports
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

try:
    import undetected_chromedriver as uc
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False


# ============== Response Models ==============

class DownloadLink(BaseModel):
    host: str
    quality: Optional[str] = None
    direct_link: str
    is_direct: bool  # True if it's a direct CDN link, False if page only


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
    selenium: bool
    stealth_mode: bool


# ============== Extractor Class ==============

class DownloadExtractor:
    def __init__(self, stealth: bool = True):
        self.stealth = stealth
        self.driver = None
    
    def _init_browser(self):
        """Initialize browser with anti-detection."""
        if self.driver:
            return
        
        if self.stealth and UC_AVAILABLE:
            try:
                options = uc.ChromeOptions()
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--window-size=1920,1080')
                self.driver = uc.Chrome(options=options, headless=True)
                return
            except Exception:
                pass
        
        # Fallback to regular selenium
        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        # For Docker/Linux - use system Chrome
        import shutil
        chrome_path = shutil.which('google-chrome') or shutil.which('chromium-browser')
        if chrome_path:
            options.binary_location = chrome_path
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        })
    
    def _close_browser(self):
        """Close the browser."""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
    
    def _extract_movie_info(self, html: str, url: str) -> MovieInfo:
        """Extract movie information from page."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Title - try multiple methods
        title = ""
        
        # Method 1: Extract from URL (most reliable for this site)
        url_path = urlparse(url).path.strip('/')
        if url_path:
            # Convert URL slug to title: "avatar-3-fire-and-ash-2025-1080p-bluray" -> "Avatar 3 Fire And Ash"
            title_from_url = url_path.replace('-', ' ')
            # Remove quality indicators
            title_from_url = re.sub(r'\b(1080p|720p|480p|bluray|webrip|hdtv|cam)\b', '', title_from_url, flags=re.I)
            title_from_url = ' '.join(title_from_url.split()).strip().title()
            title = title_from_url
        
        # Method 2: Try meta tags
        if not title:
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                title = og_title['content']
        
        # Method 3: Try page title
        if not title:
            page_title = soup.find('title')
            if page_title:
                title = page_title.get_text(strip=True).split('|')[0].strip()
        
        # Year - extract from title or URL
        year = None
        year_match = re.search(r'(19|20)\d{2}', url + title)
        if year_match:
            year = year_match.group(0)
        
        # Main image - try more selectors
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
        
        # Quality badge
        quality = None
        quality_elem = soup.select_one('.quality, .qlty, span.quality, .label-quality')
        if quality_elem:
            quality = quality_elem.get_text(strip=True)
        else:
            # Extract from URL
            q_match = re.search(r'(1080p|720p|480p|4k)', url, re.I)
            if q_match:
                quality = q_match.group(1).upper()
        
        # Rating
        rating = None
        rating_elem = soup.select_one('.rating .num, .imdb-rating, [class*="rating"] span')
        if rating_elem:
            rating_text = rating_elem.get_text(strip=True)
            # Extract number
            r_match = re.search(r'[\d.]+', rating_text)
            if r_match:
                rating = r_match.group(0)
        
        # Duration
        duration = None
        duration_elem = soup.select_one('.runtime, .duration, [class*="duration"], .time')
        if duration_elem:
            duration = duration_elem.get_text(strip=True)
        
        # Genres - filter navigation items
        genres = []
        genre_selectors = ['.genres a', '.genre a', 'a[href*="/genre/"]', '.cats a']
        for selector in genre_selectors:
            genre_links = soup.select(selector)
            for g in genre_links[:5]:
                text = g.get_text(strip=True)
                # Filter out navigation items
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
            genres=list(set(genres))[:5]  # Remove duplicates
        )
    
    def _find_hidden_links(self, html: str) -> list:
        """Find hidden/obfuscated download links."""
        links = []
        
        # Base64 encoded URLs
        b64_pattern = r'[A-Za-z0-9+/]{50,}={0,2}'
        for match in re.findall(b64_pattern, html):
            try:
                decoded = base64.b64decode(match).decode('utf-8', errors='ignore')
                if 'http' in decoded:
                    url_match = re.search(r'https?://[^\s"\'<>]+', decoded)
                    if url_match:
                        links.append(url_match.group(0))
            except:
                pass
        
        # URLs in JavaScript
        js_pattern = r'["\']?(https?://[^"\'<>\s]+(?:\.mp4|\.mkv|premilkyway|cdn)[^"\'<>\s]*)["\']?'
        links.extend(re.findall(js_pattern, html, re.IGNORECASE))
        
        # Data attributes
        soup = BeautifulSoup(html, 'html.parser')
        for attr in ['data-url', 'data-href', 'data-link']:
            for elem in soup.find_all(attrs={attr: True}):
                links.append(elem[attr])
        
        return list(set(links))
    
    def _click_watch_button(self) -> bool:
        """Click the المشاهده والتحميل button."""
        try:
            # Try multiple selectors for the watch button
            selectors = [
                "//button[@type='submit']//span[contains(text(), 'المشاهده')]/..",
                "//button[contains(., 'المشاهده')]",
                "//button[contains(., 'التحميل')]",
                "//a[contains(., 'المشاهده')]",
                "button[type='submit']",
                ".watch-button",
                "#watch-btn"
            ]
            
            for selector in selectors:
                try:
                    if selector.startswith('//'):
                        elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for elem in elements:
                        if elem.is_displayed():
                            self.driver.execute_script("arguments[0].click();", elem)
                            time.sleep(3)
                            return True
                except:
                    continue
            
            return False
        except Exception:
            return False
    
    def _find_download_links(self, html: str) -> list:
        """Find all حمل الان download links."""
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        
        for a_tag in soup.find_all('a', href=True):
            text = a_tag.get_text(strip=True)
            inner = str(a_tag)
            
            if 'حمل الان' in text or 'حمل الان' in inner:
                href = a_tag['href']
                if href and not href.startswith('#'):
                    links.append(href)
        
        return links
    
    def _find_quality_link(self, url: str) -> str:
        """Navigate to quality/download page."""
        try:
            self.driver.get(url)
            time.sleep(2)
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            # Look for downloadv-item or quality links
            selectors = [
                {'class_': 'downloadv-item'},
                {'class_': 'download-item'},
                {'class_': re.compile(r'download')},
            ]
            
            for selector in selectors:
                items = soup.find_all('a', **selector)
                for item in items:
                    href = item.get('href')
                    if href and not href.startswith('#') and not href.startswith('javascript'):
                        return urljoin(url, href)
            
            # Quality text links
            for a_tag in soup.find_all('a', href=True):
                text = a_tag.get_text(strip=True)
                if 'quality' in text.lower() or 'download' in text.lower():
                    href = a_tag['href']
                    if href and not href.startswith('#'):
                        return urljoin(url, href)
            
            return None
        except:
            return None
    
    def _extract_final_link(self, url: str) -> tuple:
        """Extract final download link. Returns (link, is_direct)."""
        try:
            self.driver.get(url)
            time.sleep(4)
            
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            current_url = self.driver.current_url
            
            # First, aggressively search HTML for direct CDN links
            cdn_patterns = [
                r'https?://[a-z0-9]+\.premilkyway\.com[^"\'<>\s]+\.mp4[^"\'<>\s]*',
                r'https?://[a-z0-9]+\.streamruby\.net[^"\'<>\s]+\.mp4[^"\'<>\s]*',
                r'https?://[^"\'<>\s]*cdn[^"\'<>\s]*\.mp4[^"\'<>\s]*',
            ]
            
            for pattern in cdn_patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                if matches:
                    return (matches[0], True)
            
            # Check all links for direct download URLs
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                classes = a_tag.get('class', [])
                class_str = ' '.join(classes) if isinstance(classes, list) else ''
                
                # Direct file links in href
                if any(x in href.lower() for x in ['.mp4', '.mkv', 'premilkyway', 'streamruby.net']):
                    if not href.startswith('#') and not href.startswith('javascript'):
                        return (urljoin(current_url, href), True)
                
                # Download buttons with direct href
                if any(x in class_str for x in ['submit-btn', 'download-btn', 'btn-gr']):
                    if href and not href.startswith('#') and not href.startswith('javascript'):
                        if 'registration' not in href.lower() and 'login' not in href.lower():
                            # Check if it's a CDN link
                            if any(x in href.lower() for x in ['.mp4', 'premilkyway', 'cdn']):
                                return (urljoin(current_url, href), True)
            
            # Try clicking download button to see if link appears
            try:
                buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                    'a.submit-btn, a.btn-gr, a.download-btn, a.btn-primary.download-btn')
                
                for btn in buttons:
                    if btn.is_displayed():
                        href = btn.get_attribute('href')
                        if href and any(x in href.lower() for x in ['.mp4', 'premilkyway', 'streamruby.net', 'cdn']):
                            return (href, True)
                        
                        # Try clicking
                        try:
                            self.driver.execute_script("arguments[0].click();", btn)
                            time.sleep(4)
                            
                            new_html = self.driver.page_source
                            
                            # Search for CDN links again
                            for pattern in cdn_patterns:
                                matches = re.findall(pattern, new_html, re.IGNORECASE)
                                if matches:
                                    return (matches[0], True)
                            
                            # Check current URL
                            new_url = self.driver.current_url
                            if any(x in new_url.lower() for x in ['.mp4', 'premilkyway']):
                                return (new_url, True)
                                
                        except:
                            pass
                        break
            except:
                pass
            
            # Return the final page URL we reached
            return (current_url, False)
            
        except Exception:
            return (url, False)
    
    def extract(self, url: str, limit: int = None) -> ExtractResponse:
        """Main extraction method."""
        if not SELENIUM_AVAILABLE:
            return ExtractResponse(
                success=False,
                message="Selenium not installed",
                url=url
            )
        
        try:
            self._init_browser()
            
            # Load the movie page
            self.driver.get(url)
            time.sleep(3)
            
            # Get initial page HTML for movie info
            html = self.driver.page_source
            
            # Extract movie info
            movie_info = self._extract_movie_info(html, url)
            
            # Click watch button
            self._click_watch_button()
            time.sleep(2)
            
            # Get page after clicking (or same page with download links visible)
            html = self.driver.page_source
            
            # Find all download links
            download_urls = self._find_download_links(html)
            
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
                    # Extract host name
                    host = urlparse(dl_url).netloc or "unknown"
                    
                    # Navigate through quality pages
                    current_url = dl_url
                    for _ in range(5):  # Max 5 hops
                        next_url = self._find_quality_link(current_url)
                        if not next_url or next_url == current_url:
                            break
                        current_url = next_url
                    
                    # Extract final link
                    final_link, is_direct = self._extract_final_link(current_url)
                    
                    download_links.append(DownloadLink(
                        host=host,
                        direct_link=final_link,
                        is_direct=is_direct
                    ))
                    
                except Exception as e:
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
            return ExtractResponse(
                success=False,
                message=f"Error: {str(e)}",
                url=url
            )
        
        finally:
            self._close_browser()


# ============== FastAPI App ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    print("🚀 Download Extractor API starting...")
    print(f"   Selenium: {'✓' if SELENIUM_AVAILABLE else '✗'}")
    print(f"   Stealth Mode: {'✓' if UC_AVAILABLE else '✗'}")
    yield
    print("👋 Shutting down...")


app = FastAPI(
    title="Download Link Extractor API",
    description="Extract download links from Arabic streaming websites",
    version="1.0.0",
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
        selenium=SELENIUM_AVAILABLE,
        stealth_mode=UC_AVAILABLE
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
    
    Returns movie info and all available download links.
    """
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    # Clean URL
    if url.startswith('view-source:'):
        url = url.replace('view-source:', '')
    
    extractor = DownloadExtractor(stealth=UC_AVAILABLE)
    result = extractor.extract(url, limit=limit)
    
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
