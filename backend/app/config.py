"""Runtime configuration loaded from environment variables."""

from dataclasses import dataclass
import os
import secrets


@dataclass(frozen=True)
class Settings:
    app_name: str = "IDDVR API"
    app_version: str = "0.1.0"
    database_url: str = "postgresql://iddrv_user:iddrv_secret_2024@localhost:5432/iddrv"
    db_connect_timeout_s: int = 3
    session_secret: str = ""
    session_ttl_s: int = 28800
    session_cookie_name: str = "iddrv_session"
    session_cookie_secure: bool = False
    app_environment: str = "development"

    @classmethod
    def from_env(cls) -> "Settings":
        timeout = os.getenv("DB_CONNECT_TIMEOUT_S", "3")
        try:
            timeout_value = int(timeout)
        except ValueError:
            timeout_value = 3
        ttl = os.getenv("SESSION_TTL_S", "28800")
        try:
            ttl_value = int(ttl)
        except ValueError:
            ttl_value = 28800
        # A random fallback keeps local development usable while ensuring a
        # copied source tree cannot share a production signing secret.
        secret = os.getenv("SESSION_SECRET") or secrets.token_urlsafe(32)
        environment = os.getenv("APP_ENV", "development").lower()
        return cls(
            app_name=os.getenv("APP_NAME", "IDDVR API"),
            app_version=os.getenv("APP_VERSION", "0.1.0"),
            database_url=os.getenv("DATABASE_URL", cls.database_url),
            db_connect_timeout_s=max(1, timeout_value),
            session_secret=secret,
            session_ttl_s=max(300, ttl_value),
            session_cookie_name=os.getenv("SESSION_COOKIE_NAME", "iddrv_session"),
            session_cookie_secure=os.getenv("SESSION_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"},
            app_environment=environment,
        )


settings = Settings.from_env()
