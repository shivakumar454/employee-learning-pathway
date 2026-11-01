from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "learning_pathway.duckdb"
OUTPUT_PATH = ROOT / "sql" / "seed.sql"

TABLE_ORDER = [
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

BATCH_SIZE = 500


def quote_identifier(value):
    return '"' + value.replace('"', '""') + '"'


def sql_value(value):
    if value is None:
        return "NULL"

    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"

    if isinstance(value, int):
        return str(value)

    if isinstance(value, (float, Decimal)):
        return str(value)

    if isinstance(value, datetime):
        return f"TIMESTAMP '{value.isoformat(sep=' ')}'"

    if isinstance(value, date):
        return f"DATE '{value.isoformat()}'"

    if isinstance(value, str):
        escaped = value.replace("'", "''")
        return f"'{escaped}'"

    raise TypeError(f"Unsupported SQL value: {type(value).__name__}")


def export_table(connection, output, table):
    columns = [
        row[0]
        for row in connection.execute(
            f"DESCRIBE {quote_identifier(table)}"
        ).fetchall()
    ]

    quoted_columns = ", ".join(
        quote_identifier(column) for column in columns
    )

    cursor = connection.execute(
        f"SELECT * FROM {quote_identifier(table)}"
    )

    total = 0

    while True:
        rows = cursor.fetchmany(BATCH_SIZE)

        if not rows:
            break

        values = [
            "(" + ", ".join(sql_value(value) for value in row) + ")"
            for row in rows
        ]

        output.write(
            f"INSERT INTO {quote_identifier(table)} "
            f"({quoted_columns}) VALUES\n"
        )
        output.write(",\n".join(values))
        output.write(";\n\n")

        total += len(rows)

    return total


def export_employees(connection, output):
    columns = [
        row[0]
        for row in connection.execute(
            'DESCRIBE "employees"'
        ).fetchall()
    ]

    manager_index = columns.index("manager_id")

    quoted_columns = ", ".join(
        quote_identifier(column) for column in columns
    )

    cursor = connection.execute('SELECT * FROM "employees"')
    total = 0

    # Insert employees without manager references first.
    while True:
        rows = cursor.fetchmany(BATCH_SIZE)

        if not rows:
            break

        values = []

        for row in rows:
            row = list(row)
            row[manager_index] = None

            values.append(
                "(" + ", ".join(sql_value(value) for value in row) + ")"
            )

        output.write(
            f'INSERT INTO "employees" ({quoted_columns}) VALUES\n'
        )
        output.write(",\n".join(values))
        output.write(";\n\n")

        total += len(rows)

    # Restore manager relationships after all employees exist.
    manager_rows = connection.execute("""
        SELECT employee_id, manager_id
        FROM employees
        WHERE manager_id IS NOT NULL
        ORDER BY employee_id
    """).fetchall()

    output.write("-- Restore employee manager relationships\n")

    for employee_id, manager_id in manager_rows:
        output.write(
            "UPDATE employees SET manager_id = "
            f"{sql_value(manager_id)} "
            f"WHERE employee_id = {sql_value(employee_id)};\n"
        )

    output.write("\n")

    return total


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    connection = duckdb.connect(str(DB_PATH), read_only=True)

    actual_tables = {
        row[0]
        for row in connection.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
        """).fetchall()
    }

    missing_tables = set(TABLE_ORDER) - actual_tables

    if missing_tables:
        raise RuntimeError(
            f"Missing database tables: {sorted(missing_tables)}"
        )

    total_records = 0

    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="\n") as output:
        output.write("-- Employee Learning Pathway SQL seed\n")
        output.write("-- Generated from the validated DuckDB database.\n")
        output.write("-- Execute schema.sql before this file.\n")
        output.write("-- All generated records are synthetic.\n\n")
        output.write("BEGIN TRANSACTION;\n\n")

        for table in TABLE_ORDER:
            output.write(f"-- Table: {table}\n")

            if table == "employees":
                count = export_employees(connection, output)
            else:
                count = export_table(connection, output, table)

            total_records += count
            print(f"{table}: {count:,} rows exported")

        output.write("COMMIT;\n")

    connection.close()

    print("\nSQL SEED EXPORT COMPLETE")
    print(f"Total records: {total_records:,}")
    print(f"Output: {OUTPUT_PATH}")
    print(
        f"File size: {OUTPUT_PATH.stat().st_size / (1024 * 1024):.2f} MB"
    )


if __name__ == "__main__":
    main()