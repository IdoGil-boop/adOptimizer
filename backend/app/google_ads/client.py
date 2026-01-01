"""Google Ads API client wrapper."""

import logging
from typing import Optional

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ConnectedAccount
from app.security import decrypt_token

logger = logging.getLogger(__name__)
settings = get_settings()


def create_google_ads_client(account: ConnectedAccount, db: Session) -> GoogleAdsClient:
    """Create authenticated Google Ads API client for an account."""
    try:
        # Decrypt the refresh token from storage
        refresh_token = decrypt_token(account.encrypted_refresh_token)

        # Build client configuration
        credentials = {
            "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
            "client_id": settings.GOOGLE_ADS_CLIENT_ID,
            "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "use_proto_plus": True,
        }

        # Add login_customer_id if using MCC
        if account.login_customer_id:
            credentials["login_customer_id"] = account.login_customer_id
        elif settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID:
            credentials["login_customer_id"] = settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID

        # Let the library use its default API version (avoids deprecated version issues)
        client = GoogleAdsClient.load_from_dict(credentials)
        return client

    except Exception as e:
        logger.error(f"Failed to create Google Ads client for {account.customer_id}: {e}")
        raise


def validate_account_access(
    client: GoogleAdsClient, customer_id: str
) -> Optional[dict]:
    """Validate account access with a lightweight GAQL query."""
    try:
        ga_service = client.get_service("GoogleAdsService")

        query = """
            SELECT
                customer.id,
                customer.descriptive_name,
                customer.currency_code,
                customer.time_zone
            FROM customer
            WHERE customer.id = '{customer_id}'
            LIMIT 1
        """.format(
            customer_id=customer_id
        )

        response = ga_service.search(customer_id=customer_id, query=query)

        for row in response:
            return {
                "id": row.customer.id,
                "descriptive_name": row.customer.descriptive_name,
                "currency_code": row.customer.currency_code,
                "time_zone": row.customer.time_zone,
            }

        return None

    except GoogleAdsException as ex:
        logger.error(
            f"Account validation failed for {customer_id}: "
            f"Request ID: {ex.request_id}, Error: {ex.error.code().name}"
        )
        raise
    except Exception as e:
        logger.error(f"Unexpected error validating account {customer_id}: {e}")
        raise


def list_accessible_customers(client: GoogleAdsClient) -> list[str]:
    """List all customer IDs accessible by the authenticated user."""
    try:
        customer_service = client.get_service("CustomerService")
        accessible_customers = customer_service.list_accessible_customers()
        return [
            customer.split("/")[-1] for customer in accessible_customers.resource_names
        ]
    except GoogleAdsException as ex:
        logger.error(
            f"Failed to list accessible customers: "
            f"Request ID: {ex.request_id}, Error: {ex.error.code().name}"
        )
        raise
    except Exception as e:
        logger.error(f"Unexpected error listing customers: {e}")
        raise
