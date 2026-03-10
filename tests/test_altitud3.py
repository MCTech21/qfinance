from fastapi.testclient import TestClient
import backend.server as server
from tests.test_issue_2_5 import FakeDB, FakeCollection


def mk_client(role="admin"):
    db = FakeDB()
    server.db = db

    async def fake_user():
        return {"user_id": "u1", "email": "u@test.com", "role": role, "empresa_id": "e1", "must_change_password": False}

    server.app.dependency_overrides[server.get_current_user] = fake_user
    return TestClient(server.app), db


def test_purchase_order_with_iva_withholding_calculates_net_and_mxn():
    client, _ = mk_client()
    payload = {
        "project_id": "pr1",
        "vendor_name": "Proveedor Uno",
        "currency": "USD",
        "exchange_rate": "20",
        "order_date": "2026-01-10",
        "apply_iva_withholding": True,
        "iva_withholding_rate": "50",
        "lines": [{"line_no": 1, "partida_codigo": "301", "description": "Servicio", "qty": "1", "price_unit": "100", "discount_pct": "0", "iva_rate": "16", "apply_isr_withholding": False, "isr_withholding_rate": "0"}],
    }
    res = client.post("/api/purchase-orders", json=payload)
    assert res.status_code == 200
    po = res.json()["purchase_order"]
    assert po["iva_retenido"] == "8.00"
    assert po["total_neto"] == "108.00"
    assert po["total_mxn"] == "2160.00"


def test_movement_usd_requires_exchange_rate_and_sets_amount_mxn():
    client, _ = mk_client()
    bad = client.post("/api/movements", json={"project_id": "pr1", "partida_codigo": "301", "provider_id": "pv1", "date": "2026-01-10", "currency": "USD", "amount_original": 10, "exchange_rate": 0, "reference": "A"})
    assert bad.status_code == 422
    ok = client.post("/api/movements", json={"project_id": "pr1", "partida_codigo": "301", "provider_id": "pv1", "date": "2026-01-10", "currency": "USD", "amount_original": 10, "exchange_rate": 20, "reference": "B"})
    assert ok.status_code == 200
    assert ok.json()["movement"]["amount_mxn"] == 200.0


def test_invoices_anticipo_and_liquidacion_flow():
    client, _ = mk_client()
    created = client.post("/api/invoices", json={"empresa_id": "e1", "project_id": "pr1", "provider_id": "pv1", "invoice_folio": "FAC-1", "currency": "MXN", "exchange_rate": "1", "invoice_total_original": "100"})
    assert created.status_code == 200
    inv_id = created.json()["id"]

    anticipo = client.post(f"/api/invoices/{inv_id}/pay", json={"mode": "ANTICIPO", "advance_pct": "50", "date": "2026-01-10", "reference": "ANT-1", "partida_codigo": "301"})
    assert anticipo.status_code == 200
    assert anticipo.json()["invoice"]["balance_mxn"] == "50.00"

    exceso = client.post(f"/api/invoices/{inv_id}/pay", json={"mode": "PAGO", "amount_original": "60", "date": "2026-01-10", "reference": "PAY-2", "partida_codigo": "301"})
    assert exceso.status_code == 422

    liquidacion = client.post(f"/api/invoices/{inv_id}/pay", json={"mode": "LIQUIDACION", "date": "2026-01-10", "reference": "LIQ-1", "partida_codigo": "301"})
    assert liquidacion.status_code == 200
    assert liquidacion.json()["invoice"]["balance_mxn"] == "0.00"


def test_provider_search_and_sort():
    client, db = mk_client()
    db.providers.rows = [
        {"id": "p1", "code": "2", "name": "Árbol", "rfc": "XXX", "is_active": True, "created_at": "2026-01-01T00:00:00+00:00"},
        {"id": "p2", "code": "1", "name": "abeja", "rfc": "RFC1", "is_active": True, "created_at": "2026-01-01T00:00:00+00:00"},
    ]
    res = client.get("/api/providers", params={"q": "rfc1"})
    assert res.status_code == 200
    assert len(res.json()) == 1
    all_res = client.get("/api/providers")
    assert [r["name"] for r in all_res.json()] == ["abeja", "Árbol"]


def test_csv_import_inventory_and_clients_dry_run():
    client, _ = mk_client()
    inv_csv = "code,company_id,project_id,lote_edificio,manzana_departamento,m2_superficie,precio_m2_superficie\nI-1,e1,pr1,L1,M1,10,100\n"
    res = client.post("/api/inventory/import-csv?dry_run=true", files={"file": ("inv.csv", inv_csv, "text/csv")})
    assert res.status_code == 200
    assert res.json()["created_count"] >= 1
    assert len(res.json()["sample_rows"]) == 1

    cli_csv = "code,company_id,project_id,nombre,telefono\nC1,e1,pr1,Cliente 1,555\n"
    res2 = client.post("/api/clients/import-csv?dry_run=true", files={"file": ("clients.csv", cli_csv, "text/csv")})
    assert res2.status_code == 200
    assert len(res2.json()["sample_rows"]) == 1
