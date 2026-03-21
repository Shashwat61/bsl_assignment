#!/bin/bash
set -e

echo "=== Fix 1: PostgreSQL listen_addresses ==="
sed -i "s/listen_addresses = ''/listen_addresses = 'localhost'/" /etc/postgresql/15/main/postgresql.conf

echo "=== Fix 4: Correct DB_PORT environment variable ==="
export DB_PORT=5432

echo "=== Fix 6: Correct REDIS_PORT environment variable ==="
export REDIS_PORT=6379

echo "=== Fix 2: Add Redis password to config.py and app.py ==="
# Add REDIS_PASSWORD to config.py
sed -i '/REDIS_PORT/a\    REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "secretpass123")' /app/config.py

# Add password parameter to Redis() call in app.py
python3 -c "
content = open('/app/app.py').read()
content = content.replace(
    'decode_responses=True,',
    'decode_responses=True,\n            password=config.REDIS_PASSWORD,'
)
open('/app/app.py', 'w').write(content)
"

echo "=== Fix 5: Increase email VARCHAR length ==="
sed -i 's/email VARCHAR(50)/email VARCHAR(255)/' /app/init_db.sql

echo "=== Fix 3: Add pg_isready wait loop to start.sh ==="
cat > /app/start.sh << 'STARTEOF'
#!/bin/bash

# Start Redis
redis-server /app/redis.conf

# Start PostgreSQL
pg_ctlcluster 15 main start

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
until pg_isready -h localhost -p 5432 -U flaskuser; do
    echo "PostgreSQL not ready, waiting..."
    sleep 1
done
echo "PostgreSQL is ready!"

# Fix DB_PORT and REDIS_PORT if they're wrong
export DB_PORT=5432
export REDIS_PORT=6379

# Initialize database schema
PGPASSWORD=flaskpass psql -h localhost -U flaskuser -d flaskapp -f /app/init_db.sql

# Start Flask application
cd /app
python app.py
STARTEOF
chmod +x /app/start.sh

echo "=== Starting services ==="

# Start Redis
redis-server /app/redis.conf 2>/dev/null || true

# Start PostgreSQL
pg_ctlcluster 15 main start 2>/dev/null || true

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
until pg_isready -h localhost -p 5432 -U flaskuser 2>/dev/null; do
    sleep 1
done
echo "PostgreSQL is ready!"

# Export correct port
export DB_PORT=5432

# Initialize schema and alter existing table if it already exists
PGPASSWORD=flaskpass psql -h localhost -U flaskuser -d flaskapp -f /app/init_db.sql 2>/dev/null || true
PGPASSWORD=flaskpass psql -h localhost -U flaskuser -d flaskapp -c "ALTER TABLE users ALTER COLUMN email TYPE VARCHAR(255);" 2>/dev/null || true

# Start Flask in background
cd /app
python app.py &

# Wait for Flask to be ready
echo "Waiting for Flask..."
for i in $(seq 1 30); do
    if curl -s http://localhost:5000/health > /dev/null 2>&1; then
        echo "Flask is ready!"
        break
    fi
    sleep 1
done

echo "=== All fixes applied and services started ==="
