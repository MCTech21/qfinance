import backend.server as server
from tests.test_required_scope import make_client


def _dashboard(client, **params):
    base = {"empresa_id": "c1", "project_id": "p1", "period": "month", "year": 2026, "month": 1}
    base.update(params)
    clean = {k: v for k, v in base.items() if v is not None}
    return client.get('/api/reports/dashboard', params=clean)


def _movement(code, amount, mid, date="2026-01-10T00:00:00+00:00"):
    return {
        "id": mid,
        "project_id": "p1",
        "partida_codigo": code,
        "status": "posted",
        "is_deleted": False,
        "date": date,
        "amount_mxn": amount,
    }


def _plan(code, total=0, monthly=None, annual=None):
    return {
        "id": f"bp-{code}",
        "project_id": "p1",
        "partida_codigo": code,
        "total_amount": total,
        "annual_breakdown": annual or {},
        "monthly_breakdown": monthly or {},
        "approval_status": "approved",
    }


def test_totals_exclude_income_400_499_and_include_100_399():
    c, db = make_client(role="admin")
    db.budget_plans.rows.extend([
        _plan("101", total=100, monthly={"2026-01": 100}),
        _plan("201", total=200, monthly={"2026-01": 200}),
        _plan("301", total=300, monthly={"2026-01": 300}),
        _plan("401", total=400, monthly={"2026-01": 400}),
        _plan("402", total=500, monthly={"2026-01": 500}),
        _plan("403", total=600, monthly={"2026-01": 600}),
        _plan("404", total=700, monthly={"2026-01": 700}),
        _plan("405", total=800, monthly={"2026-01": 800}),
    ])
    db.movements.rows.extend([
        _movement("101", 10, "m101"),
        _movement("201", 20, "m201"),
        _movement("301", 30, "m301"),
        _movement("401", 40, "m401"),
        _movement("402", 50, "m402"),
        _movement("403", 60, "m403"),
        _movement("404", 70, "m404"),
        _movement("405", 80, "m405"),
    ])

    payload = _dashboard(c).json()
    assert payload["shared_kpis"]["presupuesto_total"] == 600.0
    assert payload["shared_kpis"]["real_ejecutado"] == 60.0


def test_is_income_partida_code_only_402_403():
    assert server._is_income_partida_code("402") is True
    assert server._is_income_partida_code("403") is True
    assert server._is_income_partida_code("404") is False
    assert server._is_income_partida_code("401") is False
    assert server._is_income_partida_code("405") is False


def test_shared_kpis_sales_progress_and_none_without_405_budget():
    c, db = make_client(role="admin")
    db.movements.rows.extend([
        _movement("402", 300, "m402"),
        _movement("403", 200, "m403"),
    ])

    payload_no_meta = _dashboard(c).json()
    assert payload_no_meta["shared_kpis"]["real_ventas_402_403"] == 500.0
    assert payload_no_meta["shared_kpis"]["meta_ventas_405"] is None
    assert payload_no_meta["shared_kpis"]["avance_ventas_pct"] is None

    db.budget_plans.rows.append(_plan("405", total=1000, monthly={"2026-01": 1000}))
    payload_meta = _dashboard(c).json()
    assert payload_meta["shared_kpis"]["real_ventas_402_403"] == 500.0
    assert payload_meta["shared_kpis"]["meta_ventas_405"] == 1000.0
    assert payload_meta["shared_kpis"]["avance_ventas_pct"] == 50.0


def test_sales_progress_allows_above_100_and_projection_excludes_404_realized_income():
    c, db = make_client(role="admin")
    db.budget_plans.rows.append(_plan("405", total=100, monthly={"2026-01": 100}))
    db.movements.rows.extend([
        _movement("402", 120, "m402"),
        _movement("403", 30, "m403"),
        _movement("404", 999, "m404"),
    ])

    response = _dashboard(c)
    assert response.status_code == 200
    payload = response.json()
    assert payload["shared_kpis"]["avance_ventas_pct"] > 100
    assert payload["financial_projection"]["kpis"]["projected_income_remaining"] == 0.0
    assert payload["financial_projection"]["source_details"]["projected_income_policy"] == "405_presupuesto - realizados_402_403"
    assert payload["financial_projection"]["source_details"]["income_405_policy"] == "budget_plan partida 405"
