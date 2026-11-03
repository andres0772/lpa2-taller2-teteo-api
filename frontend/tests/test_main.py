from __future__ import annotations

import json
import runpy
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import pytest
from flask.testing import FlaskClient

from frontend.app import main as frontend_main

app = frontend_main.app

INVOICE = {
    "numero_factura": "FAC-2025-001",
    "fecha_emision": "2025-08-15",
    "empresa": {
        "nombre": "Tech Solutions S.L.",
        "direccion": "Calle Mayor 123, Madrid",
        "telefono": "+34 912 345 678",
        "email": "facturacion@tech-solutions.example",
    },
    "cliente": {
        "nombre": "Cliente de Prueba S.A.",
        "direccion": "Avenida Central 45, Madrid",
        "telefono": "+34 933 444 555",
    },
    "detalle": [
        {
            "descripcion": "Desarrollo de la aplicación",
            "cantidad": 2,
            "precio_unitario": 150.5,
            "total": 301.0,
        }
    ],
    "subtotal": 301.0,
    "impuesto": 63.21,
    "total": 364.21,
}


@pytest.fixture
def client() -> FlaskClient:
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def backend_server():
    request_paths: list[str] = []
    response_status = [200]
    response_delay = [0.0]
    handler_finished = threading.Event()

    class InvoiceHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            request_paths.append(self.path)
            if response_delay[0]:
                time.sleep(response_delay[0])

            body = json.dumps(INVOICE).encode("utf-8")
            try:
                self.send_response(response_status[0])
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                handler_finished.set()

        def log_message(self, format: str, *args) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), InvoiceHandler)
    server.daemon_threads = True
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    yield {
        "base_url": f"http://127.0.0.1:{server.server_port}",
        "request_paths": request_paths,
        "response_status": response_status,
        "response_delay": response_delay,
    }

    server.shutdown()
    server.server_close()
    server_thread.join(timeout=2)
    handler_finished.wait(timeout=1)


def test_index_exposes_invoice_form(client: FlaskClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert b'name="id_factura"' in response.data
    assert b'action="/generar-pdf"' in response.data


def test_generar_pdf_uses_backend_url_and_returns_valid_pdf(
    client: FlaskClient,
    backend_server: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BACKEND_API_URL", f"{backend_server['base_url']}/")

    response = client.post(
        "/generar-pdf",
        data={"id_factura": "FAC-2025-001"},
    )

    assert response.status_code == 200
    assert backend_server["request_paths"] == ["/facturas/v1/FAC-2025-001"]
    assert response.content_type == "application/pdf"
    assert response.headers["Content-Disposition"] == (
        "attachment; filename=factura_FAC-2025-001.pdf"
    )
    assert response.data.startswith(b"%PDF-")
    assert response.data.rstrip().endswith(b"%%EOF")
    assert len(response.data) > 1000


def test_generar_pdf_preserves_not_found_response(
    client: FlaskClient,
    backend_server: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend_server["response_status"][0] = 404
    monkeypatch.setenv("BACKEND_API_URL", backend_server["base_url"])

    response = client.post(
        "/generar-pdf",
        data={"id_factura": "FAC-2025-001"},
    )

    assert response.status_code == 404
    assert b"Factura no encontrada" in response.data


def test_generar_pdf_handles_backend_connection_failure(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with socket.socket() as unused_socket:
        unused_socket.bind(("127.0.0.1", 0))
        unused_port = unused_socket.getsockname()[1]
    monkeypatch.setenv("BACKEND_API_URL", f"http://127.0.0.1:{unused_port}")

    response = client.post(
        "/generar-pdf",
        data={"id_factura": "FAC-2025-001"},
    )

    assert response.status_code == 503
    assert b"Error de conexi\xc3\xb3n con el servidor" in response.data


def test_generar_pdf_handles_backend_timeout(
    client: FlaskClient,
    backend_server: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend_server["response_delay"][0] = 0.2
    monkeypatch.setenv("BACKEND_API_URL", backend_server["base_url"])
    monkeypatch.setenv("BACKEND_TIMEOUT_SECONDS", "0.05")

    response = client.post(
        "/generar-pdf",
        data={"id_factura": "FAC-2025-001"},
    )

    assert response.status_code == 504
    assert b"Tiempo de espera agotado" in response.data


@pytest.mark.parametrize(
    ("debug_value", "expected_debug"),
    [(None, False), ("0", False), ("1", True)],
)
def test_debug_mode_is_opt_in(
    monkeypatch: pytest.MonkeyPatch,
    debug_value: str | None,
    expected_debug: bool,
) -> None:
    if debug_value is None:
        monkeypatch.delenv("FLASK_DEBUG", raising=False)
    else:
        monkeypatch.setenv("FLASK_DEBUG", debug_value)

    with patch("flask.Flask.run") as run:
        runpy.run_path(frontend_main.__file__, run_name="__main__")

    run.assert_called_once()
    assert run.call_args.kwargs["debug"] is expected_debug
