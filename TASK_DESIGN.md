# Task Design: Broken Flask Deployment

## Overview

A Flask REST API was deployed with PostgreSQL and Redis in a single Docker container. The app code is mostly correct, but the **infrastructure/configuration is broken** in 5 subtle ways. The AI agent must act like a sysadmin debugging a broken deployment.

---

## The 5 Bugs

### Bug 1: Postgres Won't Accept TCP Connections
- **Where:** `postgresql.conf` (inside the container at `/var/lib/postgresql/16/main/postgresql.conf`)
- **What:** `listen_addresses = ''` (empty string = no TCP)
- **Symptom:** `connection refused` on any database operation
- **Fix:** Change to `listen_addresses = 'localhost'`
- **Why it's hard:** "connection refused" could mean many things. The AI has to know to check `postgresql.conf`, not just `pg_hba.conf`

### Bug 2: Redis Auth Mismatch (Silent Failure)
- **Where:** `redis.conf` has `requirepass secretpass123` / `config.py` has no password
- **What:** App connects to Redis without a password, but Redis requires one
- **Symptom:** Redis operations fail with `NOAUTH Authentication required` BUT the app catches this silently and falls back to DB-only mode. **The app appears to work!**
- **Fix:** Add `REDIS_PASSWORD = 'secretpass123'` to config.py + pass it to `redis.Redis()` in app.py
- **Why it's hard:** The app "works" — only a specific caching test catches this. The AI might think everything is fine.

### Bug 3: Startup Race Condition
- **Where:** `start.sh`
- **What:** Flask starts immediately after `pg_ctl start`, before Postgres is ready to accept connections
- **Symptom:** First requests fail because tables aren't accessible yet. Intermittent — sometimes works if Postgres starts fast enough.
- **Fix:** Add a `pg_isready` wait loop in start.sh before starting Flask
- **Why it's hard:** If the AI manually starts services during debugging, the timing might be fine. But the test checks that start.sh has a proper readiness check.

### Bug 4: Wrong Database Port (Second Layer)
- **Where:** Dockerfile `ENV DB_PORT=5433`
- **What:** Environment variable says port 5433, but Postgres runs on default 5432
- **Symptom:** Same "connection refused" as Bug 1 — even AFTER fixing Bug 1, this persists
- **Fix:** Change `DB_PORT=5433` to `DB_PORT=5432` (or remove it so the default in config.py kicks in)
- **Why it's hard:** After fixing Bug 1, the AI might think Postgres is still broken. It's a second layer of the same error. The AI has to check env vars, which is a different debugging path.

### Bug 5: Email Column Too Short
- **Where:** `init_db.sql` — `email VARCHAR(50)`
- **What:** Some email addresses are longer than 50 characters
- **Symptom:** `INSERT` fails with `value too long for type character varying(50)` — but only for long emails
- **Fix:** Change to `VARCHAR(255)` in init_db.sql + run `ALTER TABLE users ALTER COLUMN email TYPE VARCHAR(255)` on the live DB
- **Why it's hard:** Short emails work fine. Only triggered by specific test data. The AI has to trace the error back to the schema definition.

---

## Bug Interaction Map

```
Agent runs start.sh
    |
    v
"connection refused" error
    |
    +-- Bug 1: listen_addresses = '' in postgresql.conf
    |   (fix it)
    |
    +-- Still "connection refused"!
    |   Bug 4: DB_PORT=5433 in env (Postgres is on 5432)
    |   (fix it)
    |
    v
DB works now! But...
    |
    +-- Bug 3: Sometimes Flask starts before Postgres is ready
    |   (fix start.sh with pg_isready wait loop)
    |
    v
App seems to work! CRUD operations pass! But...
    |
    +-- Bug 2: Redis caching is silently broken
    |   (app falls back to DB, looks fine unless you test caching specifically)
    |   (add password to Redis connection)
    |
    +-- Bug 5: Long emails fail
        (only shows up with emails >50 chars)
        (fix VARCHAR(50) → VARCHAR(255))
```

---

## File Structure

```
broken_flask_deployment/
├── task.toml
├── instruction.md
├── environment/
│   ├── Dockerfile
│   ├── app.py
│   ├── config.py
│   ├── init_db.sql
│   ├── redis.conf
│   ├── start.sh
│   └── requirements.txt
├── solution/
│   └── solve.sh
└── tests/
    ├── test.sh          (don't touch — Harbor standard)
    └── test_outputs.py
```

---

## API Endpoints (What They Should Do When Working)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Returns JSON with status of app, PostgreSQL, and Redis. All must say `"connected"`. Returns 200 if all connected, 503 otherwise. |
| `POST` | `/users` | Creates a user. Body: `{"name": "...", "email": "...", "age": ...}`. Returns 201. |
| `GET` | `/users/<id>` | Returns user. Checks Redis cache first, falls back to Postgres. Response includes `"source": "cache"` or `"source": "database"`. |
| `GET` | `/users` | Lists all users from Postgres. |
| `DELETE` | `/users/<id>` | Deletes user from Postgres + invalidates Redis cache. Returns 200, or 404 if not found. |

---

## Test Suite (10 Functional Tests)

| # | Test | What It Checks | Which Bug It Catches |
|---|------|---------------|---------------------|
| 1 | `test_services_running` | `ps aux` shows postgres, redis, python processes | General startup |
| 2 | `test_health_endpoint` | GET /health → 200, all services "connected" | Bugs 1, 2, 3, 4 |
| 3 | `test_create_user` | POST /users → 201 with correct data | Bugs 1, 3, 4 |
| 4 | `test_get_user` | GET /users/id → correct user data | Bugs 1, 3, 4 |
| 5 | `test_list_users` | GET /users → list with required fields | Bugs 1, 3, 4 |
| 6 | `test_delete_user` | DELETE then GET → 404 | Bugs 1, 3, 4 |
| 7 | `test_delete_nonexistent_user` | DELETE /users/99999 → 404 | Bugs 1, 3, 4 |
| 8 | `test_redis_caching` | 1st GET source="database", 2nd GET source="cache" | **Bug 2** |
| 9 | `test_long_email` | POST with 88-char email works + not truncated | **Bug 5** |
| 10 | `test_startup_script_works` | start.sh exists, executable, contains pg_isready | **Bug 3** |

---

## Each File — What Goes In It

### task.toml
```toml
version = "1.0"

[metadata]
author_name = "Shashwat"
author_email = "your_email@example.com"
difficulty = "hard"
category = "system-administration"
tags = ["devops", "docker", "database", "web-server", "debugging"]
expert_time_estimate_min = 30.0
junior_time_estimate_min = 180.0

[verifier]
timeout_sec = 900.0

[agent]
timeout_sec = 900.0

[environment]
build_timeout_sec = 600.0
cpus = 1
memory = "2G"
storage = "10G"

[environment.runtime]
python = "3.12"
```

### instruction.md
- Tells the AI: "A Flask API with Postgres and Redis is deployed here but broken. Debug and fix it."
- Lists the expected endpoints and what they should do
- Mentions start.sh is the entrypoint
- Mentions config file locations (so AI knows the landscape)
- Hints about long email support and Redis caching being functional
- Does NOT mention specific bugs, config values, or fixes

### environment/Dockerfile
- Base: `python:3.12-slim-bookworm`
- Installs: `postgresql-16`, `redis-server`, `curl`, `procps`
- Sets up Postgres DB + user during build (initdb, create user/db, run init_db.sql)
- **Injects Bug 1:** Appends `listen_addresses = ''` to postgresql.conf AFTER setup
- **Injects Bug 4:** Sets `ENV DB_PORT=5433`
- Copies all environment files to /app/
- Does NOT include solution/ or tests/

### environment/app.py
- Flask app with 5 endpoints (health, CRUD for users)
- `get_redis_client()` wraps Redis connection in try/except, returns None on failure → **silent fallback (Bug 2 mechanism)**
- GET /users/<id> returns `"source": "cache"` or `"source": "database"` — critical for test_redis_caching

### environment/config.py
- Reads DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS from env vars
- Reads REDIS_HOST, REDIS_PORT from env vars
- **Bug 2:** No REDIS_PASSWORD field at all

### environment/init_db.sql
- Creates users table: id, name, email, age, created_at
- **Bug 5:** `email VARCHAR(50)` — too short

### environment/redis.conf
- Standard Redis config with `daemonize yes`
- **Bug 2 source:** `requirepass secretpass123`

### environment/start.sh
- Starts Redis, Postgres, Flask in sequence
- **Bug 3:** No wait between Postgres start and Flask start

### environment/requirements.txt
```
flask==3.1.0
psycopg2-binary==2.9.10
redis==5.2.1
gunicorn==23.0.0
```

### solution/solve.sh
1. Fix postgresql.conf: `listen_addresses = 'localhost'`
2. Fix config.py + app.py: add Redis password
3. Rewrite start.sh with pg_isready wait loop + correct DB_PORT export
4. Fix init_db.sql: VARCHAR(255)
5. Start services
6. ALTER TABLE on running DB for existing schema

### tests/test_outputs.py
- 10 pytest functions as described in test suite table above
- Has `_wait_for_api()` helper with 30s retry loop
- Uses `requests` library to make HTTP calls to localhost:5000

---

## Implementation Steps

1. Install Harbor CLI: `uv tool install harbor`
2. Initialize: `harbor tasks init "broken_flask_deployment"`
3. Write all files listed above
4. Test Docker build works (may need to adjust package version pins)
5. Run oracle: `harbor run -p "./broken_flask_deployment" -a oracle` — must pass all 10 tests
6. Run AI agent: `harbor run -p "./broken_flask_deployment" -a terminus-2 --model groq/moonshotai/kimi-k2-instruct-0905 -k 10 -n 10`
7. Check: 0% < pass rate < 70%
8. Adjust difficulty if needed
9. Zip: `SHASHWAT_LASTNAME_EXORDIOM_20260322.zip`
10. Email to recruitingops@exordiom.com

---

## Difficulty Tuning Levers

**If too easy (>70% pass rate):**
- Remove hints about long emails from instruction.md
- Add a 6th bug (e.g., wrong pg_hba.conf auth method)
- Make the Redis password read from a file instead of hardcoded

**If too hard (0% pass rate):**
- Add more hints in instruction.md
- Remove Bug 5 (VARCHAR issue)
- Make Bug 2 non-silent (remove the try/except in get_redis_client)
