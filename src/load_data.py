 
import duckdb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "generated"
DB_PATH = ROOT / "data" / "learning_pathway.duckdb"

LOAD_ORDER = [
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


def sql_path(path):
    return str(path).replace("\\", "/").replace("'", "''")


def csv_source(table):
    path = sql_path(DATA_DIR / f"{table}.csv")
    return f"""
        read_csv_auto(
            '{path}',
            header = true,
            sample_size = -1
        )
    """


def check_inputs(connection):
    existing = {
        row[0]
        for row in connection.execute("SHOW TABLES").fetchall()
    }

    for table in LOAD_ORDER:
        if table not in existing:
            raise ValueError(f"Missing database table: {table}")

        path = DATA_DIR / f"{table}.csv"

        if not path.exists():
            raise FileNotFoundError(f"Missing CSV: {path}")

        count = connection.execute(
            f'SELECT COUNT(*) FROM "{table}"'
        ).fetchone()[0]

        if count > 0:
            raise RuntimeError(
                f"Table '{table}' already contains {count} records. "
                "This loader is designed for an empty database. "
                "Do not overwrite existing data."
            )


def insert_standard_table(connection, table):
    connection.execute(
        f"""
        INSERT INTO "{table}" BY NAME
        SELECT *
        FROM {csv_source(table)}
        """
    )

    count = connection.execute(
        f'SELECT COUNT(*) FROM "{table}"'
    ).fetchone()[0]

    print(f"{table}: {count:,} records loaded")


def insert_employees(connection):
    source = csv_source("employees")

    # First insert employees without manager references.
    # This ensures every employee exists before self-references
    # are restored.
    connection.execute(
        f"""
        CREATE TEMP TABLE employee_stage AS
        SELECT *
        FROM {source}
        """
    )

    connection.execute(
        """
        INSERT INTO employees (
            employee_id,
            employee_name,
            email,
            department,
            role_id,
            manager_id,
            hire_date,
            employment_status
        )
        SELECT
            employee_id,
            employee_name,
            email,
            department,
            role_id,
            NULL,
            CAST(hire_date AS DATE),
            employment_status
        FROM employee_stage
        """
    )

    # Restore manager references after all employees exist.
    connection.execute(
        """
        UPDATE employees AS target
        SET manager_id = NULLIF(source.manager_id, '')
        FROM employee_stage AS source
        WHERE target.employee_id = source.employee_id
          AND NULLIF(source.manager_id, '') IS NOT NULL
        """
    )

    count = connection.execute(
        "SELECT COUNT(*) FROM employees"
    ).fetchone()[0]

    print(f"employees: {count:,} records loaded")
    connection.execute("DROP TABLE employee_stage")


def insert_enrollments(connection):
    connection.execute(
        f"""
        INSERT INTO enrollments (
            enrollment_id,
            employee_id,
            course_id,
            enrolled_at,
            status
        )
        SELECT
            enrollment_id,
            employee_id,
            course_id,
            CAST(enrolled_at AS TIMESTAMP),
            status
        FROM {csv_source("enrollments")}
        """
    )

    count = connection.execute(
        "SELECT COUNT(*) FROM enrollments"
    ).fetchone()[0]

    print(f"enrollments: {count:,} records loaded")


def insert_completions(connection):
    connection.execute(
        f"""
        INSERT INTO completions (
            completion_id,
            enrollment_id,
            completed_at,
            completion_score,
            outcome,
            recorded_at
        )
        SELECT
            completion_id,
            enrollment_id,
            CAST(completed_at AS TIMESTAMP),
            CAST(score AS DECIMAL(5,2)),
            outcome,
            CAST(completed_at AS TIMESTAMP)
        FROM {csv_source("completions")}
        """
    )

    count = connection.execute(
        "SELECT COUNT(*) FROM completions"
    ).fetchone()[0]

    print(f"completions: {count:,} records loaded")


def insert_enrollment_events(connection):
    connection.execute(
        f"""
        INSERT INTO enrollment_events (
            event_id,
            enrollment_id,
            previous_status,
            new_status,
            event_timestamp,
            reason
        )
        SELECT
            event_id,
            enrollment_id,

            CASE event_type
                WHEN 'ENROLLED' THEN NULL
                WHEN 'STARTED' THEN 'ENROLLED'
                WHEN 'COMPLETED' THEN
                    CASE
                        WHEN previous_event = 'STARTED'
                        THEN 'IN_PROGRESS'
                        ELSE 'ENROLLED'
                    END
                WHEN 'CANCELLED' THEN 'ENROLLED'
            END,

            CASE event_type
                WHEN 'ENROLLED' THEN 'ENROLLED'
                WHEN 'STARTED' THEN 'IN_PROGRESS'
                WHEN 'COMPLETED' THEN 'COMPLETED'
                WHEN 'CANCELLED' THEN 'CANCELLED'
            END,

            CAST(event_at AS TIMESTAMP),
            'Generated lifecycle event'

        FROM (
            SELECT
                *,
                LAG(event_type) OVER (
                    PARTITION BY enrollment_id
                    ORDER BY event_at, event_id
                ) AS previous_event
            FROM {csv_source("enrollment_events")}
        ) AS event_stage
        """
    )

    count = connection.execute(
        "SELECT COUNT(*) FROM enrollment_events"
    ).fetchone()[0]

    print(f"enrollment_events: {count:,} records loaded")


def verify_foreign_keys(connection):
    checks = [
        (
            "Employee roles",
            """
            SELECT COUNT(*)
            FROM employees e
            LEFT JOIN roles r ON e.role_id = r.role_id
            WHERE r.role_id IS NULL
            """
        ),
        (
            "Employee managers",
            """
            SELECT COUNT(*)
            FROM employees e
            LEFT JOIN employees m ON e.manager_id = m.employee_id
            WHERE e.manager_id IS NOT NULL
              AND m.employee_id IS NULL
            """
        ),
        (
            "Employee skills",
            """
            SELECT COUNT(*)
            FROM employee_skills es
            LEFT JOIN employees e ON es.employee_id = e.employee_id
            LEFT JOIN skills s ON es.skill_id = s.skill_id
            WHERE e.employee_id IS NULL OR s.skill_id IS NULL
            """
        ),
        (
            "Enrollment references",
            """
            SELECT COUNT(*)
            FROM enrollments en
            LEFT JOIN employees e ON en.employee_id = e.employee_id
            LEFT JOIN courses c ON en.course_id = c.course_id
            WHERE e.employee_id IS NULL OR c.course_id IS NULL
            """
        ),
        (
            "Completion references",
            """
            SELECT COUNT(*)
            FROM completions c
            LEFT JOIN enrollments en
                ON c.enrollment_id = en.enrollment_id
            WHERE en.enrollment_id IS NULL
            """
        ),
        (
            "Event references",
            """
            SELECT COUNT(*)
            FROM enrollment_events ev
            LEFT JOIN enrollments en
                ON ev.enrollment_id = en.enrollment_id
            WHERE en.enrollment_id IS NULL
            """
        ),
    ]

    print("\nFOREIGN KEY VERIFICATION")

    for label, query in checks:
        count = connection.execute(query).fetchone()[0]
        print(f"{label}: {count} invalid references")

        if count:
            raise ValueError(f"Foreign key verification failed: {label}")


def load_data():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            "Database not found. Run initialize_db.py first."
        )

    connection = duckdb.connect(str(DB_PATH))

    try:
        connection.execute("BEGIN TRANSACTION")

        check_inputs(connection)

        print("Loading CSV datasets into DuckDB...\n")

        insert_standard_table(connection, "roles")
        insert_standard_table(connection, "skills")

        insert_employees(connection)

        for table in [
            "role_skill_targets",
            "employee_skills",
            "courses",
            "course_skills",
            "prerequisites",
            "budgets",
        ]:
            insert_standard_table(connection, table)

        insert_enrollments(connection)
        insert_completions(connection)
        insert_enrollment_events(connection)

        verify_foreign_keys(connection)

        connection.execute("COMMIT")

        print("\nDATABASE LOADING COMPLETE")
        print(f"Database: {DB_PATH}")

    except Exception:
        connection.execute("ROLLBACK")
        print("\nLoading failed. Transaction rolled back.")
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    load_data()
