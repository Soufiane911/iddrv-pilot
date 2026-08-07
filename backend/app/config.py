"""Runtime configuration loaded from environment variables."""

from dataclasses import dataclass
import os
import secrets


@dataclass(frozen=True)
class Settings:
    app_name: str = "IDDVR API"
    app_version: str = "0.1.0"
    database_url: str = "postgresql://iddrv_user@localhost:5432/iddrv"
    db_connect_timeout_s: int = 3
    session_secret: str = ""
    session_ttl_s: int = 28800
    session_cookie_name: str = "iddrv_session"
    session_cookie_secure: bool = False
    app_environment: str = "development"
    session_fail_open: bool = False
    allow_anonymous_reads: bool = False
    metrics_token: str = ""
    metrics_public: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        environment = os.getenv("APP_ENV", "development").lower()
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
        configured_secret = os.getenv("SESSION_SECRET", "").strip()
        insecure_placeholders = {
            "local-development-only-change-me",
            "change-this-before-pilot",
        }
        if environment in {"pilot", "prod", "production"}:
            if len(configured_secret) < 32 or configured_secret in insecure_placeholders:
                raise RuntimeError(
                    "SESSION_SECRET must be explicitly configured with at least 32 characters "
                    "in pilot/production"
                )
            secret = configured_secret
        else:
            # Random per-process fallback is limited to local development/tests.
            secret = configured_secret or secrets.token_urlsafe(32)
        fail_open = os.getenv("SESSION_FAIL_OPEN", "false").lower() in {"1", "true", "yes"}
        allow_anonymous = (
            environment in {"development", "test"}
            and os.getenv("ALLOW_ANONYMOUS_READS", "false").lower() in {"1", "true", "yes"}
        )
        metrics_token = os.getenv("METRICS_TOKEN", "").strip()
        metrics_public_raw = os.getenv("METRICS_PUBLIC", "").strip().lower()
        if metrics_public_raw in {"1", "true", "yes"}:
            metrics_public = True
        elif metrics_public_raw in {"0", "false", "no"}:
            metrics_public = False
        else:
            # Local DX keeps /metrics open; pilot/production require token or admin.
            metrics_public = environment in {"development", "test"} and not metrics_token
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
            session_fail_open=fail_open if environment in {"development", "test"} else False,
            allow_anonymous_reads=allow_anonymous,
            metrics_token=metrics_token,
            metrics_public=metrics_public,
        )


settings = Settings.from_env()
