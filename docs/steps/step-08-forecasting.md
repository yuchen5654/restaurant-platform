# Step 8 — Demand Forecasting with LightGBM

**Estimated time:** 8–12 hours
**Phase:** 2 (Intelligence)
**Depends on:** Phase 1 live with 60+ days of data.

---

## Goal

Per-restaurant gradient-boosted tree model predicting daily revenue for the next 7–14 days. Trains weekly (Sunday 2am Celery beat).

## `app/services/forecasting_service.py`

```python
import pandas as pd, numpy as np, lightgbm as lgb
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.models.sales import SalesSummary
from datetime import timedelta

FEATURE_COLS = ['day_of_week','week_of_year','month','is_weekend','is_holiday',
                'lag_7d','lag_14d','lag_28d','rolling_7d_avg','rolling_30d_avg']

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['date'] = pd.to_datetime(df['business_date'])
    df['day_of_week']    = df['date'].dt.dayofweek
    df['week_of_year']   = df['date'].dt.isocalendar().week.astype(int)
    df['month']          = df['date'].dt.month
    df['is_weekend']     = df['day_of_week'].isin([4,5,6]).astype(int)
    df['is_holiday']     = 0  # TODO: holiday calendar API
    df = df.sort_values('date')
    df['lag_7d']         = df['net_revenue'].shift(7)
    df['lag_14d']        = df['net_revenue'].shift(14)
    df['lag_28d']        = df['net_revenue'].shift(28)
    df['rolling_7d_avg'] = df['net_revenue'].shift(1).rolling(7).mean()
    df['rolling_30d_avg']= df['net_revenue'].shift(1).rolling(30).mean()
    return df.dropna()

def train_forecast_model(db: Session, restaurant_id: str):
    rows = db.execute(select(
        SalesSummary.business_date,
        func.sum(SalesSummary.net_revenue).label('net_revenue'),
    ).where(SalesSummary.restaurant_id==restaurant_id, SalesSummary.daypart=='all',
    ).group_by(SalesSummary.business_date
    ).order_by(SalesSummary.business_date)).all()
    if len(rows) < 60: return None
    df = build_features(pd.DataFrame(rows, columns=['business_date','net_revenue']))
    split = int(len(df) * 0.8)
    X_train, y_train = df[FEATURE_COLS].iloc[:split], df['net_revenue'].iloc[:split]
    X_val,   y_val   = df[FEATURE_COLS].iloc[split:], df['net_revenue'].iloc[split:]
    return lgb.train(
        params={'objective':'regression','metric':'mae','learning_rate':0.05,
                'num_leaves':31,'verbose':-1},
        train_set=lgb.Dataset(X_train, label=y_train),
        valid_sets=[lgb.Dataset(X_val, label=y_val)],
        num_boost_round=300,
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)])

def generate_forecast(model, df: pd.DataFrame, days_ahead=14) -> list[dict]:
    predictions = []
    last_date = pd.to_datetime(df['business_date']).max()
    all_rev   = list(df['net_revenue'])
    for i in range(1, days_ahead+1):
        nd = last_date + timedelta(days=i)
        hist = all_rev + [p['predicted_revenue'] for p in predictions]
        row = {'day_of_week':nd.dayofweek,'week_of_year':nd.isocalendar()[1],
               'month':nd.month,'is_weekend':int(nd.dayofweek in[4,5,6]),'is_holiday':0,
               'lag_7d':hist[-7] if len(hist)>=7 else np.mean(hist),
               'lag_14d':hist[-14] if len(hist)>=14 else np.mean(hist),
               'lag_28d':hist[-28] if len(hist)>=28 else np.mean(hist),
               'rolling_7d_avg':np.mean(hist[-7:]),'rolling_30d_avg':np.mean(hist[-30:])}
        pred = max(0, float(model.predict(pd.DataFrame([row])[FEATURE_COLS])[0]))
        predictions.append({'date':nd.date().isoformat(),'predicted_revenue':round(pred,2)})
    return predictions
```

**Pro tip:** retrain weekly, not daily. With 60–365 rows, daily retraining gives negligible accuracy gains. Add OpenMeteo weather features only after the baseline is established.

## Done when
You can train a model on 60+ days of seeded data and generate a 14-day forecast.

## Then
Update checkbox, `git commit`, move to `step-09-llm.md`.
