import json
from datetime import datetime
from typing import Any

from sqlalchemy import text

from ..database.session import SessionLocal


def _trend(current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    current_scores = {str(item.get("course")): float(item.get("score") or 0) for item in current.get("course_scores") or []}
    previous_scores = {str(item.get("course")): float(item.get("score") or 0) for item in (previous or {}).get("course_scores") or []}
    changes = []
    for course, score in current_scores.items():
        if course not in previous_scores:
            continue
        delta = round(score - previous_scores[course], 1)
        changes.append({"course": course, "delta": delta, "direction": "improving" if delta >= 5 else "regressing" if delta <= -5 else "steady"})
    recent_count = int(current.get("recent_record_count") or 0)
    if not previous:
        direction = "new" if recent_count == 0 else "baseline"
    elif not changes:
        direction = "steady"
    else:
        mean_delta = sum(item["delta"] for item in changes) / len(changes)
        direction = "improving" if mean_delta >= 5 else "regressing" if mean_delta <= -5 else "steady"
    return {"direction": direction, "course_changes": changes, "record_count": recent_count}


def persist_ai_profile_sync(user_id: int, diagnosis: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.execute(text("SELECT diagnosis_json,trend_json FROM user_ai_profiles WHERE user_id=:user_id"), {"user_id": user_id}).mappings().first()
        previous = row["diagnosis_json"] if row and isinstance(row["diagnosis_json"], dict) else None
        if row and isinstance(row["diagnosis_json"], str):
            try:
                previous = json.loads(row["diagnosis_json"])
            except json.JSONDecodeError:
                previous = None
        trend = _trend(diagnosis, previous)
        advice = {"focus": [str(item.get("fine_tag") or item.get("knowledge_tag")) for item in diagnosis.get("weak_points") or []][:3]}
        db.execute(text("""
            INSERT INTO user_ai_profiles(user_id,diagnosis_json,previous_diagnosis_json,trend_json,advice_json,last_diagnosed_at)
            VALUES(:user_id,:diagnosis,:previous,:trend,:advice,:now)
            ON DUPLICATE KEY UPDATE previous_diagnosis_json=diagnosis_json,diagnosis_json=VALUES(diagnosis_json),
              trend_json=VALUES(trend_json),advice_json=VALUES(advice_json),last_diagnosed_at=VALUES(last_diagnosed_at)
        """), {"user_id": user_id, "diagnosis": json.dumps(diagnosis, ensure_ascii=False, default=str),
                 "previous": json.dumps(previous, ensure_ascii=False, default=str) if previous else None,
                 "trend": json.dumps(trend, ensure_ascii=False), "advice": json.dumps(advice, ensure_ascii=False), "now": datetime.now()})
        db.commit()
    return {"trend": trend, "previous_diagnosis": previous, "advice": advice}


def get_ai_profile_sync(user_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.execute(text("SELECT diagnosis_json,previous_diagnosis_json,trend_json,advice_json,last_diagnosed_at FROM user_ai_profiles WHERE user_id=:user_id"), {"user_id": user_id}).mappings().first()
    if not row:
        return {"trend": {"direction": "new", "course_changes": []}, "diagnosis": None, "previous_diagnosis": None, "advice": {}}
    def parse(value: Any) -> Any:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return value
    return {"diagnosis": parse(row["diagnosis_json"]), "previous_diagnosis": parse(row["previous_diagnosis_json"]),
            "trend": parse(row["trend_json"]) or {}, "advice": parse(row["advice_json"]) or {},
            "last_diagnosed_at": row["last_diagnosed_at"].isoformat() if row["last_diagnosed_at"] else None}
