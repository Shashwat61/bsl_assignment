import subprocess
import time
import requests
import pytest

BASE_URL = "http://localhost:5000"


def _wait_for_api(timeout=30):
    """Wait for the Flask API to become responsive."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=3)
            if r.status_code in (200, 503):
                return True
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(1)
    return False


@pytest.fixture(autouse=True)
def wait_for_api():
    """Ensure API is up before each test."""
    assert _wait_for_api(), "Flask API did not start within 30 seconds"


def test_services_running():
    """Test that PostgreSQL, Redis, and Python processes are running."""
    result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
    ps_output = result.stdout.lower()
    assert "postgres" in ps_output, "PostgreSQL process not found"
    assert "redis" in ps_output, "Redis process not found"
    assert "python" in ps_output, "Python/Flask process not found"


def test_health_endpoint():
    """Test that /health returns 200 with all services connected."""
    r = requests.get(f"{BASE_URL}/health", timeout=5)
    assert r.status_code == 200, f"Health check returned {r.status_code}: {r.text}"
    data = r.json()
    assert data["postgres"] == "connected", f"Postgres status: {data['postgres']}"
    assert data["redis"] == "connected", f"Redis status: {data['redis']}"
    assert data["app"] == "running", f"App status: {data['app']}"


def test_create_user():
    """Test creating a user via POST /users."""
    payload = {"name": "Alice Smith", "email": "alice@example.com", "age": 30}
    r = requests.post(f"{BASE_URL}/users", json=payload, timeout=5)
    assert r.status_code == 201, f"Create user returned {r.status_code}: {r.text}"
    data = r.json()
    assert data["name"] == "Alice Smith"
    assert data["email"] == "alice@example.com"
    assert data["age"] == 30
    assert "id" in data


def test_get_user():
    """Test getting a user via GET /users/<id>."""
    # Create a user first
    payload = {"name": "Bob Jones", "email": "bob@example.com", "age": 25}
    create_resp = requests.post(f"{BASE_URL}/users", json=payload, timeout=5)
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    # Get the user
    r = requests.get(f"{BASE_URL}/users/{user_id}", timeout=5)
    assert r.status_code == 200, f"Get user returned {r.status_code}: {r.text}"
    data = r.json()
    assert data["name"] == "Bob Jones"
    assert data["email"] == "bob@example.com"
    assert data["age"] == 25
    assert "source" in data


def test_list_users():
    """Test listing users via GET /users."""
    # Create a user to ensure list is non-empty
    payload = {"name": "Charlie Brown", "email": "charlie@example.com", "age": 35}
    requests.post(f"{BASE_URL}/users", json=payload, timeout=5)

    r = requests.get(f"{BASE_URL}/users", timeout=5)
    assert r.status_code == 200, f"List users returned {r.status_code}: {r.text}"
    data = r.json()
    assert isinstance(data, list), "Expected a list of users"
    assert len(data) > 0, "Expected at least one user"
    user = data[0]
    assert "id" in user
    assert "name" in user
    assert "email" in user
    assert "age" in user


def test_delete_user():
    """Test deleting a user via DELETE /users/<id>."""
    # Create a user
    payload = {"name": "Dave Wilson", "email": "dave@example.com", "age": 40}
    create_resp = requests.post(f"{BASE_URL}/users", json=payload, timeout=5)
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    # Delete the user
    r = requests.delete(f"{BASE_URL}/users/{user_id}", timeout=5)
    assert r.status_code == 200, f"Delete returned {r.status_code}: {r.text}"

    # Verify user is gone
    r = requests.get(f"{BASE_URL}/users/{user_id}", timeout=5)
    assert r.status_code == 404, f"Expected 404 after delete, got {r.status_code}"


def test_delete_nonexistent_user():
    """Test deleting a user that doesn't exist returns 404."""
    r = requests.delete(f"{BASE_URL}/users/99999", timeout=5)
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"


def test_redis_caching():
    """Test that Redis caching works — first fetch from DB, second from cache."""
    # Create a fresh user
    payload = {"name": "Eve Cache", "email": "eve.cache@example.com", "age": 28}
    create_resp = requests.post(f"{BASE_URL}/users", json=payload, timeout=5)
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    # First GET should come from database
    r1 = requests.get(f"{BASE_URL}/users/{user_id}", timeout=5)
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["source"] == "database", f"First fetch should be from database, got: {data1['source']}"

    # Second GET should come from cache
    r2 = requests.get(f"{BASE_URL}/users/{user_id}", timeout=5)
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["source"] == "cache", f"Second fetch should be from cache, got: {data2['source']}"


def test_long_email():
    """Test that long email addresses (>50 chars) are accepted and stored correctly."""
    long_email = "this.is.a.very.long.email.address.for.testing.purposes@subdomain.example.com"
    assert len(long_email) > 50, "Test email should be longer than 50 characters"

    payload = {"name": "Long Email User", "email": long_email, "age": 33}
    r = requests.post(f"{BASE_URL}/users", json=payload, timeout=5)
    assert r.status_code == 201, f"Create with long email returned {r.status_code}: {r.text}"
    user_id = r.json()["id"]

    # Verify the email was stored correctly (not truncated)
    r2 = requests.get(f"{BASE_URL}/users/{user_id}", timeout=5)
    assert r2.status_code == 200
    assert r2.json()["email"] == long_email, "Long email was truncated or modified"


def test_startup_script_works():
    """Test that start.sh exists, is executable, and has a pg_isready wait loop."""
    import os
    assert os.path.isfile("/app/start.sh"), "start.sh does not exist"
    assert os.access("/app/start.sh", os.X_OK), "start.sh is not executable"

    with open("/app/start.sh", "r") as f:
        content = f.read()
    has_readiness_check = (
        "pg_isready" in content
        or ("until" in content and ("psql" in content or "pg_" in content))
        or ("while" in content and ("psql" in content or "pg_" in content))
        or ("for" in content and ("psql" in content or "pg_" in content))
        or ("sleep" in content and ("psql" in content or "pg_" in content))
    )
    assert has_readiness_check, "start.sh should contain a PostgreSQL readiness check (e.g., pg_isready wait loop)"
