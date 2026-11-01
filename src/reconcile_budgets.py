
import csv
from collections import defaultdict
from decimal import Decimal, ROUND_UP
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "generated"
DB_PATH = ROOT / "data" / "learning_pathway.duckdb"

FISCAL_YEAR = 2026
BUDGET_START = "2026-01-01"
BUDGET_END = "2026-12-31"
RESERVE_RATE = Decimal("0.10")
MINIMUM_RESERVE = Decimal("50000.00")

CHARGEABLE_STATUSES = {"COMPLETED", "IN_PROGRESS", "ENROLLED"}


def read_csv(filename):
    path = DATA_DIR / filename
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def write_csv(filename, rows):
    path = DATA_DIR / filename

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"))


def reconcile():
    employees = read_csv("employees.csv")
    courses = read_csv("courses.csv")
    enrollments = read_csv("enrollments.csv")
    budgets = read_csv("budgets.csv")

    employee_department = {
        row["employee_id"]: row["department"]
        for row in employees
    }

    course_cost = {
        row["course_id"]: money(row["cost_inr"])
        for row in courses
    }

    commitments = defaultdict(Decimal)

    for enrollment in enrollments:
        if enrollment["status"] not in CHARGEABLE_STATUSES:
            continue

        enrollment_date = enrollment["enrolled_at"][:10]

        # Only charge enrollments initiated during fiscal year 2026.
        if not (BUDGET_START <= enrollment_date <= BUDGET_END):
            continue

        department = employee_department[enrollment["employee_id"]]
        cost = course_cost[enrollment["course_id"]]

        commitments[department] += cost

    updated_budgets = []

    print("\nBUDGET RECONCILIATION")
    print("=" * 75)

    for budget in budgets:
        department = budget["department"]
        committed = money(commitments[department])

        reserve = max(
            MINIMUM_RESERVE,
            (committed * RESERVE_RATE).quantize(
                Decimal("1"),
                rounding=ROUND_UP
            )
        )

        new_budget = committed + reserve

        updated = dict(budget)
        updated["allocated_amount"] = f"{new_budget:.2f}"
        updated_budgets.append(updated)

        print(
            f"{department:15} "
            f"Commitments: ₹{committed:>12,.2f} | "
            f"Reserve: ₹{reserve:>10,.2f} | "
            f"Budget: ₹{new_budget:>12,.2f}"
        )

    # Update CSV only after all calculations succeed.
    write_csv("budgets.csv", updated_budgets)

    # Update the existing database in one transaction.
    connection = duckdb.connect(str(DB_PATH))

    try:
        connection.execute("BEGIN TRANSACTION")

        for budget in updated_budgets:
            connection.execute(
                """
                UPDATE budgets
                SET allocated_amount = ?
                WHERE budget_id = ?
                """,
                [
                    float(budget["allocated_amount"]),
                    budget["budget_id"]
                ]
            )

        # Confirm every budget row was updated.
        database_budgets = connection.execute(
            """
            SELECT department, allocated_amount
            FROM budgets
            WHERE fiscal_year = ?
            ORDER BY department
            """,
            [FISCAL_YEAR]
        ).fetchall()

        if len(database_budgets) != len(updated_budgets):
            raise RuntimeError("Budget row count mismatch after update.")

        connection.execute("COMMIT")

    except Exception:
        connection.execute("ROLLBACK")
        raise

    finally:
        connection.close()

    print("\nBUDGET RECONCILIATION COMPLETE")
    print(f"Updated budget CSV: {DATA_DIR / 'budgets.csv'}")
    print(f"Updated database: {DB_PATH}")


if __name__ == "__main__":
    reconcile()
