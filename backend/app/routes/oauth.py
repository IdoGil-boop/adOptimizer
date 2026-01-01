"""OAuth2 authentication routes for Google Ads."""

import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import get_settings
from app.database import get_async_db
from app.google_ads.client import list_accessible_customers, validate_account_access
from app.models import ConnectedAccount, User
from app.oauth import (
    create_oauth_flow,
    exchange_code_for_tokens,
    get_authorization_url,
)
from app.security import decrypt_token, encrypt_token, generate_oauth_state

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


class OAuthStartResponse(BaseModel):
    """Response for OAuth start."""

    authorization_url: str
    state: str


class OAuthCallbackResponse(BaseModel):
    """Response for OAuth callback."""

    success: bool
    message: str
    account_id: Optional[int] = None
    customer_ids: Optional[list[str]] = None


@router.get("/google-ads/start", response_model=OAuthStartResponse)
async def start_google_ads_oauth():
    """
    Start OAuth2 flow for Google Ads.

    Returns authorization URL for user to consent.
    """
    try:
        state = generate_oauth_state()
        auth_url = get_authorization_url(state)

        logger.info(f"OAuth flow started with state: {state[:10]}...")

        return OAuthStartResponse(authorization_url=auth_url, state=state)

    except Exception as e:
        logger.error(f"Failed to start OAuth flow: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start OAuth: {str(e)}")


@router.get("/google-ads/callback", response_model=OAuthCallbackResponse)
async def google_ads_oauth_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Handle OAuth2 callback from Google.

    Exchanges code for tokens and lists accessible customer accounts.
    """
    try:
        logger.info(f"OAuth callback received with state: {state[:10]}...")

        # Exchange code for tokens
        credentials = exchange_code_for_tokens(code, state)

        if not credentials.refresh_token:
            raise HTTPException(
                status_code=400,
                detail="No refresh token received. User may need to revoke access and re-authenticate.",
            )

        logger.info("Successfully exchanged code for tokens")

        # Validate developer token is set
        if not settings.GOOGLE_ADS_DEVELOPER_TOKEN:
            raise HTTPException(
                status_code=500,
                detail="Developer token not configured. Please set GOOGLE_ADS_DEVELOPER_TOKEN.",
            )

        # Create temporary client to list accessible customers
        from google.ads.googleads.client import GoogleAdsClient

        temp_credentials = {
            "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
            "client_id": settings.GOOGLE_ADS_CLIENT_ID,
            "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
            "refresh_token": credentials.refresh_token,
            "use_proto_plus": True,
        }

        if settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID:
            temp_credentials["login_customer_id"] = settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID

        customer_ids = []
        account_info_map = {}
        try:
            # Use default API version (library will pick latest supported)
            temp_client = GoogleAdsClient.load_from_dict(temp_credentials)

            # List accessible customers
            customer_ids = list_accessible_customers(temp_client)
            logger.info(f"Found {len(customer_ids)} accessible customer accounts")

            # Validate and get account info for each customer
            for customer_id in customer_ids:
                try:
                    info = validate_account_access(temp_client, customer_id)
                    if info:
                        account_info_map[customer_id] = info
                except Exception as validate_error:
                    logger.warning(f"Could not validate account {customer_id}: {validate_error}")

            if not customer_ids:
                logger.warning("No accessible customer accounts found")
        except HTTPException:
            # Re-raise HTTP exceptions (like validation errors)
            raise
        except Exception as list_error:
            logger.error(f"Failed to list accessible customers: {list_error}", exc_info=True)
            # If listing fails, continue - user can connect accounts manually later
            # The OAuth flow succeeded, we just couldn't list accounts

        # Get or create user (MVP: single user)
        user = await db.execute(select(User).limit(1))
        user = user.scalar_one_or_none()

        if not user:
            user = User(email="default@example.com", is_active=True)
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info(f"Created default user: {user.id}")

        # Encrypt refresh token for storage
        encrypted_refresh = encrypt_token(credentials.refresh_token)

        # If no customer IDs found, return error
        if not customer_ids:
            logger.warning("OAuth succeeded but no customer accounts were discovered.")
            return OAuthCallbackResponse(
                success=True,
                message="Authentication successful, but no Google Ads accounts were found.",
                account_id=None,
                customer_ids=[],
            )

        # Create ConnectedAccount records for accessible customers
        connected_accounts = []
        for customer_id in customer_ids:
            # Check if already connected
            existing = await db.execute(
                select(ConnectedAccount).filter(
                    ConnectedAccount.user_id == user.id,
                    ConnectedAccount.customer_id == customer_id,
                )
            )
            existing = existing.scalar_one_or_none()

            if existing:
                logger.info(f"Account {customer_id} already connected, skipping")
                connected_accounts.append(existing)
                continue

            # Get account info if available
            info = account_info_map.get(customer_id, {})

            # Create new connected account
            account = ConnectedAccount(
                user_id=user.id,
                customer_id=customer_id,
                login_customer_id=settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID or None,
                descriptive_name=info.get("descriptive_name"),
                currency_code=info.get("currency_code"),
                time_zone=info.get("time_zone"),
                encrypted_refresh_token=encrypted_refresh,
                is_active=True,
            )
            db.add(account)
            connected_accounts.append(account)
            logger.info(f"Created ConnectedAccount for {customer_id}")

        await db.commit()

        # Refresh accounts to get IDs
        for account in connected_accounts:
            await db.refresh(account)

        account_id = connected_accounts[0].id if connected_accounts else None

        return OAuthCallbackResponse(
            success=True,
            message=f"Authentication successful. Connected {len(connected_accounts)} account(s).",
            account_id=account_id,
            customer_ids=customer_ids,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OAuth callback failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"OAuth callback failed: {str(e)}")


class ConnectAccountRequest(BaseModel):
    """Request to connect a specific customer account."""

    customer_id: str
    refresh_token: str
    login_customer_id: Optional[str] = None


class ConnectAccountResponse(BaseModel):
    """Response for account connection."""

    success: bool
    message: str
    account_id: int
    customer_id: str
    descriptive_name: Optional[str]


@router.post("/google-ads/connect", response_model=ConnectAccountResponse)
async def connect_google_ads_account(
    request: ConnectAccountRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Connect a specific Google Ads customer account.

    Validates access and stores encrypted tokens.
    """
    try:
        # Get or create user
        user = await db.execute(select(User).limit(1))
        user = user.scalar_one_or_none()

        if not user:
            user = User(email="default@example.com", is_active=True)
            db.add(user)
            await db.commit()
            await db.refresh(user)

        # Check if account already connected
        existing = await db.execute(
            select(ConnectedAccount).filter(
                ConnectedAccount.user_id == user.id,
                ConnectedAccount.customer_id == request.customer_id,
            )
        )
        existing = existing.scalar_one_or_none()

        if existing:
            logger.info(f"Account {request.customer_id} already connected")
            return ConnectAccountResponse(
                success=True,
                message="Account already connected",
                account_id=existing.id,
                customer_id=existing.customer_id,
                descriptive_name=existing.descriptive_name,
            )

        # Create client and validate access
        from google.ads.googleads.client import GoogleAdsClient

        credentials = {
            "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
            "client_id": settings.GOOGLE_ADS_CLIENT_ID,
            "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
            "refresh_token": request.refresh_token,
            "use_proto_plus": True,
        }

        if request.login_customer_id:
            credentials["login_customer_id"] = request.login_customer_id
        elif settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID:
            credentials["login_customer_id"] = settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID

        client = GoogleAdsClient.load_from_dict(credentials)

        # Validate account access
        account_info = validate_account_access(client, request.customer_id)

        if not account_info:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot access account {request.customer_id}",
            )

        logger.info(f"Validated access to account: {account_info}")

        # Encrypt and store tokens
        encrypted_refresh = encrypt_token(request.refresh_token)

        account = ConnectedAccount(
            user_id=user.id,
            customer_id=request.customer_id,
            login_customer_id=request.login_customer_id,
            descriptive_name=account_info.get("descriptive_name"),
            currency_code=account_info.get("currency_code"),
            time_zone=account_info.get("time_zone"),
            encrypted_refresh_token=encrypted_refresh,
            is_active=True,
        )

        db.add(account)
        await db.commit()
        await db.refresh(account)

        logger.info(f"Connected account {request.customer_id} as ID {account.id}")

        return ConnectAccountResponse(
            success=True,
            message="Account connected successfully",
            account_id=account.id,
            customer_id=account.customer_id,
            descriptive_name=account.descriptive_name,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to connect account: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to connect account: {str(e)}")
