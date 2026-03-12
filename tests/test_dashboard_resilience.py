from fastapi.testclient import TestClient
import backend.server as server


class FakeCursor:
    def __init__(self, items):
        self.items = items

    def sort(self, *args, **kwargs):
        return self

    async def to_list(self, n):
        return list(self.items)


class FakeCollection:
    def __init__(self, rows=None):
        self.rows = rows or []

    def _matches(self, row, query):
        for k, v in query.items():
            value = row.get(k)
            if isinstance(v, dict):
                if "$in" in v and value not in v["$in"]:
                    return False
            elif value != v:
                return False
        return True

    def find(self, query, projection=None):
        return FakeCursor([dict(r) for r in self.rows if self._matches(r, query)])

    async def count_documents(self, query):
        return len([r for r in self.rows if self._matches(r, query)])


class FakeDB:
    def __init__(self):
        self.projects = FakeCollection([
            {"id": "p-a1", "empresa_id": "A", "name": "A1", "manual_405": "1000"},
            {"id": "p-b1", "empresa_id": "B", "name": "B1", "manual_405": "2000"},
        ])
        self.movements = FakeCollection([
            {"id": "m1", "project_id": "p-a1", "partida_codigo": None, "date": "2026-01-03T00:00:00+00:00", "status": "posted", "amount_mxn": -120},
            {"id": "m2", "project_id": "p-a1", "partida_codigo": "101", "date": "2026-01-04T00:00:00+00:00", "status": "posted", "amount_mxn": -80},
            {"id": "m3", "project_id": "p-b1", "partida_codigo": "201", "date": "2026-01-04T00:00:00+00:00", "status": "posted", "amount_mxn": -50},
        ])
        self.budget_plans = FakeCollection([
            {"id": "bp1", "project_id": "p-a1", "partida_codigo": "101", "total_amount": "500", "annual_breakdown": {}, "monthly_breakdown": {}, "approval_status": "approved"},
            {"id": "bp-global-a", "project_id": None, "company_id": "A", "partida_codigo": "777", "total_amount": "100", "annual_breakdown": {}, "monthly_breakdown": {}, "approval_status": "approved"},
        ])
        self.budgets = FakeCollection([])
        self.purchase_orders = FakeCollection([])
        self.inventory_items = FakeCollection([])
        self.catalogo_partidas = FakeCollection([
            {"codigo": "101", "nombre": "Terreno", "grupo": "obra"},
            {"codigo": "201", "nombre": "Otro", "grupo": "obra"},
        ])
        self.empresas = FakeCollection([{"id": "A", "nombre": "Empresa A"}, {"id": "B", "nombre": "Empresa B"}])
        self.config = FakeCollection([{"key": "threshold_yellow", "value": 80}, {"key": "threshold_red", "value": 95}])
        self.authorizations = FakeCollection([])


def make_client():
    server.db = FakeDB()

    async def fake_user():
        return {"user_id": "u1", "email": "u@test.com", "role": "admin", "must_change_password": False}

    server.app.dependency_overrides[server.get_current_user] = fake_user
    return TestClient(server.app)


def test_dashboard_returns_200_with_partial_data_and_no_na_partida_rows():
    client = make_client()
    res = client.get("/api/reports/dashboard", params={"empresa_id": "A", "project_id": "p-a1", "period": "month", "year": 2026, "month": 1})
    assert res.status_code == 200
    payload = res.json()
    assert payload["shared_kpis"] is not None
    assert all((row.get("partida_codigo") or "") != "N/A" for row in payload.get("by_partida", []))


def test_dashboard_financial_projection_failure_isolated(monkeypatch):
    client = make_client()

    def boom(*args, **kwargs):
        raise RuntimeError("broken")

    monkeypatch.setattr(server, "_build_financial_projection", boom)
    res = client.get("/api/reports/dashboard", params={"empresa_id": "A", "project_id": "p-a1", "period": "month", "year": 2026, "month": 1})
    assert res.status_code == 200
    payload = res.json()
    assert payload["shared_kpis"]["presupuesto_total"] is not None
    assert payload["financial_projection"]["rows"] == []
    assert payload["financial_projection"]["empty_reason"]


def test_dashboard_company_scope_excludes_other_company_data():
    client = make_client()
    res = client.get("/api/reports/dashboard", params={"empresa_id": "A", "period": "month", "year": 2026, "month": 1})
    assert res.status_code == 200
    payload = res.json()
    by_codes = {row.get("partida_codigo") for row in payload.get("by_partida", [])}
    assert "201" not in by_codes
