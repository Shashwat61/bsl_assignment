#!/bin/bash

# Start Redis
redis-server /app/redis.conf

# Start PostgreSQL
pg_ctlcluster 15 main start

# Initialize database schema
PGPASSWORD=flaskpass psql -h localhost -U flaskuser -d flaskapp -f /app/init_db.sql

# Start Flask application
cd /app
python app.py
