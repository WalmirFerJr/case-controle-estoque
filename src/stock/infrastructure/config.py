from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração via variáveis de ambiente com prefixo ``STOCK_`` (12-factor).

    Os defaults servem apenas para desenvolvimento local com o docker-compose.
    """

    model_config = SettingsConfigDict(env_prefix="STOCK_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://stock:stock@localhost:5432/stock"
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_lock_timeout_ms: int = 5_000
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
