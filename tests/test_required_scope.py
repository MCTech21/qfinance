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
                if "$ne" in v and row.get(k) == v["$ne"]: return False
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
    async def delete_one(self, query):
        self.rows = [r for r in self.rows if not self._matches(r, query)]


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


def test_mov_402_project_mismatch_422():
    c, _ = make_client()
    payload = {
        "project_id": "p2",
        "partida_codigo": "402",
        "provider_id": None,
        "client_id": "cl1",
        "date": "2026-01-01",
        "currency": "MXN",
        "amount_original": 1000,
        "exchange_rate": 1,
        "reference": "R",
    }
    r = c.post("/api/movements", json=payload)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "client_project_mismatch"


def test_validate_abono_limit_counts_legacy_without_client_id():
    c, db = make_client()
    db.clients.rows[0].update({"nombre": "JUAN", "precio_venta_snapshot": 100000.0, "saldo_restante": 100000.0})
    db.movements.rows.append({
        "id": "m-legacy-1",
        "project_id": "p1",
        "partida_codigo": "402",
        "customer_name": "JUAN",
        "status": "posted",
        "date": "2026-01-02T00:00:00+00:00",
        "amount_mxn": 95000.0,
    })

    payload = {
        "project_id": "p1",
        "partida_codigo": "402",
        "provider_id": None,
        "client_id": "cl1",
        "date": "2026-01-03",
        "currency": "MXN",
        "amount_original": 10000,
        "exchange_rate": 1,
        "reference": "R2",
    }
    r = c.post("/api/movements", json=payload)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "payment_exceeds_balance"


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


def test_clients_list_includes_abonos_and_inventory_clave():
    c, db = make_client()
    db.movements.rows.append({"id": "m2", "project_id": "p1", "partida_codigo": "402", "client_id": "cl1", "date": "2026-01-15T00:00:00+00:00", "status": "posted", "amount_mxn": 2500.0})
    r = c.get("/api/clients")
    assert r.status_code == 200
    cl = next(x for x in r.json() if x["id"] == "cl1")
    assert cl["inventory_clave"] == "L1-M3"
    assert cl["abonos_total_mxn"] == 2500.0


def test_inventory_summary_returns_totals():
    c, db = make_client()
    db.inventory_items.rows[0].update({"precio_total": 10000.0})
    db.clients.rows[0].update({"abonos_total_mxn": 1000.0})
    r = c.get("/api/inventory/summary")
    assert r.status_code == 200
    assert r.json()["valor_total_inventario_mxn"] == 10000.0


def test_delete_client_conflict_when_has_movements():
    c, db = make_client()
    db.movements.rows.append({"id": "m3", "client_id": "cl1", "status": "posted", "partida_codigo": "402"})
    r = c.delete("/api/clients/cl1")
    assert r.status_code == 409


def test_create_client_conflict_when_inventory_already_linked():
    c, _ = make_client()
    payload = {
        "company_id": "c1",
        "project_id": "p1",
        "nombre": "MARIA",
        "telefono": "555",
        "domicilio": "X",
        "inventory_item_id": "inv1",
    }
    r = c.post("/api/clients", json=payload)
    assert r.status_code == 409


def test_authorization_approval_recalculates_client_abonos():
    c, db = make_client()
    db.clients.rows[0].update({"precio_venta_snapshot": 100000.0, "abonos_total_mxn": 0.0, "saldo_restante": 100000.0})
    db.movements.rows.append({
        "id": "m-auth-1",
        "project_id": "p1",
        "partida_codigo": "402",
        "client_id": "cl1",
        "status": "pending_approval",
        "amount_mxn": 17500.0,
        "date": "2026-02-18T00:00:00+00:00",
    })
    db.authorizations.rows.append({"id": "a1", "status": "pending", "movement_id": "m-auth-1"})

    r = c.put("/api/authorizations/a1", json={"status": "approved"})
    assert r.status_code == 200

    cl = next(x for x in db.clients.rows if x["id"] == "cl1")
    assert cl["abonos_total_mxn"] == 17500.0
    assert cl["saldo_restante"] == 82500.0


def test_smoke_create_client_201():
    c, db = make_client()
    db.inventory_items.rows.append({"id": "inv2", "company_id": "c1", "project_id": "p1", "lote_edificio": "L2", "manzana_departamento": "M8", "precio_total": 350000.0})
    payload = {
        "empresa": "C1",
        "proyecto": "P1",
        "nombre": "Jeff Texos",
        "telefono": "6824646789",
        "domicilio": "6 de BN",
        "inventario": "L2-M8",
    }
    r = c.post("/api/clients", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["nombre"] == "JEFF TEXOS"
    assert body["inventory_item_id"] == "inv2"


def test_smoke_clients_abonos_include_legacy_customer_name():
    c, db = make_client()
    db.clients.rows[0].update({"nombre": "JOSE REYES DIAZ", "precio_venta_snapshot": 2646500.0, "abonos_total_mxn": 0.0, "saldo_restante": 2646500.0})
    db.movements.rows.extend([
        {"id": "m402a", "project_id": "p1", "partida_codigo": "402", "client_id": "cl1", "customer_name": "JOSE REYES DIAZ", "date": "2026-02-16T00:00:00+00:00", "status": "posted", "amount_mxn": 150000.0},
        {"id": "m402b", "project_id": "p1", "partida_codigo": "402", "customer_name": "JOSE REYES DIAZ", "date": "2026-02-19T00:00:00+00:00", "status": "posted", "amount_mxn": 18950.0},
    ])

    r = c.get("/api/clients")
    assert r.status_code == 200
    client = next(item for item in r.json() if item["id"] == "cl1")
    assert client["abonos_total_mxn"] == 168950.0
    assert client["saldo_restante_mxn"] == 2477550.0


def test_smoke_movement_receipt_pdf_valid():
    c, db = make_client()
    db.movements.rows.append({
        "id": "m-receipt-1",
        "project_id": "p1",
        "partida_codigo": "402",
        "client_id": "cl1",
        "customer_name": "JUAN",
        "date": "2026-02-16T00:00:00+00:00",
        "status": "posted",
        "currency": "MXN",
        "amount_original": 150000.0,
        "exchange_rate": 1,
        "amount_mxn": 150000.0,
        "reference": "A-103",
    })
    r = c.get("/api/movements/m-receipt-1/receipt.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert "inline; filename=recibo_m-receipt-1.pdf" in r.headers.get("content-disposition", "")
    assert r.content.startswith(b"%PDF")


def test_smoke_post_movement_402_with_client():
    c, _ = make_client()
    payload = {
        "project_id": "p1",
        "partida_codigo": "402",
        "provider_id": None,
        "client_id": "cl1",
        "date": "2026-02-16",
        "currency": "MXN",
        "amount_original": 12000,
        "exchange_rate": 1,
        "reference": "TEMP",
    }
    r = c.post("/api/movements", json=payload)
    assert r.status_code == 200
    assert r.json()["movement"]["partida_codigo"] == "402"


def test_dashboard_period_company_with_no_projects_returns_zero_totals():
    c, db = make_client()
    db.empresas.rows.append({"id": "c3", "nombre": "C3"})
    db.budgets.rows.append({"id": "b-global", "project_id": "p1", "partida_codigo": "205", "year": 2026, "month": 1, "amount_mxn": 9999})
    db.movements.rows.append({"id": "m-global", "project_id": "p1", "partida_codigo": "205", "status": "posted", "date": "2026-01-10T00:00:00+00:00", "amount_mxn": 7777})

    r = c.get('/api/dashboard/monthly', params={"empresa_id": "c3", "year": 2026, "month": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["totals"]["budget"] == 0.0
    assert body["totals"]["real"] == 0.0
    assert body["by_partida"] == []


def test_dashboard_period_real_uses_abs_for_legacy_negative_amounts():
    c, db = make_client()
    db.budgets.rows.append({"id": "b1", "project_id": "p1", "partida_codigo": "205", "year": 2026, "month": 1, "amount_mxn": 5000})
    db.movements.rows.append({"id": "m-neg", "project_id": "p1", "partida_codigo": "205", "status": "posted", "date": "2026-01-10T00:00:00+00:00", "amount_mxn": -1000})

    r = c.get('/api/dashboard/monthly', params={"empresa_id": "c1", "year": 2026, "month": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["totals"]["real"] == 1000.0


def test_update_client_inventory_rejects_already_linked_inventory():
    c, db = make_client()
    db.clients.rows.append({"id": "cl2", "company_id": "c1", "project_id": "p1", "nombre": "MARIA", "inventory_item_id": None, "saldo_restante": 0.0})

    r = c.put('/api/clients/cl2', json={"inventory_item_id": "inv1"})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "inventory_already_linked"


def test_update_client_inventory_rejects_scope_mismatch():
    c, db = make_client()
    db.inventory_items.rows.append({"id": "inv-c2", "company_id": "c2", "project_id": "p2", "lote_edificio": "L2", "manzana_departamento": "M2", "precio_total": 90000})

    r = c.put('/api/clients/cl1', json={"inventory_item_id": "inv-c2"})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "inventory_scope_mismatch"


def test_captura_can_read_inventory_and_summary_but_cannot_modify_inventory():
    c, _ = make_client(role="captura", empresa_id="c1")

    listed = c.get("/api/inventory")
    summary = c.get("/api/inventory/summary")
    create = c.post("/api/inventory", json={
        "company_id": "c1",
        "project_id": "p1",
        "m2_superficie": 100,
        "m2_construccion": 0,
        "lote_edificio": "L8",
        "manzana_departamento": "M8",
        "precio_m2_superficie": 1000,
        "precio_m2_construccion": 0,
        "descuento_bonificacion": 0,
    })
    delete = c.delete("/api/inventory/inv1")

    assert listed.status_code == 200
    assert summary.status_code == 200
    assert create.status_code == 403
    assert delete.status_code == 403


def test_finanzas_can_create_inventory_but_cannot_delete_inventory():
    c, _ = make_client(role="finanzas", empresa_id="c1")

    create = c.post("/api/inventory", json={
        "company_id": "c1",
        "project_id": "p1",
        "m2_superficie": 100,
        "m2_construccion": 0,
        "lote_edificio": "L10",
        "manzana_departamento": "M10",
        "precio_m2_superficie": 1000,
        "precio_m2_construccion": 0,
        "descuento_bonificacion": 0,
    })
    delete = c.delete("/api/inventory/inv1")

    assert create.status_code in (200, 201)
    assert delete.status_code == 403


def test_captura_can_read_receipt_in_scope_and_forbidden_out_of_scope():
    c, db = make_client(role="captura", empresa_id="c1")
    db.movements.rows.append({
        "id": "m4",
        "project_id": "p1",
        "partida_codigo": "402",
        "client_id": "cl1",
        "date": "2026-01-15T00:00:00+00:00",
        "currency": "MXN",
        "amount_original": 1000,
        "exchange_rate": 1,
        "amount_mxn": 1000,
        "reference": "L1-M3",
        "status": "posted",
    })
    db.movements.rows.append({
        "id": "m5",
        "project_id": "p2",
        "partida_codigo": "402",
        "client_id": None,
        "date": "2026-01-15T00:00:00+00:00",
        "currency": "MXN",
        "amount_original": 1000,
        "exchange_rate": 1,
        "amount_mxn": 1000,
        "reference": "X",
        "status": "posted",
    })

    in_scope = c.get("/api/movements/m4/receipt.pdf")
    out_scope = c.get("/api/movements/m5/receipt.pdf")

    assert in_scope.status_code == 200
    assert out_scope.status_code == 403
