from app.routes.extract import router as extract_router
from app.routes.health import router as health_router
from app.routes.auth import router as auth_router
from app.routes.movies import router as movies_router

__all__ = ["extract_router", "health_router", "auth_router", "movies_router"]
