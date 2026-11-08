from collections.abc import Callable
from datetime import UTC, datetime

Clock = Callable[[], datetime]
"""Fonte de tempo injetável: testes usam um relógio fixo, produção usa ``utc_now``."""


def utc_now() -> datetime:
    return datetime.now(UTC)
