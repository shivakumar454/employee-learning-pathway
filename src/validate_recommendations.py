
import duckdb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "learning_pathway.duckdb"


def validate_recommendations():
    connection = duckdb.connect(str(DB_PATH), read_only=True)

    checks = [
        (
            "Recommended courses are active",
            """
            SELECT COUNT(*)
            FROM recommendation_decisions d
            JOIN courses c ON d.course_id = c.course_id
            WHERE d.decision_status = 'RECOMMENDED'
              AND c.course_status <> 'ACTIVE'
            """
        ),
        (
            "Recommended courses are available",
            """
            SELECT COUNT(*)
            FROM recommendation_decisions d
            JOIN courses c ON d.course_id = c.course_id
            WHERE d.decision_status = 'RECOMMENDED'
              AND (
                  c.available_from > CURRENT_DATE + INTERVAL '90 days'
                  OR c.available_to < CURRENT_DATE
              )
            """
        ),
        (
            "Prerequisites are satisfied",
            """
            SELECT COUNT(*)
            FROM recommendation_decisions d
            JOIN prerequisites p ON d.course_id = p.course_id
            WHERE d.decision_status = 'RECOMMENDED'
              AND NOT EXISTS (
                  SELECT 1
                  FROM completions cp
                  JOIN enrollments en
                    ON cp.enrollment_id = en.enrollment_id
                  WHERE en.employee_id = d.employee_id
                    AND en.course_id = p.prerequisite_course_id
                    AND cp.outcome = 'PASSED'
                    AND CAST(cp.completed_at AS DATE) < CURRENT_DATE
              )
            """
        ),
        (
            "Recommended courses have available capacity",
            """
            SELECT COUNT(*)
            FROM recommendation_decisions d
            JOIN courses c ON d.course_id = c.course_id
            WHERE d.decision_status = 'RECOMMENDED'
              AND (
                  SELECT COUNT(*)
                  FROM enrollments en
                  WHERE en.course_id = d.course_id
                    AND en.status IN ('ENROLLED', 'IN_PROGRESS')
              ) >= c.capacity
            """
        ),
        (
            "No duplicate employee-course decisions",
            """
            SELECT COUNT(*)
            FROM (
                SELECT employee_id, course_id
                FROM recommendation_decisions
                GROUP BY employee_id, course_id
                HAVING COUNT(*) > 1
            ) duplicates
            """
        ),
        (
            "Every recommendation covers a skill gap",
            """
            WITH latest AS (
                SELECT
                    employee_id,
                    skill_id,
                    proficiency,
                    ROW_NUMBER() OVER (
                        PARTITION BY employee_id, skill_id
                        ORDER BY assessed_at DESC, employee_skill_id DESC
                    ) AS rn
                FROM employee_skills
            )
            SELECT COUNT(*)
            FROM recommendation_decisions d
            WHERE d.decision_status = 'RECOMMENDED'
              AND NOT EXISTS (
                  SELECT 1
                  FROM employees e
                  JOIN role_skill_targets rst
                    ON e.role_id = rst.role_id
                  JOIN course_skills cs
                    ON rst.skill_id = cs.skill_id
                  LEFT JOIN latest l
                    ON l.employee_id = e.employee_id
                    AND l.skill_id = rst.skill_id
                    AND l.rn = 1
                  WHERE e.employee_id = d.employee_id
                    AND cs.course_id = d.course_id
                    AND rst.skill_id IS NOT NULL
                    AND rst.effective_from <= CURRENT_DATE
                    AND (
                        rst.effective_to IS NULL
                        OR rst.effective_to >= CURRENT_DATE
                    )
                    AND l.proficiency IS NOT NULL
                    AND l.proficiency < rst.target_proficiency
              )
            """
        ),
    ]

    failures = 0

    try:
        print("\nRECOMMENDATION VALIDATION")
        print("=" * 55)

        for label, query in checks:
            count = connection.execute(query).fetchone()[0]

            status = "PASS" if count == 0 else "FAIL"

            print(f"[{status}] {label}: {count}")

            if count:
                failures += 1

        total = connection.execute("""
            SELECT COUNT(*)
            FROM recommendation_decisions
            WHERE decision_status = 'RECOMMENDED'
        """).fetchone()[0]

        print("\nTotal recommended decisions:", total)

        if failures == 0:
            print("\nALL CHECKS PASSED")
        else:
            print(f"\n{failures} CHECK(S) FAILED")

    finally:
        connection.close()


if __name__ == "__main__":
    validate_recommendations()
