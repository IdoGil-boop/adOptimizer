# Setup Guide - Start Here

## Option 1: Start Docker Desktop (Recommended)

1. **Start Docker Desktop**:
   ```bash
   # macOS: Open Docker Desktop application
   open -a Docker

   # Wait 10-15 seconds for Docker to fully start
   # You'll see the Docker icon in your menu bar
   ```

2. **Verify Docker is running**:
   ```bash
   docker ps
   # Should show: CONTAINER ID   IMAGE   ...
   ```

3. **Start infrastructure**:
   ```bash
   cd /Users/idogil/keyword_planner/app
   docker-compose up -d postgres redis

   # Wait 10 seconds for databases to initialize
   sleep 10

   # Verify containers are running
   docker ps
   ```

---

## Option 2: Install & Start Services Natively (No Docker)

If you prefer not to use Docker, install PostgreSQL and Redis directly:

### macOS (Homebrew)

```bash
# Install services
brew install postgresql@16 redis

# Start services
brew services start postgresql@16
brew services start redis

# Verify they're running
brew services list

# Create database
createdb adsoptimizer
```

### Update Backend .env

Edit `/Users/idogil/keyword_planner/app/backend/.env`:

```env
# Change these lines:
DATABASE_URL=postgresql://YOUR_USERNAME@localhost:5432/adsoptimizer
REDIS_URL=redis://localhost:6379/0

# Replace YOUR_USERNAME with your Mac username:
# Find it with: whoami
```

---

## Next Steps (After Services Are Running)

```bash
# Navigate to backend
cd /Users/idogil/keyword_planner/app/backend

# Install Python dependencies
poetry install
# OR if you don't have poetry:
pip install -r requirements.txt

# Generate secure keys
python scripts/generate_keys.py

# Copy the output and add to .env:
# TOKEN_ENCRYPTION_KEY=...
# SECRET_KEY=...

# Edit .env with your API keys
nano .env
# Add your:
# - GOOGLE_ADS_DEVELOPER_TOKEN
# - GOOGLE_ADS_CLIENT_ID
# - GOOGLE_ADS_CLIENT_SECRET
# - OPENAI_API_KEY

# Initialize database
poetry run alembic upgrade head
poetry run python scripts/init_db.py

# Start backend (Terminal 1)
poetry run uvicorn app.main:app --reload --port 8000

# Start Celery worker (Terminal 2)
poetry run celery -A app.worker.celery_app worker --loglevel=info

# Start Celery beat (Terminal 3)
poetry run celery -A app.worker.celery_app beat --loglevel=info

# Start frontend (Terminal 4)
cd ../frontend
npm install
npm run dev
```

---

## Quick Check Commands

```bash
# Check Docker is running
docker --version
docker ps

# Check PostgreSQL
psql -h localhost -U adsoptimizer -d adsoptimizer -c "SELECT 1;"
# OR native: psql adsoptimizer -c "SELECT 1;"

# Check Redis
redis-cli ping
# Should return: PONG

# Check backend API
curl http://localhost:8000/health

# Check frontend
open http://localhost:3000
```

---

## Troubleshooting

### "Docker daemon not running"
- **Solution**: Open Docker Desktop application
- macOS: `open -a Docker`
- Wait 15 seconds, then retry

### "docker-compose: command not found"
- **Solution**: Use `docker compose` (no hyphen) with newer Docker versions:
  ```bash
  docker compose up -d postgres redis
  ```

### "Port 5432 already in use"
- **Solution**: You have PostgreSQL already running natively
- Either stop it: `brew services stop postgresql@16`
- OR skip Docker and use native (see Option 2)

### "poetry: command not found"
- **Solution**: Install poetry:
  ```bash
  curl -sSL https://install.python-poetry.org | python3 -
  ```
- OR use pip: `pip install -r requirements.txt`

### "Cannot connect to database"
- **Docker**: Check containers: `docker ps`
- **Native**: Check service: `brew services list`
- Verify DATABASE_URL in .env matches your setup

---

## What You Need Before Starting

✅ **Required API Keys:**
1. **Google Ads API** (from ads.google.com/aw/apicenter):
   - Developer Token
   - OAuth2 Client ID + Secret (from Google Cloud Console)
   - Login Customer ID (if using MCC)

2. **OpenAI API** (from platform.openai.com):
   - API Key (starts with `sk-`)

✅ **From root .env.local** (add your own credentials):
```
developer_token=YOUR_DEVELOPER_TOKEN_HERE
client_id=YOUR_CLIENT_ID_HERE
client_secret=YOUR_CLIENT_SECRET_HERE
refresh_token=YOUR_REFRESH_TOKEN_HERE
login_customer_id=YOUR_LOGIN_CUSTOMER_ID_HERE
```

Copy these to `app/backend/.env` and replace with your actual values!

---

## Recommended: Start Docker Desktop First

The easiest path is:

```bash
# 1. Start Docker Desktop (GUI app)
open -a Docker

# 2. Wait 15 seconds

# 3. Run this script:
cd /Users/idogil/keyword_planner/app
./quick-start.sh
```

Let me create that quick-start script for you...
