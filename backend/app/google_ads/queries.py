"""GAQL query builders with field capability fallback for Explorer access."""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

logger = logging.getLogger(__name__)


class GAQLQueryBuilder:
    """Build GAQL queries with graceful field fallback."""

    # Known problematic fields for Explorer access
    KNOWN_INVALID_FIELDS = {
        "metrics.conversion_rate",  # Not available at ad level
        "metrics.value_micros",  # Not available at ad level
        "metrics.cost_per_all_conversion",  # Computed manually instead
    }

    @staticmethod
    def build_ads_query_90d(customer_id: str, days: int = 90) -> str:
        """Build query for ads with 90-day aggregated metrics."""
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days)

        # Base query with safe fields for Explorer access
        query = f"""
            SELECT
                ad_group_ad.ad.id,
                ad_group_ad.ad.type,
                ad_group_ad.status,
                ad_group_ad.ad.responsive_search_ad.headlines,
                ad_group_ad.ad.responsive_search_ad.descriptions,
                ad_group_ad.ad.final_urls,
                ad_group_ad.ad.creation_time,
                ad_group.id,
                ad_group.name,
                ad_group.status,
                campaign.id,
                campaign.name,
                campaign.status,
                campaign.advertising_channel_type,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.ctr,
                metrics.average_cpc,
                metrics.conversions,
                metrics.all_conversions,
                metrics.cost_per_conversion
            FROM ad_group_ad
            WHERE ad_group_ad.status = 'ENABLED'
              AND segments.date BETWEEN '{start_date}' AND '{end_date}'
        """
        return query

    @staticmethod
    def build_ads_query_daily(customer_id: str, start_date: str, end_date: str) -> str:
        """Build query for ads with daily metrics."""
        query = f"""
            SELECT
                ad_group_ad.ad.id,
                segments.date,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.ctr,
                metrics.average_cpc,
                metrics.conversions,
                metrics.all_conversions,
                metrics.cost_per_conversion
            FROM ad_group_ad
            WHERE ad_group_ad.status = 'ENABLED'
              AND segments.date BETWEEN '{start_date}' AND '{end_date}'
        """
        return query

    @staticmethod
    def build_keywords_query(customer_id: str) -> str:
        """Build query for ad group keywords with quality score metrics."""
        # Try with quality scores first, fallback will remove them if not available
        query = """
            SELECT
                ad_group_criterion.criterion_id,
                ad_group_criterion.keyword.text,
                ad_group_criterion.keyword.match_type,
                ad_group_criterion.status,
                ad_group_criterion.quality_info.quality_score,
                ad_group_criterion.quality_info.creative_quality_score,
                ad_group_criterion.quality_info.post_click_quality_score,
                ad_group_criterion.quality_info.search_predicted_ctr,
                ad_group.id,
                ad_group.name
            FROM ad_group_criterion
            WHERE ad_group_criterion.type = 'KEYWORD'
              AND ad_group_criterion.status IN ('ENABLED', 'PAUSED')
        """
        return query

    @staticmethod
    def build_campaigns_query(customer_id: str) -> str:
        """Build query for campaigns."""
        query = """
            SELECT
                campaign.id,
                campaign.name,
                campaign.status,
                campaign.advertising_channel_type
            FROM campaign
            WHERE campaign.status IN ('ENABLED', 'PAUSED')
        """
        return query

    @staticmethod
    def execute_with_fallback(
        client: GoogleAdsClient,
        customer_id: str,
        query: str,
        max_retries: int = 2,
    ) -> list[Any]:
        """
        Execute GAQL query with field fallback on errors.

        If query fails due to unknown fields, progressively removes fields and retries.
        """
        ga_service = client.get_service("GoogleAdsService")
        current_query = query

        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"Executing GAQL query (attempt {attempt + 1}): {current_query[:200]}...")

                response = ga_service.search(customer_id=customer_id, query=current_query)
                results = list(response)

                logger.info(
                    f"Query successful on attempt {attempt + 1}, returned {len(results)} rows"
                )
                return results

            except GoogleAdsException as ex:
                error_messages = [error.message for error in ex.failure.errors]
                error_code = ex.error.code().name

                logger.warning(
                    f"GAQL query failed (attempt {attempt + 1}/{max_retries + 1}): "
                    f"Code: {error_code}, Request ID: {ex.request_id}, "
                    f"Errors: {error_messages}"
                )

                # Check if it's a field-related error
                if attempt < max_retries and any(
                    keyword in msg.lower()
                    for msg in error_messages
                    for keyword in ["field", "invalid", "unknown", "not supported"]
                ):
                    # Try to identify problematic field from error message
                    current_query = GAQLQueryBuilder._remove_problematic_field(
                        current_query, error_messages
                    )
                    logger.info(f"Retrying with modified query...")
                    continue

                # Not a field error or max retries reached
                raise

            except Exception as e:
                logger.error(f"Unexpected error executing GAQL query: {e}")
                raise

        return []

    @staticmethod
    def _remove_problematic_field(query: str, error_messages: list[str]) -> str:
        """
        Remove problematic field from query based on error messages.

        This is a simple heuristic that tries to extract field names from errors.
        """
        # Try to extract field name from error message
        for msg in error_messages:
            # Look for patterns like "field 'metrics.conversion_rate'"
            if "'" in msg:
                parts = msg.split("'")
                if len(parts) >= 2:
                    field_name = parts[1]
                    if field_name in query:
                        logger.info(f"Removing field '{field_name}' from query")
                        # Remove the field line
                        lines = query.split("\n")
                        filtered_lines = [
                            line for line in lines if field_name not in line
                        ]
                        return "\n".join(filtered_lines)

        # Fallback: remove known problematic fields
        for field in GAQLQueryBuilder.KNOWN_INVALID_FIELDS:
            if field in query:
                logger.info(f"Removing known invalid field '{field}' from query")
                lines = query.split("\n")
                filtered_lines = [line for line in lines if field not in line]
                return "\n".join(filtered_lines)

        return query


def fetch_ads_with_metrics_90d(
    client: GoogleAdsClient, customer_id: str, days: int = 90
) -> list[Any]:
    """Fetch ads with 90-day aggregated metrics using fallback logic."""
    query = GAQLQueryBuilder.build_ads_query_90d(customer_id, days)
    return GAQLQueryBuilder.execute_with_fallback(client, customer_id, query)


def fetch_ads_daily_metrics(
    client: GoogleAdsClient, customer_id: str, start_date: str, end_date: str
) -> list[Any]:
    """Fetch ads with daily metrics using fallback logic."""
    query = GAQLQueryBuilder.build_ads_query_daily(customer_id, start_date, end_date)
    return GAQLQueryBuilder.execute_with_fallback(client, customer_id, query)


def fetch_keywords(client: GoogleAdsClient, customer_id: str) -> list[Any]:
    """Fetch ad group keywords using fallback logic."""
    query = GAQLQueryBuilder.build_keywords_query(customer_id)
    return GAQLQueryBuilder.execute_with_fallback(client, customer_id, query)


def fetch_campaigns(client: GoogleAdsClient, customer_id: str) -> list[Any]:
    """Fetch campaigns using fallback logic."""
    query = GAQLQueryBuilder.build_campaigns_query(customer_id)
    return GAQLQueryBuilder.execute_with_fallback(client, customer_id, query)


def fetch_rsa_asset_performance(
    client: GoogleAdsClient, customer_id: str, ad_id: str, days: int = 90
) -> list[Any]:
    """Fetch RSA headline and description performance metrics."""
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days)

    query = f"""
        SELECT
            ad_group_ad_asset_view.ad_group_ad,
            ad_group_ad_asset_view.asset.asset_text_asset.text,
            ad_group_ad_asset_view.field_type,
            ad_group_ad_asset_view.performance_label,
            metrics.impressions,
            metrics.clicks,
            metrics.conversions,
            metrics.cost_micros,
            metrics.ctr
        FROM ad_group_ad_asset_view
        WHERE ad_group_ad_asset_view.ad_group_ad.ad.id = '{ad_id}'
          AND ad_group_ad_asset_view.field_type IN ('HEADLINE', 'DESCRIPTION')
          AND segments.date BETWEEN '{start_date}' AND '{end_date}'
    """
    try:
        return GAQLQueryBuilder.execute_with_fallback(client, customer_id, query)
    except Exception as e:
        logger.warning(f"Failed to fetch RSA asset performance (may not be available): {e}")
        return []
