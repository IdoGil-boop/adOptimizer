# Google Ads Copy Optimizer

Production-grade SaaS application for analyzing and optimizing Google Ads copy using AI.

## 🎯 Product Overview

Connects to Google Ads accounts via OAuth2, ingests last 90 days of ad performance data, analyzes best vs. worst performing ads, and generates AI-powered copy suggestions using OpenAI with embeddings-based retrieval.

### Key Features

- **OAuth2 Google Ads Integration**: Secure connection to production accounts (Explorer access compatible)
- **Scheduled & On-Demand Sync**: Nightly Celery jobs + manual triggers
- **Performance Analysis**: Composite scoring algorithm with volume thresholds
- **AI-Powered Suggestions**: OpenAI GPT-4 with embeddings similarity to bias toward proven copy patterns
- **RSA Compliance**: Enforces Google Responsive Search Ad constraints (30-char headlines, 90-char descriptions)
- **Field Capability Fallback**: Graceful GAQL query degradation for Explorer access limitations
- **Feature Flags**: "Apply Suggestion" disabled by default for safety

## 🏗️ Architecture

```
┌─────────────────┐
│   Next.js UI    │  (Optional - API-first design)
│  (Port 3000)    │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐
│  FastAPI Backend│
│   (Port 8000)   │
│  - OAuth2       │
│  - REST API     │
│  - Analysis     │
└────────┬────────┘
         │
    ┌────┴────┬───────────┬──────────┐
    │         │           │          │
    ▼         ▼           ▼          ▼
┌────────┐ ┌─────┐  ┌──────────┐ ┌──────┐
│Postgres│ │Redis│  │  Celery  │ │OpenAI│
│        │ │     │  │ Workers  │ │ API  │
│ SQLAlch│ │Queue│  │  + Beat  │ └──────┘
└────────┘ └─────┘  └──────────┘
    ▲                     │
    └─────────────────────┘
          Sync Jobs
```

### Tech Stack

- **Backend**: Python 3.11+ | FastAPI | SQLAlchemy 2.x | Alembic
- **Workers**: Celery + Redis | Beat scheduler
- **Database**: PostgreSQL 16
- **AI**: OpenAI (GPT-4o-mini + text-embedding-3-small)
- **Ads API**: google-ads v16 (Explorer access compatible)
- **Frontend** (optional): Next.js 14 + TypeScript + Tailwind + shadcn/ui

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Poetry (or pip)
- Docker & Docker Compose (recommended)
- PostgreSQL 16
- Redis 7
- Google Ads API credentials (Explorer access minimum)
- OpenAI API key

### 1. Clone and Navigate

```bash
cd /Users/idogil/keyword_planner/app
```

### 2. Backend Setup

```bash
cd backend

# Install dependencies
poetry install
# Or with pip:
# pip install -r requirements.txt

# Generate secure keys
python scripts/generate_keys.py

# Edit .env with your keys and API credentials
cp .env.example .env
nano .env  # Add your API keys
```

**Required .env variables:**

```env
# Google Ads API
GOOGLE_ADS_DEVELOPER_TOKEN=your_token
GOOGLE_ADS_CLIENT_ID=your_client_id
GOOGLE_ADS_CLIENT_SECRET=your_secret
GOOGLE_ADS_LOGIN_CUSTOMER_ID=your_mcc_id  # Optional

# Security (generate with scripts/generate_keys.py)
TOKEN_ENCRYPTION_KEY=your_fernet_key
SECRET_KEY=your_jwt_secret

# OpenAI
OPENAI_API_KEY=sk-...
```

### 3. Start Infrastructure (Docker)

```bash
# From app/ directory
docker-compose up -d postgres redis
```

Or install PostgreSQL and Redis locally.

### 4. Initialize Database

```bash
cd backend

# Run migrations
poetry run alembic upgrade head

# Or initialize manually
poetry run python scripts/init_db.py
```

### 5. Start Services

#### Development (separate terminals)

```bash
# Terminal 1: FastAPI backend
cd backend
poetry run uvicorn app.main:app --reload --port 8000

# Terminal 2: Celery worker
cd backend
poetry run celery -A app.worker.celery_app worker --loglevel=info

# Terminal 3: Celery beat (scheduler)
cd backend
poetry run celery -A app.worker.celery_app beat --loglevel=info
```

#### Production (Docker)

```bash
docker-compose up -d
```

### 6. Connect Google Ads Account

```bash
# Navigate to OAuth start
open http://localhost:8000/oauth/google-ads/start

# Follow OAuth flow, then connect account via API:
curl -X POST http://localhost:8000/oauth/google-ads/connect \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "1234567890",
    "refresh_token": "1//03...",
    "login_customer_id": "9876543210"
  }'
```

### 7. Trigger First Sync

```bash
# Get account ID from /accounts endpoint
curl http://localhost:8000/accounts

# Trigger sync
curl -X POST http://localhost:8000/accounts/1/sync
```

## 📋 API Endpoints

### OAuth & Accounts

- `GET /oauth/google-ads/start` - Initiate OAuth flow
- `GET /oauth/google-ads/callback` - OAuth callback handler
- `POST /oauth/google-ads/connect` - Connect specific account
- `GET /accounts` - List connected accounts with stats
- `GET /accounts/{id}` - Account details + sync history
- `POST /accounts/{id}/sync` - Trigger on-demand sync

### Ads

- `GET /ads?account_id={id}&bucket={best|worst|all}` - List ads with filters
- `GET /ads/{id}` - Ad details with metrics

### Suggestions

- `POST /suggestions/{ad_id}/generate` - Generate AI suggestions
- `GET /suggestions/{ad_id}` - List suggestions for ad
- `POST /suggestions/{ad_id}/apply` - Apply suggestion (feature-flagged)

### Health

- `GET /health` - Basic health check
- `GET /health/db` - Health check with DB test

## 🔍 How It Works

### 1. OAuth & Connection

User authorizes via Google OAuth2 → Backend exchanges code for refresh token → Stores encrypted token → Validates account access with lightweight GAQL query.

### 2. Data Ingestion (Celery Worker)

```python
# Nightly at 2 AM (configurable)
schedule_all_account_syncs()
  → sync_account_data(account_id)
    → Fetch ads with 90d metrics via GAQL
    → Fetch keywords (best-effort)
    → Ingest into normalized DB tables
    → Compute derived metrics (CVR, CPA)
```

**Field Fallback Logic:**

```python
# If GAQL fails due to unknown fields (Explorer limits)
execute_with_fallback(query)
  → Try query
  → On field error, remove problematic field
  → Retry up to 3 times
```

### 3. Performance Analysis

```python
classify_ads_by_performance(account_id)
  → For each ad with metrics:
    → Check minimum thresholds (impressions, clicks)
    → Compute composite score:
      score = 0.25*ctr_score + 0.35*cvr_score
            + 0.25*cpa_score + 0.15*volume_score
    → Rank all ads by score
    → Top 20% = BEST, Bottom 20% = WORST
    → Update Ad.bucket and explanation
```

**Scoring Safeguards:**

- Minimum 100 impressions (configurable)
- Minimum 10 clicks (configurable)
- Ads below thresholds marked UNKNOWN
- Prevents low-sample-size outliers

### 4. AI Suggestion Generation

```python
generate_suggestions(ad_id)
  → Get worst-performing ad
  → Embed best-performing ads (OpenAI embeddings)
  → Find top-5 most similar best ads (cosine similarity)
  → Prompt GPT-4o-mini:
    "Given this low-performing ad and these high-performing examples,
     generate 3 improved RSA variants..."
  → Parse response
  → Validate RSA constraints:
    - 3-15 headlines, max 30 chars each
    - 2-4 descriptions, max 90 chars each
    - All unique, no duplicates
  → Store with provenance (exemplar IDs, similarity scores)
```

**Prompt Strategy:**

- Show 5 high-performing exemplars with similarity scores
- Include current ad for context
- Specify strict RSA constraints
- Request multiple variants for A/B testing

### 5. Optional: Apply Suggestion

Feature-flagged OFF by default (Explorer access can't write ads).

When enabled (Basic/Standard access):

```python
apply_suggestion(ad_id, suggestion_id)
  → Create new RSA in Google Ads
  → Pause old ad (safer than edit)
  → Track applied_ad_id for monitoring
```

## 🗃️ Database Schema

### Core Tables

- **users** - MVP: single user, multi-tenant ready
- **connected_accounts** - Google Ads accounts, encrypted tokens
- **campaigns** - Campaign metadata
- **ad_groups** - Ad group metadata
- **ads** - Ad creative (RSAs focus), bucket classification
- **ad_metrics_90d** - 90-day aggregate metrics
- **ad_metrics_daily** - Daily time-series (optional)
- **keywords** - Ad group keywords (best-effort)
- **suggestions** - Generated copy with provenance
- **suggestion_runs** - Batch generation tracking
- **sync_runs** - Sync job execution history

### Key Fields

**ads table:**

- `bucket` - best | worst | unknown
- `bucket_score` - Composite score (0-1)
- `bucket_explanation` - Human-readable reasoning
- `headlines` - JSON array of RSA headlines
- `descriptions` - JSON array of RSA descriptions

**suggestions table:**

- `exemplar_ad_ids` - IDs of high-performing ads used
- `similarity_scores` - Cosine similarity to each exemplar
- `prompt_version` - Prompt versioning for A/B testing
- `applied` - Boolean, tracked for lift analysis

## ⚙️ Configuration

### Environment Variables

See `.env.example` for full list. Key configs:

```env
# Scoring
MIN_IMPRESSIONS_FOR_SCORING=100
MIN_CLICKS_FOR_SCORING=10

# Schedule
SYNC_SCHEDULE_HOUR=2  # 2 AM
SYNC_SCHEDULE_MINUTE=0

# Feature Flags
FEATURE_FLAG_APPLY_SUGGESTIONS=false  # Safety first!
```

### Celery Beat Schedule

Edit `app/worker.py`:

```python
celery_app.conf.beat_schedule = {
    "schedule-nightly-syncs": {
        "task": "app.worker.schedule_all_account_syncs",
        "schedule": crontab(hour=2, minute=0),  # Nightly at 2 AM
    },
}
```

## 🧪 Testing

```bash
cd backend

# Run all tests
poetry run pytest

# With coverage
poetry run pytest --cov=app --cov-report=html

# Specific test files
poetry run pytest tests/test_scoring.py
poetry run pytest tests/test_generation.py
```

**Key test areas:**

- Scoring algorithm with edge cases (0 conversions, low volume)
- RSA constraint validation (length, uniqueness, truncation)
- GAQL query fallback logic
- Embeddings similarity retrieval

## 🐛 Troubleshooting

### Issue: "This method is not allowed for use with explorer access"

**Cause:** Trying to use Keyword Planner API with Explorer access.

**Fix:** This app doesn't use Keyword Planner - uses read-only reporting instead. Check logs for which service failed.

### Issue: "Unrecognized field in query"

**Cause:** GAQL field not available (version or access level).

**Fix:** Fallback logic should handle this automatically. Check logs for retries. If persists, edit `app/google_ads/queries.py` to remove field.

### Issue: Sync fails with OAuth error

**Cause:** Refresh token expired or revoked.

**Fix:** User must re-authenticate via OAuth flow. Delete old `connected_accounts` row and reconnect.

### Issue: No best/worst ads classified

**Cause:** Insufficient data volume (below thresholds).

**Fix:** Lower `MIN_IMPRESSIONS_FOR_SCORING` / `MIN_CLICKS_FOR_SCORING` in `.env`, or wait for more data.

### Issue: OpenAI suggestions fail

**Cause:** API key invalid or rate limit hit.

**Fix:** Check `OPENAI_API_KEY` in `.env`. Verify API quota. Check logs for detailed error.

## 🔐 Security

### Token Encryption

Refresh tokens encrypted at rest using Fernet (AES-128):

```python
from app.security import encrypt_token, decrypt_token

encrypted = encrypt_token(refresh_token)  # Store this
plaintext = decrypt_token(encrypted)  # Use this
```

**Key rotation:** Update `TOKEN_ENCRYPTION_KEY` → decrypt all tokens with old key → re-encrypt with new key.

### OAuth State CSRF Protection

```python
state = generate_oauth_state()  # 32-byte random
# Pass in authorization URL
# Verify on callback
```

### Logging

- **Never log** refresh tokens, access tokens, or secrets
- Logs redact sensitive fields automatically
- Production: structured JSON logging recommended

## 📈 Performance

### Optimization Tips

1. **Database Indexes**: All foreign keys and common filters indexed
2. **Async Endpoints**: FastAPI uses AsyncSession for non-blocking I/O
3. **Celery Queues**: Separate queues for sync (slow) vs generation (fast)
4. **Connection Pooling**: SQLAlchemy pool_size=10, max_overflow=20
5. **Embeddings Batching**: Embed multiple ads in single OpenAI call

### Scaling

- **Horizontal**: Add more Celery workers (stateless)
- **Database**: Read replicas for reporting queries
- **Redis**: Redis Cluster for high throughput
- **Rate Limits**: Google Ads: 2,880 ops/day (Explorer), OpenAI: Tier-based

## 🚧 Roadmap

### MVP (Current)

- [x] OAuth2 connect
- [x] Scheduled sync
- [x] Best/worst classification
- [x] AI suggestions with embeddings
- [x] Feature-flagged apply

### Phase 2

- [ ] Next.js frontend UI
- [ ] Weekly digest emails
- [ ] Multi-account portfolio view
- [ ] Experiment mode (create variants, track lift)
- [ ] Prompt versioning UI

### Phase 3

- [ ] User authentication (multi-tenant)
- [ ] Webhooks for real-time notifications
- [ ] Custom scoring model editor
- [ ] Billing & subscription management
- [ ] Advanced analytics dashboard

## 📚 Resources

- [Google Ads API Docs](https://developers.google.com/google-ads/api/docs/start)
- [GAQL Grammar](https://developers.google.com/google-ads/api/docs/query/grammar)
- [RSA Best Practices](https://support.google.com/google-ads/answer/7684791)
- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Celery Docs](https://docs.celeryq.dev/)

## 🤝 Contributing

1. Create feature branch from `main`
2. Write tests for new features
3. Update README for API changes
4. Run `black` and `ruff` linters
5. Submit PR with clear description

## 📄 License

MIT License - See LICENSE file

## 🙋 Support

For issues or questions:

1. Check [Troubleshooting](#-troubleshooting) section
2. Review [Google Ads API access levels](https://developers.google.com/google-ads/api/docs/access-levels)
3. Open GitHub issue with logs and steps to reproduce

---

**Built with ❤️ for Google Ads advertisers**
