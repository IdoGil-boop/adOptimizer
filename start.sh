#!/bin/bash
set -e

echo "🚀 Starting Google Ads Optimizer (Full Docker)"
echo "=============================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running!"
    echo ""
    echo "Please start Docker Desktop:"
    echo "  macOS: open -a Docker"
    echo ""
    echo "Wait 15 seconds, then run this script again."
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Check if .env exists and has required keys
if ! grep -q "OPENAI_API_KEY=sk-" backend/.env 2>/dev/null; then
    echo "⚠️  Warning: OpenAI API key not configured"
    echo "   Edit backend/.env and add your key"
    echo ""
fi

# Build images
echo "🔨 Building Docker images (this may take a few minutes)..."
docker compose build

# Start all services
echo ""
echo "🚀 Starting all services..."
docker compose up -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Run database migrations
echo ""
echo "📊 Running database migrations..."
docker compose exec -T backend alembic upgrade head

echo ""
echo "🌱 Creating default user..."
docker compose exec -T backend python scripts/init_db.py

echo ""
echo "✅ Application is ready!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📱 Access your application:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Frontend:     http://localhost:3000"
echo "  Backend API:  http://localhost:8000"
echo "  API Docs:     http://localhost:8000/docs"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Useful commands:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  View logs:        docker compose logs -f"
echo "  View backend:     docker compose logs -f backend"
echo "  Stop services:    docker compose down"
echo "  Restart:          docker compose restart"
echo "  Shell (backend):  docker compose exec backend bash"
echo ""
echo "🎉 Happy optimizing!"
