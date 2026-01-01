"""add google_ads_created_at and keyword quality scores

Revision ID: add_google_ads_created_at
Revises: 4f94303945df
Create Date: 2025-01-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_google_ads_created_at'
down_revision = '4f94303945df'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add google_ads_created_at column to ads table
    op.add_column('ads', sa.Column('google_ads_created_at', sa.DateTime(), nullable=True))
    
    # Add raw_response column to keywords table for quality score metrics
    op.add_column('keywords', sa.Column('raw_response', postgresql.JSON(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    # Remove columns
    op.drop_column('keywords', 'raw_response')
    op.drop_column('ads', 'google_ads_created_at')

