"""
Download link extraction service using SeleniumBase.
Optimized for dhcplay.com / hgcloud.to / cdn-centaurus.com only.
"""

import re
import base64
import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse, unquote
from bs4 import BeautifulSoup

from app.config import settings
from app.models import DownloadLink, MovieInfo, ExtractResponse

logger = logging.getLogger(__name__)

# SeleniumBase import
try:
    from seleniumbase import SB
    SELENIUMBASE_AVAILABLE = True
except ImportError:
    SELENIUMBASE_AVAILABLE = False


def decode_wecima_url(encoded: str) -> str:
    """
    Decode wecima's custom base64 encoded URLs.
    """
    try:
        if not encoded:
            return None
        cleaned = encoded.replace('+', '')
        if cleaned.startswith('H'):
            fixed = 'aHR0cH' + cleaned[1:]
        else:
            fixed = cleaned
        decoded = base64.b64decode(fixed).decode('utf-8')
        return decoded
    except Exception as e:
        logger.error(f"Failed to decode wecima URL '{encoded}': {e}")
        return None


class DownloadExtractor:
    """
    Extracts download links from wecima.cx.
    Supports multiple hosts including dhcplay, hgcloud, doodstream, mixdrop, etc.
    """
    
    # Hosts that we support for direct link extraction
    SUPPORTED_HOSTS = ['dhcplay', 'hgcloud', 'audinifer', 'hanerix', 'premilkyway']
    
    # All hosts we accept (even without direct extraction)
    ALL_ACCEPTED_HOSTS = ['dhcplay', 'hgcloud', 'audinifer', 'hanerix', 'premilkyway', 
                          'doodstream', 'mixdrop', 'lulustream', 'abstream', 'streamwish',
                          'vidhide', 'filemoon', 'streamtape']
    
    def __init__(self):
        pass
    
    def _is_supported_host(self, url: str) -> bool:
        """Check if URL is from a supported host for direct extraction."""
        host = urlparse(url).netloc.lower()
        return any(h in host for h in self.SUPPORTED_HOSTS)
    
    def _is_accepted_host(self, url: str) -> bool:
        """Check if URL is from any accepted host."""
        host = urlparse(url).netloc.lower()
        return any(h in host for h in self.ALL_ACCEPTED_HOSTS)

    def _extract_hgcloud_link(self, sb, url: str) -> tuple:
        """
        Extract direct download link from dhcplay/hgcloud.
        Returns (direct_link, is_direct) tuple.
        """
        try:
            logger.info(f"[EXTRACT] Opening {url}")
            sb.open(url)
            sb.sleep(settings.CLOUDFLARE_WAIT)
            
            html = sb.get_page_source()
            
            if 'Just a moment' in html:
                logger.info("[EXTRACT] Waiting for Cloudflare...")
                sb.sleep(settings.CLOUDFLARE_EXTRA_WAIT)
                html = sb.get_page_source()
            
            # CDN patterns to look for
            cdn_pattern = r'https?://[a-zA-Z0-9]+\.cdn-centaurus\.com[^"\'<>\s]+'
            premilky_pattern = r'https?://[a-z0-9]+\.premilkyway\.com[^"\'<>\s]+\.mp4[^"\'<>\s]*'
            
            # Check if CDN link already on page
            matches = re.findall(cdn_pattern, html, re.I)
            if matches:
                return (matches[0].replace('&amp;', '&'), True)
            
            matches = re.findall(premilky_pattern, html, re.I)
            if matches:
                return (matches[0].replace('&amp;', '&'), True)
            
            # STEP 1: Click Download button
            logger.info("[EXTRACT] Step 1 - Looking for download button")
            try:
                download_btn = sb.find_element('a.videoplayer-download, a.btn-gr[href*="/f/"]')
                download_btn.click()
                sb.sleep(5)
            except:
                try:
                    f_links = sb.find_elements('a[href*="/f/"]')
                    for link in f_links:
                        href = link.get_attribute('href')
                        if href and '/f/' in href:
                            link.click()
                            sb.sleep(5)
                            break
                except:
                    pass
            
            html = sb.get_page_source()
            matches = re.findall(cdn_pattern, html, re.I)
            if matches:
                return (matches[0].replace('&amp;', '&'), True)

            # STEP 2: Choose quality (_o, _n, _l)
            logger.info("[EXTRACT] Step 2 - Looking for quality selection")
            try:
                quality_links = sb.find_elements('a.downloadv-item, a[href*="_o"], a[href*="_n"], a[href*="_l"]')
                for suffix in ['_o', '_n', '_l']:
                    for link in quality_links:
                        href = link.get_attribute('href')
                        if href and suffix in href:
                            link.click()
                            sb.sleep(5)
                            break
                    else:
                        continue
                    break
            except:
                pass
            
            html = sb.get_page_source()
            matches = re.findall(cdn_pattern, html, re.I)
            if matches:
                return (matches[0].replace('&amp;', '&'), True)
            
            # STEP 3: Click reCAPTCHA submit
            logger.info("[EXTRACT] Step 3 - Looking for submit button")
            try:
                submit_btn = sb.find_element('button.g-recaptcha, button.submit-btn, .g-recaptcha.btn')
                submit_btn.click()
                sb.sleep(8)
            except:
                try:
                    sb.execute_script("var btn = document.querySelector('button.g-recaptcha'); if(btn) btn.click();")
                    sb.sleep(8)
                except:
                    pass
            
            html = sb.get_page_source()
            matches = re.findall(cdn_pattern, html, re.I)
            if matches:
                return (matches[0].replace('&amp;', '&'), True)
            
            # STEP 4: Wait for countdown
            logger.info("[EXTRACT] Step 4 - Waiting for countdown")
            for _ in range(10):
                sb.sleep(1)
                html = sb.get_page_source()
                
                matches = re.findall(cdn_pattern, html, re.I)
                if matches:
                    return (matches[0].replace('&amp;', '&'), True)
                
                matches = re.findall(premilky_pattern, html, re.I)
                if matches:
                    return (matches[0].replace('&amp;', '&'), True)
                
                try:
                    final_btn = sb.find_element('a.submit-btn[href*="cdn-centaurus"], a.btn-gr[href*="cdn-centaurus"]')
                    href = final_btn.get_attribute('href')
                    if href:
                        return (href.replace('&amp;', '&'), True)
                except:
                    pass
            
            logger.warning("[EXTRACT] Could not find direct download link")
            return (url, False)
            
        except Exception as e:
            logger.error(f"[EXTRACT] Extraction failed: {e}")
            return (url, False)

    def _extract_wecima_movie_info(self, html: str, url: str) -> MovieInfo:
        """Extract movie information from wecima.cx page HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        
        title = ""
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title = og_title['content'].strip()
        
        if not title:
            page_title = soup.find('title')
            if page_title:
                title = page_title.get_text(strip=True).split('|')[0].split('-')[0].strip()
        
        if not title:
            h1 = soup.select_one('h1')
            if h1:
                title = h1.get_text(strip=True)
        
        if title:
            title = re.sub(r'^(مشاهده|مشاهدة)\s*(فيلم)?\s*', '', title, flags=re.I).strip()
            title = re.sub(r'\s*مترجم\s*$', '', title, flags=re.I).strip()
            title = re.sub(r'\s*-?\s*Wecima.*$', '', title, flags=re.I).strip()
        
        year = None
        year_match = re.search(r'(19|20)\d{2}', url + (title or ''))
        if year_match:
            year = year_match.group(0)
        
        image = None
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            image = og_image['content']
        
        if not image:
            for selector in ['.Poster img', '.poster img', 'img.poster']:
                img = soup.select_one(selector)
                if img:
                    src = img.get('src') or img.get('data-src')
                    if src and 'logo' not in src.lower():
                        image = urljoin(url, src)
                        break
        
        quality = None
        quality_elem = soup.select_one('.download-item .resolution')
        if quality_elem:
            quality = quality_elem.get_text(strip=True)
        
        rating = None
        rating_elem = soup.select_one('.imdb-rating, [class*="rating"] span')
        if rating_elem:
            r_match = re.search(r'[\d.]+', rating_elem.get_text(strip=True))
            if r_match:
                rating = r_match.group(0)
        
        duration = None
        duration_elem = soup.select_one('.runtime, .duration')
        if duration_elem:
            duration = duration_elem.get_text(strip=True)
        
        genres = []
        for g in soup.select('.genres a, a[href*="/category/"]')[:5]:
            text = g.get_text(strip=True)
            if text and len(text) < 30:
                genres.append(text)
        
        return MovieInfo(
            title=title or "Unknown",
            year=year,
            image=image,
            quality=quality,
            rating=rating,
            duration=duration,
            genres=list(set(genres))[:5]
        )

    def _find_wecima_download_links(self, html: str) -> list:
        """
        Find download links from wecima.cx page.
        Returns links from all accepted hosts.
        """
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        
        download_items = soup.select('li.download-item[data-href]')
        
        for item in download_items:
            encoded_url = item.get('data-href')
            if not encoded_url:
                continue
            
            decoded_url = decode_wecima_url(encoded_url)
            if not decoded_url:
                continue
            
            # Accept all hosts (not just supported ones)
            # We'll still try to get direct links for supported hosts
            
            resolution = ""
            size = ""
            quality_type = ""
            
            resolution_elem = item.select_one('.resolution')
            if resolution_elem:
                resolution = resolution_elem.get_text(strip=True)
            
            size_elem = item.select_one('.size')
            if size_elem:
                size = size_elem.get_text(strip=True)
            
            quality_elem = item.select_one('.quality')
            if quality_elem:
                quality_type = quality_elem.get_text(strip=True)
            
            links.append({
                'url': decoded_url,
                'resolution': resolution,
                'size': size,
                'quality_type': quality_type,
                'quality_label': f"{resolution} {quality_type}".strip() if resolution else quality_type,
                'can_extract_direct': self._is_supported_host(decoded_url)
            })
        
        return links
    
    def is_wecima_url(self, url: str) -> bool:
        """Check if URL is from wecima.cx domain."""
        host = urlparse(url).netloc.lower()
        return 'wecima' in host

    def extract_wecima(self, url: str, include_watch_servers: bool = False, limit: int = None, get_direct_links: bool = False) -> ExtractResponse:
        """
        Extract download links from wecima.cx page.
        Only processes dhcplay/hgcloud hosts.
        
        Args:
            url: Wecima movie page URL
            include_watch_servers: Ignored (kept for compatibility)
            limit: Max number of download links to return (default: 3)
            get_direct_links: If True, extract direct CDN URLs
            
        Returns:
            ExtractResponse with movie info and download links
        """
        if not SELENIUMBASE_AVAILABLE:
            return ExtractResponse(
                success=False,
                message="SeleniumBase not installed",
                url=url
            )
        
        try:
            with SB(uc=True, headless=True) as sb:
                logger.info(f"[WECIMA] Loading: {url}")
                
                sb.open(url)
                sb.sleep(settings.PAGE_LOAD_WAIT)
                
                html = sb.get_page_source()
                title = sb.get_title()
                
                if 'Just a moment' in html or 'Just a moment' in title:
                    logger.info("[WECIMA] Waiting for Cloudflare...")
                    sb.sleep(settings.CLOUDFLARE_WAIT)
                    html = sb.get_page_source()
                
                # Extract movie info
                movie_info = self._extract_wecima_movie_info(html, url)
                logger.info(f"[WECIMA] Movie: {movie_info.title}")
                
                # Extract download links (only supported hosts)
                wecima_downloads = self._find_wecima_download_links(html)
                logger.info(f"[WECIMA] Found {len(wecima_downloads)} supported download links")
                
                # Apply limit (default 3)
                effective_limit = limit if limit else 3
                if len(wecima_downloads) > effective_limit:
                    wecima_downloads = wecima_downloads[:effective_limit]
                
                # Convert to DownloadLink objects
                download_links = []
                direct_count = 0
                
                for dl in wecima_downloads:
                    host = urlparse(dl['url']).netloc or "unknown"
                    quality = dl.get('quality_label') or dl.get('resolution')
                    intermediate_url = dl['url']
                    can_extract = dl.get('can_extract_direct', False)
                    
                    if get_direct_links and can_extract:
                        logger.info(f"[WECIMA] Processing {host} for direct link...")
                        try:
                            final_link, is_direct = self._extract_hgcloud_link(sb, intermediate_url)
                            download_links.append(DownloadLink(
                                host=host,
                                quality=quality,
                                host_url=intermediate_url,
                                direct_link=final_link,
                                is_direct=is_direct,
                                extracted_at=datetime.utcnow().isoformat()
                            ))
                            if is_direct:
                                direct_count += 1
                        except Exception as e:
                            logger.error(f"[WECIMA] Failed to process {host}: {e}")
                            download_links.append(DownloadLink(
                                host=host,
                                quality=quality,
                                host_url=intermediate_url,
                                direct_link=intermediate_url,
                                is_direct=False
                            ))
                    else:
                        # For non-extractable hosts, just add the link as-is
                        download_links.append(DownloadLink(
                            host=host,
                            quality=quality,
                            host_url=intermediate_url,
                            direct_link=intermediate_url,
                            is_direct=False
                        ))
                
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
            logger.exception(f"[WECIMA] Extraction failed: {e}")
            return ExtractResponse(
                success=False,
                message=f"Error: {str(e)}",
                url=url
            )

    def extract_wecima_info_only(self, url: str) -> ExtractResponse:
        """
        FAST extraction - movie info only, no direct link processing.
        """
        if not SELENIUMBASE_AVAILABLE:
            return ExtractResponse(
                success=False,
                message="SeleniumBase not installed",
                url=url
            )
        
        try:
            with SB(uc=True, headless=True) as sb:
                logger.info(f"[WECIMA-FAST] Loading: {url}")
                
                sb.open(url)
                sb.sleep(settings.PAGE_LOAD_WAIT)
                
                html = sb.get_page_source()
                title = sb.get_title()
                
                if 'Just a moment' in html or 'Just a moment' in title:
                    logger.info("[WECIMA-FAST] Waiting for Cloudflare...")
                    sb.sleep(settings.CLOUDFLARE_WAIT)
                    html = sb.get_page_source()
                
                movie_info = self._extract_wecima_movie_info(html, url)
                logger.info(f"[WECIMA-FAST] Movie: {movie_info.title}")
                
                wecima_downloads = self._find_wecima_download_links(html)
                
                download_links = []
                for dl in wecima_downloads:
                    host = urlparse(dl['url']).netloc or "unknown"
                    download_links.append(DownloadLink(
                        host=host,
                        quality=dl.get('quality_label') or dl.get('resolution'),
                        host_url=dl['url'],
                        direct_link=dl['url'],
                        is_direct=False
                    ))
                
                return ExtractResponse(
                    success=True,
                    message=f"Movie info extracted with {len(download_links)} download links",
                    url=url,
                    movie=movie_info,
                    download_links=download_links,
                    total_links=len(download_links),
                    direct_links_count=0
                )
                
        except Exception as e:
            logger.exception(f"[WECIMA-FAST] Extraction failed: {e}")
            return ExtractResponse(
                success=False,
                message=f"Error: {str(e)}",
                url=url
            )

    def refresh_direct_link(self, host_url: str) -> tuple:
        """
        Refresh an expired direct link by re-extracting from the host URL.
        
        Args:
            host_url: The intermediate host URL (e.g., dhcplay.com/xxx)
            
        Returns:
            (direct_link, is_direct, extracted_at) tuple
        """
        if not SELENIUMBASE_AVAILABLE:
            return (host_url, False, None)
        
        try:
            with SB(uc=True, headless=True) as sb:
                logger.info(f"[REFRESH] Refreshing link from: {host_url}")
                final_link, is_direct = self._extract_hgcloud_link(sb, host_url)
                extracted_at = datetime.utcnow().isoformat()
                logger.info(f"[REFRESH] Got: {final_link[:80]}... (is_direct: {is_direct})")
                return (final_link, is_direct, extracted_at)
        except Exception as e:
            logger.error(f"[REFRESH] Failed to refresh: {e}")
            return (host_url, False, None)
    
    def extract(self, url: str, limit: int = None) -> ExtractResponse:
        """
        Main extraction method - delegates to extract_wecima.
        """
        return self.extract_wecima(url, limit=limit, get_direct_links=True)
    
    def extract_info_only(self, url: str) -> ExtractResponse:
        """
        Fast extraction - delegates to extract_wecima_info_only.
        """
        return self.extract_wecima_info_only(url)
