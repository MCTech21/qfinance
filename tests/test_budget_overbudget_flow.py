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
    assert res.json()["detail"]["code"] == "overbudget_rejected_and_requested"
    over = [a for a in db.authorizations.rows if a.get("approval_type") == "overbudget_exception"]
    assert len(over) == 1


def test_total_only_budget_within_total_allows_movement():
    client, _ = client_for("finanzas")
    create_budget = client.post("/api/budgets", json={"project_id": "pr1", "partida_codigo": "205", "total_amount": "500.00"})
    assert create_budget.status_code == 201

    move = {
        "project_id": "pr1",
        "partida_codigo": "205",
        "provider_id": "pv1",
        "date": "2026-01-01",
        "currency": "MXN",
        "amount_original": 250,
        "exchange_rate": 1,
        "reference": "OK-1",
    }
    res = client.post("/api/movements", json=move)
    assert res.status_code == 200
    assert res.json()["movement"]["status"] == "posted"


def test_admin_bypass_detail_overbudget_when_total_allows():
    client, db = client_for("admin")
    create_budget = client.post("/api/budgets", json={
        "project_id": "pr1",
        "partida_codigo": "205",
        "total_amount": "1000.00",
        "annual_breakdown": {"2026": "300.00"},
    })
    assert create_budget.status_code == 201

    move = {
        "project_id": "pr1",
        "partida_codigo": "205",
        "provider_id": "pv1",
        "date": "2026-02-01",
        "currency": "MXN",
        "amount_original": 500,
        "exchange_rate": 1,
        "reference": "ADM-BYPASS",
    }
    res = client.post("/api/movements", json=move)
    assert res.status_code == 200
    bypass_logs = [l for l in db.audit_logs.rows if l.get("action") == "OVERBUDGET_ADMIN_BYPASS"]
    assert len(bypass_logs) == 1


def test_fallback_to_total_when_monthly_missing_and_total_sufficient():
    client, _ = client_for("finanzas")
    create_budget = client.post("/api/budgets", json={
        "project_id": "pr1",
        "partida_codigo": "205",
        "total_amount": "900.00",
        "annual_breakdown": {"2026": "900.00"},
        "monthly_breakdown": {"2026-01": "100.00"},
    })
    assert create_budget.status_code == 201

    move = {
        "project_id": "pr1",
        "partida_codigo": "205",
        "provider_id": "pv1",
        "date": "2026-05-01",
        "currency": "MXN",
        "amount_original": 200,
        "exchange_rate": 1,
        "reference": "FALLBACK-TOTAL",
    }
    res = client.post("/api/movements", json=move)
    assert res.status_code == 200


def test_overbudget_request_is_idempotent_for_same_payload():
    client, db = client_for("finanzas")
    assert client.post("/api/budgets", json={"project_id": "pr1", "partida_codigo": "205", "total_amount": "100.00"}).status_code == 201
    move = {
        "project_id": "pr1",
        "partida_codigo": "205",
        "provider_id": "pv1",
        "date": "2026-01-01",
        "currency": "MXN",
        "amount_original": 150,
        "exchange_rate": 1,
        "reference": "DUP-OB",
    }
    first = client.post("/api/movements", json=move)
    second = client.post("/api/movements", json=move)
    assert first.status_code == 422
    assert second.status_code == 422
    over = [a for a in db.authorizations.rows if a.get("approval_type") == "overbudget_exception" and a.get("status") == "pending"]
    assert len(over) == 1


def test_cross_company_budget_forbidden():
    client, _ = client_for("captura", company_id="e1")
    payload = {"project_id": "pr2", "partida_codigo": "205", "total_amount": "1000.00"}
    res = client.post("/api/budgets", json=payload)
    assert res.status_code == 403



def test_invalid_breakdown_json_returns_422_not_500():
    client, _ = client_for("admin")
    payload = {
        "project_id": "pr1",
        "partida_codigo": "205",
        "total_amount": "1000.00",
        "annual_breakdown": "{",
    }
    res = client.post("/api/budgets", json=payload)
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "invalid_breakdown_json"


def test_invalid_breakdown_type_returns_422():
    client, _ = client_for("admin")
    payload = {
        "project_id": "pr1",
        "partida_codigo": "205",
        "total_amount": "1000.00",
        "monthly_breakdown": ["bad"],
    }
    res = client.post("/api/budgets", json=payload)
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "invalid_breakdown_type"


def test_budgets_accept_all_filters_semantics():
    client, _ = client_for("admin")
    assert client.post("/api/budgets", json={"project_id": "pr1", "partida_codigo": "205", "total_amount": "1200.00", "monthly_breakdown": {"2026-01": "100.00", "2026-02": "150.00"}}).status_code == 201
    all_mode = client.get("/api/budgets", params={"project_id": "pr1", "year": "all", "month": "all"})
    assert all_mode.status_code == 200
    assert all_mode.json()[0]["period_mode"] == "total"

    annual_mode = client.get("/api/budgets", params={"project_id": "pr1", "year": "2026", "month": "all"})
    assert annual_mode.status_code == 200
    assert annual_mode.json()[0]["period_mode"] == "annual"

    invalid = client.get("/api/budgets", params={"project_id": "pr1", "month": "2"})
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "month_requires_year"


def test_breakdown_invalid_key_422():
    client, _ = client_for("admin")
    payload = {
        "project_id": "pr1",
        "partida_codigo": "205",
        "total_amount": "1000.00",
        "annual_breakdown": {"20AA": "100"},
    }
    res = client.post("/api/budgets", json=payload)
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "invalid_breakdown_key"


def test_breakdown_invalid_value_422():
    client, _ = client_for("admin")
    payload = {
        "project_id": "pr1",
        "partida_codigo": "205",
        "total_amount": "1000.00",
        "monthly_breakdown": {"2026-01": "bad"},
    }
    res = client.post("/api/budgets", json=payload)
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "invalid_breakdown_value"


def test_zero_is_ok_total_exact_allow():
    client, _ = client_for("finanzas")
    assert client.post("/api/budgets", json={"project_id": "pr1", "partida_codigo": "205", "total_amount": "100.00"}).status_code == 201
    move = {
        "project_id": "pr1",
        "partida_codigo": "205",
        "provider_id": "pv1",
        "date": "2026-01-01",
        "currency": "MXN",
        "amount_original": 100,
        "exchange_rate": 1,
        "reference": "ZERO-OK-TOTAL",
    }
    res = client.post("/api/movements", json=move)
    assert res.status_code == 200


def test_zero_is_ok_annual_exact_allow():
    client, _ = client_for("finanzas")
    assert client.post("/api/budgets", json={"project_id": "pr1", "partida_codigo": "205", "total_amount": "1000.00", "annual_breakdown": {"2026": "100.00"}}).status_code == 201
    move = {
        "project_id": "pr1",
        "partida_codigo": "205",
        "provider_id": "pv1",
        "date": "2026-02-01",
        "currency": "MXN",
        "amount_original": 100,
        "exchange_rate": 1,
        "reference": "ZERO-OK-ANNUAL",
    }
    res = client.post("/api/movements", json=move)
    assert res.status_code == 200


def test_zero_is_ok_monthly_exact_allow():
    client, _ = client_for("finanzas")
    assert client.post("/api/budgets", json={"project_id": "pr1", "partida_codigo": "205", "total_amount": "1000.00", "monthly_breakdown": {"2026-03": "100.00"}}).status_code == 201
    move = {
        "project_id": "pr1",
        "partida_codigo": "205",
        "provider_id": "pv1",
        "date": "2026-03-05",
        "currency": "MXN",
        "amount_original": 100,
        "exchange_rate": 1,
        "reference": "ZERO-OK-MONTH",
    }
    res = client.post("/api/movements", json=move)
    assert res.status_code == 200


def test_exceeds_by_cent_rejected():
    client, _ = client_for("finanzas")
    assert client.post("/api/budgets", json={"project_id": "pr1", "partida_codigo": "205", "total_amount": "100.00"}).status_code == 201
    move = {
        "project_id": "pr1",
        "partida_codigo": "205",
        "provider_id": "pv1",
        "date": "2026-01-01",
        "currency": "MXN",
        "amount_original": 100.01,
        "exchange_rate": 1,
        "reference": "OVER-CENT",
    }
    res = client.post("/api/movements", json=move)
    assert res.status_code == 422


def test_admin_total_only_exceed_rejected():
    client, _ = client_for("admin")
    assert client.post("/api/budgets", json={"project_id": "pr1", "partida_codigo": "205", "total_amount": "100.00"}).status_code == 201
    move = {
        "project_id": "pr1",
        "partida_codigo": "205",
        "provider_id": "pv1",
        "date": "2026-01-01",
        "currency": "MXN",
        "amount_original": 150,
        "exchange_rate": 1,
        "reference": "ADMIN-TOTAL-EXCEED",
    }
    res = client.post("/api/movements", json=move)
    assert res.status_code == 422


def test_high_amount_within_total_allowed():
    client, _ = client_for("finanzas")
    assert client.post("/api/budgets", json={"project_id": "pr1", "partida_codigo": "205", "total_amount": "5000000.00"}).status_code == 201
    move = {
        "project_id": "pr1",
        "partida_codigo": "205",
        "provider_id": "pv1",
        "date": "2026-01-01",
        "currency": "MXN",
        "amount_original": 4800000,
        "exchange_rate": 1,
        "reference": "BIG-AMOUNT",
    }
    res = client.post("/api/movements", json=move)
    assert res.status_code == 200


def test_budget_availability_endpoint_returns_remaining():
    client, _ = client_for("finanzas")
    assert client.post("/api/budgets", json={"project_id": "pr1", "partida_codigo": "205", "total_amount": "1000.00"}).status_code == 201
    res = client.get("/api/budget-availability", params={"project_id": "pr1", "partida_codigo": "205", "date": "2026-01-10"})
    assert res.status_code == 200
    body = res.json()
    assert body["has_budget"] is True
    assert body["remaining_total"] is not None

def test_budgets_company_filter_excludes_other_companies_and_orphans():
    client, db = client_for("admin")
    db.budget_plans.rows.extend([
        {"id": "bp-e1", "company_id": "e1", "project_id": "pr1", "partida_codigo": "205", "total_amount": "100", "annual_breakdown": {}, "monthly_breakdown": {}, "approval_status": "approved"},
        {"id": "bp-e2", "company_id": "e2", "project_id": "pr2", "partida_codigo": "205", "total_amount": "200", "annual_breakdown": {}, "monthly_breakdown": {}, "approval_status": "approved"},
        {"id": "bp-orphan", "company_id": None, "project_id": None, "partida_codigo": "205", "total_amount": "999", "annual_breakdown": {}, "monthly_breakdown": {}, "approval_status": "approved"},
    ])

    res = client.get("/api/budgets", params={"empresa_id": "e1"})
    assert res.status_code == 200
    ids = {row["id"] for row in res.json()}
    assert "bp-e1" in ids
    assert "bp-e2" not in ids
    assert "bp-orphan" not in ids


def test_budgets_project_filter_is_pure_project_without_na_rows():
    client, db = client_for("admin")
    db.budget_plans.rows.extend([
        {"id": "bp-pr1", "company_id": "e1", "project_id": "pr1", "partida_codigo": "205", "total_amount": "100", "annual_breakdown": {}, "monthly_breakdown": {}, "approval_status": "approved"},
        {"id": "bp-pr2", "company_id": "e2", "project_id": "pr2", "partida_codigo": "205", "total_amount": "200", "annual_breakdown": {}, "monthly_breakdown": {}, "approval_status": "approved"},
        {"id": "bp-global-e1", "company_id": "e1", "project_id": None, "partida_codigo": "205", "total_amount": "300", "annual_breakdown": {}, "monthly_breakdown": {}, "approval_status": "approved"},
    ])

    res = client.get("/api/budgets", params={"empresa_id": "e1", "project_id": "pr1"})
    assert res.status_code == 200
    rows = res.json()
    assert {row["id"] for row in rows} == {"bp-pr1"}
    assert all(row.get("project_id") == "pr1" for row in rows)


def test_dashboard_reports_budget_scope_matches_company_and_project_filters():
    client, db = client_for("admin")
    db.config = db.__class__.__dict__.get('config', None) or type(db.budgets)([])
    db.budget_plans.rows.extend([
        {"id": "bp-pr1", "company_id": "e1", "project_id": "pr1", "partida_codigo": "205", "total_amount": "100", "annual_breakdown": {"2026": "100"}, "monthly_breakdown": {"2026-01": "100"}, "approval_status": "approved"},
        {"id": "bp-pr2", "company_id": "e2", "project_id": "pr2", "partida_codigo": "205", "total_amount": "200", "annual_breakdown": {"2026": "200"}, "monthly_breakdown": {"2026-01": "200"}, "approval_status": "approved"},
        {"id": "bp-global-e1", "company_id": "e1", "project_id": None, "partida_codigo": "205", "total_amount": "999", "annual_breakdown": {"2026": "999"}, "monthly_breakdown": {"2026-01": "999"}, "approval_status": "approved"},
    ])

    company_view = client.get("/api/reports/dashboard", params={"empresa_id": "e1", "project_id": "all", "period": "month", "year": 2026, "month": 1})
    assert company_view.status_code == 200
    assert company_view.json()["totals"]["presupuesto_total"] == 100.0

    project_view = client.get("/api/reports/dashboard", params={"empresa_id": "e1", "project_id": "pr1", "period": "month", "year": 2026, "month": 1})
    assert project_view.status_code == 200
    assert project_view.json()["totals"]["presupuesto_total"] == 100.0
