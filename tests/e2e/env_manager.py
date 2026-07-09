import socket
import subprocess
import urllib.parse

def check_postgres_connection(db_url):
    """
    Check connection to PostgreSQL database.
    Attempts psycopg2 connection first, falls back to direct socket connection check.
    """
    try:
        import psycopg2
        conn = psycopg2.connect(db_url, connect_timeout=3)
        conn.close()
        return True
    except Exception:
        try:
            parsed = urllib.parse.urlparse(db_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 5432
            s = socket.create_connection((host, port), timeout=3)
            s.close()
            return True
        except Exception:
            return False

def check_redis_connection(redis_url):
    """
    Check connection to Redis.
    Attempts redis ping first, falls back to direct socket connection check.
    """
    try:
        import redis
        r = redis.Redis.from_url(redis_url, socket_timeout=3)
        r.ping()
        return True
    except Exception:
        try:
            parsed = urllib.parse.urlparse(redis_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 6379
            s = socket.create_connection((host, port), timeout=3)
            s.close()
            return True
        except Exception:
            return False

def check_docker_containers():
    """
    Check status of Docker containers.
    Returns (status_bool, details_str).
    """
    try:
        res = subprocess.run(["docker", "compose", "ps", "--format", "json"], capture_output=True, text=True)
        if res.returncode == 0:
            return True, res.stdout
        res = subprocess.run(["docker", "ps"], capture_output=True, text=True)
        if res.returncode == 0:
            return True, "Docker daemon is running, but 'docker compose ps' failed or returned empty: " + res.stdout
        return False, "Docker daemon is not running or docker command failed"
    except Exception as e:
        return False, f"Docker command exception: {str(e)}"
