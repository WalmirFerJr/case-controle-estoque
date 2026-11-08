"""Composition root: o único lugar que conhece todas as camadas e as conecta."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.exc import OperationalError

from stock.application.ports import utc_now
from stock.infrastructure.config import Settings, get_settings
from stock.infrastructure.persistence import (
    SqlAlchemyUnitOfWork,
    create_db_engine,
    create_session_factory,
)
from stock.infrastructure.persistence.database import ping
from stock.presentation.api import health
from stock.presentation.api.v1 import router as v1_router
from stock.presentation.errors import register_error_handlers
from stock.presentation.observability import configure_logging, register_request_context

API_DESCRIPTION = """
Controle de estoque com **reservas** e **bloqueios**.

- `disponível = total - reservado - bloqueado`
- Toda operação é atômica e serializada por produto (lock de linha no PostgreSQL).
- Erros seguem Problem Details (`application/problem+json`) com `code` estável.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    app = FastAPI(
        title="Stock Control API",
        version="1.0.0",
        description=API_DESCRIPTION,
        lifespan=lifespan,
    )
    app.state.uow_factory = lambda: SqlAlchemyUnitOfWork(session_factory)
    app.state.clock = utc_now
    app.state.health_check = lambda: ping(engine)

    register_request_context(app)
    register_error_handlers(app, unavailable_errors=(OperationalError,))
    app.include_router(health.router)
    app.include_router(v1_router)
    return app
