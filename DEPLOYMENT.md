# Deployment & Production Notes

This document describes recommended configuration and deployment steps for production.

## Prerequisites
- Python 3.11+ (match project's venv)
- PostgreSQL (or another production DB)
- Redis (for rate-limiter storage in clustered/deployed setups)
- Docker (optional) for local integration testing

## Important environment variables
- `ADMIN_PASSWORD` — REQUIRED. Strong password for admin endpoints.
- `SECRET_KEY` — REQUIRED in production; used by Flask sessions.
- `DATABASE_URL` — optional locally, **required** for production; e.g. `postgresql://user:pass@host:5432/dbname`.
- `RATELIMIT_STORAGE_URL` or `REDIS_URL` — e.g. `redis://redis:6379/0` to persist rate limits across processes.
- Notifications:
  - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
  - `DISCORD_WEBHOOK_ALERTS`, `DISCORD_WEBHOOK_SUGGESTIONS`
  - `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SENDER_EMAIL`

## Running locally (recommended for dev)
1. Create and activate a virtualenv.
2. Install requirements: `pip install -r requirements.txt`.
3. Set `ADMIN_PASSWORD` and run: `python app.py`.

## Using Docker Compose for local integration (Redis)
The repo includes a `docker-compose.yml` with a `redis` service. To start Redis locally:

```powershell
docker compose -f docker-compose.yml up -d redis
```

Then start the app with `RATELIMIT_STORAGE_URL` pointing at the Redis instance:

```powershell
$env:RATELIMIT_STORAGE_URL='redis://127.0.0.1:6379/0'
$env:ADMIN_PASSWORD='your-admin-pass'
python app.py
```

Or use the `web` service in the compose file for a full local deploy.

## Production recommendations
- Use `gunicorn` with `eventlet` worker for Socket.IO support:
  `gunicorn -k eventlet -w 1 -b 0.0.0.0:5000 app:app`
- Ensure `SECRET_KEY` and `ADMIN_PASSWORD` are set and never committed.
- Point `DATABASE_URL` to a managed PostgreSQL instance, enable TLS.
- Point `RATELIMIT_STORAGE_URL` to a managed Redis instance for consistent limits.
- Run behind a reverse proxy (nginx, Traefik) and enable HTTPS (use HSTS).
- Configure logging aggregation (e.g., CloudWatch, Papertrail, or ELK) and alerting.

## Monitoring & backups
- Export application logs and set up alerting for errors. Consider Sentry for error monitoring.
- Back up your database regularly and test restores.

## Security notes
- The app applies security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options).
- Keep dependencies updated and scan for vulnerabilities.

## CI/CD
- Typical pipeline: install, run tests, build container image, push to registry, deploy.

## Quick verification commands
- List rate-limit headers (after app running):
  `curl -i http://127.0.0.1:5000/ | egrep -i "X-Ratelimit|Retry-After"`

## Troubleshooting
- If you see the Limiter in-memory warning, verify `RATELIMIT_STORAGE_URL` is set and reachable.
