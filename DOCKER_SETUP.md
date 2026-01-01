# Full Docker Setup - Everything in Containers

This is the recommended approach: **all services run in Docker**, no local Python/Node installation needed.

## ✅ Prerequisites

1. **Docker Desktop** installed and running
2. **Your credentials configured** in `backend/.env`

That's it! No Python, Node, PostgreSQL, or Redis installation needed locally.

## 🚀 One-Command Start

```bash
cd /Users/idogil/keyword_planner/app

# Make sure Docker Desktop is running:
open -a Docker
# Wait 15 seconds

# Start everything:
./start.sh
```

This script will:
1. ✅ Build all Docker images (backend, worker, beat, frontend)
2. ✅ Start PostgreSQL and Redis
3. ✅ Start backend API, Celery worker, Celery beat
4. ✅ Start Next.js frontend
5. ✅ Run database migrations
6. ✅ Create default user

## 📦 What's Running in Docker

After `./start.sh`, you'll have **6 containers**:

1. **postgres** - PostgreSQL 16 database
2. **redis** - Redis 7 cache/queue
3. **backend** - FastAPI API server
4. **celery_worker** - Background job worker
5. **celery_beat** - Scheduler for nightly syncs
6. **frontend** - Next.js UI

## 🌐 Access Your Application

- **Frontend (UI)**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## 📋 Common Commands

```bash
# View all logs
docker compose logs -f

# View specific service logs
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f celery_worker

# Check running containers
docker compose ps

# Stop all services
docker compose down

# Restart a service
docker compose restart backend

# Rebuild after code changes
docker compose build backend
docker compose up -d backend

# Get a shell in backend container
docker compose exec backend bash

# Run a command in backend
docker compose exec backend python scripts/generate_keys.py

# View database
docker compose exec postgres psql -U adsoptimizer -d adsoptimizer
```

## 🔧 Manual Setup (Alternative to ./start.sh)

If you prefer step-by-step:

```bash
# 1. Start Docker Desktop
open -a Docker
sleep 15

# 2. Build images
docker compose build

# 3. Start services
docker compose up -d

# 4. Wait for databases
sleep 10

# 5. Run migrations
docker compose exec backend alembic upgrade head

# 6. Create user
docker compose exec backend python scripts/init_db.py

# 7. Access app
open http://localhost:3000
```

## 🛠️ Development Workflow

### Making Backend Changes

Code is **mounted as a volume**, so changes are live-reloaded:

1. Edit files in `backend/`
2. FastAPI auto-reloads
3. No rebuild needed!

### Making Frontend Changes

Same for frontend:

1. Edit files in `frontend/`
2. Next.js hot-reloads
3. Changes appear instantly

### Adding New Dependencies

**Backend (Python):**
```bash
# Add to requirements.txt or pyproject.toml
# Then rebuild:
docker compose build backend
docker compose up -d backend
```

**Frontend (Node):**
```bash
# Add to package.json
# Then rebuild:
docker compose build frontend
docker compose up -d frontend
```

## 🗄️ Database Access

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U adsoptimizer -d adsoptimizer

# Run SQL query
docker compose exec postgres psql -U adsoptimizer -d adsoptimizer -c "SELECT COUNT(*) FROM ads;"

# Dump database
docker compose exec postgres pg_dump -U adsoptimizer adsoptimizer > backup.sql

# Restore database
cat backup.sql | docker compose exec -T postgres psql -U adsoptimizer -d adsoptimizer
```

## 🧹 Cleanup

```bash
# Stop containers (keeps data)
docker compose down

# Stop and remove volumes (deletes database!)
docker compose down -v

# Remove images too
docker compose down --rmi all -v

# Full cleanup
docker system prune -a --volumes
```

## 🔍 Troubleshooting

### "Port already in use"

```bash
# Find what's using port 8000
lsof -i :8000

# Kill it or stop the service
docker compose down
```

### "Cannot connect to database"

```bash
# Check if postgres is running
docker compose ps postgres

# View logs
docker compose logs postgres

# Restart
docker compose restart postgres
```

### "Build failed"

```bash
# Clean build cache
docker compose build --no-cache backend

# Or rebuild everything
docker compose down
docker compose build --no-cache
docker compose up -d
```

### "Migration failed"

```bash
# Check migration status
docker compose exec backend alembic current

# Force upgrade
docker compose exec backend alembic upgrade head

# If stuck, downgrade and retry
docker compose exec backend alembic downgrade -1
docker compose exec backend alembic upgrade head
```

### "Frontend won't start"

```bash
# Rebuild with fresh node_modules
docker compose build --no-cache frontend
docker compose up -d frontend

# Check logs
docker compose logs -f frontend
```

## 📊 Resource Usage

Typical memory usage:
- postgres: ~50MB
- redis: ~10MB
- backend: ~200MB
- celery_worker: ~200MB
- celery_beat: ~150MB
- frontend: ~200MB
- **Total: ~800MB**

## 🔐 Security Notes

- `.env` file is **never** copied into images (in .dockerignore)
- Secrets are passed via environment variables
- Database password should be changed in production
- Use volume mounts for development, not in production

## 🚀 Production Deployment

For production, modify docker-compose:

1. Remove volume mounts (code should be in image)
2. Change database password
3. Set `ENVIRONMENT=production`
4. Use proper secrets management
5. Add nginx reverse proxy
6. Use managed PostgreSQL/Redis

See `README.md` for full production deployment guide.

---

**Everything in Docker = Clean, reproducible, no local pollution!** 🎉
