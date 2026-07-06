from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from app.routers import ai, insights
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


@app.get('/health')
def health():
    return {'status': 'ok'}
