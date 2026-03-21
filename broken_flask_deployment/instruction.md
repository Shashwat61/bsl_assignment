# Broken Flask Deployment — Debug and Fix

A Flask REST API backed by PostgreSQL and Redis was deployed inside this container. The application source code is located in `/app/`. The deployment is **broken** — the app does not work correctly and multiple issues must be found and fixed.

## Your Goal

Get the full application running correctly so that all of the following work as expected:

1. **All services must be running** — PostgreSQL, Redis, and the Flask application.
2. **`/app/start.sh`** is the entrypoint script that should reliably start all services in the correct order. It must be robust against timing issues.
3. The Flask API (running on port 5000) must expose these endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Returns JSON health status of all three services (app, postgres, redis). All must report `"connected"`. |
| `POST` | `/users` | Creates a user. Expects JSON body with `name`, `email`, and `age`. |
| `GET` | `/users/<id>` | Returns a single user. Should use Redis as a read-through cache (response includes `"source": "cache"` or `"source": "database"`). |
| `GET` | `/users` | Lists all users. |
| `DELETE` | `/users/<id>` | Deletes a user and invalidates any cached data. Returns 404 if user doesn't exist. |

## Key Files

- `/app/app.py` — Flask application
- `/app/config.py` — Configuration (reads from environment variables)
- `/app/init_db.sql` — Database schema initialization
- `/app/redis.conf` — Redis server configuration
- `/app/start.sh` — Service startup script
- `/app/requirements.txt` — Python dependencies

## Important Details

- Redis caching must actually work — every user lookup should be cached so that subsequent reads come from Redis, not the database.
- The app should handle email addresses of any reasonable length without truncation or errors.
