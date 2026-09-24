"""同课程内知识点重名唯一化：后续同名 level3 节点追加 -2/-3 序号（保留数据）。"""
import sys

sys.path.insert(0, "backend")

from sqlalchemy import text

from app.database.repositories.curriculum import GRAPH_COURSES
from app.database.session import SessionLocal

renamed = 0
with SessionLocal.begin() as db:
    placeholders = ",".join(f":c{i}" for i in range(len(GRAPH_COURSES)))
    rows = db.execute(
        text(f"""
            SELECT id, course_name, name FROM knowledge_nodes
            WHERE course_name IN ({placeholders})
            ORDER BY course_name, name, level DESC, sort_order, id
        """),
        {f"c{i}": name for i, name in enumerate(GRAPH_COURSES)},
    ).mappings().all()
    seen: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (str(row["course_name"]), str(row["name"]))
        order = seen.get(key, 0) + 1
        seen[key] = order
        if order > 1:
            new_name = f"{row['name']}（{order}）"
            db.execute(text("UPDATE knowledge_nodes SET name=:name WHERE id=:id"), {"name": new_name, "id": int(row["id"])})
            renamed += 1
print("renamed duplicates:", renamed)
