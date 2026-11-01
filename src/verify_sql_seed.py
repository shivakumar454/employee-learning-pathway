import tempfile
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]

SOURCE_DB = ROOT / "data" / "learning_pathway.duckdb"
SCHEMA_FILE = ROOT / "sql" / "schema.sql"
SEED_FILE = ROOT / "sql" / "seed.sql"

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
    "recommendation_decisions",
    "pipeline_runs",
    "data_quality_issues",
    "ground_truth",
]


def get_table_counts(connection):
    counts = {}

    for table in TABLES:
        count = connection.execute(
            f'SELECT COUNT(*) FROM "{table}"'
        ).fetchone()[0]

        counts[table] = count

    return counts


def main():
    required_files = [SOURCE_DB, SCHEMA_FILE, SEED_FILE]

    for file_path in required_files:
        if not file_path.exists():
            raise FileNotFoundError(f"Required file missing: {file_path}")

    print("READING ORIGINAL DATABASE")

    original = duckdb.connect(str(SOURCE_DB), read_only=True)
    original_counts = get_table_counts(original)

    expected_total = sum(original_counts.values())

    print(f"Original database records: {expected_total:,}")

    with tempfile.TemporaryDirectory(
        prefix="seed_verification_",
        dir=ROOT / "data",
    ) as temp_dir:

        test_db_path = Path(temp_dir) / "verification.duckdb"

        test_connection = duckdb.connect(str(test_db_path))

        print("\nAPPLYING DATABASE SCHEMA")

        schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
        test_connection.execute(schema_sql)

        print("Schema applied successfully.")

        print("\nIMPORTING SQL SEED")

        seed_sql = SEED_FILE.read_text(encoding="utf-8")
        test_connection.execute(seed_sql)

        print("SQL seed imported successfully.")

        print("\nVERIFYING TABLE COUNTS")
        print("=" * 65)

        restored_counts = get_table_counts(test_connection)

        all_passed = True

        for table in TABLES:
            expected = original_counts[table]
            actual = restored_counts[table]

            passed = expected == actual

            if not passed:
                all_passed = False

            status = "PASS" if passed else "FAIL"

            print(
                f"[{status}] {table}: "
                f"expected={expected:,}, restored={actual:,}"
            )

        restored_total = sum(restored_counts.values())

        print("=" * 65)
        print(f"Original records: {expected_total:,}")
        print(f"Restored records: {restored_total:,}")

        test_connection.close()

    original.close()

    if not all_passed:
        raise AssertionError("SQL seed verification failed.")

    if expected_total != restored_total:
        raise AssertionError("Total database record count mismatch.")

    print("\nSQL SEED VERIFICATION PASSED")
    print("All 16 tables restored with matching row counts.")
    print("Original database was not modified.")


if __name__ == "__main__":
    main()