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
        self.unique_fields = []

    async def create_index(self, keys, unique=False):
        if unique:
            self.unique_fields.append(tuple(k for k, _ in keys))

    def _matches(self, row, query):
        for k, v in query.items():
            if isinstance(v, dict):
                if "$ne" in v and row.get(k) == v["$ne"]:
                    return False
                if "$in" in v and row.get(k) not in v["$in"]:
                    return False
            elif row.get(k) != v:
                return False
        return True

    async def find_one(self, query, projection=None):
        for row in self.rows:
            if self._matches(row, query):
                return dict(row)
        return None

    def find(self, query, projection=None):
        out = []
        for row in self.rows:
            if self._matches(row, query):
                out.append(dict(row))
        return FakeCursor(out)

    async def insert_one(self, doc):
        for unique_group in self.unique_fields:
            for row in self.rows:
                if all(row.get(field) == doc.get(field) for field in unique_group):
                    raise server.DuplicateKeyError("duplicate key")
        self.rows.append(dict(doc))

    async def update_one(self, query, update):
        for row in self.rows:
            if all(row.get(k) == v for k, v in query.items()):
                row.update(update.get("$set", {}))

    async def delete_one(self, query):
        self.rows = [r for r in self.rows if not self._matches(r, query)]

    async def delete_many(self, query):
        self.rows = [r for r in self.rows if not self._matches(r, query)]

    async def update_many(self, query, update):
        for row in self.rows:
            if self._matches(row, query):
                row.update(update.get("$set", {}))

    async def count_documents(self, query):
        return len([r for r in self.rows if self._matches(r, query)])


class FakeDB:
    def __init__(self):
        self.catalogo_partidas = FakeCollection([
            {"id": "cp1", "codigo": "401", "nombre": "Ingresos", "grupo": "ingresos", "is_active": True},
            {"id": "cp2", "codigo": "205", "nombre": "Egresos", "grupo": "obra", "is_active": True},
            {"id": "cp3", "codigo": "103", "nombre": "Obra 103", "grupo": "obra", "is_active": True},
            {"id": "cp4", "codigo": "301", "nombre": "Otros", "grupo": "obra", "is_active": True},
            {"id": "cp5", "codigo": "402", "nombre": "Ingreso 402", "grupo": "ingresos", "is_active": True},
            {"id": "cp6", "codigo": "403", "nombre": "Ingreso 403", "grupo": "ingresos", "is_active": True},
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
        self.budget_plans = FakeCollection([])
        self.purchase_orders = FakeCollection([])
        self.odoo_sync_purchase_orders = FakeCollection([])
        self.movements = FakeCollection([])
        self.authorizations = FakeCollection([])
        self.audit_logs = FakeCollection([])
        self.budget_requests = FakeCollection([])
        self.clients = FakeCollection([{"id": "cl1", "company_id": "e1", "project_id": "pr1", "nombre": "CLIENTE UNO", "inventory_item_id": "inv1", "saldo_restante": 500000.0}])
        self.inventory_items = FakeCollection([{"id": "inv1", "company_id": "e1", "project_id": "pr1", "lote_edificio": "L1", "manzana_departamento": "M3", "precio_total": 500000.0}])
        self.import_export_logs = FakeCollection([])
        self.empresas = FakeCollection([{"id": "e1", "nombre": "Empresa 1"}])

    def __getitem__(self, name):
        return getattr(self, name)


def client_for_role(role: str):
    server.db = FakeDB()

    async def fake_user():
        return {"user_id": "u1", "email": "u@test.com", "role": role, "empresa_id": "e1", "must_change_password": False}

    server.app.dependency_overrides[server.get_current_user] = fake_user
    return TestClient(server.app)


def movement_payload(partida_codigo: str, provider_id: str | None = "pv1", **extra):
    payload = {
        "project_id": "pr1",
        "partida_codigo": partida_codigo,
        "provider_id": provider_id,
        "date": "2026-01-10",
        "currency": "MXN",
        "amount_original": 1000,
        "exchange_rate": 1,
        "reference": f"REF-{partida_codigo}",
    }
    payload.update(extra)
    return payload


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


def test_captura_role_restricted_to_specific_budget_codes():
    client = client_for_role("captura")
    allowed = client.post("/api/movements", json=movement_payload("402", provider_id=None, client_id="cl1"))
    forbidden = client.post("/api/movements", json=movement_payload("401"))
    assert allowed.status_code == 200
    assert forbidden.status_code == 403


def test_requires_budget_ranges_only_100_199_and_200_299():
    client = client_for_role("admin")
    no_budget_4xx = client.post("/api/movements", json=movement_payload("402", provider_id=None, client_id="cl1"))
    no_budget_3xx = client.post("/api/movements", json=movement_payload("301"))
    needs_budget_1xx = client.post("/api/movements", json=movement_payload("103"))
    assert no_budget_4xx.status_code == 200
    assert no_budget_3xx.status_code == 200
    assert needs_budget_1xx.status_code == 422


def test_402_403_require_client_and_no_provider():
    client = client_for_role("admin")
    bad_provider = client.post("/api/movements", json=movement_payload("402", provider_id="pv1", client_id="cl1"))
    bad_client = client.post("/api/movements", json=movement_payload("403", provider_id=None))
    ok = client.post("/api/movements", json=movement_payload("403", provider_id=None, client_id="cl1"))
    assert bad_provider.status_code == 422
    assert bad_provider.json()["detail"]["code"] == "provider_not_allowed_for_abono"
    assert bad_client.status_code == 422
    assert bad_client.json()["detail"]["code"] == "client_required_for_partida_402_403"
    assert ok.status_code == 200
    assert ok.json()["movement"]["provider_id"] is None
    assert ok.json()["movement"]["reference"] == "L1-M3"


def test_finanzas_pending_budget_request_visible_to_admin_and_approvable():
    fake_db = FakeDB()
    server.db = fake_db

    async def finanzas_user():
        return {"user_id": "fin1", "email": "f@test.com", "role": "finanzas", "must_change_password": False}

    async def admin_user():
        return {"user_id": "adm1", "email": "a@test.com", "role": "admin", "must_change_password": False}

    server.app.dependency_overrides[server.get_current_user] = finanzas_user
    fin_client = TestClient(server.app)

    req_payload = {"project_id": "pr1", "partida_codigo": "205", "year": 2026, "month": 1, "amount_mxn": 5000, "notes": "n"}
    created = fin_client.post("/api/budget-requests", json=req_payload)
    assert created.status_code == 201
    request_id = created.json()["id"]

    server.app.dependency_overrides[server.get_current_user] = admin_user
    admin_client = TestClient(server.app)
    pending = admin_client.get("/api/budget-requests?status=pending")
    assert pending.status_code == 200
    pending_ids = [r["id"] for r in pending.json()]
    assert request_id in pending_ids

    resolved = admin_client.put(f"/api/budget-requests/{request_id}/resolve", json={"status": "approved", "notes": "ok"})
    assert resolved.status_code == 200

    pending_after = admin_client.get("/api/budget-requests?status=pending")
    assert pending_after.status_code == 200
    pending_after_ids = [r["id"] for r in pending_after.json()]
    assert request_id not in pending_after_ids


def test_admin_create_user_returns_201_and_duplicate_409():
    fake_db = FakeDB()
    server.db = fake_db

    async def admin_user():
        return {"user_id": "adm1", "email": "a@test.com", "role": "admin", "must_change_password": False}

    server.app.dependency_overrides[server.get_current_user] = admin_user
    client = TestClient(server.app)
    payload = {"email": "nuevo@test.com", "name": "nuevo", "role": "finanzas", "password": "Pass1234", "is_active": True}

    created = client.post("/api/admin/catalogs/usuarios", json=payload)
    assert created.status_code == 201
    assert created.json()["email"] == "nuevo@test.com"

    duplicate = client.post("/api/admin/catalogs/usuarios", json=payload)
    assert duplicate.status_code == 409


def test_general_users_endpoints_disabled():
    client = client_for_role("admin")
    res_get = client.get("/api/users")
    res_put = client.put("/api/users/u1", json={"role": "finanzas"})
    assert res_get.status_code == 404
    assert res_put.status_code == 404


def test_admin_users_list_role_patch_and_delete_safety():
    fake_db = FakeDB()
    fake_db.users.rows.append({
        "id": "u2",
        "email": "x@test.com",
        "name": "X",
        "role": "finanzas",
        "is_active": True,
        "password_hash": server.hash_password("Pass1234"),
    })
    server.db = fake_db

    async def admin_user():
        return {"user_id": "u1", "email": "u@test.com", "role": "admin", "must_change_password": False}

    server.app.dependency_overrides[server.get_current_user] = admin_user
    client = TestClient(server.app)

    listed = client.get("/api/admin/users")
    assert listed.status_code == 200
    assert len(listed.json()) >= 2

    changed = client.patch("/api/admin/users/u2/role", json={"role": "autorizador"})
    assert changed.status_code == 200
    assert changed.json()["role"] == "autorizador"

    self_delete = client.delete("/api/admin/users/u1")
    assert self_delete.status_code == 409

    removed = client.delete("/api/admin/users/u2")
    assert removed.status_code == 200


def test_audit_logs_endpoint_does_not_500_with_non_json_changes():
    fake_db = FakeDB()
    fake_db.audit_logs.rows.append({
        "id": "a1",
        "user_id": "u1",
        "user_email": "u@test.com",
        "user_role": "admin",
        "action": "TEST",
        "entity_type": "users",
        "entity_id": "u1",
        "changes": {"before": {"created_at": server.datetime.now(server.timezone.utc)}},
        "timestamp": server.datetime.now(server.timezone.utc),
    })
    server.db = fake_db

    async def admin_user():
        return {"user_id": "adm1", "email": "a@test.com", "role": "admin", "must_change_password": False}

    server.app.dependency_overrides[server.get_current_user] = admin_user
    client = TestClient(server.app)
    res = client.get("/api/audit-logs")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


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


def test_non_admin_cannot_admin_delete_movements():
    client = client_for_role("finanzas")
    res = client.request("DELETE", "/api/movements/m1", json={"reason": "cleanup"})
    assert res.status_code == 403


def test_soft_delete_hidden_from_movements_and_dashboard_and_audited():
    fake_db = FakeDB()
    fake_db.movements.rows.append({
        "id": "m1",
        "project_id": "pr1",
        "partida_codigo": "205",
        "provider_id": "pv1",
        "date": "2026-01-10T00:00:00+00:00",
        "currency": "MXN",
        "amount_original": 1000,
        "exchange_rate": 1,
        "amount_mxn": 1000,
        "reference": "R1",
        "status": "posted",
        "is_deleted": False,
        "is_active": True,
    })
    fake_db.budgets.rows.append({"id": "b1", "project_id": "pr1", "partida_codigo": "205", "year": 2026, "month": 1, "amount_mxn": 5000})
    server.db = fake_db

    async def admin_user():
        return {"user_id": "adm1", "email": "a@test.com", "role": "admin", "must_change_password": False}

    server.app.dependency_overrides[server.get_current_user] = admin_user
    client = TestClient(server.app)

    before_list = client.get("/api/movements")
    assert before_list.status_code == 200
    assert len(before_list.json()) == 1

    deleted = client.request("DELETE", "/api/movements/m1", json={"reason": "bad row"})
    assert deleted.status_code == 200

    after_list = client.get("/api/movements")
    assert after_list.status_code == 200
    assert after_list.json() == []

    dashboard = client.get("/api/dashboard/summary?year=2026&month=1")
    assert dashboard.status_code == 200
    assert dashboard.json()["totals"]["real"] == 0

    actions = [a["action"] for a in fake_db.audit_logs.rows]
    assert "ADMIN_SOFT_DELETE" in actions


def test_admin_patch_movement_creates_audit_with_reason():
    fake_db = FakeDB()
    fake_db.movements.rows.append({
        "id": "m1",
        "project_id": "pr1",
        "partida_codigo": "205",
        "provider_id": "pv1",
        "date": "2026-01-10T00:00:00+00:00",
        "currency": "MXN",
        "amount_original": 1000,
        "exchange_rate": 1,
        "amount_mxn": 1000,
        "reference": "R1",
        "status": "pending_approval",
        "is_deleted": False,
    })
    server.db = fake_db

    async def admin_user():
        return {"user_id": "adm1", "email": "a@test.com", "role": "admin", "must_change_password": False}

    server.app.dependency_overrides[server.get_current_user] = admin_user
    client = TestClient(server.app)

    updated = client.patch("/api/movements/m1", json={"description": "ajuste", "reason": "corrección"})
    assert updated.status_code == 200
    assert updated.json()["description"] == "ajuste"

    admin_updates = [a for a in fake_db.audit_logs.rows if a["action"] == "ADMIN_UPDATE" and a["entity_id"] == "m1"]
    assert len(admin_updates) == 1
    assert admin_updates[0]["changes"]["message"] == "corrección"


def test_create_client_valid_inventory_returns_201_and_persists():
    fake_db = FakeDB()
    fake_db.inventory_items.rows.append({
        "id": "inv2",
        "company_id": "e1",
        "project_id": "pr1",
        "lote_edificio": "L2",
        "manzana_departamento": "M1",
        "precio_total": 250000.0,
    })
    server.db = fake_db

    async def admin_user():
        return {"user_id": "adm1", "email": "a@test.com", "role": "admin", "must_change_password": False}

    server.app.dependency_overrides[server.get_current_user] = admin_user
    client = TestClient(server.app)

    payload = {
        "company_id": "e1",
        "project_id": "pr1",
        "nombre": "Cliente Nuevo",
        "telefono": "555123",
        "domicilio": "Calle 1",
        "inventory_item_id": "inv2",
    }
    created = client.post("/api/clients", json=payload)
    assert created.status_code == 201
    assert created.json()["inventory_item_id"] == "inv2"


def test_new_402_movement_recalculates_client_and_receipt_pdf_is_available():
    fake_db = FakeDB()
    server.db = fake_db

    async def admin_user():
        return {"user_id": "adm1", "email": "a@test.com", "role": "admin", "must_change_password": False}

    server.app.dependency_overrides[server.get_current_user] = admin_user
    client = TestClient(server.app)

    payload = movement_payload("402", provider_id=None, client_id="cl1", reference="")
    created = client.post("/api/movements", json=payload)
    assert created.status_code == 200

    movement = created.json()["movement"]
    assert movement["client_id"] == "cl1"

    client_doc = next(c for c in fake_db.clients.rows if c["id"] == "cl1")
    assert client_doc["abonos_total_mxn"] == 1000.0
    assert client_doc["saldo_restante"] == 499000.0

    receipt = client.get(f"/api/movements/{movement['id']}/receipt.pdf")
    assert receipt.status_code == 200
    assert receipt.headers["content-type"].startswith("application/pdf")
    assert receipt.content.startswith(b"%PDF")


def test_captura_ingresos_can_read_catalogs_create_client_but_cannot_modify_inventory():
    fake_db = FakeDB()
    fake_db.inventory_items.rows.append({
        "id": "inv2",
        "company_id": "e1",
        "project_id": "pr1",
        "lote_edificio": "L2",
        "manzana_departamento": "M9",
        "precio_total": 100000.0,
    })
    server.db = fake_db

    async def captura_ingresos_user():
        return {"user_id": "cap1", "email": "c@test.com", "role": "captura_ingresos", "empresa_id": "e1", "must_change_password": False}

    server.app.dependency_overrides[server.get_current_user] = captura_ingresos_user
    client = TestClient(server.app)

    list_clients = client.get("/api/clients")
    list_inventory = client.get("/api/inventory")
    list_providers = client.get("/api/providers")

    assert list_clients.status_code == 200
    assert list_inventory.status_code == 200
    assert list_providers.status_code == 200

    create_client = client.post("/api/clients", json={
        "company_id": "e1",
        "project_id": "pr1",
        "nombre": "NUEVO",
        "inventory_item_id": "inv2",
    })
    create_inventory = client.post("/api/inventory", json={
        "company_id": "e1",
        "project_id": "pr1",
        "m2_superficie": 100,
        "m2_construccion": 0,
        "lote_edificio": "L9",
        "manzana_departamento": "M9",
        "precio_m2_superficie": 1000,
        "precio_m2_construccion": 0,
        "descuento_bonificacion": 0,
    })

    assert create_client.status_code == 201
    assert create_inventory.status_code == 403


def test_receipt_pdf_legacy_abono_without_client_id_returns_200_pdf():
    fake_db = FakeDB()
    fake_db.movements.rows.append({
        "id": "m-legacy-r1",
        "project_id": "pr1",
        "partida_codigo": "402",
        "provider_id": None,
        "client_id": None,
        "customer_name": "CLIENTE UNO",
        "date": "2026-01-10T00:00:00+00:00",
        "currency": "MXN",
        "amount_original": 1000,
        "exchange_rate": 1,
        "amount_mxn": 1000,
        "reference": "L1-M3",
        "status": "posted",
    })
    server.db = fake_db

    async def admin_user():
        return {"user_id": "adm1", "email": "a@test.com", "role": "admin", "must_change_password": False}

    server.app.dependency_overrides[server.get_current_user] = admin_user
    client = TestClient(server.app)

    response = client.get("/api/movements/m-legacy-r1/receipt.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")


def test_receipt_id_with_suffix_is_resolved_without_422():
    fake_db = FakeDB()
    fake_db.movements.rows.append({
        "id": "11382",
        "project_id": "pr1",
        "partida_codigo": "402",
        "provider_id": None,
        "client_id": "cl1",
        "customer_name": "CLIENTE UNO",
        "date": "2026-01-10T00:00:00+00:00",
        "currency": "MXN",
        "amount_original": 1000,
        "exchange_rate": 1,
        "amount_mxn": 1000,
        "reference": "L1-M3",
        "status": "posted",
    })
    server.db = fake_db

    async def admin_user():
        return {"user_id": "adm1", "email": "a@test.com", "role": "admin", "must_change_password": False}

    server.app.dependency_overrides[server.get_current_user] = admin_user
    client = TestClient(server.app)

    response = client.get("/api/movements/11382_5b533/receipt.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")


def test_captura_can_get_and_create_clients_but_delete_is_forbidden():
    fake_db = FakeDB()
    fake_db.inventory_items.rows.append({
        "id": "inv2",
        "company_id": "e1",
        "project_id": "pr1",
        "lote_edificio": "L2",
        "manzana_departamento": "M5",
        "precio_total": 120000.0,
    })
    server.db = fake_db

    async def captura_user():
        return {"user_id": "cap1", "email": "c@test.com", "role": "captura", "empresa_id": "e1", "must_change_password": False}

    server.app.dependency_overrides[server.get_current_user] = captura_user
    client = TestClient(server.app)

    listed = client.get("/api/clients")
    assert listed.status_code == 200

    created = client.post("/api/clients", json={
        "company_id": "e1",
        "project_id": "pr1",
        "nombre": "CLIENTE CAPTURA",
        "inventory_item_id": "inv2",
    })
    assert created.status_code == 201

    forbidden = client.delete(f"/api/clients/{created.json()['id']}")
    assert forbidden.status_code == 403


def test_finanzas_can_get_and_create_clients_but_delete_is_forbidden():
    fake_db = FakeDB()
    fake_db.inventory_items.rows.append({
        "id": "inv2",
        "company_id": "e1",
        "project_id": "pr1",
        "lote_edificio": "L2",
        "manzana_departamento": "M6",
        "precio_total": 125000.0,
    })
    server.db = fake_db

    async def finanzas_user():
        return {"user_id": "fin1", "email": "f@test.com", "role": "finanzas", "empresa_id": "e1", "must_change_password": False}

    server.app.dependency_overrides[server.get_current_user] = finanzas_user
    client = TestClient(server.app)

    listed = client.get("/api/clients")
    assert listed.status_code == 200

    created = client.post("/api/clients", json={
        "company_id": "e1",
        "project_id": "pr1",
        "nombre": "CLIENTE FINANZAS",
        "inventory_item_id": "inv2",
    })
    assert created.status_code == 201

    forbidden = client.delete(f"/api/clients/{created.json()['id']}")
    assert forbidden.status_code == 403


def test_admin_can_delete_client():
    fake_db = FakeDB()
    fake_db.inventory_items.rows.append({
        "id": "inv2",
        "company_id": "e1",
        "project_id": "pr1",
        "lote_edificio": "L2",
        "manzana_departamento": "M7",
        "precio_total": 150000.0,
    })
    fake_db.clients.rows.append({
        "id": "cl2",
        "company_id": "e1",
        "project_id": "pr1",
        "nombre": "BORRABLE",
        "inventory_item_id": "inv2",
        "saldo_restante": 150000.0,
    })
    server.db = fake_db

    async def admin_user():
        return {"user_id": "adm1", "email": "a@test.com", "role": "admin", "empresa_id": "e1", "must_change_password": False}

    server.app.dependency_overrides[server.get_current_user] = admin_user
    client = TestClient(server.app)

    deleted = client.delete("/api/clients/cl2")
    assert deleted.status_code == 200


def test_captura_ingresos_with_null_empresa_id_can_read_catalogs_and_create_client():
    fake_db = FakeDB()
    fake_db.inventory_items.rows.append({
        "id": "inv3",
        "company_id": "e1",
        "project_id": "pr1",
        "lote_edificio": "L3",
        "manzana_departamento": "M3",
        "precio_total": 180000.0,
    })
    server.db = fake_db

    async def captura_ingresos_user():
        return {
            "user_id": "cap2",
            "email": "ci@test.com",
            "role": "captura_ingresos",
            "empresa_id": None,
            "company_id": "e1",
            "must_change_password": False,
        }

    server.app.dependency_overrides[server.get_current_user] = captura_ingresos_user
    client = TestClient(server.app)

    assert client.get("/api/clients").status_code == 200
    assert client.get("/api/inventory").status_code == 200
    assert client.get("/api/inventory/summary").status_code == 200
    assert client.get("/api/providers").status_code == 200

    created = client.post("/api/clients", json={
        "company_id": "e1",
        "project_id": "pr1",
        "nombre": "CLIENTE CI",
        "inventory_item_id": "inv3",
    })
    assert created.status_code == 201


def test_captura_ingresos_receipt_scope_and_delete_forbidden():
    fake_db = FakeDB()
    fake_db.projects.rows.append({"id": "pr2", "code": "P2", "name": "Proyecto 2", "empresa_id": "e2", "is_active": True})
    fake_db.empresas.rows.append({"id": "e2", "nombre": "Empresa 2"})
    fake_db.movements.rows.append({
        "id": "m-in",
        "project_id": "pr1",
        "partida_codigo": "402",
        "client_id": "cl1",
        "date": "2026-01-10T00:00:00+00:00",
        "currency": "MXN",
        "amount_original": 1000,
        "exchange_rate": 1,
        "amount_mxn": 1000,
        "reference": "L1-M3",
        "status": "posted",
    })
    fake_db.movements.rows.append({
        "id": "m-out",
        "project_id": "pr2",
        "partida_codigo": "402",
        "client_id": None,
        "date": "2026-01-10T00:00:00+00:00",
        "currency": "MXN",
        "amount_original": 1000,
        "exchange_rate": 1,
        "amount_mxn": 1000,
        "reference": "X",
        "status": "posted",
    })
    server.db = fake_db

    async def captura_ingresos_user():
        return {
            "user_id": "cap2",
            "email": "ci@test.com",
            "role": "captura_ingresos",
            "empresa_id": None,
            "company_id": "e1",
            "must_change_password": False,
        }

    server.app.dependency_overrides[server.get_current_user] = captura_ingresos_user
    client = TestClient(server.app)

    assert client.get("/api/movements/m-in/receipt.pdf").status_code == 200
    assert client.get("/api/movements/m-out/receipt.pdf").status_code == 403
    assert client.delete("/api/clients/cl1").status_code == 403
    assert client.delete("/api/inventory/inv1").status_code == 403


def test_login_operativo_sin_empresas_devuelve_422_empresa_required():
    fake_db = FakeDB()
    fake_db.users.rows = [{
        "id": "op1",
        "email": "op@test.com",
        "name": "Operativo",
        "role": "captura_ingresos",
        "is_active": True,
        "must_change_password": False,
        "password_hash": server.hash_password("Pass1234"),
        "empresa_ids": [],
    }]
    server.db = fake_db
    server.app.dependency_overrides = {}
    client = TestClient(server.app)

    res = client.post("/api/auth/login", json={"email": "op@test.com", "password": "Pass1234"})
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "empresa_required"


def test_login_operativo_con_empresas_requiere_select_company_para_catalogos():
    fake_db = FakeDB()
    fake_db.users.rows = [{
        "id": "op2",
        "email": "op2@test.com",
        "name": "Operativo 2",
        "role": "captura_ingresos",
        "is_active": True,
        "must_change_password": False,
        "password_hash": server.hash_password("Pass1234"),
        "empresa_ids": ["e1", "e2"],
    }]
    fake_db.empresas.rows.append({"id": "e2", "nombre": "Empresa 2"})
    server.db = fake_db
    server.app.dependency_overrides = {}
    client = TestClient(server.app)

    login = client.post("/api/auth/login", json={"email": "op2@test.com", "password": "Pass1234"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    clients = client.get("/api/clients", headers={"Authorization": f"Bearer {token}"})
    assert clients.status_code == 422
    assert clients.json()["detail"]["code"] == "empresa_not_selected"


def test_select_company_valido_emite_token_con_empresa():
    fake_db = FakeDB()
    fake_db.users.rows = [{
        "id": "op3",
        "email": "op3@test.com",
        "name": "Operativo 3",
        "role": "captura_ingresos",
        "is_active": True,
        "must_change_password": False,
        "password_hash": server.hash_password("Pass1234"),
        "empresa_ids": ["e1", "e2"],
    }]
    fake_db.empresas.rows.append({"id": "e2", "nombre": "Empresa 2"})
    fake_db.inventory_items.rows.append({"id": "inv-e2", "company_id": "e2", "project_id": "pr1", "lote_edificio": "L9", "manzana_departamento": "M9", "precio_total": 99999})
    server.db = fake_db
    server.app.dependency_overrides = {}
    client = TestClient(server.app)

    login = client.post("/api/auth/login", json={"email": "op3@test.com", "password": "Pass1234"})
    token = login.json()["access_token"]

    selected = client.post("/api/auth/select-company", json={"empresa_id": "e1"}, headers={"Authorization": f"Bearer {token}"})
    assert selected.status_code == 200
    selected_token = selected.json()["access_token"]

    clients = client.get("/api/clients", headers={"Authorization": f"Bearer {selected_token}"})
    inventory = client.get("/api/inventory", headers={"Authorization": f"Bearer {selected_token}"})
    summary = client.get("/api/inventory/summary", headers={"Authorization": f"Bearer {selected_token}"})
    assert clients.status_code == 200
    assert inventory.status_code == 200
    assert summary.status_code == 200
    assert all(it.get("company_id") == "e1" for it in inventory.json())


def test_select_company_no_permitido_devuelve_403():
    fake_db = FakeDB()
    fake_db.users.rows = [{
        "id": "op4",
        "email": "op4@test.com",
        "name": "Operativo 4",
        "role": "captura_ingresos",
        "is_active": True,
        "must_change_password": False,
        "password_hash": server.hash_password("Pass1234"),
        "empresa_ids": ["e1"],
    }]
    server.db = fake_db
    server.app.dependency_overrides = {}
    client = TestClient(server.app)

    login = client.post("/api/auth/login", json={"email": "op4@test.com", "password": "Pass1234"})
    token = login.json()["access_token"]
    bad = client.post("/api/auth/select-company", json={"empresa_id": "e2"}, headers={"Authorization": f"Bearer {token}"})
    assert bad.status_code == 403


def test_admin_puede_operar_sin_select_company():
    fake_db = FakeDB()
    fake_db.users.rows = [{
        "id": "adm2",
        "email": "adm@test.com",
        "name": "Admin",
        "role": "admin",
        "is_active": True,
        "must_change_password": False,
        "password_hash": server.hash_password("Pass1234"),
        "empresa_ids": [],
    }]
    server.db = fake_db
    server.app.dependency_overrides = {}
    client = TestClient(server.app)

    login = client.post("/api/auth/login", json={"email": "adm@test.com", "password": "Pass1234"})
    token = login.json()["access_token"]
    clients = client.get("/api/clients", headers={"Authorization": f"Bearer {token}"})
    assert clients.status_code == 200
