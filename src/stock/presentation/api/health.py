from collections.abc import Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from stock.presentation.schemas import HealthResponse

router = APIRouter(tags=["Operação"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Saúde da aplicação e do banco",
    responses={503: {"model": HealthResponse}},
)
def health(request: Request) -> HealthResponse | JSONResponse:
    check: Callable[[], None] = request.app.state.health_check
    try:
        check()
    except Exception:
        return JSONResponse({"status": "degraded", "database": "unavailable"}, status_code=503)
    return HealthResponse(status="ok", database="ok")
