"""Runtime configuration loaded from environment variables."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = "IDDVR API"
    app_version: str = "0.1.0"
    database_url: str = "postgresql://iddrv_user:iddrv_secret_2024@localhost:5432/iddrv"
    db_connect_timeout_s: int = 3

    @classmethod
    def from_env(cls) -> "Settings":
        timeout = os.getenv("DB_CONNECT_TIMEOUT_S", "3")
        try:
            timeout_value = int(timeout)
        except ValueError:
            timeout_value = 3
        return cls(
            app_name=os.getenv("APP_NAME", "IDDVR API"),
            app_version=os.getenv("APP_VERSION", "0.1.0"),
            database_url=os.getenv("DATABASE_URL", cls.database_url),
            db_connect_timeout_s=max(1, timeout_value),
        )


settings = Settings.from_env()
