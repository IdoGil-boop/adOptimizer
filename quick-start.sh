#!/bin/bash
set -e

echo "🚀 Google Ads Optimizer - Quick Start"
echo "======================================"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running!"
    echo ""
    echo "Please start Docker Desktop first:"
    echo "  macOS: open -a Docker"
    echo ""
    echo "Then wait 15 seconds and run this script again."
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Start infrastructure
echo "📦 Starting PostgreSQL and Redis..."
docker compose up -d postgres redis

echo "⏳ Waiting for databases to initialize (10 seconds)..."
sleep 10

# Check containers
if docker ps | grep -q postgres && docker ps | grep -q redis; then
    echo "✅ Databases are running"
else
    echo "❌ Database containers failed to start"
    docker ps -a
    exit 1
fi

echo ""
echo "✅ Infrastructure ready!"
echo ""
echo "Next steps:"
echo ""
echo "1. Configure backend:"
echo "   cd backend"
echo "   python scripts/generate_keys.py"
echo "   nano .env  # Add API keys"
echo ""
echo "2. Initialize database:"
echo "   poetry install"
echo "   poetry run alembic upgrade head"
echo "   poetry run python scripts/init_db.py"
echo ""
echo "3. Start services (4 terminals):"
echo "   Terminal 1: poetry run uvicorn app.main:app --reload"
echo "   Terminal 2: poetry run celery -A app.worker.celery_app worker --loglevel=info"
echo "   Terminal 3: poetry run celery -A app.worker.celery_app beat --loglevel=info"
echo "   Terminal 4: cd ../frontend && npm install && npm run dev"
echo ""
echo "4. Access application:"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "📖 See SETUP.md for detailed instructions"
