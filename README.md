# 🎬 Movies Download API

FastAPI service that extracts direct download links from Arabic streaming sites (EgyDead, etc.).

**100% FREE** - No paid services, no API keys required!

## ✨ Features

- 🎯 Extracts direct CDN download links (MP4, MKV)
- 🎬 Gets movie info (title, year, quality)
- 🔗 Supports multiple hosts (streamruby, hgcloud, forafile, etc.)
- 🛡️ Anti-detection with stealth browser mode
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
  "message": "Extracted 3 links (3 direct)",
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
      "host": "streamruby.com",
      "direct_link": "https://streamruby.com/cdn-cgi/content?id=...",
      "is_direct": true
    },
    {
      "host": "hgcloud.to",
      "direct_link": "https://...premilkyway.com/.../Movie.1080p.BluRay.mp4?t=...",
      "is_direct": true
    }
  ],
  "total_links": 3,
  "direct_links_count": 3
}
```

## 🔧 How It Works

```
Movie Page (egydead.live)
    ↓ Click "المشاهده والتحميل" button
    ↓ Find all "حمل الان" links
Host Pages (streamruby, hgcloud, etc.)
    ↓ Navigate through quality/download pages
    ↓ Extract hidden CDN links from HTML/JS
Direct Download Links (premilkyway.com, cdn, etc.)
```

## 🖥️ Requirements

- Python 3.8+
- Chrome browser installed
- ChromeDriver (auto-managed by selenium)

## 📦 Dependencies

```
fastapi
uvicorn
selenium
beautifulsoup4
requests
```

**Optional (for better anti-detection):**

```
undetected-chromedriver
```

## 🚀 Deployment

> ⚠️ **Note:** This API uses Selenium which requires a browser. It won't work on serverless platforms like Vercel.

### Recommended Platforms:

- **Railway** (free tier) - supports Docker
- **Render** (free tier) - supports Docker
- **VPS** (DigitalOcean, Linode, etc.)

## 📄 License

MIT

## 👤 Author

[Walidhamdy44](https://github.com/Walidhamdy44)
