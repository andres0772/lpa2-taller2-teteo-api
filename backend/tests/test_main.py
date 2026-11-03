from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_endpoint_reports_ready() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("invoice_number", ["FAC-2025-001", "INV-2024-123"])
def test_get_invoice_returns_complete_invoice(invoice_number: str) -> None:
    response = client.get(f"/facturas/v1/{invoice_number}")

    assert response.status_code == 200
    invoice = response.json()
    assert invoice["numero_factura"] == invoice_number
    date.fromisoformat(invoice["fecha_emision"])
    assert invoice["empresa"]["nombre"]
    assert invoice["empresa"]["email"]
    assert invoice["cliente"]["nombre"]
    assert 1 <= len(invoice["detalle"]) <= 5

    for item in invoice["detalle"]:
        assert item["descripcion"]
        assert 1 <= item["cantidad"] <= 10
        assert item["precio_unitario"] >= 50
        assert item["total"] == round(item["cantidad"] * item["precio_unitario"], 2)

    subtotal = round(sum(item["total"] for item in invoice["detalle"]), 2)
    assert invoice["subtotal"] == subtotal
    assert invoice["impuesto"] == round(subtotal * 0.21, 2)
    assert invoice["total"] == round(subtotal + invoice["impuesto"], 2)


@pytest.mark.parametrize("invoice_number", ["A", "invalid invoice", "F" * 51])
def test_get_invoice_rejects_invalid_number(invoice_number: str) -> None:
    response = client.get(f"/facturas/v1/{invoice_number}")

    assert response.status_code == 422
