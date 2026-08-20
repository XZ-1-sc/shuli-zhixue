import asyncio
import csv
import io
import json
import secrets
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ...database.session import SessionLocal
from ...security import require_teacher


router = APIRouter(prefix="/api/teacher", tags=["teacher"])


class ClassCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    stage: str = Field(min_length=2, max_length=16)
    course: str = Field(min_length=2, max_length=128)


class ClassUpdateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    stage: str = Field(min_length=2, max_length=16)
    course: str = Field(min_length=2, max_length=128)


class ClassMemberRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)


def _audit(db: Any, actor_id: int, action: str, entity_type: str, entity_id: int | None, payload: dict[str, Any]) -> None:
    db.execute(
        text(
            """
            INSERT INTO audit_logs (actor_user_id, action, entity_type, entity_id, payload)
            VALUES (:actor_id, :action, :entity_type, :entity_id, :payload)
            """
        ),
        {
            "actor_id": actor_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payload": json.dumps(payload, ensure_ascii=False),
        },
    )


def _owned_class(db: Any, teacher_id: int, class_id: int) -> dict[str, Any]:
    row = db.execute(
        text("SELECT * FROM classes WHERE id = :class_id AND teacher_id = :teacher_id LIMIT 1"),
        {"class_id": class_id, "teacher_id": teacher_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="班级不存在或不属于当前教师。")
    return dict(row)


def _new_invite_code(db: Any) -> str:
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    for _ in range(20):
        code = "".join(secrets.choice(alphabet) for _ in range(8))
        exists = db.execute(text("SELECT 1 FROM classes WHERE invite_code = :code"), {"code": code}).first()
        if not exists:
            return code
    raise HTTPException(status_code=503, detail="暂时无法生成班级邀请码，请重试。")


def _class_rows(db: Any, teacher_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT c.id, c.name, c.stage, c.course, c.invite_code, c.status, c.created_at,
                   COUNT(DISTINCT CASE WHEN cm.status = 'active' THEN cm.student_id END) AS student_count,
                   COUNT(DISTINCT CASE WHEN cm.status = 'active' AND DATE(pr.answered_at) = CURDATE()
                                       THEN cm.student_id END) AS active_today,
                   COUNT(pr.id) AS practice_count,
                   ROUND(AVG(CASE WHEN pr.is_correct IS NOT NULL THEN pr.is_correct END) * 100, 1) AS accuracy,
                   SUM(CASE WHEN pr.review_status = 'pending' THEN 1 ELSE 0 END) AS pending_review
            FROM classes AS c
            LEFT JOIN class_members AS cm ON cm.class_id = c.id AND cm.status = 'active'
            LEFT JOIN practice_records AS pr ON pr.user_id = cm.student_id
            WHERE c.teacher_id = :teacher_id AND c.status = 'active'
            GROUP BY c.id, c.name, c.stage, c.course, c.invite_code, c.status, c.created_at
            ORDER BY c.created_at DESC, c.id DESC
            """
        ),
        {"teacher_id": teacher_id},
    ).mappings().all()
    return [
        {
            "id": int(row["id"]),
            "name": str(row["name"]),
            "stage": str(row["stage"]),
            "course": str(row["course"]),
            "invite_code": str(row["invite_code"]),
            "status": str(row["status"]),
            "student_count": int(row["student_count"] or 0),
            "active_today": int(row["active_today"] or 0),
            "practice_count": int(row["practice_count"] or 0),
            "accuracy": float(row["accuracy"] or 0),
            "pending_review": int(row["pending_review"] or 0),
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]


def _classes_sync(teacher_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        items = _class_rows(db, teacher_id)
    return {"items": items, "total": len(items)}


def _create_class_sync(teacher_id: int, payload: ClassCreateRequest) -> dict[str, Any]:
    try:
        with SessionLocal() as db:
            invite_code = _new_invite_code(db)
            result = db.execute(
                text(
                    """
                    INSERT INTO classes (teacher_id, name, stage, course, invite_code)
                    VALUES (:teacher_id, :name, :stage, :course, :invite_code)
                    """
                ),
                {
                    "teacher_id": teacher_id,
                    "name": payload.name.strip(),
                    "stage": payload.stage.strip(),
                    "course": payload.course.strip(),
                    "invite_code": invite_code,
                },
            )
            class_id = int(result.lastrowid)
            _audit(db, teacher_id, "class.created", "class", class_id, payload.model_dump())
            db.commit()
            item = next(item for item in _class_rows(db, teacher_id) if item["id"] == class_id)
        return item
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="你已经创建过同名班级，请换一个名称。") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="班级创建失败，请检查数据库连接。") from exc


def _update_class_sync(teacher_id: int, class_id: int, payload: ClassUpdateRequest) -> dict[str, Any]:
    try:
        with SessionLocal() as db:
            _owned_class(db, teacher_id, class_id)
            db.execute(
                text(
                    """
                    UPDATE classes
                    SET name = :name, stage = :stage, course = :course
                    WHERE id = :class_id AND teacher_id = :teacher_id
                    """
                ),
                {**payload.model_dump(), "class_id": class_id, "teacher_id": teacher_id},
            )
            _audit(db, teacher_id, "class.updated", "class", class_id, payload.model_dump())
            db.commit()
            return next(item for item in _class_rows(db, teacher_id) if item["id"] == class_id)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="你已经创建过同名班级，请换一个名称。") from exc


def _regenerate_invite_sync(teacher_id: int, class_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        _owned_class(db, teacher_id, class_id)
        invite_code = _new_invite_code(db)
        db.execute(
            text("UPDATE classes SET invite_code=:invite_code WHERE id=:class_id AND teacher_id=:teacher_id"),
            {"invite_code": invite_code, "class_id": class_id, "teacher_id": teacher_id},
        )
        _audit(db, teacher_id, "class.invite_regenerated", "class", class_id, {"invite_code": invite_code})
        db.commit()
    return _class_detail_sync(teacher_id, class_id)


def _archive_class_sync(teacher_id: int, class_id: int) -> dict[str, bool]:
    with SessionLocal() as db:
        _owned_class(db, teacher_id, class_id)
        active_assignment = db.execute(
            text("SELECT 1 FROM assignments WHERE class_id=:class_id AND status='published' LIMIT 1"),
            {"class_id": class_id},
        ).first()
        if active_assignment:
            raise HTTPException(status_code=409, detail="班级仍有进行中的作业，请先结束作业再归档班级。")
        db.execute(text("UPDATE classes SET status='archived' WHERE id=:class_id"), {"class_id": class_id})
        _audit(db, teacher_id, "class.archived", "class", class_id, {})
        db.commit()
    return {"archived": True}


def _class_detail_sync(teacher_id: int, class_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        class_row = _owned_class(db, teacher_id, class_id)
        rows = db.execute(
            text(
                """
                SELECT u.id, u.username, u.nickname, u.current_stage, cm.joined_at,
                       COUNT(pr.id) AS practice_count,
                       ROUND(AVG(CASE WHEN pr.is_correct IS NOT NULL THEN pr.is_correct END) * 100, 1) AS accuracy,
                       COALESCE(SUM(pr.time_spent_seconds), 0) AS study_seconds,
                       MAX(pr.answered_at) AS last_active,
                       SUM(CASE WHEN pr.review_status = 'pending' THEN 1 ELSE 0 END) AS pending_review
                FROM class_members AS cm
                JOIN users AS u ON u.id = cm.student_id
                LEFT JOIN practice_records AS pr ON pr.user_id = u.id
                WHERE cm.class_id = :class_id AND cm.status = 'active'
                GROUP BY u.id, u.username, u.nickname, u.current_stage, cm.joined_at
                ORDER BY last_active DESC, u.username
                """
            ),
            {"class_id": class_id},
        ).mappings().all()
    members = [
        {
            "id": int(row["id"]),
            "username": str(row["username"]),
            "nickname": str(row["nickname"] or row["username"]),
            "current_stage": str(row["current_stage"] or "大一"),
            "practice_count": int(row["practice_count"] or 0),
            "accuracy": float(row["accuracy"] or 0),
            "study_hours": round(int(row["study_seconds"] or 0) / 3600, 1),
            "pending_review": int(row["pending_review"] or 0),
            "joined_at": row["joined_at"].isoformat() if row["joined_at"] else None,
            "last_active": row["last_active"].isoformat() if row["last_active"] else None,
        }
        for row in rows
    ]
    return {
        "class": {
            "id": int(class_row["id"]),
            "name": str(class_row["name"]),
            "stage": str(class_row["stage"]),
            "course": str(class_row["course"]),
            "invite_code": str(class_row["invite_code"]),
            "status": str(class_row["status"]),
        },
        "members": members,
        "student_count": len(members),
    }


def _csv_cell(value: Any) -> str:
    text_value = "" if value is None else str(value)
    if text_value.startswith(("=", "+", "-", "@")):
        return f"'{text_value}"
    return text_value


def _class_export_sync(teacher_id: int, class_id: int) -> tuple[str, bytes]:
    data = _class_detail_sync(teacher_id, class_id)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["用户名", "昵称", "学习阶段", "练习量", "正确率(%)", "学习时长(小时)", "待批改", "加入时间", "最近学习"])
    for member in data["members"]:
        writer.writerow(
            [
                _csv_cell(member["username"]),
                _csv_cell(member["nickname"]),
                _csv_cell(member["current_stage"]),
                member["practice_count"],
                member["accuracy"],
                member["study_hours"],
                member["pending_review"],
                member["joined_at"] or "",
                member["last_active"] or "",
            ]
        )
    with SessionLocal() as db:
        _audit(db, teacher_id, "class.members_exported", "class", class_id, {"count": len(data["members"])})
        db.commit()
    return f"class-{class_id}-students.csv", ("\ufeff" + output.getvalue()).encode("utf-8")


def _add_member_sync(teacher_id: int, class_id: int, payload: ClassMemberRequest) -> dict[str, Any]:
    username = payload.username.strip()
    with SessionLocal() as db:
        class_row = _owned_class(db, teacher_id, class_id)
        student = db.execute(
            text(
                """
                SELECT id, username FROM users
                WHERE username = :username AND role = 'student' AND status = 1
                LIMIT 1
                """
            ),
            {"username": username},
        ).mappings().first()
        if not student:
            raise HTTPException(status_code=404, detail="没有找到该学生账号，请让学生先注册学生端账号。")
        existing = db.execute(
            text("SELECT id, status FROM class_members WHERE class_id = :class_id AND student_id = :student_id"),
            {"class_id": class_id, "student_id": student["id"]},
        ).mappings().first()
        if existing and existing["status"] == "active":
            raise HTTPException(status_code=409, detail="该学生已经在这个班级中。")
        if existing:
            db.execute(
                text(
                    """
                    UPDATE class_members
                    SET status = 'active', joined_at = NOW(), removed_at = NULL
                    WHERE id = :member_id
                    """
                ),
                {"member_id": existing["id"]},
            )
        else:
            db.execute(
                text("INSERT INTO class_members (class_id, student_id) VALUES (:class_id, :student_id)"),
                {"class_id": class_id, "student_id": student["id"]},
            )
        _audit(db, teacher_id, "class.member_added", "class", class_id, {"student_id": int(student["id"]), "username": username})
        try:
            db.execute(
                text(
                    """
                    INSERT INTO user_notifications (user_id, type, title, content)
                    VALUES (:student_id, 'class', '已加入新班级', :content)
                    """
                ),
                {"student_id": student["id"], "content": f"你已加入 {class_row['name']}，任课教师会在这里同步学习安排。"},
            )
        except SQLAlchemyError:
            pass
        db.commit()
    return _class_detail_sync(teacher_id, class_id)


def _remove_member_sync(teacher_id: int, class_id: int, student_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        _owned_class(db, teacher_id, class_id)
        result = db.execute(
            text(
                """
                UPDATE class_members
                SET status = 'removed', removed_at = NOW()
                WHERE class_id = :class_id AND student_id = :student_id AND status = 'active'
                """
            ),
            {"class_id": class_id, "student_id": student_id},
        )
        if not result.rowcount:
            raise HTTPException(status_code=404, detail="该学生不在当前班级。")
        _audit(db, teacher_id, "class.member_removed", "class", class_id, {"student_id": student_id})
        db.commit()
    return _class_detail_sync(teacher_id, class_id)


def _overview_sync(teacher_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        classes = _class_rows(db, teacher_id)
        totals = db.execute(
            text(
                """
                SELECT COUNT(*) AS students,
                       SUM(EXISTS(SELECT 1 FROM practice_records pr WHERE pr.user_id=managed.student_id AND DATE(pr.answered_at)=CURDATE())) AS active_today,
                       SUM((SELECT COUNT(*) FROM practice_records pr
                         WHERE pr.review_status='pending' AND pr.user_id=managed.student_id)) AS pending_review,
                       (SELECT ROUND(AVG(CASE WHEN pr.is_correct IS NOT NULL THEN pr.is_correct END)*100,1)
                         FROM practice_records pr WHERE EXISTS (
                           SELECT 1 FROM class_members cm2 JOIN classes c2 ON c2.id=cm2.class_id
                           WHERE cm2.student_id=pr.user_id AND cm2.status='active'
                             AND c2.teacher_id=:teacher_id AND c2.status='active'
                         )) AS accuracy
                FROM (
                  SELECT DISTINCT cm.student_id
                  FROM class_members cm JOIN classes c ON c.id=cm.class_id
                  WHERE c.teacher_id=:teacher_id AND c.status='active' AND cm.status='active'
                ) managed
                """
            ),
            {"teacher_id": teacher_id},
        ).mappings().first()
        trend_rows = db.execute(
            text(
                """
                SELECT DATE(pr.answered_at) AS day,
                       COUNT(DISTINCT pr.user_id) AS active_students,
                       COUNT(*) AS attempts,
                       ROUND(AVG(CASE WHEN pr.is_correct IS NOT NULL THEN pr.is_correct END) * 100, 1) AS accuracy
                FROM practice_records AS pr
                WHERE pr.answered_at >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
                  AND EXISTS (
                    SELECT 1 FROM class_members AS cm
                    JOIN classes AS c ON c.id = cm.class_id
                    WHERE cm.student_id = pr.user_id AND cm.status = 'active'
                      AND c.teacher_id = :teacher_id AND c.status = 'active'
                  )
                GROUP BY DATE(pr.answered_at)
                ORDER BY day
                """
            ),
            {"teacher_id": teacher_id},
        ).mappings().all()
        mastery_rows = db.execute(
            text(
                """
                SELECT q.course, COUNT(pr.id) AS attempts,
                       ROUND(AVG(CASE WHEN pr.is_correct IS NOT NULL THEN pr.is_correct END) * 100, 1) AS mastery
                FROM practice_records AS pr
                JOIN questions AS q ON q.id = pr.question_id
                WHERE EXISTS (
                  SELECT 1 FROM class_members AS cm
                  JOIN classes AS c ON c.id = cm.class_id
                  WHERE cm.student_id = pr.user_id AND cm.status = 'active'
                    AND c.teacher_id = :teacher_id AND c.status = 'active'
                )
                GROUP BY q.course
                ORDER BY attempts DESC, mastery ASC
                LIMIT 5
                """
            ),
            {"teacher_id": teacher_id},
        ).mappings().all()
        attention_rows = db.execute(
            text(
                """
                SELECT u.id, u.username, COUNT(pr.id) AS practice_count,
                       ROUND(AVG(CASE WHEN pr.is_correct IS NOT NULL THEN pr.is_correct END) * 100, 1) AS accuracy,
                       MAX(pr.answered_at) AS last_active
                FROM users AS u
                JOIN (
                  SELECT DISTINCT cm.student_id
                  FROM class_members AS cm JOIN classes AS c ON c.id = cm.class_id
                  WHERE c.teacher_id = :teacher_id AND c.status = 'active' AND cm.status = 'active'
                ) AS managed ON managed.student_id = u.id
                LEFT JOIN practice_records AS pr ON pr.user_id = u.id
                GROUP BY u.id, u.username
                ORDER BY (MAX(pr.answered_at) IS NULL) DESC, accuracy ASC, practice_count ASC
                LIMIT 6
                """
            ),
            {"teacher_id": teacher_id},
        ).mappings().all()
        recent_rows = db.execute(
            text(
                """
                SELECT u.username, q.course, q.knowledge_tag, pr.score, pr.is_correct, pr.answered_at
                FROM practice_records AS pr
                JOIN users AS u ON u.id = pr.user_id
                JOIN questions AS q ON q.id = pr.question_id
                WHERE EXISTS (
                  SELECT 1 FROM class_members AS cm JOIN classes AS c ON c.id = cm.class_id
                  WHERE cm.student_id = pr.user_id AND cm.status = 'active'
                    AND c.teacher_id = :teacher_id AND c.status = 'active'
                )
                ORDER BY pr.answered_at DESC
                LIMIT 8
                """
            ),
            {"teacher_id": teacher_id},
        ).mappings().all()

    by_day = {str(row["day"]): row for row in trend_rows}
    trend = []
    for offset in range(6, -1, -1):
        day = date.today() - timedelta(days=offset)
        row = by_day.get(str(day), {})
        trend.append(
            {
                "date": day.isoformat(),
                "label": f"{day.month}/{day.day}",
                "active_students": int(row.get("active_students") or 0),
                "attempts": int(row.get("attempts") or 0),
                "accuracy": float(row.get("accuracy") or 0),
            }
        )
    return {
        "summary": {
            "class_count": len(classes),
            "student_count": int(totals["students"] or 0),
            "active_today": int(totals["active_today"] or 0),
            "pending_review": int(totals["pending_review"] or 0),
            "accuracy": float(totals["accuracy"] or 0),
        },
        "classes": classes,
        "trend": trend,
        "course_mastery": [
            {"course": str(row["course"]), "attempts": int(row["attempts"] or 0), "mastery": float(row["mastery"] or 0)}
            for row in mastery_rows
        ],
        "attention_students": [
            {
                "id": int(row["id"]),
                "username": str(row["username"]),
                "practice_count": int(row["practice_count"] or 0),
                "accuracy": float(row["accuracy"] or 0),
                "last_active": row["last_active"].isoformat() if row["last_active"] else None,
            }
            for row in attention_rows
        ],
        "recent_activity": [
            {
                "username": str(row["username"]),
                "course": str(row["course"]),
                "knowledge_tag": str(row["knowledge_tag"]),
                "score": float(row["score"] or 0),
                "is_correct": bool(row["is_correct"]) if row["is_correct"] is not None else None,
                "answered_at": row["answered_at"].isoformat() if row["answered_at"] else None,
            }
            for row in recent_rows
        ],
    }


@router.get("/overview")
async def overview(current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_overview_sync, int(current["id"]))


@router.get("/classes")
async def classes(current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_classes_sync, int(current["id"]))


@router.post("/classes", status_code=status.HTTP_201_CREATED)
async def create_class(payload: ClassCreateRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_create_class_sync, int(current["id"]), payload)


@router.get("/classes/{class_id}")
async def class_detail(class_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_class_detail_sync, int(current["id"]), class_id)


@router.get("/classes/{class_id}/export")
async def export_class_members(class_id: int, current: dict[str, Any] = Depends(require_teacher)) -> Response:
    filename, content = await asyncio.to_thread(_class_export_sync, int(current["id"]), class_id)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.put("/classes/{class_id}")
async def update_class(class_id: int, payload: ClassUpdateRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_update_class_sync, int(current["id"]), class_id, payload)


@router.post("/classes/{class_id}/regenerate-invite")
async def regenerate_invite(class_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_regenerate_invite_sync, int(current["id"]), class_id)


@router.post("/classes/{class_id}/archive")
async def archive_class(class_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, bool]:
    return await asyncio.to_thread(_archive_class_sync, int(current["id"]), class_id)


@router.post("/classes/{class_id}/members")
async def add_member(class_id: int, payload: ClassMemberRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_add_member_sync, int(current["id"]), class_id, payload)


@router.delete("/classes/{class_id}/members/{student_id}")
async def remove_member(class_id: int, student_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_remove_member_sync, int(current["id"]), class_id, student_id)
