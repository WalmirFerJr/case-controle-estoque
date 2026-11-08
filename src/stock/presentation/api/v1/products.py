from fastapi import APIRouter, Query, Response, status

from stock.application.dtos import BlockStockCommand, ReserveStockCommand, StockQuantityCommand
from stock.application.use_cases import (
    BlockStock,
    GetProductStock,
    ListMovements,
    RegisterEntry,
    RegisterExit,
    ReserveStock,
)
from stock.presentation.api.v1._responses import CONFLICT, INVALID, NOT_FOUND
from stock.presentation.dependencies import ClockDep, UowDep
from stock.presentation.schemas import (
    BlockRequest,
    HoldResponse,
    MovementResponse,
    ProductDetailsResponse,
    ProductStockResponse,
    QuantityRequest,
    ReservationRequest,
)

router = APIRouter(prefix="/products", tags=["Produtos"])

HOLD_LOCATION = "/api/v1/holds/{hold_id}"


@router.post(
    "/{sku}/entries",
    response_model=ProductStockResponse,
    summary="Entrada de unidades",
    description="Adiciona unidades ao estoque. A primeira entrada de um SKU cria o produto.",
    responses={**INVALID, **CONFLICT},
)
def register_entry(
    sku: str, body: QuantityRequest, uow: UowDep, clock: ClockDep
) -> ProductStockResponse:
    view = RegisterEntry(uow, clock).execute(StockQuantityCommand(sku, body.quantity))
    return ProductStockResponse.model_validate(view)


@router.post(
    "/{sku}/exits",
    response_model=ProductStockResponse,
    summary="Saída de unidades",
    description="Retira unidades do estoque; só é permitido até a quantidade disponível.",
    responses={**NOT_FOUND, **CONFLICT, **INVALID},
)
def register_exit(
    sku: str, body: QuantityRequest, uow: UowDep, clock: ClockDep
) -> ProductStockResponse:
    view = RegisterExit(uow, clock).execute(StockQuantityCommand(sku, body.quantity))
    return ProductStockResponse.model_validate(view)


@router.post(
    "/{sku}/reservations",
    response_model=HoldResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reservar unidades",
    description="Reserva unidades disponíveis para uma solicitação/pedido.",
    responses={**NOT_FOUND, **CONFLICT, **INVALID},
)
def reserve(
    sku: str, body: ReservationRequest, uow: UowDep, clock: ClockDep, response: Response
) -> HoldResponse:
    view = ReserveStock(uow, clock).execute(ReserveStockCommand(sku, body.quantity, body.reference))
    response.headers["Location"] = HOLD_LOCATION.format(hold_id=view.id)
    return HoldResponse.model_validate(view)


@router.post(
    "/{sku}/blocks",
    response_model=HoldResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bloquear unidades",
    description="Bloqueia unidades disponíveis, tornando-as indisponíveis até a liberação.",
    responses={**NOT_FOUND, **CONFLICT, **INVALID},
)
def block(
    sku: str, body: BlockRequest, uow: UowDep, clock: ClockDep, response: Response
) -> HoldResponse:
    view = BlockStock(uow, clock).execute(
        BlockStockCommand(sku, body.quantity, body.reference, body.reason)
    )
    response.headers["Location"] = HOLD_LOCATION.format(hold_id=view.id)
    return HoldResponse.model_validate(view)


@router.get(
    "/{sku}",
    response_model=ProductDetailsResponse,
    summary="Consultar situação do produto",
    description="Total, disponível, reservado, bloqueado e os holds ativos.",
    responses={**NOT_FOUND, **INVALID},
)
def get_product(sku: str, uow: UowDep) -> ProductDetailsResponse:
    details = GetProductStock(uow).execute(sku)
    return ProductDetailsResponse(
        **ProductStockResponse.model_validate(details.stock).model_dump(),
        active_holds=[HoldResponse.model_validate(hold) for hold in details.active_holds],
    )


@router.get(
    "/{sku}/movements",
    response_model=list[MovementResponse],
    summary="Histórico de movimentações (auditoria)",
    responses={**NOT_FOUND, **INVALID},
)
def list_movements(
    sku: str,
    uow: UowDep,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[MovementResponse]:
    movements = ListMovements(uow).execute(sku, limit=limit, offset=offset)
    return [MovementResponse.model_validate(m) for m in movements]
