
import duckdb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "learning_pathway.duckdb"


def analyze_skill_gaps():
    connection = duckdb.connect(str(DB_PATH))

    try:
        query = """
        WITH latest_assessments AS (
            SELECT
                employee_id,
                skill_id,
                proficiency,
                assessed_at,
                ROW_NUMBER() OVER (
                    PARTITION BY employee_id, skill_id
                    ORDER BY assessed_at DESC, employee_skill_id DESC
                ) AS row_num
            FROM employee_skills
        ),

        current_skills AS (
            SELECT
                employee_id,
                skill_id,
                proficiency,
                assessed_at
            FROM latest_assessments
            WHERE row_num = 1
        )

        SELECT
            e.employee_id,
            e.employee_name,
            e.department,
            r.role_name,
            s.skill_id,
            s.skill_name,
            rst.target_proficiency,
            cs.proficiency AS current_proficiency,

            CASE
                WHEN cs.proficiency IS NULL THEN 'UNKNOWN'
                WHEN cs.proficiency < rst.target_proficiency THEN 'GAP'
                ELSE 'MET'
            END AS skill_status,

            CASE
                WHEN cs.proficiency IS NULL THEN NULL
                ELSE GREATEST(
                    0,
                    rst.target_proficiency - cs.proficiency
                )
            END AS proficiency_gap

        FROM employees e

        JOIN roles r
            ON e.role_id = r.role_id

        JOIN role_skill_targets rst
            ON e.role_id = rst.role_id

        JOIN skills s
            ON rst.skill_id = s.skill_id

        LEFT JOIN current_skills cs
            ON e.employee_id = cs.employee_id
            AND rst.skill_id = cs.skill_id

        WHERE e.employment_status = 'ACTIVE'
          AND (
              rst.effective_to IS NULL
              OR rst.effective_to >= CURRENT_DATE
          )
          AND rst.effective_from <= CURRENT_DATE

        ORDER BY
            e.employee_id,
            s.skill_name
        """

        result = connection.execute(query).fetchdf()

        output_path = (
            ROOT / "reports" / "employee_skill_gaps.csv"
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(output_path, index=False)

        print("\nSKILL GAP ANALYSIS COMPLETE")
        print("=" * 45)
        print(f"Employee-skill combinations: {len(result):,}")
        print(
            f"Skills with gaps: "
            f"{(result['skill_status'] == 'GAP').sum():,}"
        )
        print(
            f"Skills met: "
            f"{(result['skill_status'] == 'MET').sum():,}"
        )
        print(
            f"Skills unknown: "
            f"{(result['skill_status'] == 'UNKNOWN').sum():,}"
        )
        print(f"\nReport saved: {output_path}")

        print("\nSample records:")
        print(result.head(10).to_string(index=False))

    finally:
        connection.close()


if __name__ == "__main__":
    analyze_skill_gaps()
