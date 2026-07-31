"""
FastAPI Application - Movie Download Link Extractor API
Using MongoDB for persistence.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import connect_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - connect/disconnect MongoDB."""
    # Startup
    await connect_db()
    yield
    # Shutdown
    await close_db()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    
    app = FastAPI(
        title=settings.APP_NAME,
        description="API for extracting download links from movie streaming sites with Cloudflare bypass",
        version="2.0.0",
        lifespan=lifespan,
    )
    
    # CORS
    origins = settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS else ["*"]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    from app.routes import extract, health, auth, movies
    
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(movies.router)
    app.include_router(extract.router)
    
    @app.get("/")
    async def root():
        return {
            "app": settings.APP_NAME,
            "version": "2.0.0",
            "database": "MongoDB",
            "docs": "/docs",
        }
    
    return app


# Create app instance
app = create_app()
