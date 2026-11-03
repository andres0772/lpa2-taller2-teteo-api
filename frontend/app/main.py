import os
from io import BytesIO
from urllib.parse import quote
from xml.sax.saxutils import escape

import requests
from flask import Flask, abort, render_template, request, send_file
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from werkzeug.exceptions import HTTPException


app = Flask(__name__)
BACKEND_URL = os.getenv(
    "BACKEND_API_URL",
    os.getenv("BACKEND_URL", "http://backend:8000"),
).rstrip("/")
BACKEND_TIMEOUT_SECONDS = float(os.getenv("BACKEND_TIMEOUT_SECONDS", "10"))


def _backend_url() -> str:
    configured_url = (
        os.getenv("BACKEND_API_URL")
        or os.getenv("BACKEND_URL")
        or BACKEND_URL
    )
    return configured_url.rstrip("/")


def _backend_timeout() -> float:
    return float(
        os.getenv("BACKEND_TIMEOUT_SECONDS", str(BACKEND_TIMEOUT_SECONDS))
    )


def _format_amount(value: object) -> str:
    return f"{float(value):.2f}"


def _build_invoice_pdf(invoice: dict) -> BytesIO:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    label_style = ParagraphStyle(
        "InvoiceLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        spaceBefore=3 * mm,
        spaceAfter=2 * mm,
    )
    table_header_style = ParagraphStyle(
        "InvoiceTableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    table_header_right_style = ParagraphStyle(
        "InvoiceTableHeaderRight",
        parent=table_header_style,
        alignment=TA_RIGHT,
    )
    table_cell_style = ParagraphStyle(
        "InvoiceTableCell",
        parent=styles["Normal"],
        fontSize=9,
    )

    empresa = invoice["empresa"]
    cliente = invoice["cliente"]
    elements = [
        Paragraph(
            f"Factura {escape(str(invoice['numero_factura']))}",
            styles["Title"],
        ),
        Paragraph(
            "<b>Fecha de emisión:</b> "
            f"{escape(str(invoice['fecha_emision']))}",
            styles["Normal"],
        ),
        Spacer(1, 4 * mm),
        Paragraph("Empresa", label_style),
        Paragraph(
            f"<b>Nombre:</b> {escape(str(empresa['nombre']))}<br/>"
            f"<b>Dirección:</b> {escape(str(empresa['direccion']))}<br/>"
            f"<b>Teléfono:</b> {escape(str(empresa['telefono']))}<br/>"
            f"<b>Email:</b> {escape(str(empresa['email']))}",
            styles["Normal"],
        ),
        Paragraph("Cliente", label_style),
        Paragraph(
            f"<b>Nombre:</b> {escape(str(cliente['nombre']))}<br/>"
            f"<b>Dirección:</b> {escape(str(cliente['direccion']))}<br/>"
            f"<b>Teléfono:</b> {escape(str(cliente['telefono']))}",
            styles["Normal"],
        ),
        Spacer(1, 4 * mm),
    ]

    detail_rows = [
        [
            Paragraph("Descripción", table_header_style),
            Paragraph("Cantidad", table_header_style),
            Paragraph("Precio unitario", table_header_right_style),
            Paragraph("Total", table_header_right_style),
        ]
    ]
    for item in invoice["detalle"]:
        detail_rows.append(
            [
                Paragraph(escape(str(item["descripcion"])), table_cell_style),
                escape(str(item["cantidad"])),
                _format_amount(item["precio_unitario"]),
                _format_amount(item["total"]),
            ]
        )

    detail_table = Table(
        detail_rows,
        colWidths=[95 * mm, 20 * mm, 32 * mm, 33 * mm],
        repeatRows=1,
    )
    detail_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4CAF50")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(detail_table)
    elements.append(Spacer(1, 4 * mm))

    totals_table = Table(
        [
            ["Subtotal", _format_amount(invoice["subtotal"])],
            ["Impuesto", _format_amount(invoice["impuesto"])],
            ["Total", _format_amount(invoice["total"])],
        ],
        colWidths=[35 * mm, 35 * mm],
        hAlign="RIGHT",
    )
    totals_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(totals_table)

    document.build(elements)
    buffer.seek(0)
    return buffer


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generar-pdf", methods=["POST"])
def generar_pdf():
    try:
        id_factura = request.form["id_factura"]
        response = requests.get(
            f"{_backend_url()}/facturas/v1/{quote(id_factura, safe='')}",
            timeout=_backend_timeout(),
        )

        if response.status_code != 200:
            abort(404, description="Factura no encontrada")

        invoice = response.json()
        pdf_buffer = _build_invoice_pdf(invoice)
    except requests.exceptions.Timeout:
        abort(504, description="Tiempo de espera agotado")
    except requests.exceptions.ConnectionError:
        abort(503, description="Error de conexión con el servidor")
    except HTTPException:
        raise
    except Exception as error:
        abort(500, description=str(error))

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"factura_{id_factura}.pdf",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)

