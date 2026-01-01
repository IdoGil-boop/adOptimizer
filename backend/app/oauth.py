"""OAuth2 authentication flow for Google Ads."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials as GoogleCredentials
from google_auth_oauthlib.flow import Flow
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ConnectedAccount
from app.security import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)
settings = get_settings()


def create_oauth_flow(state: Optional[str] = None) -> Flow:
    """Create Google OAuth2 flow for Google Ads API access."""
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_ADS_CLIENT_ID,
            "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.OAUTH_REDIRECT_URI],
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=[settings.GOOGLE_ADS_OAUTH_SCOPE],
        redirect_uri=settings.OAUTH_REDIRECT_URI,
        state=state,
    )

    return flow


def get_authorization_url(state: str) -> str:
    """Generate OAuth2 authorization URL with state."""
    flow = create_oauth_flow(state=state)
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
    )
    return authorization_url


def exchange_code_for_tokens(code: str, state: str) -> GoogleCredentials:
    """Exchange authorization code for OAuth2 tokens."""
    flow = create_oauth_flow(state=state)
    flow.fetch_token(code=code)
    return flow.credentials


def refresh_access_token(account: ConnectedAccount, db: Session) -> str:
    """Refresh access token for a connected account."""
    try:
        refresh_token = decrypt_token(account.encrypted_refresh_token)

        credentials = GoogleCredentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_ADS_CLIENT_ID,
            client_secret=settings.GOOGLE_ADS_CLIENT_SECRET,
            scopes=[settings.GOOGLE_ADS_OAUTH_SCOPE],
        )

        # Refresh the token
        credentials.refresh(GoogleAuthRequest())

        # Update stored tokens
        if credentials.token:
            account.encrypted_access_token = encrypt_token(credentials.token)
        if credentials.expiry:
            account.token_expiry = credentials.expiry
        else:
            # Default expiry if not provided
            account.token_expiry = datetime.utcnow() + timedelta(hours=1)

        account.updated_at = datetime.utcnow()
        db.commit()

        logger.info(f"Access token refreshed for account {account.customer_id}")
        return credentials.token or ""

    except Exception as e:
        logger.error(f"Failed to refresh token for account {account.customer_id}: {e}")
        raise


def get_valid_access_token(account: ConnectedAccount, db: Session) -> str:
    """Get a valid access token, refreshing if necessary."""
    # Check if token exists and is not expired
    if account.encrypted_access_token and account.token_expiry:
        if account.token_expiry > datetime.utcnow() + timedelta(minutes=5):
            # Token still valid with 5-minute buffer
            return decrypt_token(account.encrypted_access_token)

    # Token expired or doesn't exist, refresh it
    return refresh_access_token(account, db)
