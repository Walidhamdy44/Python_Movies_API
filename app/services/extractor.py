"""
Download link extraction service using SeleniumBase.
"""

import re
import logging
from urllib.parse import urljoin, urlparse
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


class DownloadExtractor:
    """
    Extracts download links from Arabic streaming websites.
    Uses SeleniumBase UC mode to bypass Cloudflare protection.
    """
    
    def __init__(self):
        pass
    
    def _extract_movie_info(self, html: str, url: str) -> MovieInfo:
        """Extract movie information from page HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Title from URL
        title = ""
        url_path = urlparse(url).path.strip('/')
        if url_path:
            title_from_url = url_path.replace('-', ' ')
            title_from_url = re.sub(
                r'\b(1080p|720p|480p|bluray|webrip|hdtv|cam)\b', 
                '', 
                title_from_url, 
                flags=re.I
            )
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
        
        # Method 1: Find links with class 'ser-link'
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
        """Extract direct download link from megaup."""
        try:
            sb.open(url)
            sb.sleep(settings.CLOUDFLARE_WAIT)
            
            html = sb.get_page_source()
            title = sb.get_title()
            
            if 'Just a moment' in html or 'Just a moment' in title:
                sb.sleep(settings.CLOUDFLARE_EXTRA_WAIT)
                html = sb.get_page_source()
            
            # Look for megadl download link
            matches = re.findall(r'https?://megadl[^"\'<>\s]+', html)
            if matches:
                return (matches[0], True)
            
            try:
                link = sb.find_element('a[href*="megadl"]')
                href = link.get_attribute('href')
                if href:
                    return (href, True)
            except:
                pass
            
            # Look for download.megaup.net redirect
            matches = re.findall(r'https?://download\.megaup\.net[^"\'<>\s]+', html)
            if matches:
                sb.open(matches[0])
                sb.sleep(settings.CLOUDFLARE_WAIT)
                
                html = sb.get_page_source()
                
                if 'Just a moment' in html:
                    sb.sleep(settings.CLOUDFLARE_EXTRA_WAIT)
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
            sb.sleep(settings.CLOUDFLARE_WAIT)
            
            html = sb.get_page_source()
            
            if 'Just a moment' in html:
                sb.sleep(settings.CLOUDFLARE_EXTRA_WAIT)
                html = sb.get_page_source()
            
            # Look for streamruby CDN link
            pattern = r'https?://[a-z0-9]+\.streamruby\.net[^"\'<>\s]+\.mp4[^"\'<>\s]*'
            matches = re.findall(pattern, html, re.I)
            if matches:
                return (matches[0], True)
            
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
                matches = re.findall(pattern, html, re.I)
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
            sb.sleep(settings.CLOUDFLARE_WAIT)
            
            html = sb.get_page_source()
            
            if 'Just a moment' in html:
                sb.sleep(settings.CLOUDFLARE_EXTRA_WAIT)
                html = sb.get_page_source()
            
            # Look for premilkyway CDN link
            pattern = r'https?://[a-z0-9]+\.premilkyway\.com[^"\'<>\s]+\.mp4[^"\'<>\s]*'
            matches = re.findall(pattern, html, re.I)
            if matches:
                return (matches[0], True)
            
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
                matches = re.findall(pattern, html, re.I)
                if matches:
                    return (matches[0], True)
                    
            except:
                pass
            
            return (url, False)
        except Exception as e:
            logger.error(f"hgcloud extraction failed: {e}")
            return (url, False)
    
    def _extract_final_link(self, sb, url: str) -> tuple:
        """Extract final download link. Returns (link, is_direct)."""
        host = urlparse(url).netloc.lower()
        
        if 'megaup' in host:
            return self._extract_megaup_link(sb, url)
        elif 'streamruby' in host:
            return self._extract_streamruby_link(sb, url)
        elif 'hgcloud' in host or 'premilkyway' in host:
            return self._extract_hgcloud_link(sb, url)
        else:
            return self._extract_generic_link(sb, url)
    
    def _extract_generic_link(self, sb, url: str) -> tuple:
        """Generic extraction for unknown hosts."""
        try:
            sb.open(url)
            sb.sleep(6)
            
            html = sb.get_page_source()
            
            if 'Just a moment' in html:
                sb.sleep(settings.CLOUDFLARE_WAIT)
                html = sb.get_page_source()
            
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
        """
        Main extraction method.
        
        Args:
            url: Movie page URL to extract from
            limit: Max number of download links to process
            
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
                logger.info(f"Loading: {url}")
                
                sb.open(url)
                sb.sleep(settings.PAGE_LOAD_WAIT)
                
                html = sb.get_page_source()
                movie_info = self._extract_movie_info(html, url)
                logger.info(f"Movie: {movie_info.title}")
                
                # Click watch button
                try:
                    buttons = sb.find_elements("button")
                    for btn in buttons:
                        text = btn.text
                        if 'المشاهده' in text or 'التحميل' in text:
                            btn.click()
                            sb.sleep(settings.BUTTON_CLICK_WAIT)
                            break
                except Exception as e:
                    logger.warning(f"Button click failed: {e}")
                
                html = sb.get_page_source()
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
                
                download_links = []
                
                for dl_url in download_urls:
                    try:
                        host = urlparse(dl_url).netloc or "unknown"
                        logger.info(f"Processing: {host}")
                        
                        final_link, is_direct = self._extract_final_link(sb, dl_url)
                        
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
