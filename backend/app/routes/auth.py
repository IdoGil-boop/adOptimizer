"""Authentication routes (placeholder for future user auth)."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/me")
async def get_current_user():
    """Get current user info (MVP: single default user)."""
    return {
        "id": 1,
        "email": "default@example.com",
        "is_active": True,
    }
