"""Injeção de dependências da camada HTTP.

As fábricas concretas são colocadas em ``app.state`` pelo composition root
(``stock.main``); aqui só existem os tipos abstratos (ports).
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request

from stock.application.ports import Clock, UnitOfWork


def get_uow(request: Request) -> UnitOfWork:
    factory: Callable[[], UnitOfWork] = request.app.state.uow_factory
    return factory()


def get_clock(request: Request) -> Clock:
    clock: Clock = request.app.state.clock
    return clock


UowDep = Annotated[UnitOfWork, Depends(get_uow)]
ClockDep = Annotated[Clock, Depends(get_clock)]
