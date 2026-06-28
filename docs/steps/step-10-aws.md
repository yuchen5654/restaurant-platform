# Step 10 — Production Deployment on AWS

**Estimated time:** 6–10 hours
**Phase:** Deploy (after Phase 1 validated).

---

## Goal
Production infrastructure: managed Postgres, API + workers on EC2, React on S3+CloudFront, secrets in Secrets Manager.

## Services

- **RDS PostgreSQL** — db.t3.medium, Multi-AZ, 7-day backups, **encryption at rest from day one**. Enable TimescaleDB via custom parameter group.
- **EC2 t3.small** — FastAPI + Celery as systemd services.
- **ElastiCache Redis** — cache.t3.micro.
- **S3 + CloudFront** — React static hosting, HTTPS via ACM.
- **Secrets Manager** — DATABASE_URL, SECRET_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, TOAST_*, SENDGRID_API_KEY.

## systemd — FastAPI (`/etc/systemd/system/restaurant-api.service`)

```ini
[Unit]
Description=Restaurant Platform API
After=network.target
[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/restaurant-platform/backend
EnvironmentFile=/home/ubuntu/restaurant-platform/backend/.env
ExecStart=/home/ubuntu/restaurant-platform/backend/venv/bin/uvicorn \
          app.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
```

## systemd — Celery (`/etc/systemd/system/restaurant-celery.service`)

```ini
[Unit]
Description=Restaurant Platform Celery Worker
After=network.target
[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/restaurant-platform/backend
EnvironmentFile=/home/ubuntu/restaurant-platform/backend/.env
ExecStart=/home/ubuntu/restaurant-platform/backend/venv/bin/celery \
          -A app.workers.celery_app worker --loglevel=info
Restart=always
[Install]
WantedBy=multi-user.target
```

## Frontend deploy — `deploy-frontend.sh`

```bash
#!/bin/bash
BUCKET='your-restaurant-platform-frontend'
DIST_ID='YOUR_CLOUDFRONT_DISTRIBUTION_ID'
cd frontend
REACT_APP_API_URL=https://api.yourplatform.com npm run build
aws s3 sync build/ s3://$BUCKET --delete
aws cloudfront create-invalidation --distribution-id $DIST_ID --paths '/*'
```

**Watch out:** enable RDS encryption at rest from the start, not as an afterthought. Restaurant financial data is sensitive, and any operator with an accountant will ask about your security posture.

## Done when
API reachable over HTTPS, frontend served from CloudFront, Celery beat running nightly POS pulls and alerts, all secrets in Secrets Manager (none in git).

## Then
Update checkbox, `git commit`. Phase 1 platform is live.
