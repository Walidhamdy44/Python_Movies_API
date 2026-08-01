"""
API entry point for uvicorn.
Usage: uvicorn api:app --host 0.0.0.0 --port 8000
"""

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from app.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
