from fastapi import APIRouter, Response, status

from stock.application.dtos import BlockStockCommand, ReserveStockCommand, StockQuantityCommand
from stock.application.use_cases import (
    BlockStock,
    GetProductStock,
    ListMovements,
    ListProducts,
    RegisterEntry,
    RegisterExit,
    ReserveStock,
)
from stock.presentation.api.v1._params import DEFAULT_PAGE_SIZE, Limit, Offset, SkuPath
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


@router.get(
    "",
    response_model=list[ProductStockResponse],
    summary="Listar produtos e saldos",
    description=(
        "Situação de todos os produtos já cadastrados (total, disponível, reservado e "
        "bloqueado), em ordem de SKU. Um produto passa a existir na sua primeira entrada."
    ),
    responses={**INVALID},
)
def list_products(
    uow: UowDep, limit: Limit = DEFAULT_PAGE_SIZE, offset: Offset = 0
) -> list[ProductStockResponse]:
    products = ListProducts(uow).execute(limit=limit, offset=offset)
    return [ProductStockResponse.model_validate(view) for view in products]


@router.post(
    "/{sku}/entries",
    response_model=ProductStockResponse,
    summary="Entrada de unidades",
    description="Adiciona unidades ao estoque. A primeira entrada de um SKU cria o produto.",
    responses={**INVALID, **CONFLICT},
)
def register_entry(
    sku: SkuPath, body: QuantityRequest, uow: UowDep, clock: ClockDep
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
    sku: SkuPath, body: QuantityRequest, uow: UowDep, clock: ClockDep
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
    sku: SkuPath, body: ReservationRequest, uow: UowDep, clock: ClockDep, response: Response
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
    sku: SkuPath, body: BlockRequest, uow: UowDep, clock: ClockDep, response: Response
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
def get_product(sku: SkuPath, uow: UowDep) -> ProductDetailsResponse:
    details = GetProductStock(uow).execute(sku)
    return ProductDetailsResponse(
        **ProductStockResponse.model_validate(details.stock).model_dump(),
        active_holds=[HoldResponse.model_validate(hold) for hold in details.active_holds],
    )


@router.get(
    "/{sku}/movements",
    response_model=list[MovementResponse],
    summary="Histórico de movimentações (auditoria)",
    description="Ledger append-only do produto, da movimentação mais antiga para a mais recente.",
    responses={**NOT_FOUND, **INVALID},
)
def list_movements(
    sku: SkuPath,
    uow: UowDep,
    limit: Limit = DEFAULT_PAGE_SIZE,
    offset: Offset = 0,
) -> list[MovementResponse]:
    movements = ListMovements(uow).execute(sku, limit=limit, offset=offset)
    return [MovementResponse.model_validate(m) for m in movements]
