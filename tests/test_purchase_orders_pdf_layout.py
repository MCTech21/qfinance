import io
import re
from decimal import Decimal

import pytest

from tests.test_purchase_orders import client_for, po_payload


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


def test_purchase_order_pdf_anti_overlap_and_total_mxn():
    fitz = pytest.importorskip("fitz")

    client, _ = client_for("admin")
    payload = po_payload(ext="OC-ANTISOLAPE", total_line="55551.00")
    payload["currency"] = "USD"
    payload["exchange_rate"] = "18.90"
    payload["lines"] = [
        {
            "line_no": 1,
            "partida_codigo": "205",
            "description": ("Descripción extensa para validar que no exista solape entre columnas numéricas y que el ajuste de celdas mantenga trazabilidad completa ") * 3,
            "qty": "1",
            "price_unit": "55551.00",
            "discount_pct": "0",
            "iva_rate": "16",
            "apply_isr_withholding": True,
            "isr_withholding_rate": "10",
        },
        {
            "line_no": 2,
            "partida_codigo": "205",
            "description": "Caso con monto extremo para validar fallback de ancho en columnas numéricas",
            "qty": "1",
            "price_unit": "100000000.00",
            "discount_pct": "0",
            "iva_rate": "16",
            "apply_isr_withholding": True,
            "isr_withholding_rate": "10",
        },
    ]

    created = client.post("/api/purchase-orders", json=payload)
    assert created.status_code == 200
    po_id = created.json()["purchase_order"]["id"]

    pdf_res = client.get(f"/api/purchase-orders/{po_id}/pdf")
    assert pdf_res.status_code == 200

    doc = fitz.open(stream=pdf_res.content, filetype="pdf")
    words = []
    for page in doc:
        words.extend(page.get_text("words"))

    def find_word(token: str):
        matched = [w for w in words if w[4] == token]
        assert matched, f"No se encontró token {token}"
        matched.sort(key=lambda w: (w[1], w[0]))
        return matched[0]

    pu = find_word("$55,551.00")
    iva = find_word("$8,888.16")
    ret_isr = find_word("$5,555.10")
    total = find_word("$58,884.06")
    long_value = find_word("$100,000,000.00")

    assert pu[2] <= iva[0] - 2
    assert iva[2] <= ret_isr[0] - 2
    assert ret_isr[2] <= total[0] - 2

    pypdf = pytest.importorskip("pypdf")
    reader = pypdf.PdfReader(io.BytesIO(pdf_res.content))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)

    assert "Descripción" in text
    assert "TOTAL (MXN)" in text
    assert "TC" in text or "Tipo de cambio" in text
    assert "$100,000,000.00" in text
    assert long_value[2] > long_value[0]

    total_usd_match = re.search(r"TOTAL \(USD\):\s*US\$([0-9,]+\.\d{2})", text)
    tc_match = re.search(r"TC:\s*([0-9,]+\.\d{2})", text)
    total_mxn_match = re.search(r"TOTAL \(MXN\):\s*\$([0-9,]+\.\d{2})", text)
    assert total_usd_match and tc_match and total_mxn_match

    total_usd = Decimal(total_usd_match.group(1).replace(",", ""))
    tc = Decimal(tc_match.group(1).replace(",", ""))
    total_mxn = Decimal(total_mxn_match.group(1).replace(",", ""))
    expected_mxn = (total_usd * tc).quantize(Decimal("0.01"))

    assert abs(total_mxn - expected_mxn) <= Decimal("0.01")


def test_purchase_order_pdf_money_columns_keep_visual_separation_for_real_case():
    fitz = pytest.importorskip("fitz")

    client, _ = client_for("admin")
    payload = po_payload(ext="OC-REAL-MONEY-COLS", total_line="1740000.00")
    payload["currency"] = "MXN"
    payload["lines"] = [
        {
            "line_no": 1,
            "partida_codigo": "205",
            "description": "Validación de separación visual entre columnas monetarias",
            "qty": "1",
            "price_unit": "1500000.00",
            "discount_pct": "0",
            "iva_rate": "16",
            "apply_isr_withholding": True,
            "isr_withholding_rate": "0",
        },
    ]

    created = client.post("/api/purchase-orders", json=payload)
    assert created.status_code == 200
    po_id = created.json()["purchase_order"]["id"]

    pdf_res = client.get(f"/api/purchase-orders/{po_id}/pdf")
    assert pdf_res.status_code == 200

    doc = fitz.open(stream=pdf_res.content, filetype="pdf")
    words = []
    for page in doc:
        words.extend(page.get_text("words"))

    def first_word(token: str):
        matched = [w for w in words if w[4] == token]
        assert matched, f"No se encontró token {token}"
        matched.sort(key=lambda w: (w[1], w[0]))
        return matched[0]

    header_pu = first_word("Unitario")
    header_iva = first_word("IVA")
    header_ret = first_word("ISR")
    value_pu = first_word("$1,500,000.00")
    value_iva = first_word("$240,000.00")
    value_ret = first_word("$0.00")
    value_total = first_word("$1,740,000.00")

    assert header_pu[2] <= header_iva[0] - 2
    assert header_iva[2] <= header_ret[0] - 2

    assert value_pu[2] <= value_iva[0] - 2
    assert value_iva[2] <= value_ret[0] - 2
    assert value_ret[2] <= value_total[0] - 2
