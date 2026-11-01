
import duckdb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "learning_pathway.duckdb"

connection = duckdb.connect(str(DB_PATH), read_only=True)

try:
    print("\n1. DEPARTMENT BUDGETS")
    print("=" * 65)

    budgets = connection.execute("""
        SELECT
            department,
            allocated_amount,
            fiscal_year,
            effective_from,
            effective_to
        FROM budgets
        ORDER BY department
    """).fetchdf()

    print(budgets.to_string(index=False))

    print("\n2. EXISTING COURSE SPENDING")
    print("=" * 65)

    spending = connection.execute("""
        SELECT
            e.department,
            COUNT(*) AS enrollment_count,
            SUM(c.cost_inr) AS total_course_cost,

            SUM(
                CASE
                    WHEN en.status = 'COMPLETED'
                    THEN c.cost_inr
                    ELSE 0
                END
            ) AS completed_course_cost,

            SUM(
                CASE
                    WHEN en.status IN ('ENROLLED', 'IN_PROGRESS')
                    THEN c.cost_inr
                    ELSE 0
                END
            ) AS active_commitments

        FROM enrollments en
        JOIN employees e
            ON en.employee_id = e.employee_id
        JOIN courses c
            ON en.course_id = c.course_id

        GROUP BY e.department
        ORDER BY e.department
    """).fetchdf()

    print(spending.to_string(index=False))

    print("\n3. COURSE AVAILABILITY")
    print("=" * 65)

    availability = connection.execute("""
        SELECT
            course_status,
            COUNT(*) AS total_courses,
            SUM(
                CASE
                    WHEN available_from <= CURRENT_DATE + INTERVAL '90 days'
                     AND available_to >= CURRENT_DATE
                    THEN 1 ELSE 0
                END
            ) AS available_in_next_90_days
        FROM courses
        GROUP BY course_status
        ORDER BY course_status
    """).fetchdf()

    print(availability.to_string(index=False))

    print("\n4. RECOMMENDATION STATUS")
    print("=" * 65)

    status = connection.execute("""
        SELECT
            decision_status,
            COUNT(*) AS total
        FROM recommendation_decisions
        GROUP BY decision_status
    """).fetchdf()

    print(status.to_string(index=False))

    print("\n5. CURRENT BUDGET VS SPENDING")
    print("=" * 65)

    comparison = connection.execute("""
        SELECT
            b.department,
            b.allocated_amount,
            COALESCE(
                SUM(
                    CASE
                        WHEN en.status IN (
                            'ENROLLED',
                            'IN_PROGRESS'
                        )
                        THEN c.cost_inr
                        ELSE 0
                    END
                ),
                0
            ) AS active_commitments

        FROM budgets b

        LEFT JOIN employees e
            ON b.department = e.department

        LEFT JOIN enrollments en
            ON e.employee_id = en.employee_id

        LEFT JOIN courses c
            ON en.course_id = c.course_id

        WHERE b.fiscal_year = 2026

        GROUP BY b.department, b.allocated_amount
        ORDER BY b.department
    """).fetchdf()

    print(comparison.to_string(index=False))

finally:
    connection.close()
