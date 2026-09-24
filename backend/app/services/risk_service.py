import json
from collections import defaultdict
from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text

from ..database.session import SessionLocal


def _insert_risk(db: Any, risk: dict[str, Any]) -> bool:
    result = db.execute(
        text(
            """
            INSERT IGNORE INTO teaching_risks
              (teacher_id,class_id,student_id,assignment_id,question_id,risk_type,severity,title,evidence_json,fingerprint)
            VALUES
              (:teacher_id,:class_id,:student_id,:assignment_id,:question_id,:risk_type,:severity,:title,:evidence,:fingerprint)
            """
        ),
        {**risk, "evidence": json.dumps(risk.get("evidence") or {}, ensure_ascii=False)},
    )
    if result.rowcount:
        db.execute(
            text("INSERT INTO user_notifications (user_id,type,title,content,action_url) VALUES (:teacher_id,'teaching_risk',:title,:content,:url)"),
            {"teacher_id": risk["teacher_id"], "title": risk["title"], "content": str((risk.get("evidence") or {}).get("summary") or "小逻发现了需要教师关注的教学信号。"), "url": "/teacher"},
        )
        return True
    return False


def scan_teacher_risks_sync(teacher_id: int) -> dict[str, Any]:
    created = 0
    with SessionLocal() as db:
        students = db.execute(
            text(
                """
                SELECT c.id AS class_id,c.name AS class_name,u.id AS student_id,COALESCE(u.nickname,u.username) AS student,
                       cm.joined_at,MAX(pr.answered_at) AS last_active
                FROM classes c JOIN class_members cm ON cm.class_id=c.id AND cm.status='active'
                JOIN users u ON u.id=cm.student_id LEFT JOIN practice_records pr ON pr.user_id=u.id
                WHERE c.teacher_id=:teacher_id AND c.status='active'
                GROUP BY c.id,c.name,u.id,u.nickname,u.username,cm.joined_at
                """
            ),
            {"teacher_id": teacher_id},
        ).mappings().all()
        for row in students:
            inactive = row["last_active"] is None or (date.today() - row["last_active"].date()).days >= 7
            joined_days = (date.today() - row["joined_at"].date()).days if row["joined_at"] else 0
            if inactive and joined_days >= 7:
                days = (date.today() - row["last_active"].date()).days if row["last_active"] else joined_days
                created += int(_insert_risk(db, {
                    "teacher_id": teacher_id, "class_id": int(row["class_id"]), "student_id": int(row["student_id"]), "assignment_id": None, "question_id": None,
                    "risk_type": "student_inactive", "severity": "high" if days >= 14 else "medium",
                    "title": f"{row['student']} 已连续 {days} 天未练习",
                    "evidence": {"summary": f"{row['class_name']} · 最近活跃：{row['last_active'] or '加入后暂无练习'}", "inactive_days": days},
                    "fingerprint": f"inactive:{row['class_id']}:{row['student_id']}:{date.today().isocalendar().year}-{date.today().isocalendar().week}",
                }))

        recent = db.execute(
            text(
                """
                SELECT c.id AS class_id,pr.user_id,u.nickname,u.username,q.knowledge_tag,q.id AS question_id,pr.is_correct,pr.answered_at
                FROM classes c JOIN class_members cm ON cm.class_id=c.id AND cm.status='active'
                JOIN users u ON u.id=cm.student_id JOIN practice_records pr ON pr.user_id=u.id AND pr.is_correct IS NOT NULL
                JOIN questions q ON q.id=pr.question_id
                WHERE c.teacher_id=:teacher_id AND c.status='active' AND pr.mastery_evidence='formal'
                  AND pr.answered_at>=DATE_SUB(NOW(),INTERVAL 30 DAY)
                ORDER BY pr.user_id,q.knowledge_tag,pr.answered_at DESC,pr.id DESC
                """
            ),
            {"teacher_id": teacher_id},
        ).mappings().all()
        grouped: dict[tuple[int, str], list[Any]] = defaultdict(list)
        for row in recent:
            grouped[(int(row["user_id"]), str(row["knowledge_tag"]))].append(row)
        for (student_id, tag), rows in grouped.items():
            latest = rows[:3]
            if len(latest) == 3 and all(item["is_correct"] == 0 for item in latest):
                row = latest[0]
                student = row["nickname"] or row["username"]
                created += int(_insert_risk(db, {
                    "teacher_id": teacher_id, "class_id": int(row["class_id"]), "student_id": student_id, "assignment_id": None, "question_id": int(row["question_id"]),
                    "risk_type": "consecutive_wrong", "severity": "high", "title": f"{student} 在“{tag}”连续答错",
                    "evidence": {"summary": "最近 3 次同知识点作答均错误，建议先补前置概念并联系学生。", "knowledge_tag": tag, "wrong_streak": 3},
                    "fingerprint": f"wrong-streak:{row['class_id']}:{student_id}:{tag}",
                }))

        health = db.execute(
            text(
                """
                SELECT q.id AS question_id,q.knowledge_tag,COUNT(DISTINCT pr.id) attempts,ROUND(AVG(pr.is_correct)*100,1) accuracy
                FROM classes c JOIN class_members cm ON cm.class_id=c.id AND cm.status='active'
                JOIN practice_records pr ON pr.user_id=cm.student_id AND pr.is_correct IS NOT NULL
                JOIN questions q ON q.id=pr.question_id
                WHERE c.teacher_id=:teacher_id AND c.status='active' AND pr.mastery_evidence='formal'
                GROUP BY q.id,q.knowledge_tag HAVING COUNT(DISTINCT pr.id)>=5 AND (AVG(pr.is_correct)<0.3 OR AVG(pr.is_correct)>0.95)
                """
            ),
            {"teacher_id": teacher_id},
        ).mappings().all()
        for row in health:
            low = float(row["accuracy"] or 0) < 30
            created += int(_insert_risk(db, {
                "teacher_id": teacher_id, "class_id": None, "student_id": None, "assignment_id": None, "question_id": int(row["question_id"]),
                "risk_type": "question_health", "severity": "high" if low else "low",
                "title": f"题目 #{row['question_id']} 正确率异常（{float(row['accuracy']):g}%）",
                "evidence": {"summary": "可能过难/超纲/题干有歧义。" if low else "题目可能过易，区分度不足。", "attempts": int(row["attempts"]), "accuracy": float(row["accuracy"])},
                "fingerprint": f"question-health:{row['question_id']}:{'low' if low else 'high'}",
            }))
        db.commit()
    return {"created": created, **risks_sync(teacher_id)}


def risks_sync(teacher_id: int, status_value: str = "open") -> dict[str, Any]:
    with SessionLocal() as db:
        rows = db.execute(
            text("SELECT * FROM teaching_risks WHERE teacher_id=:teacher_id AND status=:status ORDER BY FIELD(severity,'high','medium','low'),detected_at DESC LIMIT 100"),
            {"teacher_id": teacher_id, "status": status_value},
        ).mappings().all()
    items = []
    for row in rows:
        item = dict(row)
        for key in ("id", "teacher_id", "class_id", "student_id", "assignment_id", "question_id"):
            item[key] = int(item[key]) if item.get(key) is not None else None
        item["detected_at"] = item["detected_at"].isoformat() if item["detected_at"] else None
        items.append(item)
    return {"items": items, "total": len(items)}


def update_risk_sync(teacher_id: int, risk_id: int, status_value: str) -> dict[str, Any]:
    with SessionLocal() as db:
        result = db.execute(
            text("UPDATE teaching_risks SET status=:status,resolved_at=CASE WHEN :status='resolved' THEN NOW() ELSE NULL END WHERE id=:id AND teacher_id=:teacher_id"),
            {"status": status_value, "id": risk_id, "teacher_id": teacher_id},
        )
        if not result.rowcount:
            raise HTTPException(status_code=404, detail="风险信号不存在。")
        db.commit()
    return {"id": risk_id, "status": status_value}


def create_help_signals_sync(student_id: int, question: dict[str, Any], streak_wrong: int) -> int:
    if streak_wrong < 3:
        return 0
    created = 0
    with SessionLocal() as db:
        classes = db.execute(
            text("SELECT c.id,c.teacher_id,c.name FROM class_members cm JOIN classes c ON c.id=cm.class_id WHERE cm.student_id=:student_id AND cm.status='active' AND c.status='active'"),
            {"student_id": student_id},
        ).mappings().all()
        for class_row in classes:
            fingerprint = f"wrong:{class_row['id']}:{student_id}:{question.get('knowledge_tag')}"
            result = db.execute(
                text(
                    """
                    INSERT IGNORE INTO student_help_signals
                      (student_id,teacher_id,class_id,question_id,knowledge_tag,signal_type,evidence_json,fingerprint)
                    VALUES (:student_id,:teacher_id,:class_id,:question_id,:tag,'consecutive_wrong',:evidence,:fingerprint)
                    """
                ),
                {"student_id": student_id, "teacher_id": int(class_row["teacher_id"]), "class_id": int(class_row["id"]), "question_id": int(question["id"]), "tag": question.get("knowledge_tag"), "evidence": json.dumps({"wrong_streak": streak_wrong, "summary": f"同一知识点连续错误 {streak_wrong} 次"}, ensure_ascii=False), "fingerprint": fingerprint},
            )
            if result.rowcount:
                created += 1
                db.execute(
                    text("INSERT INTO user_notifications (user_id,type,title,content,action_url) VALUES (:teacher,'ticket_student','学生求助信号',:content,'/teacher')"),
                    {"teacher": int(class_row["teacher_id"]), "content": f"{class_row['name']}有学生在“{question.get('knowledge_tag')}”连续答错 {streak_wrong} 次；该信号只用于提示，请教师结合实际判断。"},
                )
        db.commit()
    return created


def help_signals_sync(teacher_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT s.*,COALESCE(u.nickname,u.username) student,c.name class_name
                FROM student_help_signals s JOIN users u ON u.id=s.student_id JOIN classes c ON c.id=s.class_id
                WHERE s.teacher_id=:teacher_id AND s.status<>'resolved' ORDER BY s.created_at DESC LIMIT 100
                """
            ),
            {"teacher_id": teacher_id},
        ).mappings().all()
    return {"items": [{**dict(row), "id": int(row["id"]), "student_id": int(row["student_id"]), "class_id": int(row["class_id"]), "question_id": int(row["question_id"]) if row["question_id"] else None, "created_at": row["created_at"].isoformat()} for row in rows], "total": len(rows)}


def update_help_signal_sync(teacher_id: int, signal_id: int, status_value: str) -> dict[str, Any]:
    with SessionLocal() as db:
        result = db.execute(text("UPDATE student_help_signals SET status=:status WHERE id=:id AND teacher_id=:teacher"), {"status": status_value, "id": signal_id, "teacher": teacher_id})
        if not result.rowcount:
            raise HTTPException(status_code=404, detail="求助信号不存在。")
        db.commit()
    return {"id": signal_id, "status": status_value}


def scan_all_teachers_sync() -> dict[str, Any]:
    with SessionLocal() as db:
        teacher_ids = [int(value) for value in db.execute(text("SELECT id FROM users WHERE role='teacher' AND status=1")).scalars().all()]
    results = [scan_teacher_risks_sync(teacher_id) for teacher_id in teacher_ids]
    return {"teachers": len(teacher_ids), "created": sum(item["created"] for item in results)}
