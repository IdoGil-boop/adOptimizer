"""Ad performance scoring and bucketing logic."""

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Ad, AdBucket, AdGroup, AdMetrics90d, Campaign

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ScoringConfig:
    """Configuration for ad scoring algorithm."""

    min_impressions: int = settings.MIN_IMPRESSIONS_FOR_SCORING
    min_clicks: int = settings.MIN_CLICKS_FOR_SCORING

    # Weights for composite score (must sum to 1.0)
    weight_ctr: float = 0.25
    weight_conversion_rate: float = 0.35
    weight_cost_per_conversion: float = 0.25
    weight_volume: float = 0.15  # Reward volume to avoid low-sample bias

    # Percentile thresholds for best/worst classification
    best_percentile: float = 0.80  # Top 20%
    worst_percentile: float = 0.20  # Bottom 20%


@dataclass
class AdScore:
    """Ad performance score with explanation."""

    ad_id: int
    score: float
    bucket: AdBucket
    explanation: str
    metrics: dict

    def __lt__(self, other: "AdScore") -> bool:
        """Enable sorting by score."""
        return self.score < other.score


def compute_ad_score(ad: Ad, metrics: AdMetrics90d, config: ScoringConfig) -> Optional[AdScore]:
    """
    Compute composite performance score for an ad.

    Returns None if ad doesn't meet minimum volume thresholds.
    """
    # Check minimum thresholds
    if metrics.impressions < config.min_impressions:
        return AdScore(
            ad_id=ad.id,
            score=0.0,
            bucket=AdBucket.UNKNOWN,
            explanation=f"Insufficient impressions ({metrics.impressions} < {config.min_impressions})",
            metrics={},
        )

    if metrics.clicks < config.min_clicks:
        return AdScore(
            ad_id=ad.id,
            score=0.0,
            bucket=AdBucket.UNKNOWN,
            explanation=f"Insufficient clicks ({metrics.clicks} < {config.min_clicks})",
            metrics={},
        )

    # Extract metrics
    ctr = metrics.ctr or 0.0
    conversion_rate = metrics.conversion_rate or 0.0
    cost_per_conversion = metrics.cost_per_conversion

    # Normalize cost_per_conversion (lower is better, so invert)
    # Use 0 if no conversions
    if cost_per_conversion and cost_per_conversion > 0:
        # Inverse normalized score (0-1 range)
        # Cap at $500 for normalization
        cost_score = max(0, 1 - (cost_per_conversion / 500.0))
    else:
        # No conversions = 0 score for this component
        cost_score = 0.0

    # Normalize CTR (typical range 0-20%)
    ctr_score = min(1.0, ctr / 20.0)

    # Normalize conversion rate (typical range 0-20%)
    cvr_score = min(1.0, conversion_rate / 20.0)

    # Volume score (log scale to handle wide range)
    # Normalize impressions on log scale
    import math

    volume_score = min(1.0, math.log10(metrics.impressions) / 6.0)  # 10^6 = max

    # Compute weighted composite score
    composite_score = (
        config.weight_ctr * ctr_score
        + config.weight_conversion_rate * cvr_score
        + config.weight_cost_per_conversion * cost_score
        + config.weight_volume * volume_score
    )

    # Build explanation
    explanation_parts = [
        f"CTR: {ctr:.2f}% (score: {ctr_score:.2f})",
        f"CVR: {conversion_rate:.2f}% (score: {cvr_score:.2f})",
        f"CPA: ${cost_per_conversion:.2f} (score: {cost_score:.2f})" if cost_per_conversion else "CPA: N/A",
        f"Volume: {metrics.impressions:,} imp (score: {volume_score:.2f})",
        f"Composite: {composite_score:.3f}",
    ]
    explanation = " | ".join(explanation_parts)

    return AdScore(
        ad_id=ad.id,
        score=composite_score,
        bucket=AdBucket.UNKNOWN,  # Set later after percentile calculation
        explanation=explanation,
        metrics={
            "impressions": metrics.impressions,
            "clicks": metrics.clicks,
            "ctr": ctr,
            "conversion_rate": conversion_rate,
            "cost_per_conversion": cost_per_conversion,
            "conversions": metrics.conversions,
        },
    )


def classify_ads_by_performance(
    db: Session, account_id: int, config: Optional[ScoringConfig] = None
) -> dict:
    """
    Score and classify all ads for an account into best/worst/unknown buckets.

    Returns summary statistics.
    """
    if config is None:
        config = ScoringConfig()

    logger.info(f"Classifying ads for account {account_id}")

    # Get all ads with metrics for this account
    query = (
        select(Ad, AdMetrics90d)
        .join(AdMetrics90d, Ad.id == AdMetrics90d.ad_id)
        .join(AdGroup, Ad.ad_group_id == AdGroup.id)
        .join(Campaign, AdGroup.campaign_id == Campaign.id)
        .filter(Campaign.account_id == account_id)
        .filter(Ad.status == "ENABLED")
    )

    results = db.execute(query).all()
    logger.info(f"Found {len(results)} ads with metrics for account {account_id}")

    # Compute scores for all ads
    # Always do relative classification, even if ads don't meet thresholds
    all_scores = []
    for ad, metrics in results:
        score = compute_ad_score(ad, metrics, config)
        if score:
            all_scores.append(score)
    
    if not all_scores:
        logger.warning(f"No ads with metrics found for account {account_id}")
        return {
            "account_id": account_id,
            "total_ads": len(results),
            "best_count": 0,
            "worst_count": 0,
            "unknown_count": 0,
        }
    
    # Use all scores for relative classification (even if they failed thresholds)
    scored_ads = all_scores

    # Sort by score
    scored_ads.sort(reverse=True)  # High scores first

    # Calculate percentile thresholds
    # Ensure at least 1 ad is classified as best/worst if we have scored ads
    best_threshold_idx = max(1, int(len(scored_ads) * (1 - config.best_percentile)))
    worst_threshold_idx = max(1, int(len(scored_ads) * config.worst_percentile))
    
    # Cap at total ads (can't have more best/worst than total)
    best_threshold_idx = min(best_threshold_idx, len(scored_ads))
    worst_threshold_idx = min(worst_threshold_idx, len(scored_ads))
    
    # Ensure best and worst don't overlap (if we have few ads)
    if best_threshold_idx + worst_threshold_idx > len(scored_ads):
        # Split evenly, favoring worst if odd number
        mid_point = len(scored_ads) // 2
        best_threshold_idx = max(1, mid_point)
        worst_threshold_idx = max(1, len(scored_ads) - mid_point)

    # Classify into buckets
    best_ads = scored_ads[:best_threshold_idx]
    worst_ads = scored_ads[-worst_threshold_idx:]
    
    # Remove overlap (if an ad is in both, prefer best)
    worst_ads = [ad for ad in worst_ads if ad not in best_ads]
    
    # Remaining ads go to unknown
    remaining_ads = [ad for ad in scored_ads if ad not in best_ads and ad not in worst_ads]
    unknown_ads = remaining_ads

    # Update database
    for score in best_ads:
        score.bucket = AdBucket.BEST
        ad = db.query(Ad).filter(Ad.id == score.ad_id).first()
        if ad:
            ad.bucket = AdBucket.BEST
            ad.bucket_score = score.score
            ad.bucket_explanation = f"TOP {config.best_percentile*100:.0f}% | {score.explanation}"

    for score in worst_ads:
        score.bucket = AdBucket.WORST
        ad = db.query(Ad).filter(Ad.id == score.ad_id).first()
        if ad:
            ad.bucket = AdBucket.WORST
            ad.bucket_score = score.score
            ad.bucket_explanation = f"BOTTOM {config.worst_percentile*100:.0f}% | {score.explanation}"

    for score in unknown_ads:
        ad = db.query(Ad).filter(Ad.id == score.ad_id).first()
        if ad:
            ad.bucket = AdBucket.UNKNOWN
            ad.bucket_score = score.score
            ad.bucket_explanation = score.explanation

    db.commit()

    result = {
        "account_id": account_id,
        "total_ads": len(results),
        "scored_ads": len(scored_ads),
        "best_count": len(best_ads),
        "worst_count": len(worst_ads),
        "unknown_count": len(unknown_ads),
        "best_threshold_score": best_ads[-1].score if best_ads else None,
        "worst_threshold_score": worst_ads[0].score if worst_ads else None,
    }

    logger.info(f"Classification complete for account {account_id}: {result}")
    return result


def get_best_ads(db: Session, account_id: int, limit: int = 20) -> list[Ad]:
    """Get top-performing ads for an account."""
    query = (
        select(Ad)
        .join(AdGroup, Ad.ad_group_id == AdGroup.id)
        .join(Campaign, AdGroup.campaign_id == Campaign.id)
        .filter(Campaign.account_id == account_id)
        .filter(Ad.bucket == AdBucket.BEST)
        .order_by(Ad.bucket_score.desc())
        .limit(limit)
    )

    return db.execute(query).scalars().all()


def get_worst_ads(db: Session, account_id: int, limit: int = 20) -> list[Ad]:
    """Get worst-performing ads for an account."""
    query = (
        select(Ad)
        .join(AdGroup, Ad.ad_group_id == AdGroup.id)
        .join(Campaign, AdGroup.campaign_id == Campaign.id)
        .filter(Campaign.account_id == account_id)
        .filter(Ad.bucket == AdBucket.WORST)
        .order_by(Ad.bucket_score.asc())
        .limit(limit)
    )

    return db.execute(query).scalars().all()


def explain_ad_performance(ad: Ad, metrics: AdMetrics90d) -> str:
    """Generate human-readable explanation of ad performance."""
    if not metrics:
        return "No metrics available"

    parts = [
        f"Impressions: {metrics.impressions:,}",
        f"Clicks: {metrics.clicks:,}",
        f"CTR: {metrics.ctr:.2f}%" if metrics.ctr else "CTR: N/A",
        f"Conversions: {metrics.conversions:.1f}",
        f"CVR: {metrics.conversion_rate:.2f}%" if metrics.conversion_rate else "CVR: 0%",
        f"CPA: ${metrics.cost_per_conversion:.2f}"
        if metrics.cost_per_conversion
        else "CPA: N/A",
        f"Cost: ${metrics.cost_micros / 1_000_000:.2f}",
    ]

    explanation = " | ".join(parts)

    if ad.bucket == AdBucket.BEST:
        explanation = f"✅ BEST PERFORMER | {explanation}"
    elif ad.bucket == AdBucket.WORST:
        explanation = f"⚠️ NEEDS IMPROVEMENT | {explanation}"
    else:
        explanation = f"ℹ️ INSUFFICIENT DATA | {explanation}"

    return explanation
