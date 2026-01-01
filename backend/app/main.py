"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routes import accounts, ads, auth, health, oauth, suggestions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Starting Google Ads Optimizer API")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"CORS origins: {settings.cors_origins_list}")
    yield
    logger.info("Shutting down Google Ads Optimizer API")


# Create FastAPI app
app = FastAPI(
    title="Google Ads Optimizer API",
    description="Production-grade API for analyzing and optimizing Google Ads copy",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Catch-all exception handler to prevent leaking sensitive info."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    if settings.is_production:
        # Don't leak details in production
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
    else:
        # Show details in development
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": type(exc).__name__},
        )


# Include routers
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(oauth.router, prefix="/oauth", tags=["OAuth"])
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(accounts.router, prefix="/accounts", tags=["Accounts"])
app.include_router(ads.router, prefix="/ads", tags=["Ads"])
app.include_router(suggestions.router, prefix="/suggestions", tags=["Suggestions"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Google Ads Optimizer API",
        "version": "0.1.0",
        "status": "operational",
        "environment": settings.ENVIRONMENT,
    }
