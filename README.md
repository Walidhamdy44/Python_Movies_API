# 🎬 Movie Hub - Backend API

FastAPI service that extracts direct download links from Arabic streaming sites (EgyDead, etc.) with user authentication and movie management.

**100% FREE** - No paid services, no API keys required!

## 📖 Documentation

- **[How We Bypassed Cloudflare](docs/How-We-Bypassed-Cloudflare.md)** - Technical deep-dive into the Cloudflare bypass implementation

---

## 📁 Project Structure

```
BE/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app factory
│   ├── config.py            # Settings & environment config
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── jwt_handler.py   # JWT authentication
│   │   └── api_key.py       # API key authentication
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py    # SQLite database setup
│   │   └── models.py        # SQLAlchemy models
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py       # Pydantic models
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── health.py        # Health check endpoint
│   │   ├── auth.py          # User authentication routes
│   │   ├── movies.py        # Movies CRUD endpoints
│   │   └── extract.py       # Extraction endpoints
│   └── services/
│       ├── __init__.py
│       └── extractor.py     # SeleniumBase extraction logic
├── docs/
│   └── How-We-Bypassed-Cloudflare.md
├── api.py                   # Uvicorn entry point
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

## ✨ Features

- 🎯 Extracts direct CDN download links (MP4, MKV)
- 🛡️ **Cloudflare Bypass** using SeleniumBase UC mode
- 🔐 **JWT Authentication** with admin roles
- 🗄️ **SQLite Database** - File-based, never shuts down
- 🎬 Gets movie info (title, year, quality)
- 🔗 Supports multiple hosts (megaup, streamruby, hgcloud, etc.)
- ⚡ FastAPI with auto-generated docs

## 🚀 API Endpoints

### Authentication

| Method | Endpoint         | Auth Required | Description                            |
| ------ | ---------------- | ------------- | -------------------------------------- |
| `POST` | `/auth/register` | No            | Register new user (first user = admin) |
| `POST` | `/auth/login`    | No            | User login                             |
| `GET`  | `/auth/me`       | Yes           | Get current user                       |

### Movies (CRUD)

| Method   | Endpoint              | Auth Required | Description             |
| -------- | --------------------- | ------------- | ----------------------- |
| `GET`    | `/movies`             | No            | List movies (paginated) |
| `GET`    | `/movies/:id`         | No            | Get single movie        |
| `POST`   | `/movies`             | Admin         | Create movie            |
| `PUT`    | `/movies/:id`         | Admin         | Update movie            |
| `DELETE` | `/movies/:id`         | Admin         | Delete movie            |
| `POST`   | `/movies/:id/extract` | Admin         | Extract download links  |

### Extraction

| Method | Endpoint                   | Auth Required | Description            |
| ------ | -------------------------- | ------------- | ---------------------- |
| `GET`  | `/extract?url=...&limit=N` | Optional\*    | Extract download links |
| `POST` | `/extract`                 | Optional\*    | Same as GET            |

\*Auth required only if `AUTH_ENABLED=true`

### Health & Docs

| Method | Endpoint | Description  |
| ------ | -------- | ------------ |
| `GET`  | `/`      | Health check |
| `GET`  | `/docs`  | Swagger UI   |

## 📦 Installation

```bash
# Navigate to BE folder
cd BE

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Run
python -m uvicorn api:app --host 0.0.0.0 --port 8000
```

## 🔐 Authentication

### JWT Authentication (for Frontend)

Users register and login to get JWT tokens. First registered user becomes admin.

```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","username":"admin","password":"secret123"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"secret123"}'
```

### API Key Authentication (Optional)

For direct API access without user accounts:

1. Edit `.env`:

   ```
   AUTH_ENABLED=true
   API_KEY=your-secret-api-key-here
   ```

2. Use the `X-API-Key` header:
   ```bash
   curl -H "X-API-Key: your-secret-api-key-here" \
     "http://localhost:8000/extract?url=https://tv10.egydead.live/movie-name/"
   ```

## ⚙️ Configuration

All settings via environment variables (`.env` file):

| Variable          | Default                   | Description                         |
| ----------------- | ------------------------- | ----------------------------------- |
| `SECRET_KEY`      | random                    | JWT secret key                      |
| `AUTH_ENABLED`    | `false`                   | Enable API key authentication       |
| `API_KEY`         | `""`                      | Your secret API key                 |
| `CORS_ORIGINS`    | `*`                       | Allowed CORS origins                |
| `DATABASE_URL`    | `sqlite:///./moviehub.db` | Database connection                 |
| `PAGE_LOAD_WAIT`  | `4`                       | Initial page load timeout (seconds) |
| `CLOUDFLARE_WAIT` | `10`                      | Cloudflare bypass wait (seconds)    |

## 📝 Usage Example

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
  ]
}
```

## 🚀 Deployment

### Railway

1. Connect your GitHub repo to Railway
2. Set environment variables in Railway dashboard
3. Deploy!

**Live URL:** https://movies-download-api-production.up.railway.app

### Docker

```bash
docker build -t movies-api .
docker run -p 8000:8000 movies-api
```

## 📄 License

MIT
