"""API ponta a ponta contra PostgreSQL real: contrato HTTP, persistência e erros."""

from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from stock.domain.entities import MovementType, StockMovement
from stock.domain.services.ledger import replay
from stock.domain.value_objects import Quantity, Sku
from stock.infrastructure.config import Settings
from stock.main import create_app

pytestmark = pytest.mark.integration

API = "/api/v1"


def entry(client: TestClient, sku: str, quantity: int) -> None:
    response = client.post(f"{API}/products/{sku}/entries", json={"quantity": quantity})
    assert response.status_code == 200, response.text


def reserve(client: TestClient, sku: str, quantity: int, reference: str = "PED-1") -> str:
    response = client.post(
        f"{API}/products/{sku}/reservations", json={"quantity": quantity, "reference": reference}
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def stock_of(client: TestClient, sku: str) -> dict[str, int]:
    body = client.get(f"{API}/products/{sku}").json()
    return {k: body[k] for k in ("total", "available", "reserved", "blocked")}


class TestHappyPath:
    def test_full_lifecycle_keeps_balances_and_ledger_consistent(self, client: TestClient) -> None:
        entry(client, "NOTE-15", 10)
        reservation_id = reserve(client, "NOTE-15", 3, "PED-1")
        block = client.post(
            f"{API}/products/NOTE-15/blocks",
            json={"quantity": 2, "reference": "QA-7", "reason": "avaria"},
        )
        assert block.status_code == 201
        assert stock_of(client, "NOTE-15") == {
            "total": 10,
            "available": 5,
            "reserved": 3,
            "blocked": 2,
        }

        details = client.get(f"{API}/products/NOTE-15").json()
        assert {h["type"] for h in details["active_holds"]} == {"RESERVATION", "BLOCK"}

        assert client.post(f"{API}/holds/{block.json()['id']}/release").status_code == 200
        assert client.post(f"{API}/holds/{reservation_id}/consume").status_code == 200
        exit_response = client.post(f"{API}/products/NOTE-15/exits", json={"quantity": 4})
        assert exit_response.json() == {
            "sku": "NOTE-15",
            "total": 3,
            "available": 3,
            "reserved": 0,
            "blocked": 0,
        }

        movements = client.get(f"{API}/products/NOTE-15/movements").json()
        assert [m["type"] for m in movements] == [
            "ENTRY",
            "RESERVE",
            "BLOCK",
            "RELEASE_BLOCK",
            "CONSUME_RESERVATION",
            "EXIT",
        ]
        balance = replay(
            StockMovement.record(
                sku=Sku(m["sku"]),
                movement_type=MovementType(m["type"]),
                quantity=Quantity(m["quantity"]),
                now=m["occurred_at"],
            )
            for m in movements
        )
        assert (balance.total, balance.reserved, balance.blocked) == (3, 0, 0)

    def test_reservation_is_queryable_by_id_and_location_header(self, client: TestClient) -> None:
        entry(client, "A", 5)
        response = client.post(
            f"{API}/products/A/reservations", json={"quantity": 2, "reference": "PED-9"}
        )
        hold = response.json()
        assert response.headers["Location"] == f"{API}/holds/{hold['id']}"
        fetched = client.get(response.headers["Location"]).json()
        assert fetched == hold
        assert (fetched["status"], fetched["closed_at"]) == ("ACTIVE", None)

    def test_list_holds_by_request_reference_across_products(self, client: TestClient) -> None:
        entry(client, "A", 5)
        entry(client, "B", 5)
        reserve(client, "A", 1, "PED-1")
        reserve(client, "B", 2, "PED-1")
        reserve(client, "A", 1, "PED-2")

        by_order = client.get(f"{API}/holds", params={"reference": "PED-1"}).json()
        active_of_a = client.get(f"{API}/holds", params={"sku": "A", "status": "ACTIVE"}).json()

        assert sorted(h["sku"] for h in by_order) == ["A", "B"]
        assert len(active_of_a) == 2

    def test_list_products_shows_every_product_with_balances(self, client: TestClient) -> None:
        assert client.get(f"{API}/products").json() == []
        entry(client, "NOTE-15", 10)
        entry(client, "MOUSE-1", 4)
        reserve(client, "NOTE-15", 3)

        products = client.get(f"{API}/products").json()

        assert products == [
            {"sku": "MOUSE-1", "total": 4, "available": 4, "reserved": 0, "blocked": 0},
            {"sku": "NOTE-15", "total": 10, "available": 7, "reserved": 3, "blocked": 0},
        ]
        second_page = client.get(f"{API}/products", params={"limit": 1, "offset": 1}).json()
        assert [p["sku"] for p in second_page] == ["NOTE-15"]

    def test_root_redirects_to_interactive_docs(self, client: TestClient) -> None:
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/docs"

    def test_health_reports_database_ok(self, client: TestClient) -> None:
        assert client.get("/health").json() == {"status": "ok", "database": "ok"}


class TestErrorContract:
    def test_insufficient_stock_returns_problem_details_and_changes_nothing(
        self, client: TestClient
    ) -> None:
        entry(client, "A", 5)
        response = client.post(
            f"{API}/products/A/exits",
            json={"quantity": 6},
            headers={"X-Correlation-ID": "trace-123"},
        )
        body = response.json()
        assert response.status_code == 409
        assert response.headers["content-type"] == "application/problem+json"
        assert response.headers["X-Correlation-ID"] == "trace-123"
        assert body["code"] == "INSUFFICIENT_AVAILABLE_STOCK"
        assert (body["requested"], body["available"]) == (6, 5)
        assert body["correlation_id"] == "trace-123"
        assert stock_of(client, "A")["total"] == 5

    @pytest.mark.parametrize(
        ("method", "path", "code"),
        [
            ("get", "/products/NOPE", "PRODUCT_NOT_FOUND"),
            ("post", "/products/NOPE/exits", "PRODUCT_NOT_FOUND"),
            ("get", f"/holds/{uuid4()}", "HOLD_NOT_FOUND"),
            ("post", f"/holds/{uuid4()}/release", "HOLD_NOT_FOUND"),
        ],
    )
    def test_unknown_resources_return_404(
        self, client: TestClient, method: str, path: str, code: str
    ) -> None:
        kwargs = {"json": {"quantity": 1}} if path.endswith("exits") else {}
        response = getattr(client, method)(API + path, **kwargs)
        assert (response.status_code, response.json()["code"]) == (404, code)

    @pytest.mark.parametrize(
        "payload",
        [
            {"quantity": 0},
            {"quantity": -1},
            {"quantity": 1.5},
            {"quantity": "3"},
            {"quantity": True},
            {"quantity": 1_000_001},
            {},
            {"quantity": 1, "unexpected": "field"},
        ],
    )
    def test_invalid_payloads_return_422(self, client: TestClient, payload: object) -> None:
        response = client.post(f"{API}/products/A/entries", json=payload)
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"

    @pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 501}, {"offset": -1}])
    def test_invalid_pagination_returns_422(
        self, client: TestClient, params: dict[str, int]
    ) -> None:
        response = client.get(f"{API}/products", params=params)
        assert (response.status_code, response.json()["code"]) == (422, "VALIDATION_ERROR")

    def test_invalid_sku_in_path_returns_422(self, client: TestClient) -> None:
        response = client.post(f"{API}/products/bad%20sku/entries", json={"quantity": 1})
        assert (response.status_code, response.json()["code"]) == (422, "INVALID_SKU")

    def test_blank_reference_returns_422(self, client: TestClient) -> None:
        entry(client, "A", 5)
        response = client.post(
            f"{API}/products/A/reservations", json={"quantity": 1, "reference": "   "}
        )
        assert (response.status_code, response.json()["code"]) == (422, "INVALID_HOLD_DATA")
        assert stock_of(client, "A")["reserved"] == 0

    def test_releasing_twice_returns_409(self, client: TestClient) -> None:
        entry(client, "A", 5)
        hold_id = reserve(client, "A", 2)
        assert client.post(f"{API}/holds/{hold_id}/release").status_code == 200
        response = client.post(f"{API}/holds/{hold_id}/release")
        assert (response.status_code, response.json()["code"]) == (409, "HOLD_NOT_ACTIVE")
        assert stock_of(client, "A")["available"] == 5

    def test_consuming_a_block_returns_409(self, client: TestClient) -> None:
        entry(client, "A", 5)
        block = client.post(f"{API}/products/A/blocks", json={"quantity": 1, "reference": "QA"})
        response = client.post(f"{API}/holds/{block.json()['id']}/consume")
        assert (response.status_code, response.json()["code"]) == (409, "INVALID_HOLD_OPERATION")

    def test_invalid_filter_value_returns_422(self, client: TestClient) -> None:
        response = client.get(f"{API}/holds", params={"status": "WHATEVER"})
        assert response.status_code == 422

    def test_unexpected_error_returns_500_without_internal_details(
        self, client: TestClient
    ) -> None:
        def broken_factory() -> None:
            raise RuntimeError("segredo interno")

        client.app.state.uow_factory = broken_factory  # type: ignore[attr-defined]
        with TestClient(client.app, raise_server_exceptions=False) as raw_client:
            response = raw_client.get(f"{API}/products/A")
        body = response.json()
        assert response.status_code == 500
        assert body["code"] == "INTERNAL_ERROR"
        assert "segredo" not in response.text
        assert body["correlation_id"] == response.headers["X-Correlation-ID"]


class TestDatabaseGuarantees:
    def test_check_constraint_blocks_inconsistent_state_even_bypassing_the_app(
        self, client: TestClient, engine: Engine
    ) -> None:
        entry(client, "A", 5)
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(text("UPDATE products SET reserved_quantity = 6 WHERE sku = 'A'"))

    def test_migrations_are_in_sync_with_orm_models(self, alembic_config: Config) -> None:
        command.check(alembic_config)  # falha se o modelo divergir das migrations


class TestLockTimeout:
    def test_request_waiting_too_long_for_a_locked_product_fails_fast_with_503(
        self, client: TestClient, settings: Settings, engine: Engine
    ) -> None:
        entry(client, "A", 5)
        impatient = create_app(settings.model_copy(update={"db_lock_timeout_ms": 200}))

        # Outra transação segura o lock do produto e não faz commit.
        with engine.connect() as blocker, blocker.begin():
            blocker.execute(text("SELECT * FROM products WHERE sku = 'A' FOR UPDATE"))
            with TestClient(impatient, raise_server_exceptions=False) as impatient_client:
                response = impatient_client.post(
                    f"{API}/products/A/reservations", json={"quantity": 1, "reference": "PED"}
                )

        assert (response.status_code, response.json()["code"]) == (503, "SERVICE_UNAVAILABLE")
        assert stock_of(client, "A")["reserved"] == 0
