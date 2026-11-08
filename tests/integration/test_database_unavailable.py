"""Falha de infraestrutura: banco fora do ar vira 503 previsível, não 500 genérico."""

from fastapi.testclient import TestClient

from stock.infrastructure.config import Settings
from stock.main import create_app

UNREACHABLE = "postgresql+psycopg://stock:stock@127.0.0.1:1/stock?connect_timeout=1"


def test_database_down_returns_503_problem_details() -> None:
    app = create_app(Settings(database_url=UNREACHABLE))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/v1/products/A/entries", json={"quantity": 1})
        health = client.get("/health")

    assert response.status_code == 503
    assert response.json()["code"] == "SERVICE_UNAVAILABLE"
    assert (health.status_code, health.json()["database"]) == (503, "unavailable")
