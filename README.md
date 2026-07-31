# 🎬 Movies Download API

FastAPI service that extracts direct download links from Arabic streaming sites (EgyDead, etc.).

**100% FREE** - No paid services, no API keys required!

## 📖 Documentation

- **[How We Bypassed Cloudflare](docs/How-We-Bypassed-Cloudflare.md)** - Technical deep-dive into the Cloudflare bypass implementation

---

## 📁 Project Structure

```
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app factory
│   ├── config.py            # Settings & environment config
│   ├── auth/
│   │   ├── __init__.py
│   │   └── api_key.py       # API key authentication
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py       # Pydantic models
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── health.py        # Health check endpoint
│   │   └── extract.py       # Extraction endpoints
│   └── services/
│       ├── __init__.py
│       └── extractor.py     # SeleniumBase extraction logic
├── docs/
│   └── How-We-Bypassed-Cloudflare.md  # Technical documentation
├── api.py                   # Uvicorn entry point
├── requirements.txt
├── Dockerfile
├── .env                     # Environment variables (create from .env.example)
├── .env.example             # Example environment file
├── render.yaml
└── README.md
```

## ✨ Features

- 🎯 Extracts direct CDN download links (MP4, MKV)
- 🛡️ **Cloudflare Bypass** using SeleniumBase UC mode
- 🔐 **Optional API Key Authentication**
- 🎬 Gets movie info (title, year, quality)
- 🔗 Supports multiple hosts (megaup, streamruby, hgcloud, etc.)
- ⚡ FastAPI with auto-generated docs

## 🚀 API Endpoints

| Method | Endpoint                   | Auth Required | Description            |
| ------ | -------------------------- | ------------- | ---------------------- |
| `GET`  | `/`                        | No            | Health check           |
| `GET`  | `/extract?url=...&limit=N` | Yes\*         | Extract download links |
| `POST` | `/extract`                 | Yes\*         | Same as GET            |
| `GET`  | `/docs`                    | No            | Swagger UI             |

\*Auth required only if `AUTH_ENABLED=true`

## 📦 Installation

```bash
# Clone
git clone https://github.com/Walidhamdy44/Python_Movies_API.git
cd Python_Movies_API

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Run (no auth)
python -m uvicorn api:app --host 0.0.0.0 --port 8000

# Run (with auth)
# Edit .env first: AUTH_ENABLED=true, API_KEY=your-secret-key
python -m uvicorn api:app --host 0.0.0.0 --port 8000
```

## 🔐 Authentication

Authentication is **optional** and disabled by default.

### Enable Authentication

1. Copy `.env.example` to `.env`
2. Edit `.env`:
   ```
   AUTH_ENABLED=true
   API_KEY=your-secret-api-key-here
   ```
3. Restart the server

### Generate a Secure API Key

```bash
# Linux/Mac
openssl rand -hex 32

# PowerShell
[System.Guid]::NewGuid().ToString() + [System.Guid]::NewGuid().ToString()
```

### Using the API with Auth

Include the `X-API-Key` header in your requests:

```bash
curl -H "X-API-Key: your-secret-api-key-here" \
  "http://localhost:8000/extract?url=https://tv10.egydead.live/movie-name/"
```

## ⚙️ Configuration

All settings are configured via environment variables (`.env` file):

| Variable                | Default | Description                            |
| ----------------------- | ------- | -------------------------------------- |
| `AUTH_ENABLED`          | `false` | Enable API key authentication          |
| `API_KEY`               | `""`    | Your secret API key                    |
| `CORS_ORIGINS`          | `*`     | Allowed CORS origins (comma-separated) |
| `MAX_WORKERS`           | `3`     | Thread pool size for extractions       |
| `MAX_LIMIT`             | `50`    | Max links per request                  |
| `PAGE_LOAD_WAIT`        | `4`     | Initial page load timeout (seconds)    |
| `CLOUDFLARE_WAIT`       | `10`    | Cloudflare bypass wait (seconds)       |
| `CLOUDFLARE_EXTRA_WAIT` | `15`    | Extra wait if stuck (seconds)          |
| `BUTTON_CLICK_WAIT`     | `4`     | Wait after clicking buttons (seconds)  |

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
    "quality": "1080P"
  },
  "download_links": [
    {
      "host": "megaup.net",
      "direct_link": "https://megadl.boats/download/Movie.1080p.mp4?download_token=...",
      "is_direct": true
    }
  ],
  "total_links": 5,
  "direct_links_count": 1
}
```

## 🛡️ Cloudflare Bypass

This API uses **SeleniumBase** with UC (Undetected Chrome) mode to bypass Cloudflare's JavaScript Challenge.

📖 **[Read the full technical documentation →](docs/How-We-Bypassed-Cloudflare.md)**

### Summary

| Approach                 | Works? | Cost      |
| ------------------------ | ------ | --------- |
| Regular Selenium         | ❌     | Free      |
| cloudscraper             | ❌     | Free      |
| Playwright + Stealth     | ❌     | Free      |
| **SeleniumBase UC Mode** | ✅     | **Free**  |
| Paid CAPTCHA services    | ✅     | $2-3/1000 |

### What Works:

- ✅ **megaup.net** → Extracts direct `megadl.boats` CDN links
- ⏳ streamruby.com → Page loads, additional steps may be needed
- ⏳ hgcloud.to → Page loads, additional steps may be needed

## 🚀 Deployment

### Docker (Railway/Render)

```bash
docker build -t movies-api .
docker run -p 8000:8000 \
  -e AUTH_ENABLED=true \
  -e API_KEY=your-secret-key \
  movies-api
```

### Railway

1. Connect your GitHub repo to Railway
2. Add environment variables in Railway dashboard:
   - `AUTH_ENABLED=true`
   - `API_KEY=your-secret-key`
3. Deploy!

### Render

Use the included `render.yaml` or configure manually.

> ⚠️ **Note:** This API uses Selenium which requires a browser. It won't work on serverless platforms like Vercel or AWS Lambda.

## ⚡ Performance Notes

- First request takes ~30-60 seconds (browser startup + Cloudflare wait)
- Each download link processing takes ~10-20 seconds
- Use `limit` parameter to speed up extraction (e.g., `?limit=3`)
- Requires ~500MB RAM per extraction

## 🔒 Security Notes

- Never commit your `.env` file (it's in `.gitignore`)
- Use strong, random API keys in production
- Rotate API keys periodically
- Consider IP whitelisting for additional security

## 📄 License

MIT

## 👤 Author

[Walidhamdy44](https://github.com/Walidhamdy44)
