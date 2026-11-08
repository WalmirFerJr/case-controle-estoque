from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from stock.infrastructure.config import Settings


def create_db_engine(settings: Settings) -> Engine:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )
    lock_timeout = int(settings.db_lock_timeout_ms)

    @event.listens_for(engine, "connect")
    def _set_lock_timeout(dbapi_connection, _record) -> None:  # type: ignore[no-untyped-def]
        # Uma requisição nunca espera indefinidamente por um lock de produto:
        # se a fila travar, falha rápido (vira 503) em vez de esgotar o pool.
        with dbapi_connection.cursor() as cursor:
            cursor.execute(f"SET lock_timeout = {lock_timeout}")
        dbapi_connection.commit()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False: as entidades de domínio são construídas antes do commit,
    # mas evita recargas desnecessárias caso um modelo ORM seja lido depois.
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


def ping(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
