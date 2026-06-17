from pathlib import Path

from sqlalchemy import create_engine

from app.core.config import get_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_SQL = PROJECT_ROOT / "db" / "migrations" / "001_initial_schema.sql"


def run_sql_file(path: Path, database_url: str | None = None) -> None:
    sql = path.read_text(encoding="utf-8")
    engine = create_engine(database_url or get_settings().database_url, future=True)
    with engine.begin() as connection:
        connection.exec_driver_sql(sql)
    engine.dispose()


def init_database(database_url: str | None = None) -> None:
    run_sql_file(SCHEMA_SQL, database_url=database_url)
