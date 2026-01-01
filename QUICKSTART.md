# Quick Start Guide

Get the Google Ads Optimizer running in 10 minutes.

## Prerequisites Checklist

- [ ] Python 3.11+ installed (`python --version`)
- [ ] Poetry installed (`poetry --version`) OR pip
- [ ] PostgreSQL 16 running (localhost:5432) OR Docker
- [ ] Redis running (localhost:6379) OR Docker
- [ ] Google Ads API credentials ready:
  - [ ] Developer token (from Google Ads API Center)
  - [ ] OAuth2 Client ID + Secret (from Google Cloud Console)
  - [ ] Login Customer ID (if using MCC account)
- [ ] OpenAI API key (from platform.openai.com)

## Option A: Docker (Recommended for Quick Start)

```bash
# 1. Navigate to app directory
cd /Users/idogil/keyword_planner/app

# 2. Start infrastructure (Postgres + Redis)
docker-compose up -d postgres redis

# 3. Wait for databases to be ready (10 seconds)
sleep 10

# 4. Configure backend
cd backend
cp .env.example .env

# 5. Generate secure keys
python -c "from cryptography.fernet import Fernet; print('TOKEN_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"

# 6. Edit .env with your API keys (nano, vim, or your editor)
nano .env
# Add:
# - GOOGLE_ADS_DEVELOPER_TOKEN
# - GOOGLE_ADS_CLIENT_ID
# - GOOGLE_ADS_CLIENT_SECRET
# - OPENAI_API_KEY
# - TOKEN_ENCRYPTION_KEY (from step 5)
# - SECRET_KEY (from step 5)

# 7. Install Python dependencies
poetry install
# OR: pip install -r requirements.txt

# 8. Initialize database
poetry run alembic upgrade head
poetry run python scripts/init_db.py

# 9. Start services in separate terminals:

# Terminal 1: FastAPI
poetry run uvicorn app.main:app --reload

# Terminal 2: Celery Worker
poetry run celery -A app.worker.celery_app worker --loglevel=info

# Terminal 3: Celery Beat
poetry run celery -A app.worker.celery_app beat --loglevel=info
```

## Option B: Native Services (No Docker)

```bash
# 1. Install PostgreSQL 16 and Redis 7 natively
# macOS: brew install postgresql@16 redis
# Ubuntu: apt install postgresql-16 redis-server

# 2. Start services
# macOS: brew services start postgresql@16 && brew services start redis
# Ubuntu: systemctl start postgresql redis

# 3. Create database
createdb adsoptimizer
# OR: psql -c "CREATE DATABASE adsoptimizer;"

# 4. Follow steps 4-9 from Option A above
```

## Verify Installation

```bash
# Check API health
curl http://localhost:8000/health

# Expected output:
# {"status":"healthy","timestamp":"2024-..."}

# Check database connection
curl http://localhost:8000/health/db

# Expected output:
# {"status":"healthy","database":"connected","timestamp":"..."}
```

## Connect Your First Google Ads Account

### Step 1: Start OAuth Flow

```bash
# Open in browser
open http://localhost:8000/oauth/google-ads/start

# Or get URL via API:
curl http://localhost:8000/oauth/google-ads/start

# Copy the "authorization_url" and open in browser
```

### Step 2: Authorize & Get Callback

After authorizing, Google redirects to:
```
http://localhost:8000/oauth/google-ads/callback?code=...&state=...
```

The response shows accessible customer IDs:
```json
{
  "success": true,
  "message": "Authentication successful. Found 2 account(s).",
  "customer_ids": ["1234567890", "9876543210"]
}
```

### Step 3: Connect Specific Account

```bash
# Get the refresh_token from your OAuth setup
# (For testing, use existing token from root .env.local)

curl -X POST http://localhost:8000/oauth/google-ads/connect \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "YOUR_CUSTOMER_ID",
    "refresh_token": "YOUR_REFRESH_TOKEN",
    "login_customer_id": "YOUR_MCC_ID"
  }'

# Expected output:
# {
#   "success": true,
#   "account_id": 1,
#   "customer_id": "1234567890",
#   "descriptive_name": "My Business Account"
# }
```

## Run Your First Sync

```bash
# Trigger on-demand sync
curl -X POST http://localhost:8000/accounts/1/sync

# Expected output:
# {
#   "success": true,
#   "message": "Sync initiated",
#   "task_id": "abc-123-def-456"
# }

# Check sync status
curl http://localhost:8000/accounts/1

# Wait 30-60 seconds for sync to complete, then check ads:
curl "http://localhost:8000/ads?account_id=1&bucket=all&limit=10"
```

## View Ad Performance Buckets

```bash
# List best-performing ads
curl "http://localhost:8000/ads?account_id=1&bucket=best"

# List worst-performing ads
curl "http://localhost:8000/ads?account_id=1&bucket=worst"

# Get detailed ad info
curl http://localhost:8000/ads/123
```

## Generate AI Suggestions

```bash
# For a specific ad ID (use a "worst" bucket ad)
curl -X POST http://localhost:8000/suggestions/123/generate \
  -H "Content-Type: application/json" \
  -d '{
    "num_variants": 3,
    "top_k_exemplars": 5
  }'

# Expected output:
# {
#   "ad_id": 123,
#   "variants": [
#     {
#       "headlines": ["New Headline 1", "New Headline 2", ...],
#       "descriptions": ["New Description 1", ...],
#       "valid": true,
#       "exemplar_ids": [10, 11, 12, 13, 14],
#       "similarity_scores": [0.92, 0.89, 0.87, 0.85, 0.83]
#     }
#   ],
#   "message": "Generated 3 suggestion(s) successfully"
# }
```

## Test Scheduled Sync

The default schedule is nightly at 2 AM. To test immediately:

```python
# In Python shell or script:
from app.worker import schedule_all_account_syncs

# Manually trigger scheduler
task = schedule_all_account_syncs.apply_async()
print(f"Scheduled syncs, task ID: {task.id}")
```

Or change schedule in `backend/app/worker.py`:

```python
# For testing, set to run every minute:
celery_app.conf.beat_schedule = {
    "schedule-nightly-syncs": {
        "task": "app.worker.schedule_all_account_syncs",
        "schedule": crontab(minute="*/1"),  # Every minute
    },
}
```

## Troubleshooting

### "Connection refused" to PostgreSQL

```bash
# Check Postgres is running:
pg_isready

# If using Docker:
docker ps | grep postgres

# Check DATABASE_URL in .env matches your setup
```

### "Redis connection error"

```bash
# Check Redis is running:
redis-cli ping
# Should return: PONG

# If using Docker:
docker ps | grep redis
```

### "Google Ads API error: PERMISSION_DENIED"

- Verify `GOOGLE_ADS_DEVELOPER_TOKEN` is correct
- Check token access level (Explorer minimum)
- Ensure `login_customer_id` matches your MCC (if applicable)

### "OpenAI API error"

- Verify `OPENAI_API_KEY` starts with `sk-`
- Check API quota at platform.openai.com
- Ensure billing is set up

### No ads classified as best/worst

- Check thresholds in `.env` (default: 100 impressions, 10 clicks)
- Wait for more data to accumulate
- Manually trigger scoring:

```python
from app.analysis.scoring import classify_ads_by_performance
from app.database import get_sync_db

db = get_sync_db()
result = classify_ads_by_performance(db, account_id=1)
print(result)
db.close()
```

## Next Steps

1. **Explore the API**: Open http://localhost:8000/docs for interactive API docs
2. **Schedule More Syncs**: Adjust `SYNC_SCHEDULE_HOUR` in `.env`
3. **Customize Scoring**: Modify weights in `app/analysis/scoring.py`
4. **Build Frontend**: See `frontend/` directory (optional - API-first design)
5. **Deploy to Production**: See `README.md` deployment section

## Full Documentation

See [README.md](README.md) for:
- Complete architecture details
- Database schema
- API endpoint reference
- Scoring algorithm explanation
- Deployment guide
- Testing instructions

## Support

- Check logs: `docker-compose logs -f backend` (if using Docker)
- Enable debug logging: Set `ENVIRONMENT=development` in `.env`
- Review troubleshooting: See README.md § Troubleshooting

---

**You're ready to optimize Google Ads copy with AI!** 🚀
