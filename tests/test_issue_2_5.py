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

    async def find_one(self, query, projection=None):
        for row in self.rows:
            if all(row.get(k) == v for k, v in query.items()):
                return dict(row)
        return None

    def find(self, query, projection=None):
        out = []
        for row in self.rows:
            ok = True
            for k, v in query.items():
                if isinstance(v, dict) and "$ne" in v:
                    if row.get(k) == v["$ne"]:
                        ok = False
                elif row.get(k) != v:
                    ok = False
            if ok:
                out.append(dict(row))
        return FakeCursor(out)

    async def insert_one(self, doc):
        self.rows.append(dict(doc))

    async def update_one(self, query, update):
        for row in self.rows:
            if all(row.get(k) == v for k, v in query.items()):
                row.update(update.get("$set", {}))

    async def delete_one(self, query):
        self.rows = [r for r in self.rows if not all(r.get(k) == v for k, v in query.items())]

    async def count_documents(self, query):
        return len([r for r in self.rows if all(r.get(k) == v for k, v in query.items())])


class FakeDB:
    def __init__(self):
        self.catalogo_partidas = FakeCollection([
            {"id": "cp1", "codigo": "401", "nombre": "Ingresos", "grupo": "ingresos", "is_active": True},
            {"id": "cp2", "codigo": "205", "nombre": "Egresos", "grupo": "obra", "is_active": True},
        ])
        self.projects = FakeCollection([{"id": "pr1", "code": "P1", "name": "Proyecto", "empresa_id": "e1", "is_active": True}])
        self.providers = FakeCollection([{"id": "pv1", "code": "PV", "name": "Proveedor", "is_active": True}])
        self.users = FakeCollection([
            {
                "id": "u1",
                "email": "u@test.com",
                "name": "User",
                "role": "admin",
                "is_active": True,
                "must_change_password": True,
                "password_hash": server.hash_password("OldPass123"),
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        ])
        self.budgets = FakeCollection([])
        self.movements = FakeCollection([])
        self.authorizations = FakeCollection([])
        self.audit_logs = FakeCollection([])
        self.budget_requests = FakeCollection([])


def client_for_role(role: str):
    server.db = FakeDB()

    async def fake_user():
        return {"user_id": "u1", "email": "u@test.com", "role": role, "must_change_password": False}

    server.app.dependency_overrides[server.get_current_user] = fake_user
    return TestClient(server.app)


def test_finanzas_cannot_post_budgets():
    client = client_for_role("finanzas")
    payload = {"project_id": "pr1", "partida_codigo": "401", "year": 2026, "month": 1, "amount_mxn": 1000, "notes": "n"}
    res = client.post("/api/budgets", json=payload)
    assert res.status_code == 403


def test_captura_ingresos_only_4xx():
    client = client_for_role("captura_ingresos")
    good = {
        "project_id": "pr1", "partida_codigo": "401", "provider_id": "pv1", "date": "2026-01-10",
        "currency": "MXN", "amount_original": 1000, "exchange_rate": 1, "reference": "A"
    }
    bad = dict(good)
    bad["partida_codigo"] = "205"
    ok = client.post("/api/movements", json=good)
    denied = client.post("/api/movements", json=bad)
    assert ok.status_code == 200
    assert denied.status_code == 403


def test_readonly_roles_cannot_mutate_providers_or_budgets():
    for role in ["autorizador", "solo_lectura"]:
        client = client_for_role(role)
        res1 = client.post("/api/providers", json={"code": "X", "name": "X", "rfc": "", "is_active": True})
        res2 = client.post("/api/budgets", json={"project_id": "pr1", "partida_codigo": "401", "year": 2026, "month": 1, "amount_mxn": 1000, "notes": "n"})
        assert res1.status_code == 403
        assert res2.status_code == 403


def test_provider_export_and_import_upsert_and_duplicates():
    client = client_for_role("admin")
    export_csv = client.get("/api/providers/export?format=csv")
    export_xlsx = client.get("/api/providers/export?format=xlsx")
    assert export_csv.status_code == 200
    assert "text/csv" in export_csv.headers.get("content-type", "")
    assert export_xlsx.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in export_xlsx.headers.get("content-type", "")

    csv_data = "code,name,rfc,is_active\nPV,Proveedor actualizado,RFC1,true\nNEW,Nuevo,RFC2,true\nNEW,Nuevo dup,RFC3,true\n"
    files = {"file": ("providers.csv", csv_data, "text/csv")}
    res = client.post("/api/providers/import", files=files)
    body = res.json()
    assert res.status_code == 200
    assert body["updated"] >= 1
    assert body["created"] >= 1
    assert len(body["duplicates"]) == 1


def test_login_requires_force_change_flag_and_flow():
    server.db = FakeDB()
    server.app.dependency_overrides = {}
    client = TestClient(server.app)

    login = client.post("/api/auth/login", json={"email": "u@test.com", "password": "OldPass123"})
    assert login.status_code == 200
    assert login.json()["must_change_password"] is True

    token = login.json()["access_token"]
    # protected endpoint blocked until force change
    blocked = client.get("/api/projects", headers={"Authorization": f"Bearer {token}"})
    assert blocked.status_code == 403

    changed = client.post("/api/auth/force-change-password", json={"new_password": "NewPass123"}, headers={"Authorization": f"Bearer {token}"})
    assert changed.status_code == 200
    assert changed.json()["must_change_password"] is False
