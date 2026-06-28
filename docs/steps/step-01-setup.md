# Step 1 — Project Setup & Database Initialization

**Estimated time:** 2–4 hours
**Phase:** 1 (Foundation)
**Depends on:** nothing — this is the foundation everything builds on.

---

## Goal

Create the application skeleton: directory structure, dependency management, a Docker-based local dev environment, the database connection, and the base FastAPI app.

## What to build

### 1.1 Repository structure

```
restaurant-platform/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI entry point
│   │   ├── config.py          # Settings from .env
│   │   ├── database.py        # DB engine & session
│   │   ├── models/            # SQLAlchemy ORM models
│   │   ├── schemas/           # Pydantic request/response
│   │   ├── routers/           # HTTP route handlers
│   │   ├── services/          # Business logic
│   │   └── workers/           # Celery background tasks
│   ├── alembic/
│   ├── tests/
│   ├── requirements.txt
│   └── .env
├── frontend/
│   └── src/{components,pages,hooks,api}/
└── docker-compose.yml
```

### 1.2 docker-compose.yml

```yaml
services:
  db:
    image: timescale/timescaledb:latest-pg15
    environment:
      POSTGRES_DB: restaurant_platform
      POSTGRES_USER: rp_user
      POSTGRES_PASSWORD: localdevpassword
    ports:
      - '5432:5432'
    volumes:
      - pgdata:/var/lib/postgresql/data
  redis:
    image: redis:7-alpine
    ports:
      - '6379:6379'
volumes:
  pgdata:
```

Start it and verify TimescaleDB loads:
```bash
docker compose up -d
docker exec -it restaurant-platform-db-1 \
  psql -U rp_user -d restaurant_platform \
  -c 'CREATE EXTENSION IF NOT EXISTS timescaledb;'
```

### 1.3 requirements.txt

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
sqlalchemy==2.0.30
psycopg2-binary==2.9.9
alembic==1.13.1
pydantic==2.7.1
pydantic-settings==2.2.1
python-dotenv==1.0.1
httpx==0.27.0
celery==5.4.0
redis==5.0.4
python-jose[cryptography]
passlib[bcrypt]
anthropic==0.25.0
openai==1.30.0
pillow==10.3.0
python-multipart==0.0.9
lightgbm==4.3.0
pandas==2.2.0
numpy==1.26.0
pytest==8.2.0
pytest-asyncio==0.23.6
```

Install everything now even though later steps use much of it:
```bash
cd backend
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 1.4 config.py

```python
# backend/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = 'postgresql://rp_user:localdevpassword@localhost/restaurant_platform'
    SECRET_KEY: str   = 'change-this-in-production-use-secrets-manager'
    ALGORITHM: str    = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REDIS_URL: str    = 'redis://localhost:6379/0'
    ANTHROPIC_API_KEY: str = ''

    class Config:
        env_file = '.env'

settings = Settings()
```

### 1.5 database.py

```python
# backend/app/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    """FastAPI dependency — yields DB session, closes on completion."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### 1.6 main.py

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title='Restaurant Platform API', version='1.0.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:3000'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Routers registered here as each step is completed:
# from app.routers import auth, recipes, sales, ingestion, ai
# app.include_router(auth.router)

@app.get('/health')
def health():
    return {'status': 'ok'}
```

### 1.7 Alembic init

```bash
cd backend
alembic init alembic
# Set sqlalchemy.url in alembic.ini to your DATABASE_URL
```

Every schema change from here is an Alembic migration — never `ALTER TABLE` by hand.

---

## Done when

- `docker compose up -d` brings up Postgres + Redis.
- `uvicorn app.main:app --reload` runs and `GET /health` returns `{"status":"ok"}`.
- `alembic` is initialized and points at the database.

## Then

Update Step 1 checkbox in `CLAUDE.md`, `git commit`, move to `step-02-schema.md`.
