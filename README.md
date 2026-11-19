# Generador de Facturas

Sistema de generación de facturas: un backend [FastAPI](https://fastapi.tiangolo.com/) que produce datos sintéticos con [Faker](https://faker.readthedocs.io/), y un frontend web con [Flask](https://flask.palletsprojects.com/) que consulta la API y devuelve un PDF generado con [ReportLab](https://docs.reportlab.com/reportlab/userguide/ch1_intro/).

## Autor

- Andres Esteban Vasques Peña - https://github.com/andres0772

## Requisitos

- **Opción A (local):** Python 3.12 y [`uv`](https://docs.astral.sh/uv/). No hace falta Docker.
- **Opción B (contenedores):** Docker con el plugin Compose v2 (`docker compose`).

## Inicio rápido sin Docker

Es el camino recomendado para desarrollar, porque es el que cubren los tests y el pre-commit.

```bash
uv sync --locked                     # crea el entorno con uv.lock (Python 3.12)

uv run uvicorn backend.app.main:app --reload --port 8000     # terminal 1: backend

# terminal 2: frontend (el default http://backend:8000 solo existe dentro de Docker)
BACKEND_API_URL=http://localhost:8000 uv run python frontend/app/main.py
```

- Backend: http://localhost:8000
- Frontend: http://localhost:3000
- Documentación de la API: http://localhost:8000/docs (Swagger) y http://localhost:8000/redoc

Para parar los servidores: `Ctrl+C` en cada terminal.

## Inicio rápido con Docker

```bash
docker compose up --build            # construye las imágenes y levanta los dos servicios
docker compose up -d                 # igual, en segundo plano
docker compose logs -f backend       # logs de un servicio
docker compose down                  # detener y limpiar contenedores y red
docker compose down -v               # además elimina volúmenes
```

Contenedores: `factura-api` (backend) y `factura-frontend` (frontend), sobre la red `factura-network`. El backend expone un healthcheck (`curl -f http://localhost:8000/`, cada 30s, 3 reintentos) y el frontend depende de que esté levantado.

Puertos expuestos: frontend `3000`, backend `8000`. Para cambiarlos, editá el bloque `ports` de `docker-compose.yml` (por ejemplo `"8080:3000"` y `"9000:8000"`).

## Estructura del proyecto

```
lpa2-taller2-teteo-api/
├── docker-compose.yml          # orquestación de los dos servicios
├── pyproject.toml              # dependencias, pytest, ruff y bandit
├── uv.lock                     # dependencias fijadas
├── .python-version             # 3.12
├── backend/
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py            # API FastAPI
│   │   └── requirements.txt   # deps de la imagen Docker
│   └── tests/test_main.py
└── frontend/
    ├── Dockerfile
    ├── app/
    │   ├── main.py            # servidor Flask + generación del PDF
    │   ├── requirements.txt
    │   ├── static/css/style.css
    │   ├── static/js/app.js
    │   └── templates/index.html
    └── tests/test_main.py
```

Además: `.github/workflows/ci.yml` (integración continua) y `.pre-commit-config.yaml` (hooks locales).

## Backend (API de facturas)

`GET /` — health check, devuelve `{"status": "ok"}`.

`GET /facturas/v1/{numero_factura}` — genera una factura sintética:

```bash
curl http://localhost:8000/facturas/v1/FAC-2025-001
```

El número de factura debe tener entre 3 y 50 caracteres y respetar el patrón `^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$` (letras y números, separados por guiones).Cualquier otro valor responde `422`.

```json
{
  "numero_factura": "FAC-2025-001",
  "fecha_emision": "2025-08-15",
  "empresa": {
    "nombre": "Tech Solutions S.L.",
    "direccion": "Calle Mayor 123, Madrid",
    "telefono": "+34 912 345 678",
    "email": "contacto@techsolutions.es"
  },
  "cliente": {
    "nombre": "Industrias López",
    "direccion": "Av. Libertad 456, Barcelona",
    "telefono": "+34 933 456 789"
  },
  "detalle": [
    {
      "descripcion": "Servicio de consultoría",
      "cantidad": 2,
      "precio_unitario": 625.00,
      "total": 1250.00
    }
  ],
  "subtotal": 1250.00,
  "impuesto": 262.50,
  "total": 1512.50
}
```

`impuesto` es el 21% del `subtotal` y `detalle` trae entre 1 y 5 líneas. Los datos son aleatorios (Faker con locale `es_ES`), así que cambian en cada llamada salvo el número de factura.

## Frontend (generador del PDF)

- `GET /` muestra el formulario (`templates/index.html`).
- `POST /generar-pdf` recibe el campo `id_factura`, consulta al backend y devuelve el PDF como descarga adjunta llamada `factura_<numero>.pdf`.

Uso: abrí http://localhost:3000, escribí un número de factura, hacé clic en **Generar PDF** y guardá el archivo. No hay vista previa: el clic ya devuelve el PDF.

Errores que puede devolver el frontend:

| Situación | Respuesta |
| --- | --- |
| El backend responde distinto de 200 | `404 Factura no encontrada` |
| El backend tarda más del timeout | `504 Tiempo de espera agotado` |
| El backend no responde | `503 Error de conexión con el servidor` |
| Error inesperado | `500` |

### Variables de entorno

Todas se leen en `frontend/app/main.py`:

| Variable | Default | Para qué |
| --- | --- | --- |
| `BACKEND_API_URL` | `http://backend:8000` | URL del backend; `BACKEND_URL` es un alias aceptado |
| `BACKEND_TIMEOUT_SECONDS` | `10` | timeout de la consulta al backend |
| `FLASK_DEBUG` | `0` | `1` activa el debugger de Flask (solo en desarrollo) |

En local usá siempre `BACKEND_API_URL=http://localhost:8000`; dentro de Docker Compose ya está configurado como `http://backend:8000`.

## Testing y calidad

```bash
uv run pytest -q                    # tests de backend y frontend, con cobertura
uv run pytest -q --no-cov           # más rápido, sin cobertura
uv run ruff format --check .        # formato
uv run ruff check .                 # lint
uv run bandit -r backend frontend -c pyproject.toml   # seguridad
uv run pre-commit run --all-files   # todo lo anterior de una vez
```

La CI (`.github/workflows/ci.yml`) corre esos mismos checks más un smoke test de Docker: construye las dos imágenes, levanta los servicios con `docker compose`, espera a que respondan y genera un PDF de verdad comprobando que es un PDF válido. Corre en cada push a `main` y en cada pull request.

### Probar a mano el backend

```bash
curl http://localhost:8000/                          # health check
curl http://localhost:8000/facturas/v1/TEST-001      # factura de prueba
```

### Probar a mano el frontend

1. Entrá a http://localhost:3000
2. Probá varios números de factura (`FAC-2025-001`, `INV-2024-123`)
3. Verificá que el PDF se descarga y se abre