import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from backend.app.database.models import Base
from backend.app.database.session import database_url


TEST_DATABASE = "math_brain_alembic_test"


def main() -> None:
    if TEST_DATABASE != "math_brain_alembic_test":
        raise RuntimeError("拒绝操作未明确命名的迁移测试库。")

    root = Path(os.environ.get("PROJECT_ROOT", Path(__file__).resolve().parents[1]))
    source_url = make_url(database_url)
    admin_url = source_url.set(database="mysql")
    test_url = source_url.set(database=TEST_DATABASE)
    admin_engine = create_engine(admin_url, pool_pre_ping=True)
    test_engine = create_engine(test_url, pool_pre_ping=True)
    config = Config(str(root / "backend" / "alembic.ini"))

    with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS `{TEST_DATABASE}`"))
        connection.execute(
            text(
                f"CREATE DATABASE `{TEST_DATABASE}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
            )
        )

    os.environ["DATABASE_URL"] = test_url.render_as_string(hide_password=False)
    try:
        command.upgrade(config, "head")
        tables = set(inspect(test_engine).get_table_names())
        expected = set(Base.metadata.tables) | {"alembic_version"}
        if tables != expected:
            raise AssertionError(f"升级后的表集合不一致：missing={expected - tables}, extra={tables - expected}")

        command.downgrade(config, "base")
        remaining = set(inspect(test_engine).get_table_names()) - {"alembic_version"}
        if remaining:
            raise AssertionError(f"降级后仍残留业务表：{sorted(remaining)}")

        command.upgrade(config, "head")
        print(f"ALEMBIC_E2E_OK: {len(expected) - 1} 张业务表可升级、回滚并再次升级。")
    finally:
        test_engine.dispose()
        with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.execute(text(f"DROP DATABASE IF EXISTS `{TEST_DATABASE}`"))
        admin_engine.dispose()


if __name__ == "__main__":
    main()
