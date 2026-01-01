"""Ad copy suggestion generation routes."""

import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.analysis.scoring import get_best_ads
from app.config import get_settings
from app.database import get_async_db, get_sync_db
from app.generation.embeddings import embed_best_ads, retrieve_exemplars_for_ad
from app.generation.generator import generate_suggestions_for_ad
from app.models import Ad, Suggestion, SuggestionRun

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


class GenerateSuggestionsRequest(BaseModel):
    """Request to generate suggestions for an ad."""

    num_variants: int = 3
    top_k_exemplars: int = 5


class SuggestionVariant(BaseModel):
    """A single suggestion variant."""

    headlines: list[str]
    descriptions: list[str]
    valid: bool
    validation_errors: list[str]
    exemplar_ids: list[int]
    similarity_scores: list[float]


class GenerateSuggestionsResponse(BaseModel):
    """Response with generated suggestions."""

    ad_id: int
    variants: list[SuggestionVariant]
    message: str


class ApplySuggestionRequest(BaseModel):
    """Request to apply a suggestion (create new ad in Google Ads)."""

    suggestion_id: int


class ApplySuggestionResponse(BaseModel):
    """Response for applying a suggestion."""

    success: bool
    message: str
    new_ad_id: Optional[str] = None


@router.post("/{ad_id}/generate", response_model=GenerateSuggestionsResponse)
async def generate_suggestions(
    ad_id: int,
    request: Optional[GenerateSuggestionsRequest] = Body(default=None),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Generate ad copy suggestions for a specific ad.

    Uses embeddings to find similar high-performing ads as exemplars.
    """
    try:
        # Get target ad with relationships
        from sqlalchemy.orm import selectinload
        from app.models import AdGroup, Campaign
        result = await db.execute(
            select(Ad)
            .filter(Ad.id == ad_id)
            .options(
                selectinload(Ad.ad_group).selectinload(AdGroup.campaign)
            )
        )
        target_ad = result.scalar_one_or_none()

        if not target_ad:
            raise HTTPException(status_code=404, detail="Ad not found")

        # Get account_id from ad
        account_id = target_ad.ad_group.campaign.account_id

        # Use default values if request is None
        if request is None:
            request = GenerateSuggestionsRequest()

        # Get best-performing ads for this account (use sync session for heavy ops)
        sync_db = get_sync_db()
        try:
            best_ads = get_best_ads(sync_db, account_id, limit=20)

            if not best_ads:
                return GenerateSuggestionsResponse(
                    ad_id=ad_id,
                    variants=[],
                    message="No high-performing ads found to use as exemplars. Run scoring first.",
                )

            # Generate embeddings for best ads
            best_ads_list, best_embeddings = embed_best_ads(best_ads)

            if not best_ads_list:
                return GenerateSuggestionsResponse(
                    ad_id=ad_id,
                    variants=[],
                    message="Failed to generate embeddings for exemplar ads.",
                )

            # Retrieve exemplars for target ad
            exemplars = retrieve_exemplars_for_ad(
                target_ad, best_ads_list, best_embeddings, top_k=request.top_k_exemplars
            )

            if not exemplars:
                return GenerateSuggestionsResponse(
                    ad_id=ad_id,
                    variants=[],
                    message="Failed to retrieve exemplar ads.",
                )

            # Generate suggestions
            generated_rsas = generate_suggestions_for_ad(
                target_ad, exemplars, num_variants=request.num_variants
            )

            # Convert to response format
            variants = [
                SuggestionVariant(
                    headlines=rsa.headlines,
                    descriptions=rsa.descriptions,
                    valid=rsa.valid,
                    validation_errors=rsa.validation_errors,
                    exemplar_ids=rsa.exemplar_ids,
                    similarity_scores=rsa.similarity_scores,
                )
                for rsa in generated_rsas
            ]

            # Store suggestions in database (async)
            # Create suggestion run
            suggestion_run = SuggestionRun(
                account_id=account_id,
                status="completed",
                ads_processed=1,
                suggestions_generated=len(variants),
            )
            db.add(suggestion_run)
            await db.flush()

            # Store each variant
            for rsa in generated_rsas:
                suggestion = Suggestion(
                    ad_id=target_ad.id,
                    suggestion_run_id=suggestion_run.id,
                    headlines={"items": rsa.headlines},
                    descriptions={"items": rsa.descriptions},
                    prompt_version=rsa.prompt_version,
                    exemplar_ad_ids=rsa.exemplar_ids,
                    similarity_scores=rsa.similarity_scores,
                    model_used=rsa.model_used,
                    applied=False,
                )
                db.add(suggestion)

            await db.commit()

            return GenerateSuggestionsResponse(
                ad_id=ad_id,
                variants=variants,
                message=f"Generated {len(variants)} suggestion(s) successfully",
            )

        finally:
            sync_db.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate suggestions for ad {ad_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ad_id}/apply", response_model=ApplySuggestionResponse)
async def apply_suggestion(
    ad_id: int,
    request: ApplySuggestionRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Apply a suggestion by creating a new ad in Google Ads.

    Feature-flagged - disabled by default for Explorer access.
    """
    if not settings.FEATURE_FLAG_APPLY_SUGGESTIONS:
        raise HTTPException(
            status_code=403,
            detail="Apply suggestions feature is disabled. Enable FEATURE_FLAG_APPLY_SUGGESTIONS to use this.",
        )

    # TODO: Implement actual Google Ads API ad creation
    # This requires Basic/Standard access and proper ad creation flow
    # For now, return feature flag message

    return ApplySuggestionResponse(
        success=False,
        message="Apply suggestions feature is not yet implemented. "
        "This requires Basic/Standard Google Ads API access and is currently disabled for safety.",
    )


@router.get("/{ad_id}")
async def list_suggestions_for_ad(
    ad_id: int,
    db: AsyncSession = Depends(get_async_db),
):
    """List all suggestions generated for a specific ad."""
    try:
        result = await db.execute(
            select(Suggestion).filter(Suggestion.ad_id == ad_id).order_by(Suggestion.created_at.desc())
        )
        suggestions = result.scalars().all()

        result = []
        for s in suggestions:
            # Extract headlines and descriptions from JSON format
            headlines = []
            descriptions = []
            
            if isinstance(s.headlines, dict) and "items" in s.headlines:
                headlines = s.headlines["items"]
            elif isinstance(s.headlines, list):
                headlines = s.headlines
                
            if isinstance(s.descriptions, dict) and "items" in s.descriptions:
                descriptions = s.descriptions["items"]
            elif isinstance(s.descriptions, list):
                descriptions = s.descriptions
            
            # Determine validation status
            validation_passed = True
            validation_errors = []
            
            # Basic validation checks
            if len(headlines) < 3:
                validation_passed = False
                validation_errors.append(f"Too few headlines: {len(headlines)} < 3")
            if len(headlines) > 15:
                validation_passed = False
                validation_errors.append(f"Too many headlines: {len(headlines)} > 15")
            if len(descriptions) < 2:
                validation_passed = False
                validation_errors.append(f"Too few descriptions: {len(descriptions)} < 2")
            if len(descriptions) > 4:
                validation_passed = False
                validation_errors.append(f"Too many descriptions: {len(descriptions)} > 4")
            
            # Check lengths
            for i, h in enumerate(headlines):
                if len(h) > 30:
                    validation_passed = False
                    validation_errors.append(f"Headline {i+1} too long: {len(h)} > 30")
            for i, d in enumerate(descriptions):
                if len(d) > 90:
                    validation_passed = False
                    validation_errors.append(f"Description {i+1} too long: {len(d)} > 90")
            
            result.append({
                "id": s.id,
                "headlines": headlines,
                "descriptions": descriptions,
                "validation_passed": validation_passed,
                "validation_errors": validation_errors if validation_errors else None,
                "exemplar_ad_ids": s.exemplar_ad_ids,
                "created_at": s.created_at.isoformat(),
            })
        
        return result

    except Exception as e:
        logger.error(f"Failed to list suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
