from tests.test_required_scope import make_client


def _dashboard(client, **params):
    base = {"empresa_id": "c1", "project_id": "p1", "period": "month", "year": 2026, "month": 1}
    base.update(params)
    clean = {k: v for k, v in base.items() if v is not None}
    return client.get('/api/reports/dashboard', params=clean)


def _plan_405(total=1200, annual=None, monthly=None):
    return {
        "id": "bp405",
        "project_id": "p1",
        "partida_codigo": "405",
        "total_amount": total,
        "annual_breakdown": annual or {},
        "monthly_breakdown": monthly or {},
        "approval_status": "approved",
    }


def _movement(code, amount, mid):
    return {
        "id": mid,
        "project_id": "p1",
        "partida_codigo": code,
        "status": "posted",
        "is_deleted": False,
        "date": "2026-01-10T00:00:00+00:00",
        "amount_mxn": amount,
    }


def _detail_405(payload):
    return next((x for x in payload["by_partida"] if x["partida_codigo"] == "405"), None)


def test_dashboard_without_plan_405_returns_200_and_income_none():
    c, db = make_client(role="admin")
    db.inventory_items.rows = []

    r = _dashboard(c)
    assert r.status_code == 200
    payload = r.json()
    assert payload["totals"]["ingreso_proyectado_405"] is None
    assert payload["meta"]["can_compute_income_pct"] is False


def test_income_405_budget_from_monthly_breakdown_for_selected_month():
    c, db = make_client(role="admin")
    db.inventory_items.rows = []
    db.budget_plans.rows.append(_plan_405(total=5000, monthly={"2026-01": 3456, "2026-02": 9999}))

    r = _dashboard(c)
    assert r.status_code == 200
    assert r.json()["totals"]["ingreso_proyectado_405"] == 3456.0


def test_income_405_budget_from_annual_breakdown_for_year_period():
    c, db = make_client(role="admin")
    db.inventory_items.rows = []
    db.budget_plans.rows.append(_plan_405(total=5000, annual={"2026": 7777}))

    r = _dashboard(c, period="year", month=None)
    assert r.status_code == 200
    assert r.json()["totals"]["ingreso_proyectado_405"] == 7777.0


def test_movements_402_are_accumulated_as_real_for_405():
    c, db = make_client(role="admin")
    db.inventory_items.rows = []
    db.budget_plans.rows.append(_plan_405(total=1000, monthly={"2026-01": 1000}))
    db.movements.rows.append(_movement("402", 250, "m402"))

    r = _dashboard(c)
    detail_405 = _detail_405(r.json())
    assert detail_405["presupuesto"] == 1000.0
    assert detail_405["ejecutado"] == 250.0


def test_movements_403_are_accumulated_as_real_for_405():
    c, db = make_client(role="admin")
    db.inventory_items.rows = []
    db.budget_plans.rows.append(_plan_405(total=1000, monthly={"2026-01": 1000}))
    db.movements.rows.append(_movement("403", 125, "m403"))

    r = _dashboard(c)
    detail_405 = _detail_405(r.json())
    assert detail_405["ejecutado"] == 125.0


def test_movements_401_and_404_do_not_accumulate_into_405_real():
    c, db = make_client(role="admin")
    db.inventory_items.rows = []
    db.budget_plans.rows.append(_plan_405(total=1000, monthly={"2026-01": 1000}))
    db.movements.rows.extend([
        _movement("401", 300, "m401"),
        _movement("404", 700, "m404"),
    ])

    r = _dashboard(c)
    detail_405 = _detail_405(r.json())
    assert detail_405["ejecutado"] == 0.0


def test_budget_control_rows_exclude_income_codes_401_to_405():
    c, db = make_client(role="admin")
    db.inventory_items.rows = []
    db.budget_plans.rows.append(_plan_405(total=1000, monthly={"2026-01": 1000}))
    db.movements.rows.extend([
        _movement("401", 10, "m401"),
        _movement("402", 20, "m402"),
        _movement("403", 30, "m403"),
        _movement("404", 40, "m404"),
        _movement("405", 50, "m405"),
    ])

    r = _dashboard(c)
    rows = r.json()["budget_control"]["rows"]
    codes = {x["code"] for x in rows}
    assert all(code not in codes for code in {"401", "402", "403", "404", "405"})


def test_dashboard_without_plan_405_and_without_402_403_movements_returns_200():
    c, db = make_client(role="admin")
    db.inventory_items.rows = []
    db.movements.rows = []
    db.budget_plans.rows = []

    r = _dashboard(c)
    assert r.status_code == 200
    payload = r.json()
    assert payload["totals"]["ingreso_proyectado_405"] is None


def test_by_partida_405_budget_equals_ingreso_405_budget_when_plan_exists():
    c, db = make_client(role="admin")
    db.inventory_items.rows = []
    db.budget_plans.rows.append(_plan_405(total=1500, monthly={"2026-01": 1500}))

    r = _dashboard(c)
    detail_405 = _detail_405(r.json())
    assert detail_405["presupuesto"] == 1500.0


def test_by_partida_405_ejecutado_is_independent_from_presupuesto():
    c, db = make_client(role="admin")
    db.inventory_items.rows = []
    db.budget_plans.rows.append(_plan_405(total=1500, monthly={"2026-01": 1500}))
    db.movements.rows.append(_movement("402", 200, "m402"))

    r = _dashboard(c)
    detail_405 = _detail_405(r.json())
    assert detail_405["presupuesto"] == 1500.0
    assert detail_405["ejecutado"] == 200.0
    assert detail_405["ejecutado"] != detail_405["presupuesto"]
