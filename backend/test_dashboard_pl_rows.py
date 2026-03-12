import os
from decimal import Decimal

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "qfinance_test")

from server import _build_pl_rows


def _rows_by_code(rows):
    return {row["code"]: row for row in rows}


def test_pl_includes_income_row_first_and_pending_formula():
    rows = _build_pl_rows(
        {
            "405": {"presupuesto": Decimal("1000"), "ejecutado": Decimal("200")},
            "101": {"presupuesto": Decimal("100"), "ejecutado": Decimal("40")},
        },
        {},
        Decimal("1000"),
    )
    assert rows[0]["code"] == "405"
    assert rows[0]["row_type"] == "income"
    assert rows[0]["budget"] == 1000.0
    assert rows[0]["real"] == 200.0
    assert rows[0]["remaining"] == 800.0
    assert rows[0]["income_pct"] == 100.0


def test_subtotals_follow_budgetary_control_math_and_budget_pct():
    by_partida = {
        "405": {"presupuesto": Decimal("1000"), "ejecutado": Decimal("300")},
        "101": {"presupuesto": Decimal("100"), "ejecutado": Decimal("30")},
        "102": {"presupuesto": Decimal("50"), "ejecutado": Decimal("20")},
        "201": {"presupuesto": Decimal("40"), "ejecutado": Decimal("10")},
        "301": {"presupuesto": Decimal("10"), "ejecutado": Decimal("2")},
    }
    rows = _rows_by_code(_build_pl_rows(by_partida, {}, Decimal("1000")))

    assert rows["SUBTOTAL_GROSS"]["budget"] == 850.0
    assert rows["SUBTOTAL_GROSS"]["real"] == 50.0
    assert rows["SUBTOTAL_GROSS"]["remaining"] == 800.0
    assert rows["SUBTOTAL_GROSS"]["income_pct"] == 85.0

    assert rows["SUBTOTAL_OPERATING"]["budget"] == 810.0
    assert rows["SUBTOTAL_OPERATING"]["real"] == 60.0
    assert rows["SUBTOTAL_OPERATING"]["remaining"] == 750.0
    assert rows["SUBTOTAL_OPERATING"]["income_pct"] == 81.0

    assert rows["SUBTOTAL_PRE_TAX"]["budget"] == 800.0
    assert rows["SUBTOTAL_PRE_TAX"]["real"] == 62.0
    assert rows["SUBTOTAL_PRE_TAX"]["remaining"] == 738.0
    assert rows["SUBTOTAL_PRE_TAX"]["income_pct"] == 80.0


def test_expense_partida_pct_uses_budget_not_real():
    rows = _rows_by_code(
        _build_pl_rows(
            {
                "405": {"presupuesto": Decimal("1000"), "ejecutado": Decimal("0")},
                "101": {"presupuesto": Decimal("100"), "ejecutado": Decimal("80")},
            },
            {},
            Decimal("1000"),
        )
    )
    assert rows["101"]["income_pct"] == 10.0


def test_subtotals_exclude_4xx_codes_from_expense_real_and_budget():
    rows = _rows_by_code(
        _build_pl_rows(
            {
                "405": {"presupuesto": Decimal("1000"), "ejecutado": Decimal("300")},
                "101": {"presupuesto": Decimal("100"), "ejecutado": Decimal("40")},
                "402": {"presupuesto": Decimal("999"), "ejecutado": Decimal("999")},
            },
            {},
            Decimal("1000"),
        )
    )
    assert rows["SUBTOTAL_GROSS"]["budget"] == 900.0
    assert rows["SUBTOTAL_GROSS"]["real"] == 40.0


def test_subtotal_labels_are_executive_friendly():
    rows = _rows_by_code(_build_pl_rows({}, {}, Decimal("0")))
    assert rows["SUBTOTAL_GROSS"]["name"] == "Utilidad Bruta"
    assert rows["SUBTOTAL_OPERATING"]["name"] == "Utilidad Operativa"
    assert rows["SUBTOTAL_PRE_TAX"]["name"] == "Utilidad Antes de Impuestos"
