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
    async def count_documents(self, query):
        return len([r for r in self.rows if self._matches(r, query)])


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
        self.purchase_orders = FakeCollection([])
        self.inventory_items = FakeCollection([{"id": "inv1", "company_id": "c1", "project_id": "p1", "lote_edificio": "L1", "manzana_departamento": "M3", "precio_total": 100000.0}])
        self.clients = FakeCollection([{"id": "cl1", "company_id": "c1", "project_id": "p1", "nombre": "JUAN", "inventory_item_id": "inv1", "saldo_restante": 100000.0}])
        self.import_export_logs = FakeCollection([])
        self.empresas = FakeCollection([{"id": "c1", "nombre": "C1"}, {"id": "c2", "nombre": "C2"}])
        self.config = FakeCollection([{"key": "threshold_yellow", "value": 80}, {"key": "threshold_red", "value": 95}])
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


def test_reports_dashboard_periods_and_rbac_and_serialization():
    c, db = make_client(role="captura", empresa_id="c1")
    db.projects.rows.append({"id": "p3", "empresa_id": "c1", "name": "P3", "code": "P3"})
    db.budget_plans.rows.extend([
        {
            "id": "bp1", "project_id": "p1", "partida_codigo": "205", "total_amount": 1000,
            "annual_breakdown": {"2026": 600},
            "monthly_breakdown": {"2026-01": 100, "2026-02": 200, "2026-03": 300},
            "approval_status": "approved",
        },
        {
            "id": "bp2", "project_id": "p2", "partida_codigo": "205", "total_amount": 9999,
            "annual_breakdown": {"2026": 9999},
            "monthly_breakdown": {"2026-01": 9999},
            "approval_status": "approved",
        },
        {
            "id": "bp3", "project_id": "p1", "partida_codigo": "402", "total_amount": 500,
            "monthly_breakdown": {"2026-01": 500},
            "approval_status": "pending",
        },
    ])
    db.movements.rows.extend([
        {"id": "m1", "project_id": "p1", "partida_codigo": "205", "status": "posted", "is_deleted": False, "date": "2026-01-10T00:00:00+00:00", "amount_mxn": -80},
        {"id": "m2", "project_id": "p1", "partida_codigo": "205", "status": "posted", "is_deleted": False, "date": "2026-02-10T00:00:00+00:00", "amount_mxn": -20},
        {"id": "m3", "project_id": "p2", "partida_codigo": "205", "status": "posted", "is_deleted": False, "date": "2026-01-10T00:00:00+00:00", "amount_mxn": -999},
    ])

    r_month = c.get('/api/reports/dashboard', params={"empresa_id": "all", "project_id": "all", "period": "month", "year": 2026, "month": 1})
    assert r_month.status_code == 200
    payload = r_month.json()
    assert payload["totals"]["presupuesto_total"] == 100.0
    assert payload["totals"]["ejecutado_total"] == 80.0
    assert payload["totals"]["traffic_light"] == "yellow"
    import json
    assert "\"_id\":" not in json.dumps(payload)

    r_quarter = c.get('/api/reports/dashboard', params={"period": "quarter", "year": 2026, "quarter": 1, "empresa_id": "all", "project_id": "all"})
    assert r_quarter.status_code == 200
    assert r_quarter.json()["totals"]["presupuesto_total"] == 600.0

    r_year = c.get('/api/reports/dashboard', params={"period": "year", "year": 2026, "empresa_id": "all", "project_id": "all"})
    assert r_year.status_code == 200
    assert r_year.json()["totals"]["presupuesto_total"] == 600.0

    r_all = c.get('/api/reports/dashboard', params={"period": "all", "year": 2026, "empresa_id": "all", "project_id": "all"})
    assert r_all.status_code == 200
    assert r_all.json()["totals"]["presupuesto_total"] == 600.0




def test_reports_dashboard_projection_handles_mixed_naive_and_aware_dates():
    from datetime import datetime, timezone

    c, db = make_client(role="admin")
    db.projects.rows = [p for p in db.projects.rows if p.get("id") == "p1"]
    db.budget_plans.rows.append({
        "id": "bp_mix",
        "project_id": "p1",
        "partida_codigo": "205",
        "total_amount": 1000,
        "monthly_breakdown": {"2026-01": 400, "2026-02": 600},
        "approval_status": "approved",
    })
    db.movements.rows.extend([
        {"id": "mix1", "project_id": "p1", "partida_codigo": "402", "status": "posted", "is_deleted": False, "date": datetime(2025, 12, 31, 23, 0, 0), "amount_mxn": 100},
        {"id": "mix2", "project_id": "p1", "partida_codigo": "205", "status": "posted", "is_deleted": False, "date": datetime(2026, 1, 15, 0, 0, 0, tzinfo=timezone.utc), "amount_mxn": -50},
    ])
    db.purchase_orders.rows.append({
        "id": "po_mix",
        "project_id": "p1",
        "status": "approved_for_payment",
        "pending_amount": 120,
        "planned_date": datetime(2026, 2, 20, 0, 0, 0),
        "lines": [{"partida_codigo": "205", "line_total": 120}],
    })
    db.inventory_items.rows.append({
        "id": "inv_mix",
        "company_id": "c1",
        "project_id": "p1",
        "precio_total": 500,
        "created_at": datetime(2026, 1, 5, 0, 0, 0),
    })

    r_month = c.get('/api/reports/dashboard', params={"empresa_id": "c1", "project_id": "p1", "period": "month", "year": 2026, "month": 1})
    assert r_month.status_code == 200
    month_payload = r_month.json()
    assert "financial_projection" in month_payload
    assert month_payload["financial_projection"]["rows"]

    r_quarter = c.get('/api/reports/dashboard', params={"empresa_id": "c1", "project_id": "p1", "period": "quarter", "year": 2026, "quarter": 1})
    assert r_quarter.status_code == 200

    r_year = c.get('/api/reports/dashboard', params={"empresa_id": "c1", "project_id": "p1", "period": "year", "year": 2026})
    assert r_year.status_code == 200

def test_reports_dashboard_validations_422():
    c, _ = make_client()
    assert c.get('/api/reports/dashboard', params={"period": "month", "year": 2026, "month": 0}).status_code == 422
    assert c.get('/api/reports/dashboard', params={"period": "month", "year": 2026, "month": 13}).status_code == 422
    assert c.get('/api/reports/dashboard', params={"period": "quarter", "year": 2026, "quarter": 0}).status_code == 422
    assert c.get('/api/reports/dashboard', params={"period": "quarter", "year": 2026, "quarter": 5}).status_code == 422


def test_reports_dashboard_pl_uses_inventory_405_and_subtotals():
    c, db = make_client(role="admin")
    db.catalogo_partidas.rows.extend([
        {"codigo": "101", "nombre": "TERRENO", "grupo": "COSTOS DIRECTOS", "is_active": True},
        {"codigo": "201", "nombre": "GASTOS DE PUBLICIDAD Y PROMOCION", "grupo": "GASTOS VTA/ADM", "is_active": True},
        {"codigo": "301", "nombre": "COMISIONES BANCARIAS", "grupo": "GASTOS FINANCIEROS", "is_active": True},
    ])
    db.budgets.rows.extend([
        {"id": "b101", "project_id": "p1", "partida_codigo": "101", "year": 2026, "month": 1, "amount_mxn": 1000},
        {"id": "b201", "project_id": "p1", "partida_codigo": "201", "year": 2026, "month": 1, "amount_mxn": 200},
        {"id": "b301", "project_id": "p1", "partida_codigo": "301", "year": 2026, "month": 1, "amount_mxn": 100},
    ])
    db.budget_plans.rows.append({
        "id": "bp405",
        "project_id": "p1",
        "partida_codigo": "405",
        "total_amount": 101500,
        "monthly_breakdown": {"2026-01": 101500},
        "annual_breakdown": {},
        "approval_status": "approved",
    })
    db.movements.rows.extend([
        {"id": "m101", "project_id": "p1", "partida_codigo": "101", "status": "posted", "is_deleted": False, "date": "2026-01-10T00:00:00+00:00", "amount_mxn": -800},
        {"id": "m201", "project_id": "p1", "partida_codigo": "201", "status": "posted", "is_deleted": False, "date": "2026-01-11T00:00:00+00:00", "amount_mxn": -100},
        {"id": "m301", "project_id": "p1", "partida_codigo": "301", "status": "posted", "is_deleted": False, "date": "2026-01-12T00:00:00+00:00", "amount_mxn": -50},
    ])
    db.inventory_items.rows.extend([
        {"id": "inv2", "company_id": "c1", "project_id": "p1", "precio_total": 1500},
    ])

    r = c.get('/api/reports/dashboard', params={"empresa_id": "c1", "project_id": "p1", "period": "month", "year": 2026, "month": 1})
    assert r.status_code == 200
    payload = r.json()
    assert payload["totals"]["ingreso_proyectado_405"] == 101500.0
    assert payload["totals"]["ejecucion_vs_ingreso_pct"] is not None

    rows = payload["rows"]
    row101 = next(x for x in rows if x["code"] == "101")
    assert row101["budget"] == 1000.0
    assert row101["real"] == 800.0
    assert row101["remaining"] == 200.0
    assert row101["traffic_light"] == "green"

    income = next(x for x in rows if x["code"] == "405")
    assert income["row_key"] == "income"
    assert income["budget"] == 101500.0

    gross = next(x for x in rows if x["code"] == "SUBTOTAL_GROSS")
    assert gross["row_key"] == "gross_profit"
    assert gross["budget"] == 100500.0
    assert gross["real"] == 800.0
    assert gross["remaining"] == 99700.0

    operating = next(x for x in rows if x["code"] == "SUBTOTAL_OPERATING")
    assert operating["row_key"] == "operating_profit"
    assert operating["budget"] == 100300.0
    assert operating["real"] == 900.0

    pbt = next(x for x in rows if x["code"] == "SUBTOTAL_PRE_TAX")
    assert pbt["row_key"] == "pre_tax_profit"
    assert pbt["budget"] == 100200.0
    assert pbt["real"] == 950.0


def test_reports_dashboard_pl_zero_income_pct_and_zero_budget_traffic_light():
    c, db = make_client(role="admin")
    db.projects.rows.append({"id": "p3", "empresa_id": "c1", "name": "P3", "code": "P3"})
    db.catalogo_partidas.rows.append({"codigo": "101", "nombre": "TERRENO", "grupo": "COSTOS DIRECTOS", "is_active": True})
    db.movements.rows.append({"id": "m101", "project_id": "p3", "partida_codigo": "101", "status": "posted", "is_deleted": False, "date": "2026-01-10T00:00:00+00:00", "amount_mxn": -10})

    r = c.get('/api/reports/dashboard', params={"empresa_id": "c1", "project_id": "p3", "period": "month", "year": 2026, "month": 1})
    assert r.status_code == 200
    rows = r.json()["rows"]
    row101 = next(x for x in rows if x["code"] == "101")
    assert row101["income_pct"] is None
    assert row101["traffic_light"] == "red"


def test_reports_dashboard_budget_control_rows_and_summary_and_zero_budget_cases():
    c, db = make_client(role="admin")
    db.catalogo_partidas.rows.extend([
        {"codigo": "101", "nombre": "TERRENO", "grupo": "COSTOS DIRECTOS", "is_active": True},
        {"codigo": "201", "nombre": "GASTOS DE PUBLICIDAD Y PROMOCION", "grupo": "GASTOS VTA/ADM", "is_active": True},
        {"codigo": "301", "nombre": "COMISIONES BANCARIAS", "grupo": "GASTOS FINANCIEROS", "is_active": True},
    ])
    db.budgets.rows.extend([
        {"id": "b101", "project_id": "p1", "partida_codigo": "101", "year": 2026, "month": 1, "amount_mxn": 1000},
        {"id": "b201", "project_id": "p1", "partida_codigo": "201", "year": 2026, "month": 1, "amount_mxn": 100},
    ])
    db.movements.rows.extend([
        {"id": "m101", "project_id": "p1", "partida_codigo": "101", "status": "posted", "is_deleted": False, "date": "2026-01-10T00:00:00+00:00", "amount_mxn": -950},
        {"id": "m201", "project_id": "p1", "partida_codigo": "201", "status": "posted", "is_deleted": False, "date": "2026-01-11T00:00:00+00:00", "amount_mxn": -110},
    ])
    db.purchase_orders.rows.append({
        "id": "po1",
        "project_id": "p1",
        "status": "approved_for_payment",
        "currency": "MXN",
        "total": "150.00",
        "total_mxn": "150.00",
        "approved_amount_total": "50.00",
        "pending_amount": "100.00",
        "lines": [
            {"partida_codigo": "101", "line_total": "90.00"},
            {"partida_codigo": "301", "line_total": "60.00"},
        ],
    })

    r = c.get('/api/reports/dashboard', params={"empresa_id": "c1", "project_id": "p1", "period": "month", "year": 2026, "month": 1})
    assert r.status_code == 200
    payload = r.json()

    assert payload["shared_kpis"]["presupuesto_total"] == payload["totals"]["presupuesto_total"]
    assert "rows" in payload["pnl"]

    bc_rows = payload["budget_control"]["rows"]
    row101 = next(x for x in bc_rows if x["code"] == "101")
    assert row101["budget"] == 1000.0
    assert row101["real"] == 950.0
    assert row101["committed"] == 60.0
    assert row101["available"] == -10.0
    assert row101["advance_pct"] == 95.0
    assert row101["traffic_light"] == "yellow"

    row201 = next(x for x in bc_rows if x["code"] == "201")
    assert row201["budget"] == 100.0
    assert row201["real"] == 110.0
    assert row201["committed"] == 0.0
    assert row201["available"] == -10.0
    assert row201["advance_pct"] == 110.0
    assert row201["traffic_light"] == "red"

    row301 = next(x for x in bc_rows if x["code"] == "301")
    assert row301["budget"] == 0.0
    assert row301["real"] == 0.0
    assert row301["committed"] == 40.0
    assert row301["available"] == -40.0
    assert row301["advance_pct"] is None
    assert row301["traffic_light"] == "red"

    summary = payload["budget_control"]["summary"]
    assert summary["yellow_count"] == 1
    assert summary["red_count"] == 2
    assert summary["overrun_count"] == 2
    assert summary["committed_total"] == 100.0
    assert payload["meta"]["budget_control_committed_policy"]


def test_reports_dashboard_budget_control_uses_posted_real_and_pending_commitments_with_period_scope():
    c, db = make_client(role="admin")
    db.catalogo_partidas.rows.extend([
        {"codigo": "101", "nombre": "TERRENO", "grupo": "COSTOS DIRECTOS", "is_active": True},
        {"codigo": "103", "nombre": "URBANIZACION", "grupo": "COSTOS DIRECTOS", "is_active": True},
    ])
    db.budgets.rows.append({"id": "b103", "project_id": "p1", "partida_codigo": "103", "year": 2026, "month": 1, "amount_mxn": 1000})
    db.movements.rows.extend([
        {"id": "m-expense", "project_id": "p1", "partida_codigo": "103", "status": "posted", "is_deleted": False, "date": "2026-01-15T00:00:00+00:00", "amount_mxn": -400},
    ])
    db.purchase_orders.rows.extend([
        {
            "id": "po-pending-in-period",
            "project_id": "p1",
            "status": "pending_approval",
            "order_date": "2026-01-20T00:00:00+00:00",
            "currency": "MXN",
            "total": "100.00",
            "approved_amount_total": "40.00",
            "pending_amount": "60.00",
            "lines": [{"partida_codigo": "103", "line_total": "100.00"}],
        },
        {
            "id": "po-approved-out-of-period",
            "project_id": "p1",
            "status": "approved_for_payment",
            "order_date": "2026-02-15T00:00:00+00:00",
            "currency": "MXN",
            "total": "300.00",
            "pending_amount": "300.00",
            "lines": [{"partida_codigo": "103", "line_total": "300.00"}],
        },
    ])

    r = c.get('/api/reports/dashboard', params={"empresa_id": "c1", "project_id": "p1", "period": "month", "year": 2026, "month": 1})
    assert r.status_code == 200
    payload = r.json()

    row103 = next(x for x in payload["budget_control"]["rows"] if x["code"] == "103")
    assert row103["real"] == 400.0
    assert row103["committed"] == 60.0
    assert row103["available"] == 540.0
    assert row103["advance_pct"] == 40.0

    summary = payload["budget_control"]["summary"]
    assert summary["committed_total"] == 60.0
    assert payload["meta"]["budget_control_committed_policy"]


def test_reports_dashboard_defaults_to_all_period_and_accepts_todo_alias_for_selectors():
    c, _ = make_client(role="admin")

    r = c.get('/api/reports/dashboard', params={"empresa_id": "TODO", "project_id": "todo", "year": 2026})
    assert r.status_code == 200
    filtros = r.json()["filtros"]
    assert filtros["period"] == "all"
    assert filtros["empresa_id"] == "all"
    assert filtros["project_id"] == "all"


def test_reports_dashboard_invalid_period_combinations_return_422_not_500():
    c, _ = make_client(role="admin")

    r_month_missing = c.get('/api/reports/dashboard', params={"period": "month", "year": 2026})
    assert r_month_missing.status_code == 422

    r_quarter_with_month = c.get('/api/reports/dashboard', params={"period": "quarter", "year": 2026, "quarter": 1, "month": 1})
    assert r_quarter_with_month.status_code == 422

    r_all_with_month = c.get('/api/reports/dashboard', params={"period": "all", "year": 2026, "month": 1})
    assert r_all_with_month.status_code == 422


def test_reports_dashboard_project_out_of_scope_returns_403_not_500():
    c, _ = make_client(role="gerencia", empresa_id="c1")
    r = c.get('/api/reports/dashboard', params={"empresa_id": "c1", "project_id": "p2", "period": "all", "year": 2026})
    assert r.status_code == 403



def test_reports_dashboard_tolerates_null_amounts_and_missing_income_source():
    c, db = make_client(role="admin")

    db.projects.rows = [{"id": "p_null", "empresa_id": "c1", "name": "Proyecto Null"}]
    db.movements.rows = [{
        "id": "m-null",
        "project_id": "p_null",
        "partida_codigo": "101",
        "amount_mxn": None,
        "date": "2026-01-10T00:00:00+00:00",
        "status": "posted",
    }]
    db.inventory_items.rows = []

    r = c.get('/api/reports/dashboard', params={"empresa_id": "c1", "project_id": "p_null", "period": "month", "year": 2026, "month": 1})
    assert r.status_code == 200
    payload = r.json()
    assert payload["totals"]["ingreso_proyectado_405"] is None
    assert payload["meta"]["is_informative_missing"] is True
    assert payload["meta"]["can_compute_income_pct"] is False


def test_reports_export_data_accepts_all_aliases_and_validates_month():
    c, _ = make_client(role="admin")

    ok = c.get('/api/reports/export-data', params={"empresa_id": "TODAS", "project_id": "TODO", "year": 2026, "month": 1})
    assert ok.status_code == 200
    payload = ok.json()
    assert payload["filtros"]["empresa"] == "Todas"
    assert payload["filtros"]["proyecto"] == "Todos"

    bad_month = c.get('/api/reports/export-data', params={"empresa_id": "all", "project_id": "all", "year": 2026, "month": 13})
    assert bad_month.status_code == 422
