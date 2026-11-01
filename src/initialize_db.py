from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "learning_pathway.duckdb"
SCHEMA_PATH = ROOT / "sql" / "schema.sql"


def initialize_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect(str(DB_PATH))

    try:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        connection.execute(schema)

        tables = connection.execute("SHOW TABLES").fetchall()

        print("DATABASE INITIALIZED")
        print(f"Database: {DB_PATH}")
        print(f"Tables created: {len(tables)}")

        for table in tables:
            print("-", table[0])

    finally:
        connection.close()


if __name__ == "__main__":
    initialize_database()