#!/usr/bin/env python
"""Initialize database with seed data."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import sync_engine, SyncSessionLocal
from app.models import Base, User

def init_db():
    """Create all tables and seed initial data."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=sync_engine)
    print("✓ Tables created")

    # Create default user
    db = SyncSessionLocal()
    try:
        existing_user = db.query(User).first()
        if not existing_user:
            user = User(
                email="default@example.com",
                is_active=True,
            )
            db.add(user)
            db.commit()
            print(f"✓ Created default user: {user.email}")
        else:
            print(f"✓ Default user already exists: {existing_user.email}")
    finally:
        db.close()

    print("\nDatabase initialized successfully!")

if __name__ == "__main__":
    init_db()
