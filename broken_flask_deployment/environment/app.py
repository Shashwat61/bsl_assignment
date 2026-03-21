import json
import psycopg2
import psycopg2.extras
import redis as redis_lib
from flask import Flask, request, jsonify
from config import Config

app = Flask(__name__)
config = Config()


def get_db_connection():
    """Get a PostgreSQL database connection."""
    conn = psycopg2.connect(config.DATABASE_URL)
    conn.autocommit = True
    return conn


def get_redis_client():
    """Get a Redis client. Returns None if connection fails."""
    try:
        client = redis_lib.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            decode_responses=True,
        )
        client.ping()
        return client
    except Exception:
        return None


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    status = {"app": "running", "postgres": "disconnected", "redis": "disconnected"}
    all_healthy = True

    # Check Postgres
    try:
        conn = get_db_connection()
        conn.close()
        status["postgres"] = "connected"
    except Exception:
        all_healthy = False

    # Check Redis
    try:
        r = get_redis_client()
        if r is not None:
            status["redis"] = "connected"
        else:
            all_healthy = False
    except Exception:
        all_healthy = False

    code = 200 if all_healthy else 503
    return jsonify(status), code


@app.route("/users", methods=["POST"])
def create_user():
    """Create a new user."""
    data = request.get_json()
    if not data or not all(k in data for k in ("name", "email", "age")):
        return jsonify({"error": "Missing required fields: name, email, age"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (name, email, age) VALUES (%s, %s, %s) RETURNING id, name, email, age, created_at",
            (data["name"], data["email"], data["age"]),
        )
        row = cur.fetchone()
        user = {
            "id": row[0],
            "name": row[1],
            "email": row[2],
            "age": row[3],
            "created_at": row[4].isoformat(),
        }
        cur.close()
        conn.close()
        return jsonify(user), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    """Get a user by ID. Uses Redis cache if available."""
    cache_key = f"user:{user_id}"

    # Try cache first
    r = get_redis_client()
    if r is not None:
        try:
            cached = r.get(cache_key)
            if cached:
                user = json.loads(cached)
                user["source"] = "cache"
                return jsonify(user), 200
        except Exception:
            pass

    # Fallback to database
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, email, age, created_at FROM users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row is None:
            return jsonify({"error": "User not found"}), 404

        user = {
            "id": row[0],
            "name": row[1],
            "email": row[2],
            "age": row[3],
            "created_at": row[4].isoformat(),
        }

        # Cache in Redis
        if r is not None:
            try:
                r.setex(cache_key, 3600, json.dumps(user))
            except Exception:
                pass

        user["source"] = "database"
        return jsonify(user), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/users", methods=["GET"])
def list_users():
    """List all users."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, name, email, age, created_at FROM users ORDER BY id")
        rows = cur.fetchall()
        cur.close()
        conn.close()

        users = []
        for row in rows:
            users.append(
                {
                    "id": row[0],
                    "name": row[1],
                    "email": row[2],
                    "age": row[3],
                    "created_at": row[4].isoformat(),
                }
            )
        return jsonify(users), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    """Delete a user by ID."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE id = %s RETURNING id", (user_id,))
        deleted = cur.fetchone()
        cur.close()
        conn.close()

        if deleted is None:
            return jsonify({"error": "User not found"}), 404

        # Invalidate cache
        r = get_redis_client()
        if r is not None:
            try:
                r.delete(f"user:{user_id}")
            except Exception:
                pass

        return jsonify({"message": f"User {user_id} deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
