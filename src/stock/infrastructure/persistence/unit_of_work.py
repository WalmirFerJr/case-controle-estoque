from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session, sessionmaker

from stock.infrastructure.persistence.repositories import (
    SqlAlchemyHoldRepository,
    SqlAlchemyMovementRepository,
    SqlAlchemyProductRepository,
)


class SqlAlchemyUnitOfWork:
    """Uma sessão = uma transação. Sem ``commit()`` explícito, tudo é desfeito."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def __enter__(self) -> Self:
        self._session = self._session_factory()
        self.products = SqlAlchemyProductRepository(self._session)
        self.holds = SqlAlchemyHoldRepository(self._session)
        self.movements = SqlAlchemyMovementRepository(self._session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            self.rollback()  # no-op se já houve commit; desfaz tudo em caso de erro
        finally:
            self._session.close()

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
