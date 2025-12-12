import os
from datetime import timedelta

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Redis
    redis_host: str = os.environ.get("REDIS_HOST", "redis")
    redis_port: int = os.environ.get("REDIS_PORT", 6379)
    # Runtime
    workers: int = os.environ.get("WORKERS_COUNT", 4)
    graceful_timeout_seconds: timedelta = timedelta(minutes=os.environ.get("SHUTDOWN_TIME_MINUTES", 30))
    status_log_interval: int = os.environ.get("STATUS_LOG_INTERVAL", 5)
    broadcast_interval_seconds: int = os.environ.get("BROADCAST_INTERVAL", 5)
    broadcast_channel: str = os.environ.get("BROADCAST_CHANNEL", "ws:broadcast")
    test_broadcast_owner_key: str = os.environ.get("TEST_BROADCAST_OWNER_KEY", "ws:test_broadcast_owner")
    test_broadcast_ttl_second: int = os.environ.get("TEST_BROADCAST_TTL_SECONDS", 30)

settings = Settings()
