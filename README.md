# bom-ticket-monitor — Notes

This repository contains the ticket-monitoring Flask app.

## Rate limiter (production)

The app supports a persistent rate-limit storage backend to make limits reliable across processes and restarts.

- Environment variable: `RATELIMIT_STORAGE_URL`
- Fallback env names checked: `REDIS_URL`, `RATELIMIT_STORAGE`
- Example value (local Redis): `redis://localhost:6379/0`

When `RATELIMIT_STORAGE_URL` is set the app will use that storage for `Flask-Limiter`.
If not set the app falls back to in-memory storage (suitable only for development).

Example Docker Compose snippet to run Redis for local testing:

```yaml
services:
  redis:
    image: redis:7
    ports:
      - 6379:6379

  web:
    build: .
    environment:
      - RATELIMIT_STORAGE_URL=redis://redis:6379/0
    depends_on:
      - redis
```

Quick test (after starting the app):

```bash
# GET root, inspect rate-limit headers
curl -i http://127.0.0.1:5000/ | egrep -i "X-Ratelimit|Retry-After"

# POST suggestion and see per-endpoint headers
curl -i -XPOST -H "Content-Type: application/json" -d '{"siteName":"Test","siteUrl":"https://example.com","contact":"me@example.com"}' http://127.0.0.1:5000/api/suggest-site | egrep -i "X-Ratelimit|Retry-After"
```

Notes:
- The app already enables rate-limit response headers by default (`RATELIMIT_HEADERS_ENABLED`).
- For production, point `RATELIMIT_STORAGE_URL` to a managed Redis (or compatible) instance.

See the full deployment and environment documentation in `DEPLOYMENT.md`.
