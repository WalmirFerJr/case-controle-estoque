from fastapi import APIRouter

from stock.presentation.api.v1 import holds, products

router = APIRouter(prefix="/api/v1")
router.include_router(products.router)
router.include_router(holds.router)

__all__ = ["router"]
