from fastapi.testclient import TestClient
import backend.server as server
from tests.test_issue_2_5 import FakeDB


def client_for(role: str, company_id: str = "e1"):
    db = FakeDB()
    db.projects.rows = [
        {"id": "pr1", "code": "P1", "name": "Proyecto 1", "empresa_id": "e1", "is_active": True},
        {"id": "pr2", "code": "P2", "name": "Proyecto 2", "empresa_id": "e2", "is_active": True},
    ]
    db.empresas.rows = [{"id": "e1", "nombre": "Empresa 1"}, {"id": "e2", "nombre": "Empresa 2"}]
    db.budget_plans = db.__class__.__dict__.get('budget_plans', None) or type(db.budgets)([])
    server.db = db

    async def fake_user():
        return {"user_id": "u1", "email": "u@test.com", "role": role, "empresa_id": company_id, "must_change_password": False}

    server.app.dependency_overrides[server.get_current_user] = fake_user
    return TestClient(server.app), db


def test_monthly_exceeds_annual_validation():
    client, _ = client_for("admin")
    payload = {
        "project_id": "pr1",
        "partida_codigo": "205",
        "total_amount": "2000.00",
        "annual_breakdown": {"2026": "1000.00"},
        "monthly_breakdown": {"2026-01": "600.00", "2026-02": "500.00"},
    }
    res = client.post("/api/budgets", json=payload)
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "monthly_sum_exceeds_annual"


def test_monthly_without_annual_is_valid():
    client, _ = client_for("admin")
    payload = {
        "project_id": "pr1",
        "partida_codigo": "205",
        "total_amount": "1000.00",
        "monthly_breakdown": {"2026-01": "400.00", "2026-02": "500.00"},
    }
    res = client.post("/api/budgets", json=payload)
    assert res.status_code == 201


def test_non_admin_budget_goes_pending_and_creates_approval():
    client, db = client_for("finanzas")
    payload = {"project_id": "pr1", "partida_codigo": "205", "total_amount": "1000.00"}
    res = client.post("/api/budgets", json=payload)
    assert res.status_code == 201
    assert res.json()["approval_status"] == "pending"
    auths = [a for a in db.authorizations.rows if a.get("approval_type") == "budget_definition" and a.get("status") == "pending"]
    assert len(auths) == 1


def test_admin_budget_bypass_no_pending_approval():
    client, db = client_for("admin")
    payload = {"project_id": "pr1", "partida_codigo": "205", "total_amount": "1000.00"}
    res = client.post("/api/budgets", json=payload)
    assert res.status_code == 201
    assert res.json()["approval_status"] == "approved"
    auths = [a for a in db.authorizations.rows if a.get("approval_type") == "budget_definition" and a.get("status") == "pending"]
    assert len(auths) == 0


def test_overbudget_reject_and_request():
    client, db = client_for("admin")
    create_budget = client.post("/api/budgets", json={"project_id": "pr1", "partida_codigo": "205", "total_amount": "100.00"})
    assert create_budget.status_code == 201
    move = {
        "project_id": "pr1",
        "partida_codigo": "205",
        "provider_id": "pv1",
        "date": "2026-01-01",
        "currency": "MXN",
        "amount_original": 150,
        "exchange_rate": 1,
        "reference": "A-1",
    }
    res = client.post("/api/movements", json=move)
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "movement_over_budget"
    over = [a for a in db.authorizations.rows if a.get("approval_type") == "overbudget_exception"]
    assert len(over) == 1


def test_cross_company_budget_forbidden():
    client, _ = client_for("captura", company_id="e1")
    payload = {"project_id": "pr2", "partida_codigo": "205", "total_amount": "1000.00"}
    res = client.post("/api/budgets", json=payload)
    assert res.status_code == 403
