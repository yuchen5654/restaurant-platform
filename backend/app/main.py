import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

_log = logging.getLogger(__name__)
_DEV_PLACEHOLDER = 'change-this-in-production-use-secrets-manager'
if len(settings.SECRET_KEY) < 32 or settings.SECRET_KEY == _DEV_PLACEHOLDER:
    _log.warning(
        'SECRET_KEY is a dev placeholder or too short (<32 chars). '
        'Replace with a strong random secret before any deployment.'
    )

app = FastAPI(title='Restaurant Platform API', version='1.0.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:3000', 'http://localhost:5173'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

from app.routers import auth, recipes, sales
from app.routers import ingestion, alerts
from app.routers.inventory import ingredients_router, counts_router, waste_router
from app.routers import ai, insights, labor, channel_fees, adjustments
app.include_router(auth.router)
app.include_router(recipes.router)
app.include_router(sales.router)
app.include_router(ingestion.router)
app.include_router(alerts.router)
app.include_router(ingredients_router)
app.include_router(counts_router)
app.include_router(waste_router)
app.include_router(ai.router)
app.include_router(insights.router)
app.include_router(labor.router)
app.include_router(channel_fees.router)
app.include_router(adjustments.router)


@app.get('/health')
def health():
    return {'status': 'ok'}
