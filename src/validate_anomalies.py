
import csv
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "learning_pathway.duckdb"
DATA_DIR = ROOT / "data" / "generated"

EXPECTED = {
    "ANOM-001": "PREREQUISITE_VIOLATION",
    "ANOM-002": "BUDGET_EXCEEDED",
    "ANOM-003": "DUPLICATE_COMPLETION",
    "ANOM-004": "SKILL_GAP_WITHOUT_REASSESSMENT",
    "ANOM-005": "COURSE_UNAVAILABLE",
}


def read_csv(filename):
    with (DATA_DIR / filename).open(
        "r", newline="", encoding="utf-8"
    ) as file:
        return list(csv.DictReader(file))


def validate():
    scenarios = read_csv("anomaly_scenarios.csv")
    labels = read_csv("ground_truth.csv")

    connection = duckdb.connect(str(DB_PATH), read_only=True)

    checks = []

    try:
        scenario_ids = {row["scenario_id"] for row in scenarios}
        label_ids = {row["scenario_id"] for row in labels}

        checks.append((
            "Exactly five scenarios generated",
            len(scenarios) == 5
        ))

        checks.append((
            "All five scenario IDs have ground-truth labels",
            scenario_ids == label_ids == set(EXPECTED)
        ))

        checks.append((
            "Employee IDs are unique",
            len({row["employee_id"] for row in scenarios}) == 5
        ))

        checks.append((
            "Course IDs are unique",
            len({row["course_id"] for row in scenarios}) == 5
        ))

        # Check ground-truth rows in DuckDB.
        db_labels = connection.execute(
            """
            SELECT scenario_id, expected_label
            FROM ground_truth
            WHERE scenario_id LIKE 'ANOM-%'
            """
        ).fetchall()

        checks.append((
            "Five ground-truth rows exist in database",
            len(db_labels) == 5
        ))

        db_label_map = {row[0]: row[1] for row in db_labels}
        csv_label_map = {
            row["scenario_id"]: row["expected_label"]
            for row in labels
        }

        checks.append((
            "Database labels match ground_truth.csv",
            db_label_map == csv_label_map
        ))

        # Check each scenario against the operational data.
        for scenario in scenarios:
            sid = scenario["scenario_id"]
            employee = scenario["employee_id"]
            course = scenario["course_id"]

            checks.append((
                f"{sid}: expected scenario type",
                scenario["scenario_type"] == EXPECTED[sid]
            ))

            # All employee and course references must exist.
            references_exist = connection.execute(
                """
                SELECT
                    EXISTS (
                        SELECT 1 FROM employees
                        WHERE employee_id = ?
                    ),
                    EXISTS (
                        SELECT 1 FROM courses
                        WHERE course_id = ?
                    )
                """,
                [employee, course]
            ).fetchone()

            checks.append((
                f"{sid}: valid employee and course references",
                all(references_exist)
            ))

            if sid == "ANOM-001":
                valid = connection.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM prerequisites p
                        JOIN courses c ON c.course_id = p.course_id
                        WHERE p.course_id = ?
                          AND c.course_status = 'ACTIVE'
                          AND NOT EXISTS (
                              SELECT 1
                              FROM enrollments en
                              JOIN completions cp
                                ON cp.enrollment_id = en.enrollment_id
                              WHERE en.employee_id = ?
                                AND en.course_id = p.prerequisite_course_id
                                AND cp.outcome = 'PASSED'
                          )
                    )
                    """,
                    [course, employee]
                ).fetchone()[0]

                checks.append((
                    f"{sid}: prerequisite is genuinely missing",
                    valid
                ))

            elif sid == "ANOM-002":
                valid = connection.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM recommendation_decisions rd
                        JOIN courses c ON c.course_id = rd.course_id
                        JOIN employees e ON e.employee_id = rd.employee_id
                        JOIN budgets b ON b.department = e.department
                        WHERE rd.employee_id = ?
                          AND rd.course_id = ?
                          AND rd.decision_status = 'BLOCKED'
                          AND rd.decision_reason ILIKE '%budget%'
                          AND c.cost_inr > 0
                    )
                    """,
                    [employee, course]
                ).fetchone()[0]

                checks.append((
                    f"{sid}: source recommendation was budget-blocked",
                    valid
                ))

            elif sid == "ANOM-003":
                valid = connection.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM completions cp
                        JOIN enrollments en
                          ON en.enrollment_id = cp.enrollment_id
                        WHERE en.employee_id = ?
                          AND en.course_id = ?
                          AND cp.outcome = 'PASSED'
                    )
                    """,
                    [employee, course]
                ).fetchone()[0]

                checks.append((
                    f"{sid}: original passed completion exists",
                    valid
                ))

            elif sid == "ANOM-004":
                valid = connection.execute(
                    """
                    WITH latest_assessment AS (
                        SELECT *,
                            ROW_NUMBER() OVER (
                                PARTITION BY employee_id, skill_id
                                ORDER BY assessed_at DESC,
                                         employee_skill_id DESC
                            ) AS rn
                        FROM employee_skills
                    )
                    SELECT EXISTS (
                        SELECT 1
                        FROM completions cp
                        JOIN enrollments en
                          ON en.enrollment_id = cp.enrollment_id
                        JOIN employees e
                          ON e.employee_id = en.employee_id
                        JOIN course_skills cs
                          ON cs.course_id = en.course_id
                        JOIN role_skill_targets rst
                          ON rst.role_id = e.role_id
                         AND rst.skill_id = cs.skill_id
                        JOIN latest_assessment la
                          ON la.employee_id = en.employee_id
                         AND la.skill_id = cs.skill_id
                         AND la.rn = 1
                        WHERE en.employee_id = ?
                          AND en.course_id = ?
                          AND cp.outcome = 'PASSED'
                          AND la.proficiency < rst.target_proficiency
                          AND NOT EXISTS (
                              SELECT 1
                              FROM employee_skills later
                              WHERE later.employee_id = en.employee_id
                                AND later.skill_id = cs.skill_id
                                AND later.assessed_at > cp.completed_at
                          )
                    )
                    """,
                    [employee, course]
                ).fetchone()[0]

                checks.append((
                    f"{sid}: gap remains without reassessment",
                    valid
                ))

            elif sid == "ANOM-005":
                valid = connection.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM courses c
                        WHERE c.course_id = ?
                          AND c.course_status = 'ACTIVE'
                          AND (
                              c.available_from >
                                  CURRENT_DATE + INTERVAL 90 DAY
                              OR c.available_to < CURRENT_DATE
                          )
                    )
                    """,
                    [course]
                ).fetchone()[0]

                checks.append((
                    f"{sid}: course is outside planning window",
                    valid
                ))

        print("\nANOMALY VALIDATION")
        print("=" * 65)

        passed = 0

        for description, result in checks:
            if result:
                passed += 1

            print(
                f"[{'PASS' if result else 'FAIL'}] {description}"
            )

        print("-" * 65)
        print(f"Checks passed: {passed}/{len(checks)}")

        if passed != len(checks):
            raise RuntimeError("Anomaly validation failed.")

        print("\nALL ANOMALY CHECKS PASSED")

    finally:
        connection.close()


if __name__ == "__main__":
    validate()
