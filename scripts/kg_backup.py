"""备份 knowledge_nodes 与 course_relations（图谱整改前置）"""
import sys
from datetime import datetime

sys.path.insert(0, "backend")

from app.database.session import SessionLocal
from sqlalchemy import text

TAG = datetime.now().strftime("%Y%m%d_%H%M%S")

with SessionLocal.begin() as db:
    for table in ["knowledge_nodes", "course_relations", "tag_mappings"]:
        bak = f"{table}_bak_{TAG}"
        try:
            db.execute(text(f"DROP TABLE IF EXISTS {bak}"))
            db.execute(text(f"CREATE TABLE {bak} AS SELECT * FROM {table}"))
            n = db.execute(text(f"SELECT COUNT(*) c FROM {bak}")).scalar_one()
            print(f"backup {table} -> {bak} ({n} rows)")
        except Exception as exc:
            print(f"backup {table} skipped: {str(exc)[:120]}")
print("DONE")
