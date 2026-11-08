"""Fixtures compartilhadas.

Testes de integração/concorrência usam um PostgreSQL **real**: lock de linha,
CHECK constraints e ON CONFLICT não podem ser validados com SQLite ou mocks.

- Local: sobe um container descartável via testcontainers (requer Docker).
- CI: se ``STOCK_TEST_DATABASE_URL`` estiver definida, usa esse banco (service container).
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from stock.infrastructure.config import Settings
from stock.infrastructure.persistence import create_db_engine, create_session_factory
from stock.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
POSTGRES_IMAGE = "postgres:16-alpine"


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    external_url = os.getenv("STOCK_TEST_DATABASE_URL")
    if external_url:
        yield external_url
        return
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer(POSTGRES_IMAGE, driver="psycopg") as container:
        yield container.get_connection_url()


@pytest.fixture(scope="session")
def alembic_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    config.attributes["configure_logger"] = False
    return config


@pytest.fixture(scope="session")
def settings(database_url: str, alembic_config: Config) -> Settings:
    command.upgrade(alembic_config, "head")
    return Settings(database_url=database_url, db_pool_size=20, db_max_overflow=40)


@pytest.fixture(scope="session")
def engine(settings: Settings) -> Iterator[Engine]:
    engine = create_db_engine(settings)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)


@pytest.fixture
def clean_db(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE stock_movements, holds, products CASCADE"))


@pytest.fixture
def client(settings: Settings, clean_db: None) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
