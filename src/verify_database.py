
import duckdb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "learning_pathway.duckdb"

TABLES = [
    "roles",
    "skills",
    "employees",
    "role_skill_targets",
    "employee_skills",
    "courses",
    "course_skills",
    "prerequisites",
    "budgets",
    "enrollments",
    "completions",
    "enrollment_events",
]


def verify_database():
    connection = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        print("\nDATABASE VERIFICATION")
        print("=" * 45)

        total = 0

        for table in TABLES:
            count = connection.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]

            total += count
            print(f"{table}: {count:,}")

        print("-" * 45)
        print(f"Total records: {total:,}")

    finally:
        connection.close()


if __name__ == "__main__":
    verify_database()
