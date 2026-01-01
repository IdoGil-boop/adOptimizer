#!/usr/bin/env python
"""Generate secure keys for .env file."""

import secrets
from cryptography.fernet import Fernet

print("=== Secure Key Generation ===\n")

print("TOKEN_ENCRYPTION_KEY (Fernet):")
print(Fernet.generate_key().decode())
print()

print("SECRET_KEY (JWT):")
print(secrets.token_urlsafe(32))
print()

print("Add these to your .env file!")
