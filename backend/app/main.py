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

from app.routers import auth, recipes, sales
from app.routers import ingestion
app.include_router(auth.router)
app.include_router(recipes.router)
app.include_router(sales.router)
app.include_router(ingestion.router)


@app.get('/health')
def health():
    return {'status': 'ok'}
