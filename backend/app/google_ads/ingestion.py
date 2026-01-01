"""Data ingestion layer for Google Ads API responses."""

##test commit
import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import Ad, AdGroup, AdMetrics90d, AdMetricsDaily, Campaign, Keyword

logger = logging.getLogger(__name__)


def ingest_campaigns(
    db: Session, account_id: int, campaigns_data: list[Any]
) -> dict[str, int]:
    """Ingest campaigns data into database."""
    campaign_map = {}  # Maps campaign_id -> db id

    for row in campaigns_data:
        campaign_id = str(row.campaign.id)

        campaign = (
            db.query(Campaign)
            .filter(
                Campaign.account_id == account_id, Campaign.campaign_id == campaign_id
            )
            .first()
        )

        if campaign:
            # Update existing
            campaign.name = row.campaign.name
            campaign.status = row.campaign.status.name
            campaign.advertising_channel_type = (
                row.campaign.advertising_channel_type.name
                if hasattr(row.campaign, "advertising_channel_type")
                else None
            )
            campaign.updated_at = datetime.utcnow()
        else:
            # Create new
            campaign = Campaign(
                account_id=account_id,
                campaign_id=campaign_id,
                name=row.campaign.name,
                status=row.campaign.status.name,
                advertising_channel_type=(
                    row.campaign.advertising_channel_type.name
                    if hasattr(row.campaign, "advertising_channel_type")
                    else None
                ),
            )
            db.add(campaign)
            db.flush()

        campaign_map[campaign_id] = campaign.id

    db.commit()
    logger.info(f"Ingested {len(campaign_map)} campaigns for account {account_id}")
    return campaign_map


def ingest_ads_with_90d_metrics(
    db: Session,
    account_id: int,
    ads_data: list[Any],
    period_start: datetime,
    period_end: datetime,
) -> int:
    """
    Ingest ads with 90-day aggregated metrics.

    Returns count of ads ingested.
    """
    ads_count = 0
    campaign_map = {}
    ad_group_map = {}

    for row in ads_data:
        try:
            # Extract IDs
            campaign_id = str(row.campaign.id)
            ad_group_id = str(row.ad_group.id)
            ad_id = str(row.ad_group_ad.ad.id)

            # Ensure campaign exists
            if campaign_id not in campaign_map:
                campaign = (
                    db.query(Campaign)
                    .filter(
                        Campaign.account_id == account_id,
                        Campaign.campaign_id == campaign_id,
                    )
                    .first()
                )
                if not campaign:
                    campaign = Campaign(
                        account_id=account_id,
                        campaign_id=campaign_id,
                        name=row.campaign.name,
                        status=row.campaign.status.name,
                        advertising_channel_type=(
                            row.campaign.advertising_channel_type.name
                            if hasattr(row.campaign, "advertising_channel_type")
                            else None
                        ),
                    )
                    db.add(campaign)
                    db.flush()
                campaign_map[campaign_id] = campaign.id

            # Ensure ad group exists
            if ad_group_id not in ad_group_map:
                ad_group = (
                    db.query(AdGroup)
                    .filter(
                        AdGroup.campaign_id == campaign_map[campaign_id],
                        AdGroup.ad_group_id == ad_group_id,
                    )
                    .first()
                )
                if not ad_group:
                    ad_group = AdGroup(
                        campaign_id=campaign_map[campaign_id],
                        ad_group_id=ad_group_id,
                        name=row.ad_group.name,
                        status=row.ad_group.status.name,
                    )
                    db.add(ad_group)
                    db.flush()
                ad_group_map[ad_group_id] = ad_group.id

            # Parse ad content (RSA focus)
            headlines = None
            descriptions = None
            final_urls = None
            ad_type = row.ad_group_ad.ad.type_.name if hasattr(row.ad_group_ad.ad, "type_") else "UNKNOWN"
            
            # Extract creation time
            creation_time = None
            if hasattr(row.ad_group_ad.ad, "creation_time"):
                creation_time_str = str(row.ad_group_ad.ad.creation_time)
                try:
                    # Google Ads API returns timestamp in format: "2024-01-15 10:30:00+00:00" or similar
                    creation_time = datetime.fromisoformat(creation_time_str.replace(" ", "T"))
                except (ValueError, AttributeError):
                    logger.warning(f"Could not parse creation_time: {creation_time_str}")

            if hasattr(row.ad_group_ad.ad, "responsive_search_ad"):
                rsa = row.ad_group_ad.ad.responsive_search_ad
                if rsa:
                    headlines = [
                        {"text": h.text, "pinned_field": str(h.pinned_field) if hasattr(h, "pinned_field") else None}
                        for h in rsa.headlines
                    ]
                    descriptions = [
                        {"text": d.text, "pinned_field": str(d.pinned_field) if hasattr(d, "pinned_field") else None}
                        for d in rsa.descriptions
                    ]

            if hasattr(row.ad_group_ad.ad, "final_urls"):
                final_urls = list(row.ad_group_ad.ad.final_urls)

            # Create or update ad
            ad = db.query(Ad).filter(Ad.ad_id == ad_id).first()
            if ad:
                ad.ad_type = ad_type
                ad.status = row.ad_group_ad.status.name
                ad.headlines = headlines
                ad.descriptions = descriptions
                ad.final_urls = final_urls
                if creation_time:
                    ad.google_ads_created_at = creation_time
                ad.updated_at = datetime.utcnow()
            else:
                ad = Ad(
                    ad_group_id=ad_group_map[ad_group_id],
                    ad_id=ad_id,
                    ad_type=ad_type,
                    status=row.ad_group_ad.status.name,
                    headlines=headlines,
                    descriptions=descriptions,
                    final_urls=final_urls,
                    google_ads_created_at=creation_time,
                )
                db.add(ad)
                db.flush()

            # Store raw response for provenance
            ad.raw_response = {
                "campaign_id": campaign_id,
                "ad_group_id": ad_group_id,
                "ad_id": ad_id,
                "fetched_at": datetime.utcnow().isoformat(),
            }

            # Ingest 90d metrics
            metrics = row.metrics
            metrics_90d = db.query(AdMetrics90d).filter(AdMetrics90d.ad_id == ad.id).first()

            # Compute derived metrics manually (safer for Explorer access)
            ctr = (metrics.clicks / metrics.impressions * 100) if metrics.impressions > 0 else None
            conversion_rate = (metrics.conversions / metrics.clicks * 100) if metrics.clicks > 0 else None
            cost_per_conversion = (
                (metrics.cost_micros / 1_000_000) / metrics.conversions
                if metrics.conversions > 0
                else None
            )

            if metrics_90d:
                metrics_90d.impressions = metrics.impressions
                metrics_90d.clicks = metrics.clicks
                metrics_90d.cost_micros = metrics.cost_micros
                metrics_90d.conversions = metrics.conversions
                metrics_90d.all_conversions = metrics.all_conversions
                metrics_90d.ctr = ctr
                metrics_90d.average_cpc = metrics.average_cpc / 1_000_000 if metrics.average_cpc else None
                metrics_90d.cost_per_conversion = cost_per_conversion
                metrics_90d.conversion_rate = conversion_rate
                metrics_90d.period_start = period_start
                metrics_90d.period_end = period_end
                metrics_90d.updated_at = datetime.utcnow()
            else:
                metrics_90d = AdMetrics90d(
                    ad_id=ad.id,
                    impressions=metrics.impressions,
                    clicks=metrics.clicks,
                    cost_micros=metrics.cost_micros,
                    conversions=metrics.conversions,
                    all_conversions=metrics.all_conversions,
                    ctr=ctr,
                    average_cpc=metrics.average_cpc / 1_000_000 if metrics.average_cpc else None,
                    cost_per_conversion=cost_per_conversion,
                    conversion_rate=conversion_rate,
                    period_start=period_start,
                    period_end=period_end,
                )
                db.add(metrics_90d)

            ads_count += 1

        except Exception as e:
            logger.error(f"Error ingesting ad row: {e}", exc_info=True)
            continue

    db.commit()
    logger.info(f"Ingested {ads_count} ads with 90d metrics for account {account_id}")
    return ads_count


def ingest_daily_metrics(
    db: Session, ads_data: list[Any]
) -> int:
    """Ingest daily ad metrics."""
    metrics_count = 0

    for row in ads_data:
        try:
            ad_id_str = str(row.ad_group_ad.ad.id)
            date = datetime.strptime(str(row.segments.date), "%Y-%m-%d")

            # Find ad in database
            ad = db.query(Ad).filter(Ad.ad_id == ad_id_str).first()
            if not ad:
                logger.warning(f"Ad {ad_id_str} not found, skipping daily metrics")
                continue

            metrics = row.metrics

            # Compute derived metrics
            ctr = (metrics.clicks / metrics.impressions * 100) if metrics.impressions > 0 else None
            conversion_rate = (metrics.conversions / metrics.clicks * 100) if metrics.clicks > 0 else None
            cost_per_conversion = (
                (metrics.cost_micros / 1_000_000) / metrics.conversions
                if metrics.conversions > 0
                else None
            )

            # Upsert daily metrics
            daily_metric = (
                db.query(AdMetricsDaily)
                .filter(AdMetricsDaily.ad_id == ad.id, AdMetricsDaily.date == date)
                .first()
            )

            if daily_metric:
                daily_metric.impressions = metrics.impressions
                daily_metric.clicks = metrics.clicks
                daily_metric.cost_micros = metrics.cost_micros
                daily_metric.conversions = metrics.conversions
                daily_metric.all_conversions = metrics.all_conversions
                daily_metric.ctr = ctr
                daily_metric.average_cpc = metrics.average_cpc / 1_000_000 if metrics.average_cpc else None
                daily_metric.cost_per_conversion = cost_per_conversion
                daily_metric.conversion_rate = conversion_rate
            else:
                daily_metric = AdMetricsDaily(
                    ad_id=ad.id,
                    date=date,
                    impressions=metrics.impressions,
                    clicks=metrics.clicks,
                    cost_micros=metrics.cost_micros,
                    conversions=metrics.conversions,
                    all_conversions=metrics.all_conversions,
                    ctr=ctr,
                    average_cpc=metrics.average_cpc / 1_000_000 if metrics.average_cpc else None,
                    cost_per_conversion=cost_per_conversion,
                    conversion_rate=conversion_rate,
                )
                db.add(daily_metric)

            metrics_count += 1

        except Exception as e:
            logger.error(f"Error ingesting daily metrics row: {e}", exc_info=True)
            continue

    db.commit()
    logger.info(f"Ingested {metrics_count} daily metrics rows")
    return metrics_count


def ingest_keywords(db: Session, keywords_data: list[Any]) -> int:
    """Ingest ad group keywords."""
    keywords_count = 0

    for row in keywords_data:
        try:
            ad_group_id_str = str(row.ad_group.id)
            criterion_id = str(row.ad_group_criterion.criterion_id)

            # Find ad group
            ad_group = db.query(AdGroup).filter(AdGroup.ad_group_id == ad_group_id_str).first()
            if not ad_group:
                logger.warning(f"Ad group {ad_group_id_str} not found, skipping keyword")
                continue

            # Upsert keyword
            keyword = (
                db.query(Keyword)
                .filter(
                    Keyword.ad_group_id == ad_group.id,
                    Keyword.criterion_id == criterion_id,
                )
                .first()
            )

            keyword_text = row.ad_group_criterion.keyword.text
            match_type = (
                row.ad_group_criterion.keyword.match_type.name
                if hasattr(row.ad_group_criterion.keyword, "match_type")
                else None
            )
            status = (
                row.ad_group_criterion.status.name
                if hasattr(row.ad_group_criterion, "status")
                else None
            )
            
            # Extract quality score metrics
            quality_score = None
            creative_quality_score = None
            post_click_quality_score = None
            search_predicted_ctr = None
            
            # Try to extract quality score metrics
            # Note: Quality scores may not be available with Explorer access
            try:
                if hasattr(row.ad_group_criterion, "quality_info") and row.ad_group_criterion.quality_info:
                    quality_info = row.ad_group_criterion.quality_info
                    quality_score = quality_info.quality_score if hasattr(quality_info, "quality_score") else None
                    
                    # Handle enum fields - convert to string
                    if hasattr(quality_info, "creative_quality_score") and quality_info.creative_quality_score:
                        creative_quality_score = (
                            quality_info.creative_quality_score.name
                            if hasattr(quality_info.creative_quality_score, "name")
                            else str(quality_info.creative_quality_score)
                        )
                    
                    if hasattr(quality_info, "post_click_quality_score") and quality_info.post_click_quality_score:
                        post_click_quality_score = (
                            quality_info.post_click_quality_score.name
                            if hasattr(quality_info.post_click_quality_score, "name")
                            else str(quality_info.post_click_quality_score)
                        )
                    
                    if hasattr(quality_info, "search_predicted_ctr") and quality_info.search_predicted_ctr:
                        search_predicted_ctr = (
                            quality_info.search_predicted_ctr.name
                            if hasattr(quality_info.search_predicted_ctr, "name")
                            else str(quality_info.search_predicted_ctr)
                        )
            except Exception as e:
                logger.debug(f"Could not extract quality scores for keyword {criterion_id}: {e}")
                # Quality scores not available - continue without them

            # Build quality score data
            quality_data = {}
            if quality_score is not None:
                quality_data["quality_score"] = quality_score
            if creative_quality_score:
                quality_data["creative_quality_score"] = creative_quality_score
            if post_click_quality_score:
                quality_data["post_click_quality_score"] = post_click_quality_score
            if search_predicted_ctr:
                quality_data["search_predicted_ctr"] = search_predicted_ctr

            if keyword:
                keyword.text = keyword_text
                keyword.match_type = match_type
                keyword.status = status
                if quality_data:
                    keyword.raw_response = quality_data
                keyword.updated_at = datetime.utcnow()
            else:
                keyword = Keyword(
                    ad_group_id=ad_group.id,
                    criterion_id=criterion_id,
                    text=keyword_text,
                    match_type=match_type,
                    status=status,
                    raw_response=quality_data if quality_data else None,
                )
                db.add(keyword)

            keywords_count += 1

        except Exception as e:
            logger.error(f"Error ingesting keyword row: {e}", exc_info=True)
            continue

    db.commit()
    logger.info(f"Ingested {keywords_count} keywords")
    return keywords_count
