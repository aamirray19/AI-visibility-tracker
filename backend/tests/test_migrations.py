from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_alembic_upgrade_creates_phase_2_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "phase2.db"
    database_url = f"sqlite:///{db_path}"

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    config.set_main_option("script_location", str(Path("alembic").resolve()))

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)

    table_names = set(inspector.get_table_names())

    assert {
        "campaign",
        "prompt",
        "result",
        "cited_url",
        "competitor_mention",
    }.issubset(table_names)

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
