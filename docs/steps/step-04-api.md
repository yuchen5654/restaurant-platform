# Step 4 — REST API Layer (Authentication & Routers)

**Estimated time:** 6–8 hours
**Phase:** 1 (Foundation)
**Depends on:** Step 3.

---

## Goal

The HTTP API the React frontend calls. JWT auth enforces multi-tenant isolation: every request carries a token encoding the user's `restaurant_id`, injected via `get_current_restaurant_id` into every data router.

## 4.1 Auth — `app/routers/auth.py`

```python
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from app.database import get_db
from app.models.restaurant import User
from app.config import settings

router = APIRouter(prefix='/auth', tags=['auth'])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/auth/token')
pwd_context   = CryptContext(schemes=['bcrypt'], deprecated='auto')

def create_access_token(data: dict) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({**data, 'exp': expire}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    exc = HTTPException(status.HTTP_401_UNAUTHORIZED, detail='Could not validate credentials')
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get('sub')
        if not user_id: raise exc
    except JWTError:
        raise exc
    user = db.get(User, user_id)
    if not user: raise exc
    return user

def get_current_restaurant_id(current_user: User = Depends(get_current_user)) -> str:
    """Inject into every router that needs restaurant-scoped data access."""
    return str(current_user.restaurant_id)

@router.post('/token')
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not pwd_context.verify(form.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail='Invalid credentials')
    return {'access_token': create_access_token({'sub': str(user.id)}), 'token_type': 'bearer'}
```

## 4.2 Recipes — `app/routers/recipes.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from app.database import get_db
from app.routers.auth import get_current_restaurant_id
from app.models.recipe import MenuItem, RecipeLine

router = APIRouter(prefix='/menu-items', tags=['recipes'])

@router.get('/')
def list_menu_items(db=Depends(get_db), rid=Depends(get_current_restaurant_id)):
    return db.query(MenuItem).filter(
        MenuItem.restaurant_id==rid, MenuItem.is_active==True
    ).order_by(MenuItem.category, MenuItem.name).all()

@router.post('/', status_code=201)
def create_menu_item(item: dict, db=Depends(get_db), rid=Depends(get_current_restaurant_id)):
    obj = MenuItem(**item, restaurant_id=rid)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@router.post('/{item_id}/recipe-lines', status_code=201)
def add_recipe_line(item_id: str, line: dict,
                    db=Depends(get_db), rid=Depends(get_current_restaurant_id)):
    mi = db.get(MenuItem, item_id)
    if not mi or mi.restaurant_id != rid: raise HTTPException(404, 'Not found')
    rl = RecipeLine(menu_item_id=item_id, **line)
    db.add(rl); db.commit(); db.refresh(rl)
    return rl

@router.get('/{item_id}/food-cost')
def get_item_food_cost(item_id: str, db=Depends(get_db), rid=Depends(get_current_restaurant_id)):
    mi = db.get(MenuItem, item_id)
    if not mi or mi.restaurant_id != rid: raise HTTPException(404, 'Not found')
    return {
        'name': mi.name, 'menu_price': float(mi.menu_price),
        'theoretical_cost': mi.theoretical_food_cost,
        'food_cost_pct': mi.food_cost_pct,
        'recipe': [{'ingredient': rl.ingredient.name, 'qty': float(rl.quantity),
                    'unit': rl.unit, 'line_cost': rl.line_cost}
                   for rl in mi.recipe_lines],
    }
```

> **Production note:** the raw `dict` request bodies above should become Pydantic schemas in `app/schemas/` for validation. Use raw dicts only for the first pass.

## 4.3 Sales — `app/routers/sales.py`

```python
from fastapi import APIRouter, Depends
from app.database import get_db
from app.routers.auth import get_current_restaurant_id
from app.services.depletion_service import deplete_batch
from app.services.food_cost_service import get_food_cost_summary, get_item_profitability
from datetime import datetime
from pydantic import BaseModel

router = APIRouter(prefix='/sales', tags=['sales'])

class SaleItem(BaseModel):
    menu_item_id: str
    quantity_sold: int
    gross_revenue: float

class SalesBatch(BaseModel):
    business_date: datetime
    items: list[SaleItem]

@router.post('/record-batch', status_code=201)
def record_batch(batch: SalesBatch, db=Depends(get_db), rid=Depends(get_current_restaurant_id)):
    sales = [{'menu_item_id': i.menu_item_id, 'quantity': i.quantity_sold,
              'revenue': i.gross_revenue} for i in batch.items]
    records = deplete_batch(db, rid, sales, batch.business_date)
    return {'recorded': len(records), 'business_date': batch.business_date.isoformat()}

@router.get('/food-cost')
def food_cost(date_from: datetime, date_to: datetime,
              db=Depends(get_db), rid=Depends(get_current_restaurant_id)):
    return get_food_cost_summary(db, rid, date_from, date_to)

@router.get('/item-profitability')
def profitability(date_from: datetime, date_to: datetime, limit: int=20,
                  db=Depends(get_db), rid=Depends(get_current_restaurant_id)):
    return get_item_profitability(db, rid, date_from, date_to, limit)
```

## 4.4 Register routers in `main.py`

```python
from app.routers import auth, recipes, sales
app.include_router(auth.router)
app.include_router(recipes.router)
app.include_router(sales.router)
# ingestion + ai added in later steps
```

---

## Done when

Visit `http://localhost:8000/docs`. You can: create a user (seed one directly in DB), get a token via `/auth/token`, authorize in the Swagger UI, then create a menu item, add recipe lines, and record a sales batch — all scoped to your restaurant.

## Then

Update checkbox in `CLAUDE.md`, `git commit`, move to `step-05-toast.md`.
