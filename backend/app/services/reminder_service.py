from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import text

from ..database.session import SessionLocal
from .notification_service import (
    SHANGHAI,
    _create_notification_once_sync,
    _preference_enabled_sync,
    _quiet_hours,
)


def _parse_plan_due(plan_json: Any, today: date) -> str | None:
    if isinstance(plan_json, str):
        try:
            plan_json = json.loads(plan_json)
        except json.JSONDecodeError:
            return None
    candidates: list[dict[str, Any]] = []
    if isinstance(plan_json, dict):
        candidates.append(plan_json)
        for value in plan_json.values():
            if isinstance(value, list):
                candidates.extend(item for item in value if isinstance(item, dict))
    for item in candidates:
        if str(item.get("status") or "").lower() in {"done", "completed", "finished"} or item.get("completed") is True:
            continue
        raw_due = item.get("due_date") or item.get("deadline") or item.get("date")
        if not raw_due:
            continue
        try:
            due = date.fromisoformat(str(raw_due)[:10])
        except ValueError:
            continue
        if due <= today:
            return str(item.get("title") or item.get("task") or item.get("name") or "学习计划任务")
    return None


def run_daily_reminders_sync(now: datetime | None = None, *, dry_run: bool = False) -> dict[str, Any]:
    current = (now or datetime.now(SHANGHAI)).replace(tzinfo=None)
    if _quiet_hours(current):
        return {"skipped": True, "reason": "quiet_hours", "created": 0, "candidates": []}
    today = current.date()
    yesterday = today - timedelta(days=1)
    with SessionLocal() as db:
        users = db.execute(
            text("SELECT id FROM users WHERE role='student' AND status=1 ORDER BY id")
        ).scalars().all()
    candidates: list[dict[str, Any]] = []
    created = 0
    for raw_user_id in users:
        user_id = int(raw_user_id)
        if not _preference_enabled_sync(user_id):
            continue
        with SessionLocal() as db:
            activity = db.execute(
                text(
                    """
                    SELECT MAX(answered_at) AS last_activity,
                           SUM(CASE WHEN answered_at>=DATE_SUB(:now,INTERVAL 7 DAY) AND is_correct IS NOT NULL THEN 1 ELSE 0 END) AS recent_count,
                           SUM(CASE WHEN answered_at>=DATE_SUB(:now,INTERVAL 14 DAY) AND answered_at<DATE_SUB(:now,INTERVAL 7 DAY) AND is_correct IS NOT NULL THEN 1 ELSE 0 END) AS previous_count,
                           AVG(CASE WHEN answered_at>=DATE_SUB(:now,INTERVAL 7 DAY) AND is_correct IS NOT NULL THEN is_correct END) AS recent_accuracy,
                           AVG(CASE WHEN answered_at>=DATE_SUB(:now,INTERVAL 14 DAY) AND answered_at<DATE_SUB(:now,INTERVAL 7 DAY) AND is_correct IS NOT NULL THEN is_correct END) AS previous_accuracy,
                           SUM(CASE WHEN DATE(answered_at)=:yesterday AND HOUR(answered_at)>=23 THEN 1 ELSE 0 END) AS late_night_count
                    FROM practice_records WHERE user_id=:user_id
                    """
                ),
                {"user_id": user_id, "now": current, "yesterday": yesterday},
            ).mappings().first()
            plans = db.execute(
                text("SELECT plan_name,plan_json FROM learning_plans WHERE user_id=:user_id ORDER BY updated_at DESC LIMIT 10"),
                {"user_id": user_id},
            ).mappings().all()
        notices: list[tuple[str, str, str, str]] = []
        last_activity = activity["last_activity"] if activity else None
        if last_activity and (today - last_activity.date()).days >= 3:
            days = (today - last_activity.date()).days
            notices.append(("care_inactive", "小逻想和你一起热身", f"已经 {days} 天没有新的练习记录。回来做 5 道基础题，不需要一次补完所有进度。", "/practice?limit=5"))
        recent_count = int(activity["recent_count"] or 0) if activity else 0
        previous_count = int(activity["previous_count"] or 0) if activity else 0
        recent_accuracy = float(activity["recent_accuracy"] or 0) if activity else 0
        previous_accuracy = float(activity["previous_accuracy"] or 0) if activity else 0
        if recent_count >= 3 and previous_count >= 3 and previous_accuracy - recent_accuracy >= 0.1:
            decline = round((previous_accuracy - recent_accuracy) * 100, 1)
            notices.append(("care_regress", "最近正确率有些波动", f"最近一周正确率比前一周低 {decline:g} 个百分点。先别焦虑，我可以帮你定位是哪类错误变多了。", "/review"))
        if activity and int(activity["late_night_count"] or 0) > 0:
            notices.append(("care_late_night", "昨晚学习得有些晚", "昨晚 23:00 后还有做题记录。今天先保证休息，再安排短时复盘会更有效。", "/"))
        due_task = None
        for row in plans:
            due_task = _parse_plan_due(row["plan_json"], today)
            if due_task:
                break
        if due_task:
            notices.append(("plan_due", "有一项学习计划到期", f"“{due_task}”已经到期但还没有完成标记。可以先做最小的一步，再决定是否调整计划。", "/roadmap"))
        for notification_type, title, content, action_url in notices:
            candidates.append({"user_id": user_id, "type": notification_type, "title": title})
            if dry_run:
                continue
            result = _create_notification_once_sync(user_id, notification_type, title, content, action_url)
            created += int(bool(result.get("created")))
    return {"skipped": False, "created": created, "candidates": candidates, "dry_run": dry_run}
