import random
from typing import Annotated

from faker import Faker
from fastapi import FastAPI, Path

app = FastAPI(title="API de Facturas Fake", version="1.0")

fake = Faker("es_ES")

InvoiceNumber = Annotated[
    str,
    Path(
        min_length=3,
        max_length=50,
        pattern=r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$",
    ),
]


@app.get("/")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/facturas/v1/{numero_factura}")
def get_factura(numero_factura: InvoiceNumber):
    # Generar datos falsos para empresa y cliente
    empresa = {
        "nombre": fake.company(),
        "direccion": fake.address(),
        "telefono": fake.phone_number(),
        "email": fake.company_email(),
    }

    cliente = {
        "nombre": fake.company(),
        "direccion": fake.address(),
        "telefono": fake.phone_number(),
    }

    # Generar entre 1 y 5 ítems de detalle
    detalle = []
    # B311: la aleatoriedad solo genera datos de demostración.
    for _ in range(random.randint(1, 5)):  # nosec B311 # Solo datos demo
        cantidad = random.randint(1, 10)  # nosec B311 # Solo datos demo
        precio_unitario = round(random.uniform(50, 500), 2)  # nosec B311 # Demo
        total = round(cantidad * precio_unitario, 2)
        detalle.append(
            {
                "descripcion": fake.catch_phrase(),
                "cantidad": cantidad,
                "precio_unitario": precio_unitario,
                "total": total,
            }
        )

    subtotal = round(sum(item["total"] for item in detalle), 2)
    impuesto = round(subtotal * 0.21, 2)  # IVA 21%
    total = round(subtotal + impuesto, 2)

    factura = {
        "numero_factura": numero_factura,
        "fecha_emision": str(fake.date_between(start_date="-1y", end_date="today")),
        "empresa": empresa,
        "cliente": cliente,
        "detalle": detalle,
        "subtotal": subtotal,
        "impuesto": impuesto,
        "total": total,
    }

    return factura
