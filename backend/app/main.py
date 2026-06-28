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
