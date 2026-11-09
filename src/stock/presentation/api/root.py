from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()


@router.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Quem abre a raiz da API cai direto na documentação interativa, e não num 404."""
    return RedirectResponse(url="/docs")
