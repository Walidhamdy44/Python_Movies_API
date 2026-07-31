# 🛡️ How We Bypassed Cloudflare Protection

This document explains the technical approach used to bypass Cloudflare's JavaScript Challenge on download hosting sites like megaup.net, without using any paid captcha solving services.

## 📋 Table of Contents

1. [The Problem](#the-problem)
2. [What Doesn't Work](#what-doesnt-work)
3. [The Solution: SeleniumBase UC Mode](#the-solution-seleniumbase-uc-mode)
4. [How It Works](#how-it-works)
5. [Code Walkthrough](#code-walkthrough)
6. [Extraction Flow](#extraction-flow)
7. [Supported Hosts](#supported-hosts)
8. [Limitations](#limitations)

---

## The Problem

Many download hosting sites (megaup.net, streamruby.com, hgcloud.to) use **Cloudflare's JavaScript Challenge** to protect against bots. When you visit these sites, you see:

```
"Just a moment..."
"Checking your browser before accessing..."
```

This challenge:

- Executes JavaScript to verify you're a real browser
- Checks for automation flags (`navigator.webdriver`)
- Analyzes browser fingerprints
- Sets cookies after verification

**Without bypassing this, all scraping attempts fail.**

---

## What Doesn't Work

We tested multiple approaches that **all failed**:

### ❌ Regular Selenium

```python
from selenium import webdriver
driver = webdriver.Chrome()
driver.get("https://megaup.net/...")
# Result: Stuck on "Just a moment..." forever
```

**Why it fails:** Selenium sets `navigator.webdriver = true`, which Cloudflare detects.

### ❌ Selenium with Anti-Detection Flags

```python
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_experimental_option('excludeSwitches', ['enable-automation'])
```

**Why it fails:** Cloudflare's detection is more sophisticated than simple flag checking.

### ❌ cloudscraper (Python library)

```python
import cloudscraper
scraper = cloudscraper.create_scraper()
response = scraper.get(url)
# Result: 403 Forbidden or challenge page
```

**Why it fails:** Only works for basic challenges, not JavaScript challenges.

### ❌ Playwright with Stealth Plugin

```python
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
```

**Why it fails:** Cloudflare has evolved to detect Playwright's patterns.

### ❌ undetected-chromedriver

```python
import undetected_chromedriver as uc
driver = uc.Chrome()
```

**Why it fails:** Broken on Python 3.12+ (missing `distutils` module), and Cloudflare has adapted to detect it.

---

## The Solution: SeleniumBase UC Mode

**SeleniumBase** with **UC (Undetected Chrome) mode** successfully bypasses Cloudflare's JavaScript Challenge.

### Why It Works

SeleniumBase UC mode:

1. **Patches Chrome at runtime** to remove automation indicators
2. **Uses a real Chrome profile** instead of automation profile
3. **Handles the challenge automatically** by waiting for verification
4. **Maintains proper browser fingerprint** that passes Cloudflare checks

### Installation

```bash
pip install seleniumbase
seleniumbase install chromedriver
```

### Basic Usage

```python
from seleniumbase import SB

with SB(uc=True, headless=True) as sb:
    sb.open("https://megaup.net/...")
    sb.sleep(10)  # Wait for Cloudflare bypass
    html = sb.get_page_source()
    # Now you have the real page content!
```

---

## How It Works

### Cloudflare Bypass Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLOUDFLARE BYPASS FLOW                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. SeleniumBase opens URL with UC mode                        │
│     └── Chrome is patched to hide automation flags             │
│                                                                 │
│  2. Cloudflare serves JavaScript Challenge                     │
│     └── "Just a moment..." page appears                        │
│                                                                 │
│  3. SeleniumBase waits (10-15 seconds)                         │
│     └── Browser executes Cloudflare's JS                       │
│     └── Fingerprint checks pass                                │
│     └── Verification cookie is set                             │
│                                                                 │
│  4. Cloudflare redirects to actual page                        │
│     └── Real content is now accessible                         │
│                                                                 │
│  5. Extract download links from HTML                           │
│     └── Find megadl.boats CDN links                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key Parameters

| Parameter       | Value           | Purpose                           |
| --------------- | --------------- | --------------------------------- |
| `uc=True`       | Enable UC mode  | Patches Chrome to avoid detection |
| `headless=True` | Run without GUI | Required for server deployment    |
| `sb.sleep(10)`  | Wait 10 seconds | Time for Cloudflare verification  |

---

## Code Walkthrough

### 1. Configuration (`app/config.py`)

```python
class Settings:
    # Selenium Timeouts (seconds)
    PAGE_LOAD_WAIT: int = 4           # Initial page load
    CLOUDFLARE_WAIT: int = 10         # Wait for Cloudflare bypass
    CLOUDFLARE_EXTRA_WAIT: int = 15   # Extra wait if still stuck
    BUTTON_CLICK_WAIT: int = 4        # Wait after clicking buttons
```

### 2. Main Extraction Flow (`app/services/extractor.py`)

```python
def extract(self, url: str, limit: int = None) -> ExtractResponse:
    """Main extraction method."""

    # Use SeleniumBase with UC mode
    with SB(uc=True, headless=True) as sb:

        # Step 1: Load the movie page
        sb.open(url)
        sb.sleep(settings.PAGE_LOAD_WAIT)

        # Step 2: Extract movie info
        html = sb.get_page_source()
        movie_info = self._extract_movie_info(html, url)

        # Step 3: Click "المشاهده والتحميل" (Watch & Download) button
        buttons = sb.find_elements("button")
        for btn in buttons:
            if 'المشاهده' in btn.text:
                btn.click()
                sb.sleep(settings.BUTTON_CLICK_WAIT)
                break

        # Step 4: Find all download links (حمل الان)
        html = sb.get_page_source()
        download_urls = self._find_download_links(html)

        # Step 5: Process each download link
        for dl_url in download_urls:
            final_link, is_direct = self._extract_final_link(sb, dl_url)
            # ... store result
```

### 3. MegaUp Extraction (`_extract_megaup_link`)

This is the key function that bypasses Cloudflare on megaup.net:

```python
def _extract_megaup_link(self, sb, url: str) -> tuple:
    """Extract direct download link from megaup."""

    # Open the megaup page
    sb.open(url)
    sb.sleep(settings.CLOUDFLARE_WAIT)  # 10 seconds for Cloudflare

    html = sb.get_page_source()
    title = sb.get_title()

    # Check if still on Cloudflare challenge
    if 'Just a moment' in html or 'Just a moment' in title:
        sb.sleep(settings.CLOUDFLARE_EXTRA_WAIT)  # Wait 15 more seconds
        html = sb.get_page_source()

    # Look for the megadl CDN link (the actual download URL)
    # Pattern: https://megadl.boats/download/Movie.mp4?download_token=...
    matches = re.findall(r'https?://megadl[^"\'<>\s]+', html)
    if matches:
        return (matches[0], True)  # True = direct link

    # Alternative: Find the redirect link first
    matches = re.findall(r'https?://download\.megaup\.net[^"\'<>\s]+', html)
    if matches:
        # Follow the redirect
        sb.open(matches[0])
        sb.sleep(settings.CLOUDFLARE_WAIT)

        html = sb.get_page_source()
        megadl_matches = re.findall(r'https?://megadl[^"\'<>\s]+', html)
        if megadl_matches:
            return (megadl_matches[0], True)

    return (url, False)  # False = not a direct link
```

### 4. Finding Download Links (`_find_download_links`)

```python
def _find_download_links(self, html: str) -> list:
    """Find all حمل الان (Download Now) links."""
    soup = BeautifulSoup(html, 'html.parser')
    links = []

    # Method 1: Find links with class 'ser-link' (EgyDead's structure)
    for a_tag in soup.find_all('a', class_='ser-link'):
        href = a_tag.get('href')
        if href and not href.startswith('#'):
            links.append(href)

    # Method 2: Find links containing "حمل الان" text
    if not links:
        for a_tag in soup.find_all('a', href=True):
            if 'حمل الان' in a_tag.get_text():
                links.append(a_tag['href'])

    return links
```

---

## Extraction Flow

### Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     COMPLETE EXTRACTION FLOW                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  USER REQUEST                                                       │
│  GET /extract?url=https://tv10.egydead.live/movie-name/&limit=5    │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ STEP 1: Load Movie Page                                      │   │
│  │   sb.open("https://tv10.egydead.live/movie-name/")          │   │
│  │   → Extract: title, year, quality, image                     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ STEP 2: Click Watch Button                                   │   │
│  │   Find button with "المشاهده والتحميل" text                   │   │
│  │   → Page reveals download links                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ STEP 3: Find Download Links                                  │   │
│  │   Look for <a class="ser-link"> with "حمل الان" text         │   │
│  │   → Found: megaup.net, streamruby.com, hgcloud.to, etc.     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ STEP 4: Process Each Host                                    │   │
│  │                                                              │   │
│  │   megaup.net:                                                │   │
│  │   ├── Open URL with SeleniumBase UC mode                    │   │
│  │   ├── Wait 10s for Cloudflare bypass                        │   │
│  │   ├── Find megadl.boats link in HTML                        │   │
│  │   └── Return direct CDN URL ✓                               │   │
│  │                                                              │   │
│  │   streamruby.com:                                            │   │
│  │   ├── Open URL, wait for Cloudflare                         │   │
│  │   ├── Look for streamruby.net CDN link                      │   │
│  │   └── Return link (may need more steps)                     │   │
│  │                                                              │   │
│  │   hgcloud.to:                                                │   │
│  │   ├── Open URL, wait for Cloudflare                         │   │
│  │   ├── Look for premilkyway.com CDN link                     │   │
│  │   └── Return link (may need more steps)                     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ STEP 5: Return Response                                      │   │
│  │   {                                                          │   │
│  │     "success": true,                                         │   │
│  │     "movie": { "title": "...", "year": "2025" },            │   │
│  │     "download_links": [                                      │   │
│  │       { "host": "megaup.net", "is_direct": true,            │   │
│  │         "direct_link": "https://megadl.boats/..." }         │   │
│  │     ]                                                        │   │
│  │   }                                                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Supported Hosts

### ✅ Fully Working

| Host           | CDN Domain   | Status                    |
| -------------- | ------------ | ------------------------- |
| **megaup.net** | megadl.boats | ✅ Direct links extracted |

### ⏳ Partially Working

| Host           | CDN Domain      | Status                               |
| -------------- | --------------- | ------------------------------------ |
| streamruby.com | streamruby.net  | ⏳ Page loads, may need button click |
| hgcloud.to     | premilkyway.com | ⏳ Page loads, may need button click |
| forafile.com   | -               | ⏳ Returns page URL only             |
| send.now       | -               | ⏳ Returns page URL only             |

---

## Limitations

### 1. Processing Time

- Each link takes 10-20 seconds to process
- Cloudflare wait time cannot be reduced
- Recommendation: Use `?limit=3` to speed up requests

### 2. Server Resources

- SeleniumBase runs a full Chrome browser
- Requires ~500MB RAM per extraction
- Cannot run on serverless (Vercel, Lambda)
- Works on: Railway, Render, VPS, Docker

### 3. Detection Evolution

- Cloudflare continuously improves detection
- SeleniumBase may need updates
- Some hosts may add additional protection

### 4. Not Supported

- reCAPTCHA (requires human interaction or paid service)
- hCaptcha (same as above)
- Sites requiring login/account

---

## Summary

| Approach                 | Works? | Cost             |
| ------------------------ | ------ | ---------------- |
| Regular Selenium         | ❌     | Free             |
| cloudscraper             | ❌     | Free             |
| Playwright + Stealth     | ❌     | Free             |
| undetected-chromedriver  | ❌     | Free             |
| **SeleniumBase UC Mode** | ✅     | **Free**         |
| 2Captcha / Anti-Captcha  | ✅     | $2-3/1000 solves |
| Capsolver                | ✅     | $1-2/1000 solves |

**SeleniumBase UC mode is the only FREE solution that works for Cloudflare JS Challenge bypass.**

---

## References

- [SeleniumBase Documentation](https://seleniumbase.io/)
- [SeleniumBase UC Mode](https://seleniumbase.io/help_docs/uc_mode/)
- [Dev.to Article on Cloudflare Bypass](https://dev.to/luisgustvo/how-to-bypass-cloudflare-js-challenge-for-web-scraping-and-automation-1048)
