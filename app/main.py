"""
FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import extract_router, health_router, auth_router, movies_router
from app.services import SELENIUMBASE_AVAILABLE

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    from app.database import init_db
    
    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} starting...")
    logger.info(f"   SeleniumBase: {'✓' if SELENIUMBASE_AVAILABLE else '✗'}")
    logger.info(f"   Auth Enabled: {'✓' if settings.AUTH_ENABLED else '✗'}")
    
    # Initialize database
    logger.info("   Initializing database...")
    init_db()
    logger.info("   Database: ✓")
    
    yield
    logger.info("👋 Shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title=settings.APP_NAME,
        description=settings.APP_DESCRIPTION,
        version=settings.APP_VERSION,
        lifespan=lifespan,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(movies_router)
    app.include_router(extract_router)
    
    return app


app = create_app()
