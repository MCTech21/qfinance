from fastapi.testclient import TestClient
import backend.server as server
from tests.test_issue_2_5 import FakeDB
import io
import pytest


def _pdf_text(pdf_bytes: bytes) -> str:
    pypdf = pytest.importorskip("pypdf")
    PdfReader = pypdf.PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def client_for(role: str, company_id: str = "e1"):
    db = FakeDB()
    db.projects.rows = [{"id": "pr1", "code": "P1", "name": "Proyecto 1", "empresa_id": "e1", "is_active": True}]
    db.empresas.rows = [{"id": "e1", "nombre": "Empresa 1"}]
    db.purchase_orders = db.__class__.__dict__.get('purchase_orders', None) or type(db.budgets)([])
    db.odoo_sync_purchase_orders = db.__class__.__dict__.get('odoo_sync_purchase_orders', None) or type(db.budgets)([])
    server.db = db

    async def fake_user():
        return {"user_id": "u1", "email": "u@test.com", "role": role, "empresa_id": company_id, "must_change_password": False}

    server.app.dependency_overrides[server.get_current_user] = fake_user
    return TestClient(server.app), db


def po_payload(ext: str = "OC-1", total_line: str = "100.00"):
    return {
        "external_id": ext,
        "invoice_folio": "F-SD3BC5",
        "project_id": "pr1",
        "vendor_name": "Proveedor Uno",
        "currency": "MXN",
        "exchange_rate": "1",
        "order_date": "2026-01-10",
        "lines": [
            {
                "line_no": 1,
                "partida_codigo": "205",
                "description": "Servicio",
                "qty": "1",
                "price_unit": total_line,
                "discount_pct": "0",
                "iva_rate": "16",
                "apply_isr_withholding": False,
                "isr_withholding_rate": "0"
            }
        ]
    }


def test_create_submit_reject_flow():
    client, _ = client_for("finanzas")
    created = client.post("/api/purchase-orders", json=po_payload())
    assert created.status_code == 200
    po_id = created.json()["purchase_order"]["id"]

    submitted = client.post(f"/api/purchase-orders/{po_id}/submit")
    assert submitted.status_code == 200
    assert submitted.json()["purchase_order"]["status"] == "pending_approval"

    denied = client.post(f"/api/purchase-orders/{po_id}/reject", json={"reason": "x"})
    assert denied.status_code == 403


def test_create_without_external_id_autogenerates_folio_and_invoice_folio_persists():
    client, _ = client_for("finanzas")
    payload = po_payload(ext="", total_line="100.00")
    payload["external_id"] = None
    created = client.post("/api/purchase-orders", json=payload)
    assert created.status_code == 200
    po = created.json()["purchase_order"]
    assert po["folio"].startswith("OC")
    assert po["external_id"] == po["folio"]
    assert po["invoice_folio"] == "F-SD3BC5"


def test_partial_index_creation_does_not_fail_with_legacy_null_docs():
    client, db = client_for("admin")
    db.movements.rows = [{"id": "m1", "purchase_order_line_id": None, "origin_event": None}, {"id": "m2"}]
    import asyncio
    asyncio.run(server.ensure_partial_indexes_for_movements())
    idx = db.movements.indexes.get("uq_movements_po_line_origin_event_exists")
    assert idx is not None
    assert idx.get("unique") is True
    assert idx.get("partialFilterExpression") is not None


def test_partial_approval_authorization_creates_partial_movement_and_keeps_pending():
    client, db = client_for("admin")
    assert client.post("/api/budgets", json={"project_id": "pr1", "partida_codigo": "205", "total_amount": "1000.00"}).status_code == 201
    created = client.post("/api/purchase-orders", json=po_payload(ext="", total_line="100.00"))
    po_id = created.json()["purchase_order"]["id"]
    assert client.post(f"/api/purchase-orders/{po_id}/submit").status_code == 200
    pending_auth = [a for a in db.authorizations.rows if a.get("approval_type") == "purchase_order_workflow" and a.get("status") == "pending"]
    assert len(pending_auth) == 1
    auth_id = pending_auth[0]["id"]
    res = client.put(f"/api/authorizations/{auth_id}", json={"status": "approved", "notes": "parcial", "partial_amount": "50.00"})
    assert res.status_code == 200
    po = next((p for p in db.purchase_orders.rows if p.get("id") == po_id), None)
    assert po is not None
    assert po.get("status") == "partially_approved"
    assert po.get("pending_amount") == "66.00"


def test_approve_budget_exception_and_idempotent_approval_request():
    client, db = client_for("admin")
    assert client.post("/api/budgets", json={"project_id": "pr1", "partida_codigo": "205", "total_amount": "100.00"}).status_code == 201
    created = client.post("/api/purchase-orders", json=po_payload(ext="OC-2", total_line="200.00"))
    po_id = created.json()["purchase_order"]["id"]
    assert client.post(f"/api/purchase-orders/{po_id}/submit").status_code == 200

    first = client.post(f"/api/purchase-orders/{po_id}/approve")
    second = client.post(f"/api/purchase-orders/{po_id}/approve")
    assert first.status_code == 409
    assert second.status_code == 409
    over = [a for a in db.authorizations.rows if a.get("approval_type") == "overbudget_exception"]
    assert len(over) == 1


def test_approve_posts_movements_and_odoo_stub_no_duplicates_on_retry():
    client, db = client_for("admin")
    assert client.post("/api/budgets", json={"project_id": "pr1", "partida_codigo": "205", "total_amount": "1000.00"}).status_code == 201
    created = client.post("/api/purchase-orders", json=po_payload(ext="OC-3", total_line="100.00"))
    po_id = created.json()["purchase_order"]["id"]
    assert client.post(f"/api/purchase-orders/{po_id}/submit").status_code == 200

    first = client.post(f"/api/purchase-orders/{po_id}/approve")
    second = client.post(f"/api/purchase-orders/{po_id}/approve")
    assert first.status_code == 200
    assert second.status_code == 200
    moves = [m for m in db.movements.rows if m.get("purchase_order_id") == po_id]
    assert len(moves) == 1
    odoo = [m for m in db.odoo_sync_purchase_orders.rows if m.get("purchase_order_id") == po_id]
    assert len(odoo) == 1


def test_oc_preview_endpoint_and_zero_ok_boundary():
    client, _ = client_for("admin")
    assert client.post("/api/budgets", json={"project_id": "pr1", "partida_codigo": "205", "total_amount": "100.00"}).status_code == 201
    preview = client.post("/api/budgets/availability/oc-preview", json={
        "project_id": "pr1",
        "order_date": "2026-01-10",
        "lines": [{"partida_codigo": "205", "requested_amount": "100.00"}],
    })
    assert preview.status_code == 200
    line = preview.json()["lines"][0]
    assert line["projected_remaining_total"] == "0.00"
    assert line["can_post_payment"] is True


def test_pdf_endpoint_returns_pdf_content_type():
    client, _ = client_for("admin")
    created = client.post("/api/purchase-orders", json=po_payload(ext="OC-PDF", total_line="100.00"))
    assert created.status_code == 200
    po_id = created.json()["purchase_order"]["id"]
    pdf_res = client.get(f"/api/purchase-orders/{po_id}/pdf")
    assert pdf_res.status_code == 200
    assert "application/pdf" in pdf_res.headers.get("content-type", "")
    assert len(pdf_res.content) > 10


def test_invalid_iva_rate_422():
    client, _ = client_for("admin")
    payload = po_payload(ext="OC-4", total_line="100.00")
    payload["lines"][0]["iva_rate"] = "10"
    res = client.post("/api/purchase-orders", json=payload)
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "invalid_iva_rate"


def test_authorization_payload_includes_oc_budget_summary():
    client, _ = client_for("admin")
    assert client.post("/api/budgets", json={"project_id": "pr1", "partida_codigo": "205", "total_amount": "1000.00"}).status_code == 201
    created = client.post("/api/purchase-orders", json=po_payload(ext="", total_line="100.00"))
    po_id = created.json()["purchase_order"]["id"]
    assert client.post(f"/api/purchase-orders/{po_id}/submit").status_code == 200

    listed = client.get("/api/authorizations", params={"status": "pending"})
    assert listed.status_code == 200
    auth = next((a for a in listed.json() if a.get("purchase_order_id") == po_id), None)
    assert auth is not None
    assert auth.get("purchase_order_details", {}).get("folio")
    assert auth.get("purchase_order_details", {}).get("empresa_nombre") == "Empresa 1"
    assert auth.get("purchase_order_details", {}).get("proyecto_nombre") == "Proyecto 1"
    assert auth.get("budget_gate_summary", {}).get("budget_total") is not None
    assert isinstance(auth.get("budget_gate_summary", {}).get("by_partida"), list)


def test_partial_approval_updates_pending_and_budget_fields():
    client, db = client_for("admin")
    assert client.post("/api/budgets", json={"project_id": "pr1", "partida_codigo": "205", "total_amount": "1000.00"}).status_code == 201
    created = client.post("/api/purchase-orders", json=po_payload(ext="", total_line="100.00"))
    po_id = created.json()["purchase_order"]["id"]
    assert client.post(f"/api/purchase-orders/{po_id}/submit").status_code == 200
    auth_id = next(a["id"] for a in db.authorizations.rows if a.get("purchase_order_id") == po_id and a.get("status") == "pending")

    res = client.put(f"/api/authorizations/{auth_id}", json={"status": "approved", "partial_amount": "50.00", "notes": "ok"})
    assert res.status_code == 200
    payload = res.json()
    assert payload["pending_amount"] == "66.00"
    assert payload.get("budget_gate_summary", {}).get("pending_amount") == "66.00"


def test_authorization_resolve_422_does_not_return_unserializable_error():
    client, db = client_for("admin")
    assert client.post("/api/budgets", json={"project_id": "pr1", "partida_codigo": "205", "total_amount": "1000.00"}).status_code == 201
    created = client.post("/api/purchase-orders", json=po_payload(ext="", total_line="100.00"))
    po_id = created.json()["purchase_order"]["id"]
    assert client.post(f"/api/purchase-orders/{po_id}/submit").status_code == 200
    auth_id = next(a["id"] for a in db.authorizations.rows if a.get("purchase_order_id") == po_id and a.get("status") == "pending")

    bad = client.put(f"/api/authorizations/{auth_id}", json={"status": "approved", "partial_amount": "9999.00"})
    assert bad.status_code == 422
    detail = bad.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("code") == "partial_amount_exceeds_pending"
    assert isinstance(detail.get("details"), dict)


def test_purchase_order_pdf_endpoint_returns_pdf_and_contains_folio():
    client, _ = client_for("admin")
    created = client.post("/api/purchase-orders", json=po_payload(ext="OC-2", total_line="100.00"))
    po = created.json()["purchase_order"]
    po_id = po["id"]
    pdf_res = client.get(f"/api/purchase-orders/{po_id}/pdf")
    assert pdf_res.status_code == 200
    assert b"%PDF" in pdf_res.content[:10]
    assert b"ORDEN DE COMPRA" in pdf_res.content
    assert "inline; filename=OC000002.pdf" in pdf_res.headers.get("content-disposition", "")
    import re
    text = pdf_res.content.decode("latin-1", errors="ignore")
    assert text.count("Fecha:") == 1
    assert re.search(r"\d{2}/\d{2}/\d{4}", text)


def test_index_setup_is_mongo_compatible_no_ne_in_partial_expression():
    _, db = client_for("admin")
    import asyncio
    asyncio.run(server.ensure_partial_indexes_for_movements())
    asyncio.run(server.ensure_purchase_order_indexes())
    idx = db.movements.indexes.get("uq_movements_po_line_origin_event_exists") or {}
    partial = idx.get("partialFilterExpression") or {}
    assert "$type" in partial.get("purchase_order_line_id", {})
    assert "$ne" not in partial.get("purchase_order_line_id", {})
    assert "$type" in partial.get("origin_event", {})
    po_idx = db.purchase_orders.indexes.get("uq_purchase_orders_folio_exists") or {}
    po_partial = po_idx.get("partialFilterExpression") or {}
    assert po_partial.get("folio", {}).get("$type") == "string"


def test_oc_preview_budget_calculation_with_iva_and_multi_lines():
    client, _ = client_for("admin")
    assert client.post("/api/budgets", json={"project_id": "pr1", "partida_codigo": "205", "total_amount": "300.00"}).status_code == 201
    preview = client.post("/api/budgets/availability/oc-preview", json={
        "project_id": "pr1",
        "order_date": "2026-01-10",
        "lines": [
            {"partida_codigo": "205", "requested_amount": "100.00"},
            {"partida_codigo": "205", "requested_amount": "50.00"},
        ],
    })
    assert preview.status_code == 200
    body = preview.json()
    assert body["lines"][0]["requested_amount"] == "150.00"
    assert body["summary"]["monto_solicitado"] == "150.00"


def test_startup_index_setup_is_idempotent_with_conflicting_folio_index():
    _, db = client_for("admin")
    db.purchase_orders.indexes["folio_1"] = {
        "key": [("folio", 1)],
        "unique": True,
        "partialFilterExpression": {"folio": {"$exists": True}},
    }
    import asyncio
    asyncio.run(server.ensure_purchase_order_indexes())
    idx = db.purchase_orders.indexes.get("uq_purchase_orders_folio_exists") or {}
    assert idx.get("partialFilterExpression", {}).get("folio", {}).get("$type") == "string"
    asyncio.run(server.ensure_purchase_order_indexes())
    idx2 = db.purchase_orders.indexes.get("uq_purchase_orders_folio_exists") or {}
    assert idx2.get("partialFilterExpression", {}).get("folio", {}).get("$type") == "string"


def test_purchase_order_pdf_handles_long_content_and_paginates_safely():
    client, _ = client_for("admin")
    payload = po_payload(ext="OC-999", total_line="100.00")
    payload["vendor_name"] = "Proveedor con nombre extremadamente largo " * 4
    payload["vendor_rfc"] = "RFCMUYLARGODEPRUEBA1234567890"
    payload["notes"] = "Nota extensa de prueba " * 80
    payload["lines"] = []
    for i in range(1, 36):
        payload["lines"].append({
            "line_no": i,
            "partida_codigo": "205",
            "description": ("Descripción muy larga de concepto para validar wrapping y altura dinámica " * 2).strip(),
            "qty": "1",
            "price_unit": "10.00",
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
    assert "application/pdf" in pdf_res.headers.get("content-type", "")
    assert len(pdf_res.content) > 2000
    assert b"ORDEN DE COMPRA" in pdf_res.content


def test_pdf_filename_avoids_oc_duplication_with_prefixed_external_id():
    client, _ = client_for("admin")
    created = client.post("/api/purchase-orders", json=po_payload(ext="OC-000123", total_line="100.00"))
    po_id = created.json()["purchase_order"]["id"]
    pdf_res = client.get(f"/api/purchase-orders/{po_id}/pdf")
    assert pdf_res.status_code == 200
    cd = pdf_res.headers.get("content-disposition", "")
    assert "inline; filename=OC000123.pdf" in cd



def test_build_oc_pdf_payload_minimal():
    po = {
        "folio": "OC000003",
        "order_date": "2026-02-24",
        "company_name": "EJEMPLO Q",
        "project_name": "Proyecto Demo",
        "vendor_name": "Proveedor",
        "lines": [],
        "subtotal_tax_base": "0.00",
        "tax_total": "0.00",
        "total": "0.00",
    }
    payload = server.build_purchase_order_pdf_payload(po)
    assert payload["folio"] == "OC000003"
    assert payload["date"] == "2026-02-24"
    assert payload["buyer"]["name"] == "EJEMPLO Q"
    assert payload["vendor"]["name"] == "Proveedor"
    assert payload["lines"] == []


def test_build_oc_pdf_payload_full():
    po = {
        "folio": "OC000004",
        "order_date": "2026-02-24",
        "planned_date": "2026-03-01",
        "company_name": "EJEMPLO Q",
        "company_rfc": "ABC123",
        "company_address": "CALLE 1",
        "project_name": "Proyecto Demo",
        "vendor_name": "Proveedor Largo",
        "vendor_rfc": "RFC123",
        "vendor_address": "AV 2",
        "vendor_email": "ventas@demo.com",
        "currency": "USD",
        "exchange_rate": "17.25",
        "lines": [{"line_no": 1, "partida_codigo": "205", "description": "Servicio", "qty": "2", "price_unit": "100.00", "line_total": "200.00", "iva_amount": "32.00", "isr_withholding_amount": "0.00"}],
        "subtotal_tax_base": "200.00",
        "tax_total": "32.00",
        "total": "232.00",
        "bank_details": {"clabe": "0123"},
        "notes": "nota",
        "payment_terms": "contado",
    }
    payload = server.build_purchase_order_pdf_payload(po)
    assert payload["buyer"]["rfc"] == "ABC123"
    assert payload["vendor"]["rfc"] == "RFC123"
    assert payload["bank"] == {"clabe": "0123"}
    assert payload["lines"][0]["code"] == "205"
    assert payload["lines"][0]["amount"] == "200.00"


def test_render_pdf_bytes_has_metadata_strings_and_filename_rules():
    po = {
        "folio": "OC000005",
        "order_date": "2026-02-24",
        "company_name": "EJEMPLO Q",
        "project_name": "Proyecto",
        "vendor_name": "Proveedor",
        "lines": [{"line_no": 1, "partida_codigo": "205", "description": "Servicio", "qty": "1", "price_unit": "100.00", "line_total": "116.00", "iva_amount": "16.00", "isr_withholding_amount": "0.00"}],
        "subtotal_tax_base": "100.00",
        "tax_total": "16.00",
        "total": "116.00",
    }
    pdf = server.render_purchase_order_pdf(po)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1200
    txt = pdf.decode("latin-1", errors="ignore")
    assert "QFinance / quantumgrupo.mx" in txt
    assert "Orden de Compra OC000005" in txt
    assert server.oc_pdf_filename("OC000123") == "OC000123.pdf"
    assert server.oc_pdf_filename("  F/77 ") == "F_77.pdf"
    assert server.oc_pdf_filename(None) == "purchase-order.pdf"


def test_filename_is_exact_folio_pdf():
    assert server.oc_pdf_filename("OC000003") == "OC000003.pdf"


def test_logo_scaling_no_distortion(monkeypatch):
    po = {
        "folio": "OC000009",
        "order_date": "2026-02-24",
        "company_name": "EJEMPLO Q",
        "project_name": "Proyecto",
        "vendor_name": "Proveedor",
        "lines": [],
        "subtotal_tax_base": "0.00",
        "tax_total": "0.00",
        "total": "0.00",
    }
    monkeypatch.setenv("QFINANCE_PDF_LOGO_PATH", "/tmp/logo-inexistente.png")
    no_logo = server.render_purchase_order_pdf(po)
    monkeypatch.delenv("QFINANCE_PDF_LOGO_PATH", raising=False)
    with_logo = server.render_purchase_order_pdf(po)
    assert with_logo.startswith(b"%PDF")
    assert len(with_logo) >= len(no_logo)


def test_statuses_hidden_when_missing():
    po = {
        "folio": "OC000010",
        "order_date": "2026-02-24",
        "company_name": "EJEMPLO Q",
        "project_name": "Proyecto",
        "vendor_name": "Proveedor",
        "lines": [],
        "subtotal_tax_base": "0.00",
        "tax_total": "0.00",
        "total": "0.00",
    }
    txt = _pdf_text(server.render_purchase_order_pdf(po))
    assert "Envío:" not in txt
    assert "Pago:" not in txt


def test_statuses_present_when_fields_exist():
    po = {
        "folio": "OC000011",
        "order_date": "2026-02-24",
        "company_name": "EJEMPLO Q",
        "project_name": "Proyecto",
        "vendor_name": "Proveedor",
        "sent_at": "2026-02-24T12:00:00Z",
        "payment_approved_at": "2026-02-25T12:00:00Z",
        "lines": [],
        "subtotal_tax_base": "0.00",
        "tax_total": "0.00",
        "total": "0.00",
    }
    txt = _pdf_text(server.render_purchase_order_pdf(po))
    assert "Envío: Enviado" in txt
    assert "Pago: Aprobado" in txt


def test_logo_resolution(monkeypatch):
    monkeypatch.setenv("QFINANCE_PDF_LOGO_PATH", "/tmp/does-not-exist-oc-logo.png")
    resolved = server.resolve_pdf_logo_path()
    assert resolved is None or resolved.endswith("quantum_logo.png")


def test_render_pdf_contains_key_text():
    po = {
        "folio": "OC000006",
        "order_date": "2026-02-24",
        "company_name": "EJEMPLO Q",
        "project_name": "Proyecto",
        "vendor_name": "Proveedor",
        "lines": [],
        "subtotal_tax_base": "0.00",
        "tax_total": "0.00",
        "total": "0.00",
    }
    pdf = server.render_purchase_order_pdf(po)
    assert pdf.startswith(b"%PDF")
    txt = pdf.decode("latin-1", errors="ignore")
    assert "ORDEN DE COMPRA" in txt
    assert "Unidad" in txt
    assert "OC000006" in txt


def test_pdf_contains_formatted_money_with_currency_symbol():
    po = {
        "folio": "OC000012",
        "order_date": "2026-02-24",
        "company_name": "EJEMPLO Q",
        "project_name": "Proyecto",
        "vendor_name": "Proveedor",
        "currency": "MXN",
        "lines": [{
            "line_no": 1,
            "partida_codigo": "205",
            "description": "Servicio",
            "qty": "1",
            "uom": "PZA",
            "price_unit": "120000",
            "line_total": "129600",
            "iva_amount": "9600",
            "isr_withholding_amount": "0",
        }],
        "subtotal_tax_base": "120000",
        "tax_total": "9600",
        "total": "129600",
    }
    txt = _pdf_text(server.render_purchase_order_pdf(po))
    assert "Unidad" in txt
    assert "$120,000.00" in txt


def test_metadata_present():
    po = {
        "folio": "OC000007",
        "order_date": "2026-02-24",
        "company_name": "EJEMPLO Q",
        "project_name": "Proyecto",
        "vendor_name": "Proveedor",
        "lines": [],
        "subtotal_tax_base": "0.00",
        "tax_total": "0.00",
        "total": "0.00",
    }
    txt = server.render_purchase_order_pdf(po).decode("latin-1", errors="ignore")
    assert "Creator (QFinance / quantumgrupo.mx)" in txt
    assert "Producer (QFinance / quantumgrupo.mx)" in txt
    assert "Title (Orden de Compra OC000007)" in txt


def test_notes_section_includes_bank_as_bullets():
    po = {
        "folio": "OC000008",
        "order_date": "2026-02-24",
        "company_name": "EJEMPLO Q",
        "project_name": "Proyecto",
        "vendor_name": "Proveedor",
        "notes": "Urgente",
        "bank_details": {
            "banco": "BBVA",
            "cuenta": "123456",
            "clabe": "012345678901234567",
            "beneficiario": "Quantum SA",
        },
        "lines": [],
        "subtotal_tax_base": "0.00",
        "tax_total": "0.00",
        "total": "0.00",
    }
    txt = _pdf_text(server.render_purchase_order_pdf(po))
    assert "NOTAS / COMENTARIOS ADICIONALES" in txt
    assert "Banco" in txt
    assert "BBVA" in txt
    assert any(label in txt for label in ("Cuenta", "CLABE", "Beneficiario"))
