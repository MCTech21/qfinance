from fastapi.testclient import TestClient
import backend.server as server


class FakeCursor:
    def __init__(self, items): self.items = items
    def sort(self, *args, **kwargs): return self
    async def to_list(self, n): return list(self.items)


class FakeCollection:
    def __init__(self, rows=None): self.rows = rows or []
    def _matches(self, row, query):
        for k, v in query.items():
            if isinstance(v, dict):
                if "$in" in v and row.get(k) not in v["$in"]: return False
            elif row.get(k) != v:
                return False
        return True
    async def find_one(self, query, projection=None):
        for r in self.rows:
            if self._matches(r, query): return dict(r)
        return None
    def find(self, query, projection=None):
        return FakeCursor([dict(r) for r in self.rows if self._matches(r, query)])
    async def insert_one(self, doc): self.rows.append(dict(doc))
    async def update_one(self, query, update):
        for r in self.rows:
            if self._matches(r, query): r.update(update.get("$set", {}))


class FakeDB:
    def __init__(self):
        self.catalogo_partidas = FakeCollection([
            {"codigo": "205", "nombre": "Egreso", "grupo": "obra", "is_active": True},
            {"codigo": "402", "nombre": "Ingreso", "grupo": "ingresos", "is_active": True},
            {"codigo": "403", "nombre": "Ingreso2", "grupo": "ingresos", "is_active": True},
        ])
        self.projects = FakeCollection([
            {"id": "p1", "empresa_id": "c1", "name": "P1", "code": "P1"},
            {"id": "p2", "empresa_id": "c2", "name": "P2", "code": "P2"},
        ])
        self.providers = FakeCollection([{"id": "pv1", "name": "Prov"}])
        self.budgets = FakeCollection([])
        self.movements = FakeCollection([])
        self.audit_logs = FakeCollection([])
        self.authorizations = FakeCollection([])
        self.budget_requests = FakeCollection([])
        self.budget_plans = FakeCollection([])
        self.inventory_items = FakeCollection([{"id": "inv1", "company_id": "c1", "project_id": "p1", "lote_edificio": "L1", "manzana_departamento": "M3", "precio_total": 100000.0}])
        self.clients = FakeCollection([{"id": "cl1", "company_id": "c1", "project_id": "p1", "nombre": "JUAN", "inventory_item_id": "inv1", "saldo_restante": 100000.0}])
        self.import_export_logs = FakeCollection([])
        self.empresas = FakeCollection([{"id": "c1", "nombre": "C1"}, {"id": "c2", "nombre": "C2"}])
    def __getitem__(self, n): return getattr(self, n)


def make_client(role="admin", empresa_id="c1"):
    server.db = FakeDB()
    async def fake_user():
        return {"user_id": "u1", "email": "u@test.com", "role": role, "empresa_id": empresa_id, "must_change_password": False}
    server.app.dependency_overrides[server.get_current_user] = fake_user
    return TestClient(server.app), server.db


def test_budget_annual_exceeds_total_422():
    c, _ = make_client()
    payload = {"project_id": "p1", "partida_codigo": "205", "total": 100, "annual_breakdown": {"2026": 200}, "monthly_breakdown": {}}
    r = c.post("/api/budgets/plan", json=payload)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "annual_sum_exceeds_total"


def test_budget_months_exceed_annual_422():
    c, _ = make_client()
    payload = {"project_id": "p1", "partida_codigo": "205", "total": 500, "annual_breakdown": {"2026": 100}, "monthly_breakdown": {"2026-01": 120}}
    r = c.post("/api/budgets/plan", json=payload)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "monthly_sum_exceeds_annual"


def test_mov_402_without_client_422():
    c, _ = make_client()
    payload = {"project_id": "p1", "partida_codigo": "402", "provider_id": None, "date": "2026-01-01", "currency": "MXN", "amount_original": 10, "exchange_rate": 1, "reference": "X"}
    r = c.post("/api/movements", json=payload)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "client_required_for_partida_402_403"


def test_mov_402_forces_reference_and_adjusts_balance():
    c, db = make_client()
    payload = {"project_id": "p1", "partida_codigo": "402", "provider_id": None, "date": "2026-01-01", "currency": "MXN", "amount_original": 50000, "exchange_rate": 1, "reference": "MANUAL", "client_id": "cl1"}
    r = c.post("/api/movements", json=payload)
    assert r.status_code == 200
    mov = r.json()["movement"]
    assert mov["reference"] == "L1-M3"
    cl = next(x for x in db.clients.rows if x["id"] == "cl1")
    assert cl["saldo_restante"] == 50000.0


def test_rbac_cross_company_403():
    c, _ = make_client(role="captura", empresa_id="c1")
    r = c.get("/api/dashboard/total", params={"empresa_id": "c2"})
    assert r.status_code == 403


def test_report_export_ejecutado_not_zero_with_egreso():
    c, db = make_client()
    db.movements.rows.append({"id": "m1", "project_id": "p1", "partida_codigo": "205", "date": "2026-01-15T00:00:00+00:00", "status": "posted", "amount_mxn": -123.0, "currency": "MXN", "amount_original": -123.0, "exchange_rate": 1, "reference": "R"})
    db.budgets.rows.append({"id": "b1", "project_id": "p1", "partida_codigo": "205", "year": 2026, "month": 1, "amount_mxn": 1000})
    r = c.get("/api/reports/export-data", params={"year": 2026, "month": 1})
    assert r.status_code == 200
    assert r.json()["resumen"]["ejecutado"] == 123.0


def test_update_client_endpoint_ok():
    c, db = make_client()
    r = c.put("/api/clients/cl1", json={"nombre": "maria", "telefono": "555"})
    assert r.status_code == 200
    assert r.json()["nombre"] == "MARIA"
    cl = next(x for x in db.clients.rows if x["id"] == "cl1")
    assert cl["telefono"] == "555"


def test_update_inventory_endpoint_recalculates_total():
    c, db = make_client()
    db.inventory_items.rows[0].update({
        "m2_superficie": 100,
        "m2_construccion": 0,
        "precio_m2_superficie": 1000,
        "precio_m2_construccion": 0,
        "descuento_bonificacion": 0,
        "precio_venta": 100000,
    })
    r = c.put("/api/inventory/inv1", json={"descuento_bonificacion": 1000})
    assert r.status_code == 200
    assert r.json()["precio_total"] == 99000.0
