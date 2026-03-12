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

    async def find_one(self, query, projection=None):
        for r in self.rows:
            if self._matches(r, query):
                return dict(r)
        return None

    async def count_documents(self, query):
        return len([r for r in self.rows if self._matches(r, query)])


class FakeDB:
    def __init__(self):
        self.projects = FakeCollection([
            {"id": "p-a1", "empresa_id": "A", "name": "A1"},
            {"id": "p-a2", "empresa_id": "A", "name": "A2"},
            {"id": "p-b1", "empresa_id": "B", "name": "B1"},
        ])
        self.budget_plans = FakeCollection([
            {"id": "bp-a1", "project_id": "p-a1", "partida_codigo": "101", "total_amount": "1000", "annual_breakdown": {}, "monthly_breakdown": {}, "approval_status": "approved"},
            {"id": "bp-null-partida", "project_id": "p-a1", "partida_codigo": None, "total_amount": "500", "annual_breakdown": {}, "monthly_breakdown": {}, "approval_status": "approved"},
            {"id": "bp-orphan", "project_id": "p-orphan", "partida_codigo": "999", "total_amount": "700", "annual_breakdown": {}, "monthly_breakdown": {}, "approval_status": "approved"},
            {"id": "bp-global-a", "project_id": None, "company_id": "A", "partida_codigo": "102", "total_amount": "300", "annual_breakdown": {}, "monthly_breakdown": {}, "approval_status": "approved"},
        ])
        self.budgets = FakeCollection([
            {"id": "b-a1", "project_id": "p-a1", "partida_codigo": "101", "year": 2026, "month": 1, "amount_mxn": "100"},
            {"id": "b-b1", "project_id": "p-b1", "partida_codigo": "201", "year": 2026, "month": 1, "amount_mxn": "800"},
            {"id": "b-orphan", "project_id": "missing", "partida_codigo": "301", "year": 2026, "month": 1, "amount_mxn": "900"},
            {"id": "b-global-a", "project_id": None, "company_id": "A", "partida_codigo": "777", "year": 2026, "month": 1, "amount_mxn": "50"},
        ])
        self.movements = FakeCollection([])
        self.catalogo_partidas = FakeCollection([])
        self.empresas = FakeCollection([])
        self.config = FakeCollection([])
        self.authorizations = FakeCollection([])
        self.inventory_items = FakeCollection([])
        self.purchase_orders = FakeCollection([])


def make_client():
    server.db = FakeDB()

    async def fake_user():
        return {"user_id": "u1", "email": "u@test.com", "role": "admin", "must_change_password": False}

    server.app.dependency_overrides[server.get_current_user] = fake_user
    return TestClient(server.app)


def test_budget_company_scope_excludes_other_company_rows():
    client = make_client()
    response = client.get("/api/budgets", params={"empresa_id": "A", "year": 2026, "month": 1})
    assert response.status_code == 200
    project_ids = {row.get("project_id") for row in response.json() if row.get("project_id")}
    assert "p-b1" not in project_ids


def test_project_scope_excludes_global_rows_and_null_partida_and_orphans():
    client = make_client()
    response = client.get("/api/budgets", params={"project_id": "p-a1", "year": 2026, "month": 1})
    assert response.status_code == 200
    rows = response.json()
    assert all(row.get("project_id") == "p-a1" for row in rows)
    assert all((row.get("partida_codigo") or "").strip() for row in rows)
    assert all(row.get("id") != "bp-orphan" for row in rows)
    assert all(row.get("id") != "b-global-a" for row in rows)


def test_project_specific_budget_appears_for_own_project():
    client = make_client()
    response = client.get("/api/budgets", params={"project_id": "p-a1"})
    assert response.status_code == 200
    assert any(row.get("project_id") == "p-a1" and row.get("partida_codigo") == "101" for row in response.json())
