import os
from decimal import Decimal

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "qfinance_test")

from fastapi import HTTPException
from server import _normalize_dashboard_period_filters, _resolve_dashboard_income_base


def test_period_all_accepts_no_month_or_quarter():
    period, month, quarter = _normalize_dashboard_period_filters("all", None, None)
    assert period == "all"
    assert month is None
    assert quarter is None


def test_period_month_requires_month():
    try:
        _normalize_dashboard_period_filters("month", None, None)
        assert False, "expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail["code"] == "month_required"


def test_period_quarter_requires_quarter():
    try:
        _normalize_dashboard_period_filters("quarter", None, None)
        assert False, "expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail["code"] == "quarter_required"


def test_income_source_prefers_project_total():
    resolved = _resolve_dashboard_income_base(
        project_docs=[{"monto_total_proyecto": 5000, "manual_405": 1200}],
        inventory_items=[{"precio_total": 900}],
    )
    assert resolved["value"] == Decimal("5000.00")
    assert resolved["income_source"] == "project_total"


def test_income_source_manual_405_over_inventory_when_no_project_total():
    resolved = _resolve_dashboard_income_base(
        project_docs=[{"manual_405": 3000}],
        inventory_items=[{"precio_total": 900}],
    )
    assert resolved["value"] == Decimal("3000.00")
    assert resolved["income_source"] == "manual_405"
    assert resolved["income_source_available_flags"]["manual_405_inventory_coexistence"] is True


def test_income_source_inventory_when_only_inventory_available():
    resolved = _resolve_dashboard_income_base(
        project_docs=[{"name": "Proyecto sin monto"}],
        inventory_items=[{"precio_total": 900}],
    )
    assert resolved["value"] == Decimal("900.00")
    assert resolved["income_source"] == "inventory_total"


def test_income_source_none_when_no_valid_sources():
    resolved = _resolve_dashboard_income_base(
        project_docs=[{"name": "Proyecto sin monto"}],
        inventory_items=[],
    )
    assert resolved["value"] is None
    assert resolved["income_source"] == "none"
