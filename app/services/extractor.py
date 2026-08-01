"""
Download link extraction service using SeleniumBase.
"""

import re
import base64
import logging
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
    
    Wecima encoding scheme:
    1. Removes 'aHR0c' prefix (base64 for 'https') from the standard base64
    2. Inserts '+' characters at certain positions
    
    To decode:
    1. Remove the '+' separator characters
    2. Prepend 'aHR0cH' to restore the 'https:' prefix
    3. Decode as standard base64
    
    Example: "HM6Ly9sdWx1c3Ry+ZWFtLmNvbS9lL3+VwZjJpa254ODkxZQ==" 
    -> "https://lulustream.com/e/upf2iknx891e"
    """
    try:
        if not encoded:
            return None
            
        # Step 1: Remove the '+' separators
        cleaned = encoded.replace('+', '')
        
        # Step 2: Prepend the missing 'aHR0cH' prefix (base64 for 'https:')
        # The encoded string starts with 'H' which should be 'aHR0cH' for 'https:'
        if cleaned.startswith('H'):
            fixed = 'aHR0cH' + cleaned[1:]
        else:
            fixed = cleaned
        
        # Step 3: Decode base64
        decoded = base64.b64decode(fixed).decode('utf-8')
        
        return decoded
    except Exception as e:
        logger.error(f"Failed to decode wecima URL '{encoded}': {e}")
        return None


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
        
        # Try to get title from page first
        title = ""
        
        # Method 1: og:title meta tag
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title = og_title['content'].strip()
        
        # Method 2: page title
        if not title:
            page_title = soup.find('title')
            if page_title:
                title = page_title.get_text(strip=True).split('|')[0].split('-')[0].strip()
        
        # Method 3: h1 or main title element
        if not title:
            h1 = soup.select_one('h1.entry-title, h1.title, h1, .movie-title')
            if h1:
                title = h1.get_text(strip=True)
        
        # Method 4: From URL (decode URL-encoded characters)
        if not title or title == "Unknown":
            url_path = unquote(urlparse(url).path.strip('/'))  # Decode URL encoding
            if url_path:
                # Remove common prefixes like مشاهدة-فيلم
                title_from_url = url_path.replace('-', ' ')
                # Remove quality tags
                title_from_url = re.sub(
                    r'\b(1080p|720p|480p|bluray|webrip|hdtv|cam|مترجم|مشاهده|مشاهدة|فيلم|تحميل)\b', 
                    '', 
                    title_from_url, 
                    flags=re.I
                )
                title = ' '.join(title_from_url.split()).strip()
        
        # Clean up title
        if title:
            # Remove "مشاهدة فيلم" prefix if present
            title = re.sub(r'^(مشاهده|مشاهدة)\s*(فيلم)?\s*', '', title, flags=re.I).strip()
            # Remove trailing "مترجم"
            title = re.sub(r'\s*مترجم\s*$', '', title, flags=re.I).strip()
        
        # Year - extract from title or URL
        year = None
        year_match = re.search(r'(19|20)\d{2}', url + (title or ''))
        if year_match:
            year = year_match.group(0)
        
        # Image/Poster - try multiple selectors
        image = None
        img_selectors = [
            '.single-thumb img', '.movie-thumb img', '.thumb img',
            'img.poster', '.poster img', '.movie-poster img',
            'img[itemprop="image"]', 'article img', '.featured-img img',
            '.entry-content img', '.post-thumbnail img', 'img.wp-post-image',
            '.film-poster img', '.cover img', 'meta[property="og:image"]'
        ]
        
        # Try og:image first
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            image = og_image['content']
        
        # Try other selectors
        if not image:
            for selector in img_selectors:
                if selector.startswith('meta'):
                    continue
                img = soup.select_one(selector)
                if img:
                    src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                    if src and 'logo' not in src.lower() and 'icon' not in src.lower():
                        image = urljoin(url, src)
                        break
        
        # Quality
        quality = None
        quality_elem = soup.select_one('.quality, .qlty, span.quality, .label-quality, .movie-quality')
        if quality_elem:
            quality = quality_elem.get_text(strip=True)
        else:
            q_match = re.search(r'(1080p|720p|480p|4k|bluray|hdrip|webrip)', url + (title or ''), re.I)
            if q_match:
                quality = q_match.group(1).upper()
        
        # Rating
        rating = None
        rating_elem = soup.select_one('.rating .num, .imdb-rating, [class*="rating"] span, .imdb span')
        if rating_elem:
            rating_text = rating_elem.get_text(strip=True)
            r_match = re.search(r'[\d.]+', rating_text)
            if r_match:
                rating = r_match.group(0)
        
        # Duration
        duration = None
        duration_elem = soup.select_one('.runtime, .duration, [class*="duration"], .time, .movie-duration')
        if duration_elem:
            duration = duration_elem.get_text(strip=True)
        
        # Genres
        genres = []
        genre_selectors = ['.genres a', '.genre a', 'a[href*="/genre/"]', '.cats a', '.category a']
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
        """
        Extract direct download link from hgcloud.to
        
        Flow:
        1. First page: Click "Download" button (a.videoplayer-download)
        2. Second page: Choose quality - click /f/xxxxx_n or /f/xxxxx_l link  
        3. Third page: Has reCAPTCHA form, click submit button
        4. Fourth page: Wait for countdown, get final CDN link (cdn-centaurus.com)
        """
        try:
            logger.info(f"hgcloud: Opening {url}")
            sb.open(url)
            sb.sleep(settings.CLOUDFLARE_WAIT)
            
            html = sb.get_page_source()
            
            if 'Just a moment' in html:
                logger.info("hgcloud: Waiting for Cloudflare...")
                sb.sleep(settings.CLOUDFLARE_EXTRA_WAIT)
                html = sb.get_page_source()
            
            # Check if we already have a CDN link on this page
            cdn_pattern = r'https?://[a-zA-Z0-9]+\.cdn-centaurus\.com[^"\'<>\s]+'
            matches = re.findall(cdn_pattern, html, re.I)
            if matches:
                clean_link = matches[0].replace('&amp;', '&')
                logger.info(f"hgcloud: Found CDN link directly: {clean_link}")
                return (clean_link, True)
            
            # Also check for premilkyway CDN (older pattern)
            premilky_pattern = r'https?://[a-z0-9]+\.premilkyway\.com[^"\'<>\s]+\.mp4[^"\'<>\s]*'
            matches = re.findall(premilky_pattern, html, re.I)
            if matches:
                clean_link = matches[0].replace('&amp;', '&')
                logger.info(f"hgcloud: Found premilkyway link: {clean_link}")
                return (clean_link, True)
            
            # STEP 1: Click the first Download button (videoplayer-download)
            logger.info("hgcloud: Step 1 - Looking for videoplayer-download button")
            try:
                download_btn = sb.find_element('a.videoplayer-download, a.btn-gr[href*="/f/"]')
                href = download_btn.get_attribute('href')
                logger.info(f"hgcloud: Found download button, href: {href}")
                download_btn.click()
                sb.sleep(5)
            except Exception as e:
                logger.warning(f"hgcloud: Step 1 button click failed: {e}")
                # Try finding any link with /f/ pattern
                try:
                    f_links = sb.find_elements('a[href*="/f/"]')
                    for link in f_links:
                        href = link.get_attribute('href')
                        if href and '/f/' in href:
                            logger.info(f"hgcloud: Clicking /f/ link: {href}")
                            link.click()
                            sb.sleep(5)
                            break
                except:
                    pass
            
            html = sb.get_page_source()
            
            # Check for CDN link after step 1
            matches = re.findall(cdn_pattern, html, re.I)
            if matches:
                clean_link = matches[0].replace('&amp;', '&')
                logger.info(f"hgcloud: Found CDN link after step 1: {clean_link}")
                return (clean_link, True)
            
            # STEP 2: Choose quality - click _o (original), _n (normal) or _l (low) link
            logger.info("hgcloud: Step 2 - Looking for quality selection links")
            try:
                # Look for downloadv-item links (quality selection)
                # Priority: _o (original) > _n (normal) > _l (low)
                quality_links = sb.find_elements('a.downloadv-item, a[href*="_o"], a[href*="_n"], a[href*="_l"]')
                clicked = False
                for suffix in ['_o', '_n', '_l']:
                    for link in quality_links:
                        href = link.get_attribute('href')
                        if href and suffix in href:
                            logger.info(f"hgcloud: Clicking quality link: {href}")
                            link.click()
                            sb.sleep(5)
                            clicked = True
                            break
                    if clicked:
                        break
            except Exception as e:
                logger.warning(f"hgcloud: Step 2 quality selection failed: {e}")
            
            html = sb.get_page_source()
            
            # Check for CDN link after step 2
            matches = re.findall(cdn_pattern, html, re.I)
            if matches:
                clean_link = matches[0].replace('&amp;', '&')
                logger.info(f"hgcloud: Found CDN link after step 2: {clean_link}")
                return (clean_link, True)
            
            # STEP 3: Click reCAPTCHA submit button
            logger.info("hgcloud: Step 3 - Looking for submit button (reCAPTCHA)")
            try:
                # The submit button has g-recaptcha class
                submit_btn = sb.find_element('button.g-recaptcha, button.submit-btn, .g-recaptcha.btn')
                logger.info("hgcloud: Found submit button, clicking...")
                submit_btn.click()
                sb.sleep(8)  # Wait for reCAPTCHA and page load
            except Exception as e:
                logger.warning(f"hgcloud: Step 3 submit button failed: {e}")
                # Try JavaScript click
                try:
                    sb.execute_script("""
                        var btn = document.querySelector('button.g-recaptcha, button.submit-btn');
                        if (btn) btn.click();
                    """)
                    sb.sleep(8)
                except:
                    pass
            
            html = sb.get_page_source()
            
            # Check for CDN link after step 3
            matches = re.findall(cdn_pattern, html, re.I)
            if matches:
                clean_link = matches[0].replace('&amp;', '&')
                logger.info(f"hgcloud: Found CDN link after step 3: {clean_link}")
                return (clean_link, True)
            
            # STEP 4: Wait for countdown and get final link
            logger.info("hgcloud: Step 4 - Waiting for countdown timer...")
            
            # Wait up to 10 seconds for the countdown
            for wait_sec in range(10):
                sb.sleep(1)
                html = sb.get_page_source()
                
                # Look for the final download link
                matches = re.findall(cdn_pattern, html, re.I)
                if matches:
                    clean_link = matches[0].replace('&amp;', '&')
                    logger.info(f"hgcloud: Found CDN link after countdown: {clean_link}")
                    return (clean_link, True)
                
                # Check for premilkyway pattern too
                matches = re.findall(premilky_pattern, html, re.I)
                if matches:
                    clean_link = matches[0].replace('&amp;', '&')
                    logger.info(f"hgcloud: Found premilkyway link after countdown: {clean_link}")
                    return (clean_link, True)
                
                # Also try to find submit-btn with actual download href
                try:
                    final_btn = sb.find_element('a.submit-btn[href*="cdn-centaurus"], a.btn-gr[href*="cdn-centaurus"], a.submit-btn[href*="premilkyway"], a.btn-gr[href*="premilkyway"]')
                    href = final_btn.get_attribute('href')
                    if href and ('cdn-centaurus' in href or 'premilkyway' in href):
                        clean_link = href.replace('&amp;', '&')
                        logger.info(f"hgcloud: Found final download button: {clean_link}")
                        return (clean_link, True)
                except:
                    pass
            
            # Final attempt - check page source for any CDN patterns
            html = sb.get_page_source()
            
            # Try multiple CDN patterns
            cdn_patterns = [
                r'https?://[a-zA-Z0-9]+\.cdn-centaurus\.com[^"\'<>\s]+',
                r'https?://[a-z0-9]+\.premilkyway\.com[^"\'<>\s]+\.mp4[^"\'<>\s]*',
                r'href=["\']?(https?://[^"\'<>\s]+\.mp4[^"\'<>\s]*)["\']?',
            ]
            
            for pattern in cdn_patterns:
                matches = re.findall(pattern, html, re.I)
                for match in matches:
                    if 'hgcloud' not in match and 'cloudflare' not in match:
                        # Decode HTML entities (e.g., &amp; -> &)
                        clean_match = match.replace('&amp;', '&')
                        logger.info(f"hgcloud: Found download link: {clean_match}")
                        return (clean_match, True)
            
            logger.warning("hgcloud: Could not find direct download link")
            return (url, False)
            
        except Exception as e:
            logger.error(f"hgcloud extraction failed: {e}")
            return (url, False)
    
    def _extract_abstream_link(self, sb, url: str) -> tuple:
        """
        Extract direct download link from abstream.to
        
        Flow:
        1. Open initial page /d/xxxxx
        2. Find and click quality link /d/xxxxx_n (or _h, _o)
        3. Submit the download form
        4. Extract the CDN link from response
        
        Note: This site uses proxycheck.io for VPN/proxy detection.
        If VPN is detected, it redirects to /vpn.html
        """
        try:
            logger.info(f"abstream: Opening {url}")
            sb.open(url)
            sb.sleep(3)
            
            html = sb.get_page_source()
            current_url = sb.get_current_url()
            
            # Check for VPN block
            if '/vpn.html' in current_url.lower() or '/blocked' in current_url.lower():
                logger.warning("abstream: VPN/proxy detected - site blocked access")
                return (url, False)
            
            # Check for Cloudflare
            if 'Just a moment' in html:
                logger.info("abstream: Waiting for Cloudflare...")
                sb.sleep(settings.CLOUDFLARE_WAIT)
                html = sb.get_page_source()
            
            # STEP 1: Find quality link (/d/xxxxx_n, _h, or _o)
            quality_link = None
            try:
                links = sb.find_elements('a[href*="_n"], a[href*="_h"], a[href*="_o"]')
                for link in links:
                    href = link.get_attribute('href')
                    if href and '/d/' in href:
                        quality_link = href
                        # Prefer higher quality
                        if '_h' in href:
                            break
            except:
                pass
            
            if not quality_link:
                # Try regex
                match = re.search(r'href=["\']([^"\']*?/d/[a-z0-9]+_[hno])["\']', html, re.I)
                if match:
                    quality_link = match.group(1)
                    if not quality_link.startswith('http'):
                        quality_link = f"https://abstream.to{quality_link}"
            
            if not quality_link:
                logger.warning("abstream: No quality link found")
                return (url, False)
            
            # STEP 2: Navigate to quality page
            logger.info(f"abstream: Navigating to quality page: {quality_link}")
            sb.open(quality_link)
            sb.sleep(3)
            
            html = sb.get_page_source()
            
            # STEP 3: Submit the download form
            logger.info("abstream: Looking for download form...")
            try:
                # Remove any overlay first
                try:
                    sb.execute_script("var overlay = document.getElementById('overlay'); if(overlay) overlay.style.display='none';")
                except:
                    pass
                
                # Find and click submit button
                submit_btn = sb.find_element('form#F1 button, form button.submit-btn, button.btn-gradient')
                submit_btn.click()
                logger.info("abstream: Submitted download form")
                sb.sleep(5)
            except:
                # Try JS form submit
                try:
                    sb.execute_script("document.getElementById('F1').submit();")
                    sb.sleep(5)
                except:
                    logger.warning("abstream: Could not submit form")
            
            # STEP 4: Extract CDN link from response
            html = sb.get_page_source()
            
            # Look for delucloud CDN or other CDN patterns
            cdn_patterns = [
                r'https?://[a-z0-9]+\.delucloud\.xyz/[^"\'<>\s]+\.mp4[^"\'<>\s]*',
                r'https?://[a-z0-9]+\.abstream[a-z0-9]*\.(?:com|xyz|to)/[^"\'<>\s]+\.mp4[^"\'<>\s]*',
                r'https?://[^"\'<>\s]+/v/\d+/\d+/[a-z0-9]+_[hno]/[^"\'<>\s]+\.mp4[^"\'<>\s]*',
            ]
            
            for pattern in cdn_patterns:
                matches = re.findall(pattern, html, re.I)
                if matches:
                    # Decode HTML entities
                    clean_link = matches[0].replace('&amp;', '&')
                    logger.info(f"abstream: Found CDN link: {clean_link}")
                    return (clean_link, True)
            
            logger.warning("abstream: Could not find direct download link")
            return (url, False)
            
        except Exception as e:
            logger.error(f"abstream extraction failed: {e}")
            return (url, False)
    
    def _extract_final_link(self, sb, url: str) -> tuple:
        """Extract final download link. Returns (link, is_direct)."""
        host = urlparse(url).netloc.lower()
        
        if 'megaup' in host:
            return self._extract_megaup_link(sb, url)
        elif 'streamruby' in host:
            return self._extract_streamruby_link(sb, url)
        elif 'abstream' in host:
            return self._extract_abstream_link(sb, url)
        elif any(x in host for x in ['hgcloud', 'premilkyway', 'dhcplay', 'hanerix', 'audinifer']):
            # dhcplay, hanerix, audinifer use the same system as hgcloud
            return self._extract_hgcloud_link(sb, url)
        elif any(x in host for x in ['lulustream', 'luluvdo']):
            return self._extract_lulustream_link(sb, url)
        else:
            return self._extract_generic_link(sb, url)
    
    def _extract_lulustream_link(self, sb, url: str) -> tuple:
        """
        Extract download link from lulustream/luluvdo.
        These sites have quality variants like _h (HD), _n (normal), _l (low).
        """
        try:
            logger.info(f"lulustream: Opening {url}")
            sb.open(url)
            sb.sleep(settings.CLOUDFLARE_WAIT)
            
            html = sb.get_page_source()
            
            if 'Just a moment' in html:
                logger.info("lulustream: Waiting for Cloudflare...")
                sb.sleep(settings.CLOUDFLARE_EXTRA_WAIT)
                html = sb.get_page_source()
            
            # Look for quality variant links (_h for HD, _n for normal)
            quality_pattern = r'https?://(?:lulustream|luluvdo)\.com/d/[a-z0-9]+_[hno]'
            matches = re.findall(quality_pattern, html, re.I)
            
            if matches:
                # Prefer HD (_h) variant
                hd_links = [m for m in matches if '_h' in m]
                if hd_links:
                    logger.info(f"lulustream: Found HD link: {hd_links[0]}")
                    return (hd_links[0], False)  # Not direct CDN, but best quality variant
                return (matches[0], False)
            
            # Try to find any download button with href
            try:
                dl_btns = sb.find_elements('a[href*="_h"], a[href*="_n"], a[href*="_o"]')
                for btn in dl_btns:
                    href = btn.get_attribute('href')
                    if href and ('lulustream' in href or 'luluvdo' in href):
                        logger.info(f"lulustream: Found quality button: {href}")
                        return (href, False)
            except:
                pass
            
            # Return original URL if no quality variants found
            logger.warning("lulustream: No quality variants found")
            return (url, False)
            
        except Exception as e:
            logger.error(f"lulustream extraction failed: {e}")
            return (url, False)
    
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
    
    # ============== WECIMA EXTRACTION METHODS ==============
    
    def _extract_wecima_movie_info(self, html: str, url: str) -> MovieInfo:
        """Extract movie information from wecima.cx page HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        
        title = ""
        
        # Method 1: og:title meta tag
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title = og_title['content'].strip()
        
        # Method 2: page title
        if not title:
            page_title = soup.find('title')
            if page_title:
                title = page_title.get_text(strip=True).split('|')[0].split('-')[0].strip()
        
        # Method 3: h1 element
        if not title:
            h1 = soup.select_one('h1')
            if h1:
                title = h1.get_text(strip=True)
        
        # Clean up title - remove common prefixes
        if title:
            title = re.sub(r'^(مشاهده|مشاهدة)\s*(فيلم)?\s*', '', title, flags=re.I).strip()
            title = re.sub(r'\s*مترجم\s*$', '', title, flags=re.I).strip()
            # Remove "Wecima" suffix if present
            title = re.sub(r'\s*-?\s*Wecima.*$', '', title, flags=re.I).strip()
        
        # Year - extract from title or URL
        year = None
        year_match = re.search(r'(19|20)\d{2}', url + (title or ''))
        if year_match:
            year = year_match.group(0)
        
        # Image/Poster - try og:image first
        image = None
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            image = og_image['content']
        
        # Try other image selectors
        if not image:
            img_selectors = [
                '.Poster img', '.poster img', '.movie-poster img',
                'img.poster', 'img[itemprop="image"]',
                '.film-poster img', '.cover img'
            ]
            for selector in img_selectors:
                img = soup.select_one(selector)
                if img:
                    src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                    if src and 'logo' not in src.lower():
                        image = urljoin(url, src)
                        break
        
        # Story/Description
        description = None
        story_elem = soup.select_one('.StoryMovieContent')
        if story_elem:
            description = story_elem.get_text(strip=True)
        
        # Quality from download links
        quality = None
        quality_elem = soup.select_one('.download-item .resolution')
        if quality_elem:
            quality = quality_elem.get_text(strip=True)
        
        # Rating
        rating = None
        rating_elem = soup.select_one('.imdb-rating, [class*="rating"] span, .Rating span')
        if rating_elem:
            rating_text = rating_elem.get_text(strip=True)
            r_match = re.search(r'[\d.]+', rating_text)
            if r_match:
                rating = r_match.group(0)
        
        # Duration
        duration = None
        duration_elem = soup.select_one('.runtime, .duration, [class*="duration"]')
        if duration_elem:
            duration = duration_elem.get_text(strip=True)
        
        # Genres
        genres = []
        genre_selectors = ['.genres a', '.genre a', 'a[href*="/genre/"]', 'a[href*="/category/"]']
        for selector in genre_selectors:
            genre_links = soup.select(selector)
            for g in genre_links[:5]:
                text = g.get_text(strip=True)
                if text and len(text) < 30:
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
    
    def _find_wecima_download_links(self, html: str) -> list:
        """
        Find all download links from wecima.cx page.
        Returns list of dicts with: url, resolution, size, quality
        """
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        
        # Find download items with data-href attribute
        download_items = soup.select('li.download-item[data-href]')
        
        for item in download_items:
            encoded_url = item.get('data-href')
            if not encoded_url:
                continue
            
            # Decode the URL
            decoded_url = decode_wecima_url(encoded_url)
            if not decoded_url:
                continue
            
            # Get quality info
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
                'quality_label': f"{resolution} {quality_type}".strip() if resolution else quality_type
            })
        
        return links
    
    def _find_wecima_watch_servers(self, html: str) -> list:
        """
        Find all watch/streaming servers from wecima.cx page.
        Returns list of dicts with: url, server_name
        """
        soup = BeautifulSoup(html, 'html.parser')
        servers = []
        
        # Find server buttons with data-url attribute
        server_btns = soup.select('.WatchServersList btn[data-url]')
        
        for btn in server_btns:
            encoded_url = btn.get('data-url')
            if not encoded_url:
                continue
            
            # Decode the URL
            decoded_url = decode_wecima_url(encoded_url)
            if not decoded_url:
                continue
            
            # Get server name
            server_name = "Unknown Server"
            strong_elem = btn.select_one('strong')
            if strong_elem:
                server_name = strong_elem.get_text(strip=True)
            
            servers.append({
                'url': decoded_url,
                'server_name': server_name
            })
        
        return servers
    
    def is_wecima_url(self, url: str) -> bool:
        """Check if URL is from wecima.cx domain."""
        host = urlparse(url).netloc.lower()
        return 'wecima' in host
    
    def extract_wecima(self, url: str, include_watch_servers: bool = False, limit: int = None) -> ExtractResponse:
        """
        Extract download links from wecima.cx page.
        
        Args:
            url: Wecima movie page URL
            include_watch_servers: Whether to also extract streaming server URLs
            limit: Max number of download links to return
            
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
                
                # Check if Cloudflare challenge
                if 'Just a moment' in html or 'Just a moment' in title:
                    logger.info("[WECIMA] Waiting for Cloudflare...")
                    sb.sleep(settings.CLOUDFLARE_WAIT)
                    html = sb.get_page_source()
                
                # Extract movie info
                movie_info = self._extract_wecima_movie_info(html, url)
                logger.info(f"[WECIMA] Movie: {movie_info.title}")
                
                # Extract download links
                wecima_downloads = self._find_wecima_download_links(html)
                logger.info(f"[WECIMA] Found {len(wecima_downloads)} download links")
                
                # Optionally extract watch servers
                watch_servers = []
                if include_watch_servers:
                    watch_servers = self._find_wecima_watch_servers(html)
                    logger.info(f"[WECIMA] Found {len(watch_servers)} watch servers")
                
                # Apply limit
                if limit and len(wecima_downloads) > limit:
                    wecima_downloads = wecima_downloads[:limit]
                
                # Convert to DownloadLink objects
                download_links = []
                for dl in wecima_downloads:
                    host = urlparse(dl['url']).netloc or "unknown"
                    download_links.append(DownloadLink(
                        host=host,
                        quality=dl.get('quality_label') or dl.get('resolution'),
                        direct_link=dl['url'],
                        is_direct=False  # These are intermediate links, not direct CDN links
                    ))
                
                # Add watch servers as well if requested
                if include_watch_servers:
                    for server in watch_servers:
                        host = urlparse(server['url']).netloc or "unknown"
                        download_links.append(DownloadLink(
                            host=host,
                            quality=f"Stream: {server['server_name']}",
                            direct_link=server['url'],
                            is_direct=False
                        ))
                
                return ExtractResponse(
                    success=True,
                    message=f"Extracted {len(wecima_downloads)} download links" + 
                            (f" and {len(watch_servers)} watch servers" if include_watch_servers else ""),
                    url=url,
                    movie=movie_info,
                    download_links=download_links,
                    total_links=len(download_links),
                    direct_links_count=0  # Wecima links are not direct CDN links
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
        FAST extraction for wecima - movie info only, no Selenium needed for decoding.
        
        Args:
            url: Wecima movie page URL
            
        Returns:
            ExtractResponse with movie info and decoded download links
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
                
                # Check if Cloudflare challenge
                if 'Just a moment' in html or 'Just a moment' in title:
                    logger.info("[WECIMA-FAST] Waiting for Cloudflare...")
                    sb.sleep(settings.CLOUDFLARE_WAIT)
                    html = sb.get_page_source()
                
                # Extract movie info
                movie_info = self._extract_wecima_movie_info(html, url)
                logger.info(f"[WECIMA-FAST] Movie: {movie_info.title}")
                
                # Extract and decode download links (this is fast since it's just parsing)
                wecima_downloads = self._find_wecima_download_links(html)
                
                # Convert to DownloadLink objects
                download_links = []
                for dl in wecima_downloads:
                    host = urlparse(dl['url']).netloc or "unknown"
                    download_links.append(DownloadLink(
                        host=host,
                        quality=dl.get('quality_label') or dl.get('resolution'),
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
    
    def extract_info_only(self, url: str) -> ExtractResponse:
        """
        FAST extraction - movie info only, NO download link processing.
        
        Args:
            url: Movie page URL to extract from
            
        Returns:
            ExtractResponse with movie info only (no download links processed)
        """
        if not SELENIUMBASE_AVAILABLE:
            return ExtractResponse(
                success=False,
                message="SeleniumBase not installed",
                url=url
            )
        
        try:
            with SB(uc=True, headless=True) as sb:
                logger.info(f"[FAST] Loading: {url}")
                
                sb.open(url)
                sb.sleep(settings.PAGE_LOAD_WAIT)
                
                html = sb.get_page_source()
                title = sb.get_title()
                
                # Check if Cloudflare challenge
                if 'Just a moment' in html or 'Just a moment' in title:
                    logger.info("[FAST] Waiting for Cloudflare...")
                    sb.sleep(settings.CLOUDFLARE_WAIT)
                    html = sb.get_page_source()
                
                movie_info = self._extract_movie_info(html, url)
                logger.info(f"[FAST] Movie: {movie_info.title}")
                
                # Get download link count without processing them
                download_urls = self._find_download_links(html)
                
                return ExtractResponse(
                    success=True,
                    message=f"Movie info extracted (found {len(download_urls)} download links)",
                    url=url,
                    movie=movie_info,
                    download_links=[],
                    total_links=len(download_urls),
                    direct_links_count=0
                )
                
        except Exception as e:
            logger.exception(f"[FAST] Extraction failed: {e}")
            return ExtractResponse(
                success=False,
                message=f"Error: {str(e)}",
                url=url
            )

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
