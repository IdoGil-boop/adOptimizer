.PHONY: help install dev test clean migrate upgrade downgrade worker beat run docker-up docker-down

help:
	@echo "Google Ads Optimizer - Make Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install       Install dependencies with poetry"
	@echo "  make dev           Install dev dependencies"
	@echo "  make keys          Generate secure keys for .env"
	@echo ""
	@echo "Database:"
	@echo "  make migrate       Create new migration"
	@echo "  make upgrade       Apply migrations"
	@echo "  make downgrade     Rollback last migration"
	@echo "  make init-db       Initialize database (tables + seed)"
	@echo ""
	@echo "Development:"
	@echo "  make run           Start FastAPI server"
	@echo "  make worker        Start Celery worker"
	@echo "  make beat          Start Celery beat"
	@echo "  make test          Run tests"
	@echo "  make test-cov      Run tests with coverage"
	@echo "  make lint          Run linters (black + ruff)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up     Start all services with docker-compose"
	@echo "  make docker-down   Stop all services"
	@echo "  make docker-logs   View logs"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean         Remove cache and build files"

install:
	poetry install --no-root

dev:
	poetry install --no-root --with dev

keys:
	poetry run python scripts/generate_keys.py

migrate:
	poetry run alembic revision --autogenerate -m "$(message)"

upgrade:
	poetry run alembic upgrade head

downgrade:
	poetry run alembic downgrade -1

init-db:
	poetry run python scripts/init_db.py

run:
	poetry run uvicorn app.main:app --reload --port 8000

worker:
	poetry run celery -A app.worker.celery_app worker --loglevel=info --concurrency=2

beat:
	poetry run celery -A app.worker.celery_app beat --loglevel=info

test:
	poetry run pytest

test-cov:
	poetry run pytest --cov=app --cov-report=html --cov-report=term

lint:
	poetry run black app tests
	poetry run ruff check app tests --fix

docker-up:
	cd .. && docker-compose up -d

docker-down:
	cd .. && docker-compose down

docker-logs:
	cd .. && docker-compose logs -f

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
