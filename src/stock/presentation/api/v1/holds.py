from uuid import UUID

from fastapi import APIRouter, Query

from stock.application.use_cases import (
    ConsumeReservation,
    GetHold,
    ListHolds,
    ListHoldsQuery,
    ReleaseHold,
)
from stock.domain.entities import HoldStatus, HoldType
from stock.presentation.api.v1._responses import CONFLICT, INVALID, NOT_FOUND
from stock.presentation.dependencies import ClockDep, UowDep
from stock.presentation.schemas import HoldResponse

router = APIRouter(prefix="/holds", tags=["Reservas e bloqueios"])


@router.get(
    "",
    response_model=list[HoldResponse],
    summary="Listar reservas/bloqueios",
    description="Filtra por produto, solicitação (reference), tipo e status.",
    responses={**INVALID},
)
def list_holds(
    uow: UowDep,
    sku: str | None = None,
    reference: str | None = None,
    type: HoldType | None = Query(None),
    status: HoldStatus | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[HoldResponse]:
    query = ListHoldsQuery(
        sku=sku,
        reference=reference,
        hold_type=type.value if type else None,
        status=status.value if status else None,
        limit=limit,
        offset=offset,
    )
    return [HoldResponse.model_validate(h) for h in ListHolds(uow).execute(query)]


@router.get(
    "/{hold_id}",
    response_model=HoldResponse,
    summary="Consultar reserva/bloqueio",
    responses={**NOT_FOUND, **INVALID},
)
def get_hold(hold_id: UUID, uow: UowDep) -> HoldResponse:
    return HoldResponse.model_validate(GetHold(uow).execute(hold_id))


@router.post(
    "/{hold_id}/release",
    response_model=HoldResponse,
    summary="Liberar reserva/bloqueio",
    description="Devolve as unidades ao disponível. Um hold só pode ser liberado uma vez.",
    responses={**NOT_FOUND, **CONFLICT, **INVALID},
)
def release_hold(hold_id: UUID, uow: UowDep, clock: ClockDep) -> HoldResponse:
    return HoldResponse.model_validate(ReleaseHold(uow, clock).execute(hold_id))


@router.post(
    "/{hold_id}/consume",
    response_model=HoldResponse,
    summary="Consumir (baixar) reserva",
    description="Extra ao enunciado: as unidades reservadas saem do estoque (pedido expedido).",
    responses={**NOT_FOUND, **CONFLICT, **INVALID},
)
def consume_reservation(hold_id: UUID, uow: UowDep, clock: ClockDep) -> HoldResponse:
    return HoldResponse.model_validate(ConsumeReservation(uow, clock).execute(hold_id))
