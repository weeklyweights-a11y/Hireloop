from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://hireloop:hireloop@localhost:5432/hireloop"
    database_url_sync: str = "postgresql+psycopg2://hireloop:hireloop@localhost:5432/hireloop"
    redis_url: str = "redis://localhost:6379/0"
    environment: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"
    poll_interval_hours: int = 2
    max_poll_concurrency: int = 5
    rate_limit_per_hour: int = 100
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "hireloop"
    admin_key: str = ""


settings = Settings()
