import io
import pytest

import backend.server as server
from tests.test_purchase_orders import client_for, po_payload, _pdf_text


def test_purchase_order_pdf_long_vendor_notes_and_multipage_lines():
    client, _ = client_for("admin")
    payload = po_payload(ext="OC-LAYOUT", total_line="9999999.99")
    payload["currency"] = "USD"
    payload["exchange_rate"] = "18.90"
    payload["vendor_name"] = "Proveedor con nombre extremadamente largo para validar envoltura y evitar invasión entre columnas en PDF"
    payload["notes"] = "Observación extensa " * 30
    payload["lines"] = []
    for i in range(1, 45):
        payload["lines"].append({
            "line_no": i,
            "partida_codigo": "205",
            "description": f"Línea {i} con descripción bastante extensa para forzar múltiples renglones y validar cálculo de altura por celda en PDF " * 2,
            "qty": "1",
            "price_unit": "99999.99",
            "discount_pct": "0",
            "iva_rate": "16",
            "apply_isr_withholding": False,
            "isr_withholding_rate": "0",
        })

    created = client.post("/api/purchase-orders", json=payload)
    assert created.status_code == 200
    po_id = created.json()["purchase_order"]["id"]

    pdf_res = client.get(f"/api/purchase-orders/{po_id}/pdf")
    assert pdf_res.status_code == 200

    pypdf = pytest.importorskip("pypdf")
    reader = pypdf.PdfReader(io.BytesIO(pdf_res.content))
    assert len(reader.pages) >= 2

    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    assert "TOTAL (MXN):" in text
    assert "NOTAS / COMENTARIOS ADICIONALES" in text
    assert "Proveedor:" in text
    assert "envoltura y evitar" in text
