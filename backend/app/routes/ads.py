"""Ads listing and detail routes."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database import get_async_db, sync_engine
from app.google_ads.client import create_google_ads_client
from app.google_ads.queries import fetch_rsa_asset_performance
from app.models import Ad, AdBucket, AdGroup, AdMetrics90d, Campaign, Keyword, ConnectedAccount

logger = logging.getLogger(__name__)
router = APIRouter()


class AdSummary(BaseModel):
    """Ad summary for listing."""

    id: int
    ad_id: str
    ad_type: str
    status: str
    bucket: Optional[str]
    bucket_score: Optional[float]
    campaign_name: str
    ad_group_name: str
    headlines: list[str]
    descriptions: list[str]
    metrics_90d: Optional[dict]


class AdDetail(BaseModel):
    """Detailed ad information."""

    id: int
    ad_id: str
    ad_type: str
    status: str
    bucket: Optional[str]
    bucket_score: Optional[float]
    bucket_explanation: Optional[str]
    campaign_id: str
    campaign_name: str
    ad_group_id: str
    ad_group_name: str
    headlines: Optional[list]
    descriptions: Optional[list]
    final_urls: Optional[list]
    metrics_90d: Optional[dict]
    google_ads_created_at: Optional[str]
    created_at: str
    updated_at: str
    headline_performance: Optional[dict] = None
    keyword_quality_scores: Optional[list] = None


@router.get("/", response_model=list[AdSummary])
async def list_ads(
    account_id: int = Query(..., description="Account ID to filter ads"),
    bucket: Optional[str] = Query(None, description="Filter by bucket: best, worst, unknown, all"),
    limit: int = Query(50, le=200, description="Max results to return"),
    offset: int = Query(0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_async_db),
):
    """List ads for an account with optional bucket filter."""
    try:
        # Build query - join through AdGroup -> Campaign to filter by account_id
        from app.models import AdGroup, Campaign
        
        query = (
            select(Ad, AdMetrics90d)
            .outerjoin(AdMetrics90d, Ad.id == AdMetrics90d.ad_id)
            .join(AdGroup, Ad.ad_group_id == AdGroup.id)
            .join(Campaign, AdGroup.campaign_id == Campaign.id)
            .filter(Campaign.account_id == account_id)
            .options(selectinload(Ad.ad_group).selectinload(AdGroup.campaign))
        )

        # Apply bucket filter
        if bucket and bucket != "all":
            if bucket == "best":
                query = query.filter(Ad.bucket == AdBucket.BEST)
            elif bucket == "worst":
                query = query.filter(Ad.bucket == AdBucket.WORST)
            elif bucket == "unknown":
                query = query.filter(Ad.bucket == AdBucket.UNKNOWN)

        # Order by score (nulls last)
        query = query.order_by(Ad.bucket_score.desc().nullslast())

        # Pagination
        query = query.limit(limit).offset(offset)

        result = await db.execute(query)
        rows = result.all()

        summaries = []
        for ad, metrics in rows:
            # Extract headlines and descriptions
            headlines = []
            if ad.headlines:
                headlines = [h.get("text", "") for h in ad.headlines if isinstance(h, dict)]
            
            descriptions = []
            if ad.descriptions:
                descriptions = [d.get("text", "") for d in ad.descriptions if isinstance(d, dict)]

            # Format metrics
            metrics_dict = None
            if metrics:
                metrics_dict = {
                    "impressions": metrics.impressions,
                    "clicks": metrics.clicks,
                    "ctr": metrics.ctr,
                    "conversions": metrics.conversions,
                    "cvr": metrics.conversion_rate,
                    "cost_micros": metrics.cost_micros,
                    "cost_per_conversion_micros": int(metrics.cost_per_conversion * 1_000_000) if metrics.cost_per_conversion else None,
                }

            summaries.append(
                AdSummary(
                    id=ad.id,
                    ad_id=ad.ad_id,
                    ad_type=ad.ad_type,
                    status=ad.status,
                    bucket=ad.bucket,
                    bucket_score=ad.bucket_score,
                    campaign_name=ad.ad_group.campaign.name,
                    ad_group_name=ad.ad_group.name,
                    headlines=headlines,
                    descriptions=descriptions,
                    metrics_90d=metrics_dict,
                )
            )

        return summaries

    except Exception as e:
        logger.error(f"Failed to list ads: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ad_id}", response_model=AdDetail)
async def get_ad_detail(
    ad_id: int,
    db: AsyncSession = Depends(get_async_db),
):
    """Get detailed information for a specific ad."""
    try:
        # Get ad with metrics and relationships
        # Use explicit column selection to avoid issues with missing columns
        result = await db.execute(
            select(Ad, AdMetrics90d)
            .outerjoin(AdMetrics90d, Ad.id == AdMetrics90d.ad_id)
            .filter(Ad.id == ad_id)
            .options(
                selectinload(Ad.ad_group)
                .selectinload(AdGroup.campaign)
                .selectinload(Campaign.account)
            )
        )
        row = result.first()

        if not row:
            raise HTTPException(status_code=404, detail="Ad not found")

        ad, metrics = row
        
        # Handle missing google_ads_created_at column gracefully
        google_ads_created_at = None
        try:
            google_ads_created_at = ad.google_ads_created_at.isoformat() if ad.google_ads_created_at else None
        except AttributeError:
            # Column doesn't exist in database yet
            pass

        # Extract headlines and descriptions (handle both dict and string formats)
        headlines = []
        if ad.headlines:
            if isinstance(ad.headlines, list):
                headlines = [
                    h.get("text", "") if isinstance(h, dict) else str(h)
                    for h in ad.headlines
                ]
        
        descriptions = []
        if ad.descriptions:
            if isinstance(ad.descriptions, list):
                descriptions = [
                    d.get("text", "") if isinstance(d, dict) else str(d)
                    for d in ad.descriptions
                ]

        # Format metrics to match frontend expectations
        metrics_dict = None
        if metrics:
            metrics_dict = {
                "impressions": metrics.impressions,
                "clicks": metrics.clicks,
                "ctr": metrics.ctr,
                "conversions": metrics.conversions,
                "cvr": metrics.conversion_rate,
                "cost_micros": metrics.cost_micros,
                "cost_per_conversion_micros": int(metrics.cost_per_conversion * 1_000_000) if metrics.cost_per_conversion else None,
                "average_cpc_micros": int(metrics.average_cpc * 1_000_000) if metrics.average_cpc else 0,
            }

        # Fetch keyword quality scores for this ad group
        keyword_quality_scores = []
        try:
            keywords_result = await db.execute(
                select(Keyword).filter(Keyword.ad_group_id == ad.ad_group_id)
            )
            keywords = keywords_result.scalars().all()
            for kw in keywords:
                quality_data = {}
                # Handle missing raw_response column gracefully
                if hasattr(kw, "raw_response") and kw.raw_response:
                    quality_data = kw.raw_response
                keyword_quality_scores.append({
                    "criterion_id": kw.criterion_id,
                    "text": kw.text,
                    "match_type": kw.match_type,
                    "status": kw.status,
                    "quality_score": quality_data.get("quality_score"),
                    "creative_quality_score": quality_data.get("creative_quality_score"),
                    "post_click_quality_score": quality_data.get("post_click_quality_score"),
                    "search_predicted_ctr": quality_data.get("search_predicted_ctr"),
                })
        except Exception as e:
            logger.warning(f"Failed to fetch keyword quality scores (columns may not exist yet): {e}")
            # Continue without quality scores

        # Try to fetch RSA asset performance (optional, may fail for Explorer access)
        headline_performance = None
        try:
            # Get account to create client
            account = ad.ad_group.campaign.account
            from sqlalchemy.orm import sessionmaker
            
            # Create sync session for client creation
            SessionLocal = sessionmaker(bind=sync_engine)
            sync_db = SessionLocal()
            try:
                client = create_google_ads_client(account, sync_db)
                
                # Fetch RSA asset performance
                asset_data = fetch_rsa_asset_performance(
                    client, account.customer_id, ad.ad_id, days=90
                )
                
                # Group by headline/description text
                headline_perf = {}
                desc_perf = {}
                
                for row in asset_data:
                    if hasattr(row, "ad_group_ad_asset_view"):
                        asset_view = row.ad_group_ad_asset_view
                        field_type = asset_view.field_type.name if hasattr(asset_view.field_type, "name") else str(asset_view.field_type)
                        text = ""
                        if hasattr(asset_view, "asset") and asset_view.asset:
                            if hasattr(asset_view.asset, "asset_text_asset"):
                                text = asset_view.asset.asset_text_asset.text
                        
                        metrics = row.metrics if hasattr(row, "metrics") else None
                        perf_data = {
                            "text": text,
                            "impressions": metrics.impressions if metrics else 0,
                            "clicks": metrics.clicks if metrics else 0,
                            "conversions": metrics.conversions if metrics else 0,
                            "cost_micros": metrics.cost_micros if metrics else 0,
                            "ctr": metrics.ctr if metrics else 0,
                        }
                        
                        if field_type == "HEADLINE":
                            if text not in headline_perf:
                                headline_perf[text] = perf_data
                            else:
                                # Aggregate metrics
                                headline_perf[text]["impressions"] += perf_data["impressions"]
                                headline_perf[text]["clicks"] += perf_data["clicks"]
                                headline_perf[text]["conversions"] += perf_data["conversions"]
                                headline_perf[text]["cost_micros"] += perf_data["cost_micros"]
                        elif field_type == "DESCRIPTION":
                            if text not in desc_perf:
                                desc_perf[text] = perf_data
                            else:
                                desc_perf[text]["impressions"] += perf_data["impressions"]
                                desc_perf[text]["clicks"] += perf_data["clicks"]
                                desc_perf[text]["conversions"] += perf_data["conversions"]
                                desc_perf[text]["cost_micros"] += perf_data["cost_micros"]
                
                headline_performance = {
                    "headlines": list(headline_perf.values()),
                    "descriptions": list(desc_perf.values()),
                }
            finally:
                sync_db.close()
        except Exception as e:
            logger.warning(f"Failed to fetch RSA asset performance for ad {ad_id}: {e}")
            # Don't fail the whole request if this fails

        logger.info(
            f"Ad detail response for {ad_id}: "
            f"google_ads_created_at={google_ads_created_at}, "
            f"keyword_quality_scores_count={len(keyword_quality_scores)}, "
            f"headline_performance={headline_performance is not None}"
        )

        return AdDetail(
            id=ad.id,
            ad_id=ad.ad_id,
            ad_type=ad.ad_type,
            status=ad.status,
            bucket=ad.bucket,
            bucket_score=ad.bucket_score,
            bucket_explanation=ad.bucket_explanation,
            campaign_id=str(ad.ad_group.campaign.campaign_id),
            campaign_name=ad.ad_group.campaign.name,
            ad_group_id=str(ad.ad_group.ad_group_id),
            ad_group_name=ad.ad_group.name,
            headlines=headlines,
            descriptions=descriptions,
            final_urls=ad.final_urls,
            metrics_90d=metrics_dict,
            google_ads_created_at=google_ads_created_at,
            created_at=ad.created_at.isoformat(),
            updated_at=ad.updated_at.isoformat(),
            keyword_quality_scores=keyword_quality_scores,
            headline_performance=headline_performance,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get ad detail: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
