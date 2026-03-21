# Architecture & Component Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Container                         │
│                                                             │
│  ┌──────────┐     ┌──────────────┐     ┌────────────────┐  │
│  │  Redis    │◄────│  Flask App   │────►│  PostgreSQL    │  │
│  │ (Cache)   │     │  (Port 5000) │     │  (Port 5432)   │  │
│  │ Port 6379 │     │              │     │                │  │
│  └──────────┘     └──────────────┘     └────────────────┘  │
│       ▲                  ▲                     ▲           │
│       │                  │                     │           │
│  redis.conf         app.py + config.py    postgresql.conf  │
│                          │                pg_hba.conf       │
│                     start.sh                               │
│                  (entrypoint)                               │
└─────────────────────────────────────────────────────────────┘
```

## Component Descriptions

### 1. Flask Application (`app.py`)
- REST API with 5 endpoints (health, CRUD for users)
- Reads config from `config.py` which pulls from environment variables
- Uses `psycopg2` for PostgreSQL connections
- Uses `redis-py` for Redis caching with **silent fallback** — if Redis fails, the app still works but returns `"source": "database"` instead of `"source": "cache"`
- Runs on port 5000 via `python app.py`

### 2. PostgreSQL 15
- Installed via Debian packages (`postgresql-15`)
- Cluster initialized automatically by the Debian package at install time
- Config location: `/etc/postgresql/15/main/postgresql.conf`
- Data directory: `/var/lib/postgresql/15/main/`
- Auth config: `/etc/postgresql/15/main/pg_hba.conf` (uses `scram-sha-256` for TCP)
- Database: `flaskapp`, User: `flaskuser`, Password: `flaskpass`
- Managed via `pg_ctlcluster 15 main start/stop`

### 3. Redis 7
- Installed via Debian packages (`redis-server`)
- Custom config at `/app/redis.conf`
- Runs daemonized on port 6379
- **Has password authentication enabled** (`requirepass secretpass123`)
- Used as a read-through cache for user lookups

### 4. Configuration (`config.py`)
- Reads all connection parameters from environment variables with sensible defaults
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASS` → PostgreSQL
- `REDIS_HOST`, `REDIS_PORT` → Redis
- Constructs a `DATABASE_URL` as a libpq connection string

### 5. Startup Script (`start.sh`)
- Entrypoint for the container (`CMD ["/app/start.sh"]`)
- Starts Redis, then PostgreSQL, then runs `init_db.sql`, then starts Flask
- **Critical**: Must ensure PostgreSQL is ready before Flask starts

### 6. Database Schema (`init_db.sql`)
- Creates the `users` table with columns: `id`, `name`, `email`, `age`, `created_at`
- Run during startup by `start.sh`

## Request Flow

```
Client Request
    │
    ▼
Flask App (port 5000)
    │
    ├── GET /health
    │     ├── Try psycopg2.connect() → postgres status
    │     ├── Try redis.ping() → redis status
    │     └── Return JSON with all statuses
    │
    ├── POST /users
    │     └── INSERT into PostgreSQL → return 201
    │
    ├── GET /users/<id>
    │     ├── Check Redis cache (key: "user:{id}")
    │     │     ├── HIT → return with "source": "cache"
    │     │     └── MISS → query PostgreSQL
    │     │               ├── Store in Redis (TTL: 1 hour)
    │     │               └── Return with "source": "database"
    │     └── Redis unavailable → fallback to PostgreSQL silently
    │
    ├── GET /users
    │     └── SELECT all from PostgreSQL → return list
    │
    └── DELETE /users/<id>
          ├── DELETE from PostgreSQL
          ├── Invalidate Redis cache (delete key)
          └── Return 200 or 404
```

## Injected Bugs (6 Total)

| # | Bug | Location | Symptom | Type |
|---|-----|----------|---------|------|
| 1 | `listen_addresses = ''` | Dockerfile → postgresql.conf | Postgres refuses TCP connections | Infra config |
| 2 | Redis password mismatch | redis.conf vs config.py/app.py | Redis silently fails, caching broken | App + infra |
| 3 | No startup wait loop | start.sh | Race condition: Flask starts before Postgres is ready | Startup script |
| 4 | `DB_PORT=5433` (wrong) | Dockerfile ENV | Second "connection refused" after fixing Bug 1 | Env var |
| 5 | `email VARCHAR(50)` | init_db.sql | Long emails fail to insert | Schema |
| 6 | `REDIS_PORT=6380` (wrong) | Dockerfile ENV | Redis connection fails even after fixing password | Env var |

### Bug Interaction Map

```
Agent starts debugging
    │
    ▼
"connection refused" on DB
    ├── Bug 1: listen_addresses = '' → fix postgresql.conf
    │   (still broken!)
    └── Bug 4: DB_PORT=5433 → fix env var to 5432
            │
            ▼
    DB now works, but...
    ├── Bug 3: Flask may start before Postgres → fix start.sh
    │
    ▼
    App "works" for basic CRUD, but...
    ├── Bug 2: Redis needs password → fix config.py + app.py
    │   (still broken even after password fix!)
    ├── Bug 6: REDIS_PORT=6380 → fix env var to 6379
    │
    ▼
    Redis caching now works, but...
    └── Bug 5: email VARCHAR(50) → only fails with long emails
              → fix init_db.sql + ALTER TABLE
```

**Why it's hard:**
- Bugs 1+4 produce the **same symptom** (double layer)
- Bugs 2+6 produce the **same symptom** for Redis (triple layer with silent failure)
- Bug 2 is **silent** — app appears to work without Redis
- Bug 3 is **intermittent** — sometimes works if Postgres starts fast
- Bug 5 only triggers with **specific data** (emails > 50 chars)

## Test Suite (10 Functional Tests)

| # | Test | What It Validates |
|---|------|-------------------|
| 1 | `test_services_running` | All 3 processes are running (ps aux) |
| 2 | `test_health_endpoint` | GET /health → 200, all services "connected" |
| 3 | `test_create_user` | POST /users → 201 with correct data |
| 4 | `test_get_user` | GET /users/id → correct user data + source field |
| 5 | `test_list_users` | GET /users → non-empty list with all fields |
| 6 | `test_delete_user` | DELETE then GET → 404 |
| 7 | `test_delete_nonexistent` | DELETE /users/99999 → 404 |
| 8 | `test_redis_caching` | 1st GET source="database", 2nd GET source="cache" |
| 9 | `test_long_email` | POST with 77-char email succeeds + not truncated |
| 10 | `test_startup_script` | start.sh exists, executable, has readiness check |

## File Structure

```
broken_flask_deployment/
├── task.toml              # Harbor metadata (hard, system-administration)
├── instruction.md         # Agent prompt (goal-oriented, no solutions)
├── ARCHITECTURE.md        # This file
├── environment/
│   ├── Dockerfile         # Python 3.12 + PG 15 + Redis, injects Bugs 1,4,6
│   ├── app.py             # Flask API with silent Redis fallback (Bug 2)
│   ├── config.py          # Config from env vars, missing Redis password
│   ├── init_db.sql        # Schema with VARCHAR(50) email (Bug 5)
│   ├── redis.conf         # requirepass set (Bug 2 source)
│   ├── start.sh           # No readiness check (Bug 3)
│   └── requirements.txt   # Pinned: flask, psycopg2-binary, redis, gunicorn
├── solution/
│   └── solve.sh           # Fixes all 6 bugs, starts services, verifies
└── tests/
    ├── test.sh            # Harbor test runner (writes reward file)
    └── test_outputs.py    # 10 functional pytest tests
```

## Validation Results

- **Oracle**: 10/10 tests pass (Mean: 1.000)
- **AI Agent** (terminus-2, kimi-k2-instruct-0905, k=10): Mean: 0.600 (6/10 pass)
- Target range: > 0.0 and < 0.7 ✓
