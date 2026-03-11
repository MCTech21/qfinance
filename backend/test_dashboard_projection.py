import os
from decimal import Decimal
from datetime import datetime, date, timezone

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "qfinance_test")

from server import _build_financial_projection, normalize_utc_datetime  # noqa: E402


def test_build_financial_projection_generates_rows_and_funding():
    projection = _build_financial_projection(
        period="month",
        selected_year=2026,
        selected_month=1,
        selected_quarter=None,
        ingreso_405_total=Decimal("1000"),
        movement_rows=[
            {"date": "2025-12-15", "partida_codigo": "402", "amount_mxn": 200},
            {"date": "2026-01-10", "partida_codigo": "402", "amount_mxn": 100},
            {"date": "2026-01-11", "partida_codigo": "101", "amount_mxn": 300},
        ],
        budget_control_rows=[{"available": 600}],
        purchase_orders=[
            {"pending_amount": 100, "planned_date": "2026-02-15", "status": "approved_for_payment"},
        ],
        inventory_items=[],
        budget_plan_rows=[],
    )

    assert projection["metadata"]["periodicity"] == "month"
    assert projection["rows"]
    assert projection["kpis"]["projected_income_remaining"] == 700.0
    assert projection["kpis"]["pending_expense_remaining"] == 600.0
    assert projection["kpis"]["max_funding_need"] >= 0
    assert projection["source_details"]["income_405_policy"] == "sum(inventory_items.precio_total)"


def test_build_financial_projection_uses_base_scenario_without_dates():
    projection = _build_financial_projection(
        period="quarter",
        selected_year=2026,
        selected_month=None,
        selected_quarter=2,
        ingreso_405_total=Decimal("1200"),
        movement_rows=[],
        budget_control_rows=[{"available": 300}],
        purchase_orders=[{"pending_amount": 200}],
        inventory_items=[{"precio_total": 1200}],
        budget_plan_rows=[],
    )

    assert len(projection["rows"]) == 3
    assert any("uniformemente" in assumption.lower() for assumption in projection["assumptions"])
    assert projection["rows"][0]["committed_expense"] == 200.0


def test_normalize_utc_datetime_supports_naive_aware_and_date():
    naive = normalize_utc_datetime(datetime(2026, 1, 1, 8, 0, 0))
    aware = normalize_utc_datetime(datetime(2026, 1, 1, 8, 0, 0, tzinfo=timezone.utc))
    only_date = normalize_utc_datetime(date(2026, 1, 1))

    assert naive.tzinfo is not None
    assert aware.tzinfo is not None
    assert only_date.tzinfo is not None
    assert naive.utcoffset().total_seconds() == 0
    assert aware.utcoffset().total_seconds() == 0
    assert only_date.hour == 0
