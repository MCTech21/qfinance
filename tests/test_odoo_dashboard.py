from fastapi.testclient import TestClient
from decimal import Decimal
import backend.server as server
from tests.test_issue_2_5 import FakeDB


def make_client(role="admin", empresa_ids=None):
    db = FakeDB()
    db.projects.rows = [{"id": "pr1", "empresa_id": "e1", "name": "Proyecto 1"}, {"id": "pr2", "empresa_id": "e2", "name": "Proyecto 2"}]
    db.empresas.rows = [{"id": "e1", "nombre": "Empresa 1"}, {"id": "e2", "nombre": "Empresa 2"}]
    db.catalogo_partidas.rows = [
        {"codigo": "101", "nombre": "Costo", "grupo": "COSTOS DIRECTOS"},
        {"codigo": "402", "nombre": "Ingreso", "grupo": "INGRESOS"},
    ]
    db.budget_plans.rows = [{"id": "b1", "project_id": "pr1", "partida_codigo": "101", "total_amount": "0", "approval_status": "approved", "annual_breakdown": {}, "monthly_breakdown": {}}]
    db.movements.rows = [{"id": "m1", "project_id": "pr1", "partida_codigo": "101", "status": "posted", "amount_mxn": 100, "date": "2026-01-01", "is_active": True}]
    db.odoo_sync_purchase_orders = type(db.budgets)([])
    db.config = type(db.budgets)([{"key": "threshold_yellow", "value": 90}, {"key": "threshold_red", "value": 100}])
    server.db = db

    async def fake_user():
        return {"user_id": "u1", "email": "u@test.com", "role": role, "empresa_id": "e1", "empresa_ids": empresa_ids or ["e1"], "must_change_password": False}

    server.app.dependency_overrides[server.get_current_user] = fake_user
    return TestClient(server.app), db


def test_budget_signal_no_budget_no_spend_is_green():
    signal = server.build_budget_signal(Decimal("0"), Decimal("0"), Decimal("90"), Decimal("100"))
    assert signal["traffic_light"] == "green"
    assert signal["porcentaje"] == Decimal("0.00")


def test_budget_signal_no_budget_with_spend_is_yellow_and_na_pct():
    signal = server.build_budget_signal(Decimal("0"), Decimal("10"), Decimal("90"), Decimal("100"))
    assert signal["traffic_light"] == "yellow"
    assert signal["porcentaje"] is None
    assert signal["porcentaje_label"] == "N/A"


def test_reports_corrida_endpoint_returns_rows():
    client, _ = make_client("admin")
    r = client.get("/api/reports/corrida", params={"period": "month", "year": 2026, "month": 1, "empresa_id": "all"})
    assert r.status_code == 200
    body = r.json()
    assert "rows" in body
    assert isinstance(body["rows"], list)


def test_odoo_config_admin_only_and_masked_key():
    admin_client, _ = make_client("admin")
    put = admin_client.put("/api/admin/integrations/odoo", json={"odoo_mode": "stub", "odoo_url": "https://x", "odoo_db": "db", "odoo_username": "u", "odoo_api_key": "secret"})
    assert put.status_code == 200
    assert put.json()["odoo_api_key"] == "***"

    non_admin_client, _ = make_client("finanzas")
    denied = non_admin_client.get("/api/admin/integrations/odoo")
    assert denied.status_code == 403


def test_oc_pdf_filename_normalized_prefix():
    assert server.oc_pdf_filename("OC000002") == "OC000002.pdf"
    assert server.oc_pdf_filename("OC-OC000002") == "OC000002.pdf"
