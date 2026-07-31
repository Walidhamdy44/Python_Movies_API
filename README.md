# Download Link Extractor with 2Captcha Support

Automatically extracts direct download links from Arabic streaming sites like EgyDead, with automatic captcha solving using 2Captcha.

## Features

- ✅ Finds all "حمل الان" download links
- ✅ Follows multiple intermediate pages automatically
- ✅ Solves reCAPTCHA v2/v3 using 2Captcha service
- ✅ Extracts final direct download URLs (premilkyway, cdn, etc.)

## Installation

```bash
pip install requests beautifulsoup4 selenium
```

## Usage

### Without Captcha Solving

Will stop at the captcha page:

```bash
python download_extractor.py "https://tv10.egydead.live/shelter-2026-1080p-bluray/"
```

### With 2Captcha API Key

Automatically solves captcha and gets direct download link:

```bash
# Using command line argument
python download_extractor.py -k YOUR_2CAPTCHA_API_KEY "https://tv10.egydead.live/shelter-2026-1080p-bluray/"

# Or using environment variable
set CAPTCHA_API_KEY=your_key_here
python download_extractor.py "https://tv10.egydead.live/shelter-2026-1080p-bluray/"
```

### Options

```
-h, --help         Show help
-d, --debug        Enable debug mode
-l, --limit N      Only process first N download links
-k, --key KEY      2Captcha API key
```

### Examples

```bash
# Process first 3 links with captcha solving
python download_extractor.py -k YOUR_KEY -l 3 "https://tv10.egydead.live/movie/"

# Debug mode
python download_extractor.py -d -k YOUR_KEY "https://tv10.egydead.live/movie/"
```

## Getting a 2Captcha API Key

1. Sign up at https://2captcha.com
2. Add funds to your account (~$3 for 1000 captchas)
3. Copy your API key from the dashboard
4. Use it with the `-k` flag or set `CAPTCHA_API_KEY` environment variable

## How It Works

```
Movie Page (egydead.live)
    ↓ Find "حمل الان" links
Host Page (streamruby, hgcloud, etc.)
    ↓ Find quality/download link
    ↓ Follow intermediate pages
Final Page (captcha protected)
    ↓ Solve reCAPTCHA via 2Captcha
Direct Download Link (premilkyway.com, cdn, etc.)
```

## Example Output

```
STEP 1: Finding 'حمل الان' download links
Found 14 download link(s)

STEP 2: Finding quality/download link
Found download item link: https://hgcloud.to/f/ziff8kioqzbk_n

STEP 3: Extracting final download link
[CAPTCHA] Found reCAPTCHA v3
[2CAPTCHA] Submitting reCAPTCHA v3...
[2CAPTCHA] Captcha ID: 12345678
[2CAPTCHA] Waiting for solution...
[2CAPTCHA] ✓ Captcha solved!

✓ DOWNLOAD LINK FOUND AFTER CAPTCHA:
  https://yhqd4yg264.premilkyway.com/vp/01/.../file.mp4?t=...

FINAL RESULTS
1. https://yhqd4yg264.premilkyway.com/vp/01/.../file.mp4?t=...
```

## Cost

2Captcha pricing (as of 2024):

- reCAPTCHA v2: ~$2.99 per 1000 solves
- reCAPTCHA v3: ~$2.99 per 1000 solves

Each download link requires 1 captcha solve.

## Requirements

- Python 3.7+
- Chrome browser
- 2Captcha API key (for automatic captcha solving)
