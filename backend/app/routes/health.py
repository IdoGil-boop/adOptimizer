"""Health check endpoints."""

from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db

router = APIRouter()


@router.get("/")
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/db")
async def health_check_db():
    """Health check with database connection test."""
    try:
        async for db in get_async_db():
            result = await db.execute(text("SELECT 1"))
            result.scalar()
            return {
                "status": "healthy",
                "database": "connected",
                "timestamp": datetime.utcnow().isoformat(),
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
