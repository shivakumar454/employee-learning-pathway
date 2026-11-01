
import csv
import duckdb
from pathlib import Path
from collections import defaultdict
from datetime import date

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "learning_pathway.duckdb"
REPORT_DIR = ROOT / "reports"


def allocate_budget():
    connection = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        today = date.today()

        # Get current-year department budgets.
        budgets = connection.execute("""
            SELECT
                department,
                allocated_amount,
                effective_from,
                effective_to
            FROM budgets
            WHERE fiscal_year = YEAR(CURRENT_DATE)
              AND CURRENT_DATE BETWEEN effective_from AND effective_to
        """).fetchall()

        # Calculate historical spending and active commitments.
        spending = connection.execute("""
            SELECT
                e.department,
                SUM(c.cost_inr) AS committed_spend
            FROM enrollments en
            JOIN employees e
                ON en.employee_id = e.employee_id
            JOIN courses c
                ON en.course_id = c.course_id
            JOIN budgets b
                ON e.department = b.department
                AND b.fiscal_year = YEAR(CURRENT_DATE)
            WHERE en.status IN (
                'ENROLLED',
                'IN_PROGRESS',
                'COMPLETED'
            )
              AND CAST(en.enrolled_at AS DATE)
                  BETWEEN b.effective_from AND b.effective_to
            GROUP BY e.department
        """).fetchall()

        spend_map = {
            department: float(amount)
            for department, amount in spending
        }

        remaining_budget = {}

        for department, allocated, start, end in budgets:
            allocated = float(allocated)
            spent = spend_map.get(department, 0.0)

            remaining_budget[department] = {
                "allocated": allocated,
                "spent": spent,
                "remaining": allocated - spent,
            }

        # Get all individually feasible recommendations.
        candidates = connection.execute("""
            SELECT
                d.employee_id,
                e.department,
                d.course_id,
                c.course_name,
                c.cost_inr,
                d.decision_score
            FROM recommendation_decisions d
            JOIN employees e
                ON d.employee_id = e.employee_id
            JOIN courses c
                ON d.course_id = c.course_id
            WHERE d.decision_status = 'RECOMMENDED'
            ORDER BY
                e.department,
                d.decision_score DESC,
                d.employee_id,
                d.course_id
        """).fetchall()

    finally:
        connection.close()

    # Group candidate courses by department.
    department_candidates = defaultdict(list)

    for row in candidates:
        employee_id, department, course_id, course_name, cost, score = row

        department_candidates[department].append({
            "employee_id": employee_id,
            "course_id": course_id,
            "course_name": course_name,
            "cost": float(cost),
            "score": float(score),
        })

    allocation_rows = []
    selected_by_department = defaultdict(int)
    selected_cost_by_department = defaultdict(float)

    # One primary course per employee.
    # Other recommendations remain alternative options.
    for department, candidates_for_department in (
        department_candidates.items()
    ):
        remaining = remaining_budget.get(
            department,
            {"allocated": 0, "spent": 0, "remaining": 0}
        )["remaining"]

        processed_employees = set()

        for candidate in candidates_for_department:
            employee_id = candidate["employee_id"]

            # Do not allocate multiple courses to one employee.
            if employee_id in processed_employees:
                continue

            processed_employees.add(employee_id)

            if candidate["cost"] <= remaining:
                remaining -= candidate["cost"]

                selected_by_department[department] += 1
                selected_cost_by_department[department] += (
                    candidate["cost"]
                )

                status = "ALLOCATED"
                reason = "Highest-ranked affordable course for employee."

            else:
                status = "NOT_ALLOCATED"
                reason = "Insufficient remaining department budget."

            allocation_rows.append({
                "employee_id": employee_id,
                "department": department,
                "course_id": candidate["course_id"],
                "course_name": candidate["course_name"],
                "course_cost_inr": candidate["cost"],
                "recommendation_score": candidate["score"],
                "allocation_status": status,
                "allocation_reason": reason,
            })

        remaining_budget[department]["remaining"] = remaining

    # Include departments with no recommendations too.
    summary_rows = []

    for department, budget in sorted(remaining_budget.items()):
        summary_rows.append({
            "department": department,
            "allocated_budget_inr": round(budget["allocated"], 2),
            "existing_spend_inr": round(budget["spent"], 2),
            "remaining_before_allocation_inr": round(
                budget["allocated"] - budget["spent"], 2
            ),
            "new_allocation_inr": round(
                selected_cost_by_department[department], 2
            ),
            "remaining_after_allocation_inr": round(
                budget["remaining"], 2
            ),
            "employees_allocated": selected_by_department[department],
        })

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    allocation_path = REPORT_DIR / "budget_allocation.csv"
    summary_path = REPORT_DIR / "department_budget_summary.csv"

    with allocation_path.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(allocation_rows[0].keys())
            if allocation_rows else [
                "employee_id", "department", "course_id",
                "course_name", "course_cost_inr",
                "recommendation_score", "allocation_status",
                "allocation_reason"
            ]
        )
        writer.writeheader()
        writer.writerows(allocation_rows)

    with summary_path.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "department",
                "allocated_budget_inr",
                "existing_spend_inr",
                "remaining_before_allocation_inr",
                "new_allocation_inr",
                "remaining_after_allocation_inr",
                "employees_allocated",
            ]
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    allocated_count = sum(selected_by_department.values())
    rejected_count = sum(
        1 for row in allocation_rows
        if row["allocation_status"] == "NOT_ALLOCATED"
    )

    print("\nLEARNING BUDGET ALLOCATION COMPLETE")
    print("=" * 50)
    print(f"Employees evaluated: {len(allocation_rows):,}")
    print(f"Courses allocated: {allocated_count:,}")
    print(f"Employees not allocated: {rejected_count:,}")

    print("\nDEPARTMENT BUDGET SUMMARY")

    for row in summary_rows:
        print(
            f"{row['department']}: "
            f"Allocated ₹{row['new_allocation_inr']:,.2f}, "
            f"Remaining ₹{row['remaining_after_allocation_inr']:,.2f}"
        )

    print(f"\nAllocation report: {allocation_path}")
    print(f"Budget summary: {summary_path}")


if __name__ == "__main__":
    allocate_budget()
