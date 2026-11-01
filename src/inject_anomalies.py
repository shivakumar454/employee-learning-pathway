 
import csv
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "learning_pathway.duckdb"
OUTPUT_DIR = ROOT / "data" / "generated"


def write_csv(filename, rows):
    path = OUTPUT_DIR / filename
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{filename}: {len(rows)} records")


def fetch_unique(connection, query, used_employees, used_courses):
    rows = connection.execute(query).fetchall()

    for row in rows:
        employee_id, course_id = row[0], row[1]

        if (
            employee_id not in used_employees
            and course_id not in used_courses
        ):
            used_employees.add(employee_id)
            used_courses.add(course_id)
            return row

    raise RuntimeError(
        "Could not find a unique employee-course pair for a scenario."
    )


def generate():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(DB_PATH))

    used_employees = set()
    used_courses = set()
    scenarios = []
    ground_truth = []

    def add(scenario_id, scenario_type, record,
            simulated_action, details, label, reason):

        employee_id, course_id = record[0], record[1]

        scenarios.append({
            "scenario_id": scenario_id,
            "scenario_type": scenario_type,
            "employee_id": employee_id,
            "course_id": course_id,
            "simulated_action": simulated_action,
            "scenario_details": details,
        })

        ground_truth.append({
            "ground_truth_id": f"GT-{scenario_id}",
            "scenario_id": scenario_id,
            "employee_id": employee_id,
            "course_id": course_id,
            "expected_label": label,
            "expected_reason": reason,
        })

    try:
        # 1. Prerequisite violation
        record = fetch_unique(
            connection,
            """
            SELECT e.employee_id, c.course_id,
                   p.prerequisite_course_id
            FROM employees e
            CROSS JOIN prerequisites p
            JOIN courses c ON c.course_id = p.course_id
            WHERE c.course_status = 'ACTIVE'
              AND NOT EXISTS (
                  SELECT 1
                  FROM enrollments en
                  JOIN completions cp
                    ON cp.enrollment_id = en.enrollment_id
                  WHERE en.employee_id = e.employee_id
                    AND en.course_id = p.prerequisite_course_id
                    AND cp.outcome = 'PASSED'
              )
            ORDER BY e.employee_id, c.course_id
            """,
            used_employees, used_courses
        )

        add(
            "ANOM-001", "PREREQUISITE_VIOLATION", record,
            "RECOMMEND",
            f"Prerequisite not passed: {record[2]}",
            "BLOCKED",
            f"Required prerequisite {record[2]} has no passed completion."
        )

        # 2. Budget exceeded
        record = fetch_unique(
            connection,
            """
            SELECT rd.employee_id, rd.course_id,
                   c.cost_inr, e.department, b.allocated_amount
            FROM recommendation_decisions rd
            JOIN employees e ON e.employee_id = rd.employee_id
            JOIN courses c ON c.course_id = rd.course_id
            JOIN budgets b ON b.department = e.department
            WHERE rd.decision_status = 'BLOCKED'
              AND rd.decision_reason ILIKE '%budget%'
            ORDER BY rd.employee_id, rd.course_id
            """,
            used_employees, used_courses
        )

        add(
            "ANOM-002", "BUDGET_EXCEEDED", record,
            "APPROVE_OVER_BUDGET",
            f"Course cost INR {record[2]}, department {record[3]}, "
            f"budget INR {record[4]}",
            "BLOCKED",
            "The proposed allocation exceeds available department budget."
        )

        # 3. Duplicate completion
        record = fetch_unique(
            connection,
            """
            SELECT en.employee_id, en.course_id,
                   cp.enrollment_id, cp.completion_id,
                   cp.completed_at, cp.completion_score, cp.outcome
            FROM completions cp
            JOIN enrollments en
              ON en.enrollment_id = cp.enrollment_id
            WHERE cp.outcome = 'PASSED'
            ORDER BY cp.completion_id
            """,
            used_employees, used_courses
        )

        add(
            "ANOM-003", "DUPLICATE_COMPLETION", record,
            "RECORD_DUPLICATE_COMPLETION",
            f"Simulated duplicate of completion {record[3]} "
            f"for enrollment {record[2]}",
            "REJECT_DUPLICATE",
            "The same enrollment completion must not be counted twice."
        )

        # 4. Skill gap without reassessment
        record = fetch_unique(
            connection,
            """
            WITH latest_assessment AS (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY employee_id, skill_id
                        ORDER BY assessed_at DESC, employee_skill_id DESC
                    ) AS rn
                FROM employee_skills
            )
            SELECT en.employee_id, en.course_id,
                   cs.skill_id, la.proficiency,
                   rst.target_proficiency, cp.completed_at
            FROM completions cp
            JOIN enrollments en
              ON en.enrollment_id = cp.enrollment_id
            JOIN employees e ON e.employee_id = en.employee_id
            JOIN course_skills cs ON cs.course_id = en.course_id
            JOIN role_skill_targets rst
              ON rst.role_id = e.role_id
             AND rst.skill_id = cs.skill_id
            JOIN latest_assessment la
              ON la.employee_id = en.employee_id
             AND la.skill_id = cs.skill_id
             AND la.rn = 1
            WHERE cp.outcome = 'PASSED'
              AND la.proficiency < rst.target_proficiency
              AND NOT EXISTS (
                  SELECT 1
                  FROM employee_skills later
                  WHERE later.employee_id = en.employee_id
                    AND later.skill_id = cs.skill_id
                    AND later.assessed_at > cp.completed_at
              )
            ORDER BY en.employee_id, en.course_id, cs.skill_id
            """,
            used_employees, used_courses
        )

        add(
            "ANOM-004", "SKILL_GAP_WITHOUT_REASSESSMENT", record,
            "MARK_SKILL_IMPROVED",
            f"Skill {record[2]} proficiency {record[3]}, "
            f"target {record[4]}, no post-completion reassessment",
            "REASSESSMENT_REQUIRED",
            "Course completion alone does not prove skill improvement."
        )

        # 5. Course unavailable in planning period
        record = fetch_unique(
            connection,
            """
            WITH latest_assessment AS (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY employee_id, skill_id
                        ORDER BY assessed_at DESC, employee_skill_id DESC
                    ) AS rn
                FROM employee_skills
            )
            SELECT e.employee_id, c.course_id,
                   c.available_from, c.available_to
            FROM employees e
            JOIN role_skill_targets rst ON rst.role_id = e.role_id
            JOIN latest_assessment la
              ON la.employee_id = e.employee_id
             AND la.skill_id = rst.skill_id
             AND la.rn = 1
            JOIN course_skills cs ON cs.skill_id = rst.skill_id
            JOIN courses c ON c.course_id = cs.course_id
            WHERE la.proficiency < rst.target_proficiency
              AND c.course_status = 'ACTIVE'
              AND (
                  c.available_from > CURRENT_DATE + INTERVAL 90 DAY
                  OR c.available_to < CURRENT_DATE
              )
            ORDER BY e.employee_id, c.course_id
            """,
            used_employees, used_courses
        )

        add(
            "ANOM-005", "COURSE_UNAVAILABLE", record,
            "RECOMMEND",
            f"Course availability: {record[2]} to {record[3]}",
            "BLOCKED",
            "Course is unavailable during the 90-day planning period."
        )

        if len(ground_truth) != 5:
            raise RuntimeError("Expected exactly five scenarios.")

        write_csv("anomaly_scenarios.csv", scenarios)
        write_csv("ground_truth.csv", ground_truth)

        # Replace only this script's existing ground-truth records.
        connection.execute("BEGIN TRANSACTION")

        try:
            connection.execute(
                "DELETE FROM ground_truth WHERE scenario_id LIKE 'ANOM-%'"
            )

            connection.executemany(
                """
                INSERT INTO ground_truth (
                    ground_truth_id,
                    scenario_id,
                    employee_id,
                    course_id,
                    expected_label,
                    expected_reason
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row["ground_truth_id"],
                        row["scenario_id"],
                        row["employee_id"],
                        row["course_id"],
                        row["expected_label"],
                        row["expected_reason"],
                    )
                    for row in ground_truth
                ]
            )

            connection.execute("COMMIT")

        except Exception:
            connection.execute("ROLLBACK")
            raise

        print("\nANOMALY SCENARIOS GENERATED")
        print("=" * 60)

        for row in scenarios:
            print(
                row["scenario_id"],
                "|", row["scenario_type"],
                "|", row["employee_id"],
                "|", row["course_id"]
            )

        print("\nScenario records:", len(scenarios))
        print("Ground-truth records:", len(ground_truth))
        print("Baseline operational records were not modified.")

    finally:
        connection.close()


if __name__ == "__main__":
    generate()
