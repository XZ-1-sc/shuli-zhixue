from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy import text

from ..api.utils import _json_safe
from ..database.repositories.diagnosis import _diagnose_sync
from ..database.session import SessionLocal


try:
    SHANGHAI = ZoneInfo("Asia/Shanghai")
except ZoneInfoNotFoundError:
    SHANGHAI = timezone(timedelta(hours=8), name="Asia/Shanghai")
AI_NOTIFICATION_TYPES = {
    "assistant",
    "care_inactive",
    "care_regress",
    "care_late_night",
    "daily_greeting",
    "plan_due",
    "practice_followup",
    "ticket_reply",
    "ticket_student",
    "weekly_report",
}


def _now_local() -> datetime:
    return datetime.now(SHANGHAI).replace(tzinfo=None)


def _day_bounds(value: date | None = None) -> tuple[datetime, datetime]:
    target = value or _now_local().date()
    start = datetime.combine(target, time.min)
    return start, start + timedelta(days=1)


def _quiet_hours(now: datetime | None = None) -> bool:
    hour = (now or _now_local()).hour
    return hour >= 23 or hour < 7


def _notification_payload(row: Any) -> dict[str, Any]:
    content = str(row["content"] or "")
    metadata: dict[str, Any] = {}
    if content.lstrip().startswith("{"):
        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            parsed = None
        if isinstance(parsed, dict):
            metadata = parsed
            content = str(parsed.get("content") or parsed.get("message") or content)
    return {
        "id": int(row["id"]),
        "type": str(row["type"]),
        "title": str(row["title"]),
        "content": content,
        "action_url": str(row["action_url"]) if row["action_url"] else None,
        "is_read": bool(row["is_read"]),
        "created_at": _json_safe(row["created_at"]),
        "metadata": metadata,
    }


def _preference_enabled_sync(user_id: int) -> bool:
    with SessionLocal() as db:
        value = db.execute(
            text("SELECT value FROM user_preferences WHERE user_id=:user_id AND `key`='notify_xiaoluo' LIMIT 1"),
            {"user_id": user_id},
        ).scalar()
    return value is None or str(value) == "1"


def _preferences_sync(user_id: int) -> dict[str, Any]:
    return {"notify_xiaoluo": _preference_enabled_sync(user_id)}


def _save_preferences_sync(user_id: int, notify_xiaoluo: bool) -> dict[str, Any]:
    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO user_preferences (user_id, `key`, value)
                VALUES (:user_id, 'notify_xiaoluo', :value)
                ON DUPLICATE KEY UPDATE value=VALUES(value), updated_at=CURRENT_TIMESTAMP
                """
            ),
            {"user_id": user_id, "value": "1" if notify_xiaoluo else "0"},
        )
        db.commit()
    return {"notify_xiaoluo": notify_xiaoluo}


def _create_notification_once_sync(
    user_id: int,
    notification_type: str,
    title: str,
    content: str,
    action_url: str | None = None,
    *,
    target_day: date | None = None,
) -> dict[str, Any]:
    start, end = _day_bounds(target_day)
    params = {
        "user_id": user_id,
        "type": notification_type[:40],
        "title": title[:160],
        "content": content,
        "action_url": action_url,
        "start": start,
        "end": end,
    }
    with SessionLocal() as db:
        result = db.execute(
            text(
                """
                INSERT INTO user_notifications (user_id, type, title, content, action_url)
                SELECT :user_id, :type, :title, :content, :action_url FROM DUAL
                WHERE NOT EXISTS (
                  SELECT 1 FROM user_notifications
                  WHERE user_id=:user_id AND type=:type AND created_at>=:start AND created_at<:end
                )
                """
            ),
            params,
        )
        db.commit()
        row = db.execute(
            text(
                """
                SELECT id,type,title,content,action_url,is_read,created_at
                FROM user_notifications
                WHERE user_id=:user_id AND type=:type AND created_at>=:start AND created_at<:end
                ORDER BY id DESC LIMIT 1
                """
            ),
            params,
        ).mappings().first()
    return {"created": bool(result.rowcount), "notification": _notification_payload(row) if row else None}


def _notification_summary_sync(user_id: int) -> dict[str, Any]:
    enabled = _preference_enabled_sync(user_id)
    now = _now_local()
    today_start, tomorrow = _day_bounds(now.date())
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT id,type,title,content,action_url,is_read,created_at
                FROM user_notifications
                WHERE user_id=:user_id AND type IN (
                  'assistant','care_inactive','care_regress','care_late_night','daily_greeting',
                  'plan_due','practice_followup','ticket_reply','ticket_student','weekly_report'
                  ,'assignment_report','teacher_advice','teacher_message','student_message','peer_message'
                )
                ORDER BY is_read ASC, created_at DESC, id DESC LIMIT 40
                """
            ),
            {"user_id": user_id},
        ).mappings().all()
        activity = db.execute(
            text(
                """
                SELECT MAX(answered_at) AS last_activity,
                       SUM(CASE WHEN answered_at>=:today_start AND answered_at<:tomorrow THEN 1 ELSE 0 END) AS today_count
                FROM practice_records WHERE user_id=:user_id
                """
            ),
            {"user_id": user_id, "today_start": today_start, "tomorrow": tomorrow},
        ).mappings().first()
    items = [_notification_payload(row) for row in rows]
    latest = next((item for item in items if not item["is_read"]), items[0] if items else None)
    last_activity = activity["last_activity"] if activity else None
    days_inactive = (now.date() - last_activity.date()).days if last_activity else None
    quiet = _quiet_hours(now)
    message_notification_types = {"teacher_advice", "teacher_message", "student_message", "peer_message"}
    notification_unread = sum(
        1 for item in items if not item["is_read"] and item["type"] not in message_notification_types
    )
    role_row = None
    with SessionLocal() as db:
        role_row = db.execute(text("SELECT role FROM users WHERE id=:user_id"), {"user_id": user_id}).scalar()
        relation_clause = "AND c.relation='teacher_student'" if str(role_row) in {"teacher", "admin"} else ""
        message_unread = int(
            db.execute(
                text(
                    f"""
                    SELECT COUNT(*)
                    FROM messages m JOIN conversations c ON c.id=m.conversation_id
                    WHERE (c.participant_a=:user_id OR c.participant_b=:user_id)
                      AND m.sender_id<>:user_id AND m.is_read=0 {relation_clause}
                    """
                ),
                {"user_id": user_id},
            ).scalar()
            or 0
        )
    # 消息未读以统一消息表为准；对应通知只承担提示与跳转，避免同一事件重复计数。
    unread_count = notification_unread + message_unread
    return {
        "unread_count": unread_count,
        "message_unread_count": message_unread,
        "latest": latest,
        "preference": {"notify_xiaoluo": enabled},
        "activity": {
            "has_records": last_activity is not None,
            "today_learned": bool(activity and int(activity["today_count"] or 0) > 0),
            "today_count": int(activity["today_count"] or 0) if activity else 0,
            "last_activity": _json_safe(last_activity),
            "days_inactive": days_inactive,
        },
        "quiet_hours": quiet,
        "should_nudge": bool(enabled and not quiet and unread_count and latest),
    }


def _mark_notification_read_sync(user_id: int, notification_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        result = db.execute(
            text("UPDATE user_notifications SET is_read=1 WHERE id=:id AND user_id=:user_id"),
            {"id": notification_id, "user_id": user_id},
        )
        db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="通知不存在或不属于当前账号。")
    return {"read": True, "id": notification_id}


def _daily_greeting_sync(user_id: int) -> dict[str, Any]:
    now = _now_local()
    if _quiet_hours(now):
        return {"created": False, "reason": "quiet_hours", "notification": None}
    if not _preference_enabled_sync(user_id):
        return {"created": False, "reason": "disabled", "notification": None}
    today_start, tomorrow = _day_bounds(now.date())
    yesterday_start, _ = _day_bounds(now.date() - timedelta(days=1))
    week_start = today_start - timedelta(days=7)
    previous_start = week_start - timedelta(days=7)
    with SessionLocal() as db:
        stats = db.execute(
            text(
                """
                SELECT
                  SUM(CASE WHEN answered_at>=:today_start AND answered_at<:tomorrow THEN 1 ELSE 0 END) AS today_total,
                  SUM(CASE WHEN answered_at>=:yesterday_start AND answered_at<:today_start THEN 1 ELSE 0 END) AS yesterday_total,
                  ROUND(AVG(CASE WHEN answered_at>=:yesterday_start AND answered_at<:today_start AND is_correct IS NOT NULL THEN is_correct END)*100,1) AS yesterday_accuracy,
                  ROUND(AVG(CASE WHEN answered_at>=:week_start AND is_correct IS NOT NULL THEN is_correct END)*100,1) AS week_accuracy,
                  ROUND(AVG(CASE WHEN answered_at>=:previous_start AND answered_at<:week_start AND is_correct IS NOT NULL THEN is_correct END)*100,1) AS previous_accuracy,
                  COUNT(*) AS all_total
                FROM practice_records WHERE user_id=:user_id
                """
            ),
            {
                "user_id": user_id,
                "today_start": today_start,
                "tomorrow": tomorrow,
                "yesterday_start": yesterday_start,
                "week_start": week_start,
                "previous_start": previous_start,
            },
        ).mappings().first()
    if not stats or int(stats["all_total"] or 0) == 0:
        return {"created": False, "reason": "new_account", "notification": None}
    diagnosis = _diagnose_sync(user_id)
    weak = (diagnosis.get("weak_points") or [{}])[0]
    focus_course = str(weak.get("course") or "当前课程")
    focus = str(weak.get("fine_tag") or weak.get("knowledge_tag") or "基础题")
    if now.hour < 12:
        yesterday_accuracy = float(stats["yesterday_accuracy"] or 0)
        content = f"早上好，今天先攻 {focus_course}。昨天正确率 {yesterday_accuracy:g}%，建议用“{focus}”做热身。"
        title = "小逻的早安学习播报"
    else:
        today_total = int(stats["today_total"] or 0)
        week_accuracy = float(stats["week_accuracy"] or 0)
        previous = stats["previous_accuracy"]
        change = week_accuracy - float(previous) if previous is not None else 0
        trend = f"比上周{'提升' if change >= 0 else '下降'} {abs(change):g} 个百分点" if previous is not None else "正在建立本周基线"
        content = f"今天完成 {today_total} 题，本周正确率 {week_accuracy:g}%，{trend}。明天建议继续补强“{focus}”。"
        title = "小逻的晚间学习播报"
    return _create_notification_once_sync(user_id, "daily_greeting", title, content, "/")


def _teacher_tickets_sync(teacher_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT id,type,title,content,action_url,is_read,created_at
                FROM user_notifications
                WHERE user_id=:teacher_id AND type='ticket_student'
                ORDER BY is_read ASC, created_at DESC, id DESC LIMIT 30
                """
            ),
            {"teacher_id": teacher_id},
        ).mappings().all()
    return {"items": [_notification_payload(row) for row in rows]}


def _reply_ticket_sync(teacher_id: int, ticket_id: int, content: str) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT id,content FROM user_notifications
                WHERE id=:ticket_id AND user_id=:teacher_id AND type='ticket_student' LIMIT 1
                """
            ),
            {"ticket_id": ticket_id, "teacher_id": teacher_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="该工单不属于当前教师。")
        try:
            metadata = json.loads(str(row["content"]))
        except (json.JSONDecodeError, TypeError):
            metadata = {}
        student_id = int(metadata.get("student_id") or 0)
        if not student_id:
            raise HTTPException(status_code=409, detail="工单缺少学生关联信息。")
        reply_payload = json.dumps(
            {"content": content, "teacher_id": teacher_id, "ticket_id": ticket_id}, ensure_ascii=False
        )
        db.execute(
            text(
                """
                INSERT INTO user_notifications (user_id,type,title,content,action_url)
                VALUES (:student_id,'ticket_reply','教师回复了你的小逻工单',:content,'/messages')
                """
            ),
            {"student_id": student_id, "content": reply_payload},
        )
        db.execute(
            text("UPDATE user_notifications SET is_read=1 WHERE id=:ticket_id AND user_id=:teacher_id"),
            {"ticket_id": ticket_id, "teacher_id": teacher_id},
        )
        db.commit()
    return {"replied": True, "ticket_id": ticket_id, "student_id": student_id}
