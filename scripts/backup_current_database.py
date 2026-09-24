"""Create a recoverable dump of the configured development database."""
from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from backend.app.database.session import database_url


ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = ROOT / "backups"
MYSQLDUMP = Path(r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe")
ALLOWED_DATABASES = {"math_brain", "xingce"}


def main() -> None:
    url = make_url(database_url)
    database = str(url.database or "")
    if database not in ALLOWED_DATABASES:
        raise RuntimeError(f"拒绝备份未列入白名单的数据库：{database or '<empty>'}")
    if not MYSQLDUMP.is_file():
        raise RuntimeError(f"找不到 mysqldump：{MYSQLDUMP}")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    output = BACKUP_DIR / f"{database}_pre_teaching_intelligence_{datetime.now():%Y%m%d_%H%M%S}.sql"
    environment = os.environ.copy()
    if url.password:
        environment["MYSQL_PWD"] = url.password
    command = [
        str(MYSQLDUMP), "-h", url.host or "localhost", "-P", str(url.port or 3306),
        "-u", url.username or "root", "--default-character-set=utf8mb4", "--routines",
        "--triggers", "--single-transaction", "--result-file", str(output), database,
    ]
    completed = subprocess.run(command, capture_output=True, env=environment, check=False)
    if completed.returncode or not output.is_file() or output.stat().st_size == 0:
        output.unlink(missing_ok=True)
        detail = completed.stderr.decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(detail or "数据库备份未生成有效文件。")
    print(f"DATABASE_BACKUP_OK: {output} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
