"""Security utilities for token encryption and session management."""

import secrets
from datetime import datetime, timedelta
from typing import Optional

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

# Password hashing (not used in MVP but included for future user auth)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Fernet encryption for OAuth tokens
_cipher_suite: Optional[Fernet] = None


def get_cipher_suite() -> Fernet:
    """Get or create Fernet cipher suite for token encryption."""
    global _cipher_suite
    if _cipher_suite is None:
        if not settings.TOKEN_ENCRYPTION_KEY:
            raise ValueError(
                "TOKEN_ENCRYPTION_KEY not set. Generate with: "
                "python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        _cipher_suite = Fernet(settings.TOKEN_ENCRYPTION_KEY.encode())
    return _cipher_suite


def encrypt_token(token: str) -> str:
    """Encrypt an OAuth token for storage."""
    cipher = get_cipher_suite()
    return cipher.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt an OAuth token from storage."""
    cipher = get_cipher_suite()
    return cipher.decrypt(encrypted_token.encode()).decode()


def generate_oauth_state() -> str:
    """Generate secure random state for OAuth2 CSRF protection."""
    return secrets.token_urlsafe(32)


def create_session_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT session token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


def verify_session_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT session token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password for storage."""
    return pwd_context.hash(password)
