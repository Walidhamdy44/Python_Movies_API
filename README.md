# 🎬 Movies Download API

FastAPI service that extracts direct download links from Arabic streaming sites (EgyDead, etc.).

**100% FREE** - No paid services, no API keys required!

## ✨ Features

- 🎯 Extracts direct CDN download links (MP4, MKV)
- 🛡️ **Cloudflare Bypass** using SeleniumBase UC mode
- 🎬 Gets movie info (title, year, quality)
- 🔗 Supports multiple hosts (megaup, streamruby, hgcloud, forafile, etc.)
- ⚡ FastAPI with auto-generated docs

## 🚀 API Endpoints

| Method | Endpoint                   | Description            |
| ------ | -------------------------- | ---------------------- |
| `GET`  | `/`                        | Health check           |
| `GET`  | `/extract?url=...&limit=N` | Extract download links |
| `POST` | `/extract`                 | Same as GET            |
| `GET`  | `/docs`                    | Swagger UI             |

## 📦 Installation

```bash
# Clone
git clone https://github.com/Walidhamdy44/Python_Movies_API.git
cd Python_Movies_API

# Install dependencies
pip install -r requirements.txt

# Run
python -m uvicorn api:app --host 0.0.0.0 --port 8000
```

## 📝 Usage

### Extract Download Links

```bash
GET /extract?url=https://tv10.egydead.live/movie-name/&limit=5
```

### Response

```json
{
  "success": true,
  "message": "Extracted 5 links (1 direct)",
  "url": "https://tv10.egydead.live/avatar-3-fire-and-ash-2025-1080p-bluray/",
  "movie": {
    "title": "Avatar 3 Fire And Ash 2025",
    "year": "2025",
    "quality": "1080P",
    "image": null,
    "genres": []
  },
  "download_links": [
    {
      "host": "megaup.net",
      "direct_link": "https://megadl.boats/download/Movie.1080p.mp4?download_token=...",
      "is_direct": true
    },
    {
      "host": "streamruby.com",
      "direct_link": "https://streamruby.com/d/abc123",
      "is_direct": false
    }
  ],
  "total_links": 5,
  "direct_links_count": 1
}
```

## 🔧 How It Works

```
Movie Page (egydead.live)
    ↓ Click "المشاهده والتحميل" button
    ↓ Find all "حمل الان" links
Host Pages (megaup, streamruby, hgcloud, etc.)
    ↓ SeleniumBase UC mode bypasses Cloudflare
    ↓ Extract CDN links from HTML
Direct Download Links (megadl.boats, premilkyway.com, etc.)
```

## 🛡️ Cloudflare Bypass

This API uses **SeleniumBase** with UC (Undetected Chrome) mode to bypass Cloudflare's JavaScript challenge on download hosts like megaup.net. This is the only free method that works reliably.

### What Works:

- ✅ **megaup.net** → Extracts direct `megadl.boats` CDN links
- ⏳ streamruby.com → Page loads but may need additional steps
- ⏳ hgcloud.to → Page loads but may need additional steps

## 🖥️ Requirements

- Python 3.8+
- Chrome browser installed
- SeleniumBase (auto-manages ChromeDriver)

## 📦 Dependencies

```
seleniumbase>=4.23.0
fastapi>=0.100.0
uvicorn[standard]>=0.22.0
beautifulsoup4>=4.11.0
pydantic>=2.0.0
```

## 🚀 Deployment

> ⚠️ **Note:** This API uses Selenium which requires a browser. It won't work on serverless platforms like Vercel.

### Docker (Railway/Render)

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y wget gnupg unzip curl xvfb
RUN wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y /tmp/chrome.deb && rm /tmp/chrome.deb
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN seleniumbase install chromedriver
COPY . .
EXPOSE 8000
CMD uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}
```

### Recommended Platforms:

- **Railway** (free tier) - supports Docker
- **Render** (free tier) - supports Docker
- **VPS** (DigitalOcean, Linode, etc.)

## ⚡ Performance Notes

- First request takes ~30-60 seconds (browser startup + Cloudflare wait)
- Each download link processing takes ~10-20 seconds
- Use `limit` parameter to speed up extraction (e.g., `?limit=3`)

## 📄 License

MIT

## 👤 Author

[Walidhamdy44](https://github.com/Walidhamdy44)
