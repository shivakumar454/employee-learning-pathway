
import duckdb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "learning_pathway.duckdb"

PLANNING_DAYS = 90
MAX_RECOMMENDATIONS_PER_EMPLOYEE = 5


def generate_recommendations():
    connection = duckdb.connect(str(DB_PATH))

    try:
        connection.execute("BEGIN TRANSACTION")

        connection.execute(
            "DELETE FROM recommendation_decisions"
        )

        query = f"""
        INSERT INTO recommendation_decisions (
            decision_id,
            employee_id,
            course_id,
            decision_status,
            decision_reason,
            decision_score,
            evaluated_at
        )

        WITH latest_assessments AS (
            SELECT
                employee_id,
                skill_id,
                proficiency,
                ROW_NUMBER() OVER (
                    PARTITION BY employee_id, skill_id
                    ORDER BY assessed_at DESC, employee_skill_id DESC
                ) AS rn
            FROM employee_skills
        ),

        current_skills AS (
            SELECT employee_id, skill_id, proficiency
            FROM latest_assessments
            WHERE rn = 1
        ),

        skill_gaps AS (
            SELECT
                e.employee_id,
                e.department,
                rst.skill_id,
                rst.target_proficiency,
                cs.proficiency,
                rst.target_proficiency - cs.proficiency AS gap
            FROM employees e
            JOIN role_skill_targets rst
                ON e.role_id = rst.role_id
            LEFT JOIN current_skills cs
                ON cs.employee_id = e.employee_id
                AND cs.skill_id = rst.skill_id
            WHERE e.employment_status = 'ACTIVE'
              AND rst.effective_from <= CURRENT_DATE
              AND (
                  rst.effective_to IS NULL
                  OR rst.effective_to >= CURRENT_DATE
              )
              AND cs.proficiency IS NOT NULL
              AND cs.proficiency < rst.target_proficiency
        ),

        course_matches AS (
            SELECT
                sg.employee_id,
                sg.department,
                c.course_id,
                c.course_name,
                c.course_status,
                c.cost_inr,
                c.capacity,
                c.available_from,
                c.available_to,

                COUNT(DISTINCT sg.skill_id) AS covered_skills,
                SUM(sg.gap) AS total_gap,

                LEAST(
                    100,
                    40
                    + COUNT(DISTINCT sg.skill_id) * 8
                    + SUM(sg.gap) * 5
                ) AS recommendation_score

            FROM skill_gaps sg
            JOIN course_skills cs
                ON sg.skill_id = cs.skill_id
            JOIN courses c
                ON cs.course_id = c.course_id

            GROUP BY
                sg.employee_id,
                sg.department,
                c.course_id,
                c.course_name,
                c.course_status,
                c.cost_inr,
                c.capacity,
                c.available_from,
                c.available_to
        ),

        enrollment_counts AS (
            SELECT
                course_id,
                COUNT(*) AS enrolled_count
            FROM enrollments
            WHERE status IN ('ENROLLED', 'IN_PROGRESS')
            GROUP BY course_id
        ),

        department_spend AS (
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
        ),

        evaluated AS (
            SELECT
                cm.*,

                COALESCE(ec.enrolled_count, 0) AS enrolled_count,

                b.budget_id,
                b.allocated_amount,

                COALESCE(ds.committed_spend, 0) AS committed_spend,

                CASE
                    WHEN b.budget_id IS NULL
                        THEN 'NO_ACTIVE_BUDGET'

                    WHEN cm.course_status <> 'ACTIVE'
                        THEN 'COURSE_NOT_ACTIVE'

                    WHEN cm.available_from >
                        CURRENT_DATE + INTERVAL '{PLANNING_DAYS} days'
                        OR cm.available_to < CURRENT_DATE
                        THEN 'COURSE_UNAVAILABLE'

                    WHEN COALESCE(ec.enrolled_count, 0) >= cm.capacity
                        THEN 'COURSE_CAPACITY_FULL'

                    WHEN EXISTS (
                        SELECT 1
                        FROM prerequisites p
                        WHERE p.course_id = cm.course_id
                          AND NOT EXISTS (
                              SELECT 1
                              FROM completions cp
                              JOIN enrollments pen
                                ON cp.enrollment_id = pen.enrollment_id
                              WHERE pen.employee_id = cm.employee_id
                                AND pen.course_id = p.prerequisite_course_id
                                AND cp.outcome = 'PASSED'
                                AND CAST(cp.completed_at AS DATE)
                                    < CURRENT_DATE
                          )
                    )
                        THEN 'PREREQUISITE_NOT_COMPLETED'

                    WHEN cm.cost_inr >
                        GREATEST(
                            0,
                            b.allocated_amount -
                            COALESCE(ds.committed_spend, 0)
                        )
                        THEN 'BUDGET_EXCEEDED'

                    ELSE 'ALL_RULES_SATISFIED'
                END AS evaluation_reason

            FROM course_matches cm

            LEFT JOIN enrollment_counts ec
                ON cm.course_id = ec.course_id

            LEFT JOIN budgets b
                ON cm.department = b.department
                AND b.fiscal_year = YEAR(CURRENT_DATE)
                AND CURRENT_DATE BETWEEN
                    b.effective_from AND b.effective_to

            LEFT JOIN department_spend ds
                ON cm.department = ds.department
        ),

        feasible_ranked AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY employee_id
                    ORDER BY
                        recommendation_score DESC,
                        course_id
                ) AS recommendation_rank
            FROM evaluated
            WHERE evaluation_reason = 'ALL_RULES_SATISFIED'
        ),

        blocked_ranked AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY employee_id
                    ORDER BY
                        recommendation_score DESC,
                        course_id
                ) AS blocked_rank
            FROM evaluated
            WHERE evaluation_reason <> 'ALL_RULES_SATISFIED'
        ),

        selected_feasible AS (
            SELECT *
            FROM feasible_ranked
            WHERE recommendation_rank <=
                {MAX_RECOMMENDATIONS_PER_EMPLOYEE}
        ),

        selected_blocked AS (
            SELECT b.*
            FROM blocked_ranked b
            WHERE b.blocked_rank = 1
              AND NOT EXISTS (
                  SELECT 1
                  FROM selected_feasible f
                  WHERE f.employee_id = b.employee_id
              )
        ),

        selected AS (
            SELECT
                employee_id,
                course_id,
                recommendation_score,
                covered_skills,
                evaluation_reason
            FROM selected_feasible

            UNION ALL

            SELECT
                employee_id,
                course_id,
                recommendation_score,
                covered_skills,
                evaluation_reason
            FROM selected_blocked
        )

        SELECT
            'DEC-' || LPAD(
                CAST(ROW_NUMBER() OVER (
                    ORDER BY employee_id, course_id
                ) AS VARCHAR),
                9,
                '0'
            ),

            employee_id,
            course_id,

            CASE
                WHEN evaluation_reason = 'ALL_RULES_SATISFIED'
                    THEN 'RECOMMENDED'
                ELSE 'BLOCKED'
            END,

            CASE evaluation_reason
                WHEN 'NO_ACTIVE_BUDGET'
                    THEN 'No active department budget found.'

                WHEN 'COURSE_NOT_ACTIVE'
                    THEN 'Course is not active.'

                WHEN 'COURSE_UNAVAILABLE'
                    THEN 'Course is outside the 90-day planning window.'

                WHEN 'COURSE_CAPACITY_FULL'
                    THEN 'Course has reached its enrollment capacity.'

                WHEN 'PREREQUISITE_NOT_COMPLETED'
                    THEN 'Required prerequisite course has not been passed.'

                WHEN 'BUDGET_EXCEEDED'
                    THEN 'Course cost exceeds remaining department budget.'

                ELSE
                    'Covers ' || CAST(covered_skills AS VARCHAR)
                    || ' skill gaps; all feasibility checks passed.'
            END,

            recommendation_score,
            CURRENT_TIMESTAMP

        FROM selected
        """

        connection.execute(query)
        connection.execute("COMMIT")

        print("\nRECOMMENDATION ENGINE COMPLETE")
        print("=" * 45)

        summary = connection.execute("""
            SELECT
                decision_status,
                COUNT(*)
            FROM recommendation_decisions
            GROUP BY decision_status
            ORDER BY decision_status
        """).fetchall()

        for status, count in summary:
            print(f"{status}: {count:,}")

        total = connection.execute("""
            SELECT COUNT(*)
            FROM recommendation_decisions
        """).fetchone()[0]

        print(f"Total decisions: {total:,}")

        print("\nBLOCK REASONS")

        reasons = connection.execute("""
            SELECT
                decision_reason,
                COUNT(*)
            FROM recommendation_decisions
            WHERE decision_status = 'BLOCKED'
            GROUP BY decision_reason
            ORDER BY COUNT(*) DESC
        """).fetchall()

        for reason, count in reasons:
            print(f"{reason}: {count:,}")

        print("\nSAMPLE DECISIONS")

        samples = connection.execute("""
            SELECT
                employee_id,
                course_id,
                decision_status,
                decision_reason,
                decision_score
            FROM recommendation_decisions
            ORDER BY employee_id, decision_score DESC
            LIMIT 10
        """).fetchdf()

        print(samples.to_string(index=False))

        report_path = ROOT / "reports" / "recommendations.csv"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        connection.execute(f"""
            COPY (
                SELECT
                    d.decision_id,
                    d.employee_id,
                    e.department,
                    e.role_id,
                    d.course_id,
                    c.course_name,
                    d.decision_status,
                    d.decision_reason,
                    d.decision_score,
                    d.evaluated_at
                FROM recommendation_decisions d
                JOIN employees e
                    ON d.employee_id = e.employee_id
                JOIN courses c
                    ON d.course_id = c.course_id
                ORDER BY d.employee_id, d.decision_score DESC
            )
            TO '{report_path.as_posix()}'
            (HEADER, DELIMITER ',')
        """)

        print(f"\nReport saved: {report_path}")

    except Exception:
        connection.execute("ROLLBACK")
        print("\nRecommendation generation failed. Transaction rolled back.")
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    generate_recommendations()
