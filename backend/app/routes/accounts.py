"""Connected accounts management routes."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_async_db, get_sync_db
from app.models import Ad, AdBucket, ConnectedAccount, SyncRun, SyncStatus
from app.analysis.scoring import classify_ads_by_performance
from app.worker import sync_account_data

logger = logging.getLogger(__name__)
router = APIRouter()


class AccountSummary(BaseModel):
    """Account summary with sync status."""

    id: int
    customer_id: str
    descriptive_name: Optional[str]
    currency_code: Optional[str]
    last_sync_at: Optional[str]
    last_sync_status: Optional[str]
    total_ads: int
    best_ads_count: int
    worst_ads_count: int
    is_active: bool


class SyncResponse(BaseModel):
    """Sync initiation response."""

    success: bool
    message: str
    task_id: Optional[str]


@router.get("/", response_model=list[AccountSummary])
async def list_accounts(db: AsyncSession = Depends(get_async_db)):
    """List all connected accounts with summary stats."""
    try:
        result = await db.execute(select(ConnectedAccount).filter(ConnectedAccount.is_active == True))
        accounts = result.scalars().all()

        summaries = []
        for account in accounts:
            # For now, return 0 for ad counts (will be populated after sync)
            # TODO: Fix the complex query once ads are synced
            summaries.append(
                AccountSummary(
                    id=account.id,
                    customer_id=account.customer_id,
                    descriptive_name=account.descriptive_name,
                    currency_code=account.currency_code,
                    last_sync_at=account.last_sync_at.isoformat() if account.last_sync_at else None,
                    last_sync_status=account.last_sync_status,
                    total_ads=0,
                    best_ads_count=0,
                    worst_ads_count=0,
                    is_active=account.is_active,
                )
            )

        return summaries

    except Exception as e:
        logger.error(f"Failed to list accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{account_id}/sync", response_model=SyncResponse)
async def trigger_sync(
    account_id: int,
    db: AsyncSession = Depends(get_async_db),
):
    """Trigger on-demand sync for an account."""
    try:
        # Verify account exists
        result = await db.execute(
            select(ConnectedAccount).filter(ConnectedAccount.id == account_id)
        )
        account = result.scalar_one_or_none()

        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        if not account.is_active:
            raise HTTPException(status_code=400, detail="Account is inactive")

        # Check for recent running sync
        recent_sync = await db.execute(
            select(SyncRun)
            .filter(
                SyncRun.account_id == account_id,
                SyncRun.status == SyncStatus.RUNNING,
            )
            .order_by(SyncRun.created_at.desc())
            .limit(1)
        )
        recent_sync = recent_sync.scalar_one_or_none()

        if recent_sync:
            return SyncResponse(
                success=False,
                message="Sync already in progress",
                task_id=recent_sync.celery_task_id,
            )

        # Queue sync task
        task = sync_account_data.apply_async(args=[account_id], queue="sync")

        logger.info(f"Queued sync task {task.id} for account {account_id}")

        return SyncResponse(
            success=True,
            message="Sync initiated",
            task_id=task.id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{account_id}/score")
async def trigger_scoring(
    account_id: int,
    db: AsyncSession = Depends(get_async_db),
):
    """Trigger ad performance scoring for an account."""
    try:
        # Verify account exists
        result = await db.execute(
            select(ConnectedAccount).filter(ConnectedAccount.id == account_id)
        )
        account = result.scalar_one_or_none()

        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        if not account.is_active:
            raise HTTPException(status_code=400, detail="Account is inactive")

        # Run scoring using sync session
        sync_db = get_sync_db()
        try:
            result = classify_ads_by_performance(sync_db, account_id)
            return {
                "success": True,
                "message": "Scoring completed",
                "account_id": account_id,
                "total_ads": result.get("total_ads", 0),
                "best_count": result.get("best_count", 0),
                "worst_count": result.get("worst_count", 0),
                "unknown_count": result.get("unknown_count", 0),
            }
        finally:
            sync_db.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to run scoring: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{account_id}")
async def get_account_details(
    account_id: int,
    db: AsyncSession = Depends(get_async_db),
):
    """Get detailed account information."""
    try:
        result = await db.execute(
            select(ConnectedAccount).filter(ConnectedAccount.id == account_id)
        )
        account = result.scalar_one_or_none()

        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Get recent sync runs
        sync_runs = await db.execute(
            select(SyncRun)
            .filter(SyncRun.account_id == account_id)
            .order_by(SyncRun.created_at.desc())
            .limit(10)
        )
        sync_runs = sync_runs.scalars().all()

        return {
            "id": account.id,
            "customer_id": account.customer_id,
            "descriptive_name": account.descriptive_name,
            "currency_code": account.currency_code,
            "time_zone": account.time_zone,
            "last_sync_at": account.last_sync_at.isoformat() if account.last_sync_at else None,
            "last_sync_status": account.last_sync_status,
            "last_sync_error": account.last_sync_error,
            "is_active": account.is_active,
            "recent_syncs": [
                {
                    "id": run.id,
                    "status": run.status,
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                    "ads_synced": run.ads_synced,
                    "error_message": run.error_message,
                }
                for run in sync_runs
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get account details: {e}")
        raise HTTPException(status_code=500, detail=str(e))
