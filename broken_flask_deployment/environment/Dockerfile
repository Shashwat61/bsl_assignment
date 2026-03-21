FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-15 \
    postgresql-client-15 \
    redis-server \
    curl \
    procps \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Create Redis log directory
RUN mkdir -p /var/log/redis && chown redis:redis /var/log/redis
RUN mkdir -p /var/lib/redis && chown redis:redis /var/lib/redis

# PostgreSQL cluster is already initialized by the Debian package.
# Config is in /etc/postgresql/15/main/, data in /var/lib/postgresql/15/main/
# Start Postgres temporarily to create user and DB.
RUN pg_ctlcluster 15 main start && \
    su - postgres -c "psql --command \"CREATE USER flaskuser WITH PASSWORD 'flaskpass';\"" && \
    su - postgres -c "psql --command \"CREATE DATABASE flaskapp OWNER flaskuser;\"" && \
    su - postgres -c "psql --command \"GRANT ALL PRIVILEGES ON DATABASE flaskapp TO flaskuser;\"" && \
    pg_ctlcluster 15 main stop

# === BUG 1: Disable TCP connections by setting listen_addresses to empty string ===
RUN echo "listen_addresses = ''" >> /etc/postgresql/15/main/postgresql.conf

# === BUG 4: Wrong database port in environment variable ===
ENV DB_PORT=5433
ENV DB_HOST=localhost
ENV DB_NAME=flaskapp
ENV DB_USER=flaskuser
ENV DB_PASS=flaskpass
ENV REDIS_HOST=localhost
# === BUG 6: Wrong Redis port in environment variable ===
ENV REDIS_PORT=6380

# Copy application files
WORKDIR /app
COPY * /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Make start script executable
RUN chmod +x /app/start.sh

# Create PostgreSQL log directory
RUN mkdir -p /var/log/postgresql && chown postgres:postgres /var/log/postgresql

EXPOSE 5000

CMD ["/app/start.sh"]
