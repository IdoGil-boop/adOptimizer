"""Celery worker configuration and task definitions."""

import logging
from datetime import datetime, timedelta

from celery import Celery
from celery.schedules import crontab
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_sync_db
from app.google_ads.client import create_google_ads_client
from app.google_ads.ingestion import ingest_ads_with_90d_metrics, ingest_keywords
from app.google_ads.queries import fetch_ads_with_metrics_90d, fetch_keywords
from app.analysis.scoring import classify_ads_by_performance
from app.models import ConnectedAccount, SyncRun, SyncStatus

settings = get_settings()
logger = logging.getLogger(__name__)

# Initialize Celery app
celery_app = Celery(
    "google_ads_optimizer",
    broker=settings.redis_url_str,
    backend=settings.redis_url_str,
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=1800,  # 30 minutes max per task
    task_soft_time_limit=1500,  # 25 minutes soft limit
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    task_routes={
        "app.worker.sync_account_data": {"queue": "sync"},
        "app.worker.generate_suggestions_for_account": {"queue": "generation"},
        "app.worker.schedule_all_account_syncs": {"queue": "scheduler"},
    },
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "schedule-nightly-syncs": {
        "task": "app.worker.schedule_all_account_syncs",
        "schedule": crontab(
            hour=settings.SYNC_SCHEDULE_HOUR,
            minute=settings.SYNC_SCHEDULE_MINUTE,
        ),
        "options": {"queue": "scheduler"},
    },
}


@celery_app.task(
    bind=True,
    name="app.worker.sync_account_data",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 300},  # Retry after 5 minutes
    retry_backoff=True,
    retry_backoff_max=3600,  # Max 1 hour backoff
    retry_jitter=True,
)
def sync_account_data(self, account_id: int, days: int = 90) -> dict:
    """
    Sync Google Ads data for a connected account.

    Pulls ads, metrics, and keywords for the specified period.
    Uses Celery's retry mechanism with exponential backoff.
    """
    db = get_sync_db()
    sync_run = None

    try:
        logger.info(f"Starting sync for account {account_id}, task {self.request.id}")

        # Get account
        account = db.query(ConnectedAccount).filter(ConnectedAccount.id == account_id).first()
        if not account:
            logger.error(f"Account {account_id} not found")
            return {"status": "error", "message": "Account not found"}

        if not account.is_active:
            logger.info(f"Account {account_id} is inactive, skipping sync")
            return {"status": "skipped", "message": "Account inactive"}

        # Create sync run record
        sync_run = SyncRun(
            account_id=account_id,
            celery_task_id=self.request.id,
            status=SyncStatus.RUNNING,
            started_at=datetime.utcnow(),
        )
        db.add(sync_run)
        db.commit()

        # Calculate date range
        period_end = datetime.utcnow()
        period_start = period_end - timedelta(days=days)

        logger.info(
            f"Syncing account {account.customer_id} from {period_start.date()} to {period_end.date()}"
        )

        # Create Google Ads client
        client = create_google_ads_client(account, db)

        # Fetch ads with 90d metrics
        logger.info(f"Fetching ads with {days}-day metrics for {account.customer_id}")
        ads_data = fetch_ads_with_metrics_90d(client, account.customer_id, days)
        logger.info(f"Fetched {len(ads_data)} ad records")

        # Ingest ads data
        ads_count = ingest_ads_with_90d_metrics(
            db, account_id, ads_data, period_start, period_end
        )

        # Fetch keywords (best-effort)
        try:
            logger.info(f"Fetching keywords for {account.customer_id}")
            keywords_data = fetch_keywords(client, account.customer_id)
            keywords_count = ingest_keywords(db, keywords_data)
            logger.info(f"Ingested {keywords_count} keywords")
        except Exception as e:
            logger.warning(f"Keywords ingestion failed (non-critical): {e}")
            keywords_count = 0

        # Run ad performance scoring automatically
        try:
            logger.info(f"Running ad performance scoring for account {account_id}")
            scoring_result = classify_ads_by_performance(db, account_id)
            logger.info(
                f"Scoring complete: {scoring_result.get('best_count', 0)} best, "
                f"{scoring_result.get('worst_count', 0)} worst, "
                f"{scoring_result.get('unknown_count', 0)} unknown ads"
            )
        except Exception as e:
            logger.warning(f"Ad scoring failed (non-critical): {e}", exc_info=True)
            # Don't fail the sync if scoring fails

        # Update sync run status
        sync_run.status = SyncStatus.SUCCESS
        sync_run.completed_at = datetime.utcnow()
        sync_run.ads_synced = ads_count
        db.commit()

        # Update account metadata
        account.last_sync_at = datetime.utcnow()
        account.last_sync_status = SyncStatus.SUCCESS
        account.last_sync_error = None
        db.commit()

        result = {
            "status": "success",
            "account_id": account_id,
            "customer_id": account.customer_id,
            "ads_synced": ads_count,
            "keywords_synced": keywords_count,
            "sync_run_id": sync_run.id,
            "duration_seconds": (
                sync_run.completed_at - sync_run.started_at
            ).total_seconds(),
        }

        logger.info(f"Sync completed successfully for account {account_id}: {result}")
        return result

    except Exception as e:
        logger.error(f"Sync failed for account {account_id}: {e}", exc_info=True)

        # Update sync run with error
        if sync_run:
            sync_run.status = SyncStatus.FAILED
            sync_run.completed_at = datetime.utcnow()
            sync_run.error_message = str(e)
            db.commit()

        # Update account with error
        if account:
            account.last_sync_status = SyncStatus.FAILED
            account.last_sync_error = str(e)
            db.commit()

        # Retry or fail
        if self.request.retries < self.max_retries:
            logger.info(
                f"Retrying sync for account {account_id} (attempt {self.request.retries + 1}/{self.max_retries})"
            )
            raise  # Let Celery handle retry
        else:
            logger.error(f"Max retries reached for account {account_id}, giving up")
            return {
                "status": "error",
                "account_id": account_id,
                "message": str(e),
                "retries": self.request.retries,
            }

    finally:
        db.close()


@celery_app.task(
    name="app.worker.schedule_all_account_syncs",
    bind=True,
    time_limit=300,  # 5 minutes to schedule all
)
def schedule_all_account_syncs(self) -> dict:
    """
    Schedule sync tasks for all active connected accounts.

    This runs nightly via Celery Beat and creates individual sync tasks.
    Uses locking to prevent duplicate scheduled syncs.
    """
    db = get_sync_db()

    try:
        logger.info("Starting scheduled sync for all active accounts")

        # Get all active accounts
        accounts = (
            db.query(ConnectedAccount)
            .filter(ConnectedAccount.is_active == True)
            .all()
        )

        if not accounts:
            logger.info("No active accounts to sync")
            return {"status": "success", "accounts_scheduled": 0}

        scheduled_count = 0
        skipped_count = 0
        errors = []

        for account in accounts:
            try:
                # Check if there's already a running sync for this account
                recent_sync = (
                    db.query(SyncRun)
                    .filter(
                        SyncRun.account_id == account.id,
                        SyncRun.status == SyncStatus.RUNNING,
                        SyncRun.started_at > datetime.utcnow() - timedelta(hours=2),
                    )
                    .first()
                )

                if recent_sync:
                    logger.info(
                        f"Skipping account {account.id} ({account.customer_id}): sync already running"
                    )
                    skipped_count += 1
                    continue

                # Schedule sync task
                sync_account_data.apply_async(
                    args=[account.id],
                    kwargs={"days": 90},
                    queue="sync",
                )

                scheduled_count += 1
                logger.info(
                    f"Scheduled sync for account {account.id} ({account.customer_id})"
                )

            except Exception as e:
                logger.error(
                    f"Failed to schedule sync for account {account.id}: {e}",
                    exc_info=True,
                )
                errors.append({"account_id": account.id, "error": str(e)})

        result = {
            "status": "success",
            "accounts_scheduled": scheduled_count,
            "accounts_skipped": skipped_count,
            "total_accounts": len(accounts),
            "errors": errors,
        }

        logger.info(f"Scheduled sync completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Failed to schedule account syncs: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="app.worker.sync_account_on_demand",
    time_limit=1800,  # 30 minutes
)
def sync_account_on_demand(self, account_id: int) -> dict:
    """
    On-demand sync triggered by user action.

    Similar to scheduled sync but with immediate execution priority.
    """
    logger.info(f"On-demand sync requested for account {account_id}")
    return sync_account_data(account_id, days=90)


@celery_app.task(
    bind=True,
    name="app.worker.generate_suggestions_for_account",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2, "countdown": 600},
    retry_backoff=True,
)
def generate_suggestions_for_account(self, account_id: int) -> dict:
    """
    Generate ad copy suggestions for worst-performing ads in an account.

    This is a placeholder - the actual implementation will use OpenAI + embeddings.
    Will be implemented in the generation module.
    """
    logger.info(f"Suggestion generation for account {account_id} - placeholder")
    # TODO: Implement in app.generation.generator module
    return {
        "status": "pending_implementation",
        "account_id": account_id,
        "message": "Suggestion generation will be implemented in generation module",
    }


# Health check task
@celery_app.task(name="app.worker.health_check")
def health_check() -> dict:
    """Health check task for monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "worker": "google_ads_optimizer",
    }
