import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..api.routes.teacher import _owned_class
from ..api.teacher_schemas import ArtifactGenerateRequest, PregradeDecisionRequest, ReviewRequest
from ..database.repositories.questions import _random_questions_sync
from ..database.repositories.teacher_assignments import _grade_sync, _owned_assignment
from ..database.session import SessionLocal
from ..utils.llm_client import call_llm_json
from .analytics_service import class_dashboard_sync, common_issues_sync
from .teacher_experience_service import teacher_memory_context_sync


class TeachingArtifactPayload(BaseModel):
    headline: str = Field(min_length=1, max_length=300)
    evidence: list[str] = Field(default_factory=list, max_length=12)
    recommendations: list[str] = Field(default_factory=list, max_length=12)
    sections: list[dict[str, Any]] = Field(default_factory=list, max_length=12)
    cautions: list[str] = Field(default_factory=list, max_length=8)


class PregradePayload(BaseModel):
    suggested_score: float = Field(ge=0, le=100)
    reason: str = Field(min_length=1, max_length=2000)
    issues: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    feedback_draft: str = Field(min_length=1, max_length=3000)


ARTIFACT_TITLES = {
    "next_lesson": "下堂课建议",
    "student_consultation": "学生会诊报告",
    "remediation": "补救任务包",
    "weekly_report": "班级学情周报",
    "substitute_handoff": "代课交接包",
    "semester_review": "学期教学复盘",
    "layered_teaching": "分层教学建议",
    "cross_class": "跨班横向对比",
    "pace_review": "教学节奏诊断",
    "question_health": "题目健康度巡检",
    "breakpoint_review": "学习拐点复盘",
    "engagement_review": "真实投入度分析",
}


def _student_scope(db: Any, teacher_id: int, student_id: int) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT u.id,COALESCE(u.nickname,u.username) student,c.id class_id,c.name class_name,c.course
            FROM users u JOIN class_members cm ON cm.student_id=u.id AND cm.status='active'
            JOIN classes c ON c.id=cm.class_id AND c.teacher_id=:teacher AND c.status='active'
            WHERE u.id=:student LIMIT 1
            """
        ),
        {"teacher": teacher_id, "student": student_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="学生不存在，或不属于当前教师。")
    return dict(row)


def _snapshot_sync(teacher_id: int, payload: ArtifactGenerateRequest) -> dict[str, Any]:
    snapshot: dict[str, Any] = {"kind": payload.kind, "note": payload.note}
    if payload.kind in {"cross_class", "semester_review"} and not payload.class_id:
        with SessionLocal() as db:
            classes = db.execute(
                text("SELECT id,name,course FROM classes WHERE teacher_id=:teacher AND status='active' ORDER BY course,name"),
                {"teacher": teacher_id},
            ).mappings().all()
        snapshot["class_dashboards"] = [class_dashboard_sync(teacher_id, int(item["id"])) for item in classes]
        snapshot["teacher_classes"] = [dict(item) for item in classes]
    if payload.class_id:
        snapshot["dashboard"] = class_dashboard_sync(teacher_id, payload.class_id)
        snapshot["common_issues"] = common_issues_sync(teacher_id, payload.class_id)["items"]
    if payload.assignment_id:
        with SessionLocal() as db:
            snapshot["assignment"] = _owned_assignment(db, teacher_id, payload.assignment_id)
    if payload.student_id:
        with SessionLocal() as db:
            student = _student_scope(db, teacher_id, payload.student_id)
            rows = db.execute(
                text(
                    """
                    SELECT pr.is_correct,pr.score,pr.time_spent_seconds,pr.answered_at,pr.mistake_tags,
                           q.course,q.knowledge_tag,q.fine_tag,q.question_type
                    FROM practice_records pr JOIN questions q ON q.id=pr.question_id
                    WHERE pr.user_id=:student AND pr.mastery_evidence='formal'
                    ORDER BY pr.answered_at DESC LIMIT 300
                    """
                ),
                {"student": payload.student_id},
            ).mappings().all()
        by_tag: dict[str, list[int]] = defaultdict(list)
        reasons: Counter[str] = Counter()
        records = []
        for row in rows:
            if row["is_correct"] is not None:
                by_tag[str(row["fine_tag"] or row["knowledge_tag"])].append(int(row["is_correct"]))
            raw = row["mistake_tags"]
            if row["is_correct"] == 0:
                if isinstance(raw, str):
                    try:
                        raw = json.loads(raw)
                    except json.JSONDecodeError:
                        raw = [raw]
                reasons.update(str(item) for item in (raw or ["知识点需巩固"]))
            records.append({**dict(row), "answered_at": row["answered_at"].isoformat() if row["answered_at"] else None})
        snapshot["student"] = student
        snapshot["student_stats"] = {
            "records": records[:80],
            "weak_knowledge": sorted([{"knowledge_tag": tag, "attempts": len(values), "accuracy": round(sum(values) / len(values) * 100, 1)} for tag, values in by_tag.items()], key=lambda item: (item["accuracy"], -item["attempts"]))[:8],
            "mistake_distribution": reasons.most_common(8),
        }
    return snapshot


def _fallback_artifact(kind: str, snapshot: dict[str, Any]) -> TeachingArtifactPayload:
    dashboard = snapshot.get("dashboard") or {}
    bottom = dashboard.get("knowledge_bottom") or []
    issues = snapshot.get("common_issues") or []
    student_stats = snapshot.get("student_stats") or {}
    weak = student_stats.get("weak_knowledge") or bottom
    evidence = [f"{item.get('knowledge_tag') or item.get('name')}：正确率 {item.get('accuracy', 0):g}%，样本 {item.get('attempts', item.get('student_count', 0))}" for item in weak[:5]]
    if issues:
        evidence.extend(f"{item['fine_tag'] or item['knowledge_tag']}：{item['student_count']} 名学生共错" for item in issues[:3])
    recommendations = ["先处理样本充分且正确率最低的知识点，再用 1 分钟自测确认。", "所有建议均需教师结合课堂进度确认后执行。"]
    sections: list[dict[str, Any]] = []
    if kind == "layered_teaching":
        students = dashboard.get("student_activity") or []
        sections = [{"title": "A 组·拔高", "students": [item["student"] for item in students if item["attempts_7d"] >= 8]}, {"title": "B 组·巩固", "students": [item["student"] for item in students if 3 <= item["attempts_7d"] < 8]}, {"title": "C 组·补基础", "students": [item["student"] for item in students if item["attempts_7d"] < 3]}]
    elif kind == "pace_review":
        sections = [{"title": "当前负荷", "value": f"近 7 天覆盖 {len(dashboard.get('knowledge_mastery') or [])} 个知识点"}, {"title": "建议", "value": "优先保证薄弱点闭环，不依据不完整数据擅自删减教学内容。"}]
    elif kind == "engagement_review":
        sections = [{"title": "投入证据", "items": dashboard.get("student_activity") or []}, {"title": "解释边界", "value": "时长与时段只能作为学习行为线索，不能推断态度或心理状态。"}]
    elif kind == "question_health":
        sections = [{"title": "巡检规则", "value": "正确率 <30% 或 >95%、答案解析冲突、题干歧义。"}]
    elif kind == "cross_class":
        class_dashboards = snapshot.get("class_dashboards") or []
        sections = [
            {
                "title": item.get("class", {}).get("name", "班级"),
                "items": [
                    f"{row['knowledge_tag']}：{row['accuracy']:g}%（{row['attempts']} 次）"
                    for row in (item.get("knowledge_bottom") or [])[:5]
                ],
            }
            for item in class_dashboards
        ]
        if len(class_dashboards) < 2:
            recommendations.insert(0, "当前仅有一个具备统计权限的班级，跨班结论需等待第二个班级形成有效样本。")
    elif kind == "semester_review":
        class_dashboards = snapshot.get("class_dashboards") or []
        sections = [
            {
                "title": item.get("class", {}).get("name", "班级"),
                "value": f"覆盖 {len(item.get('knowledge_mastery') or [])} 个有作答样本的知识点，近 7 天作答 {sum(day.get('attempts', 0) for day in item.get('trend_7d') or [])} 次。",
            }
            for item in class_dashboards
        ]
    else:
        sections = [{"title": "处理顺序", "items": ["展示真实数据", "讲清第一处错误步骤", "安排变式验证", "课后查看求助信号"]}]
    return TeachingArtifactPayload(
        headline=f"{ARTIFACT_TITLES[kind]}已根据当前可核验数据生成草稿。",
        evidence=evidence or ["当前有效样本不足，建议先补充作答后再做稳定判断。"],
        recommendations=recommendations,
        sections=sections,
        cautions=["这是 AI 辅助草稿，不替代教师判断。", "不得依据投入度或相似度信号直接给学生定性。"],
    )


def generate_artifact_sync(teacher_id: int, payload: ArtifactGenerateRequest) -> dict[str, Any]:
    if payload.kind in {"next_lesson", "weekly_report", "substitute_handoff", "layered_teaching", "pace_review", "question_health"} and not payload.class_id:
        raise HTTPException(status_code=422, detail="该功能需要选择班级。")
    if payload.kind in {"student_consultation", "remediation", "breakpoint_review", "engagement_review"} and not payload.student_id:
        raise HTTPException(status_code=422, detail="该功能需要选择学生。")
    snapshot = _snapshot_sync(teacher_id, payload)
    fallback = _fallback_artifact(payload.kind, snapshot)
    artifact, usage = call_llm_json(
        [
            {"role": "system", "content": "你是教师教学决策助手。只根据给定统计给出证据、可执行建议和边界提醒。不得诊断心理状态、不得把雷同提示写成抄袭结论、不得声称已自动发布或改分。"},
            {"role": "user", "content": json.dumps({"requested_artifact": ARTIFACT_TITLES[payload.kind], "snapshot": snapshot, "teacher_memory": teacher_memory_context_sync(teacher_id)}, ensure_ascii=False, default=str)[:26000]},
        ],
        TeachingArtifactPayload,
        fallback=fallback,
        agent_name=f"teaching_{payload.kind}"[:64],
        temperature=0.2,
        max_tokens=2600,
    )
    content = artifact.model_dump()
    class_id = payload.class_id or (snapshot.get("student") or {}).get("class_id")
    title = ARTIFACT_TITLES[payload.kind]
    with SessionLocal() as db:
        result = db.execute(
            text(
                """
                INSERT INTO teaching_artifacts
                  (teacher_id,artifact_type,class_id,student_id,assignment_id,title,content_json,source_snapshot_json)
                VALUES (:teacher,:kind,:class_id,:student_id,:assignment_id,:title,:content,:snapshot)
                """
            ),
            {"teacher": teacher_id, "kind": payload.kind, "class_id": class_id, "student_id": payload.student_id, "assignment_id": payload.assignment_id, "title": title, "content": json.dumps(content, ensure_ascii=False), "snapshot": json.dumps(snapshot, ensure_ascii=False, default=str)},
        )
        artifact_id = int(result.lastrowid)
        if payload.kind == "remediation" and payload.student_id:
            weak = (snapshot.get("student_stats") or {}).get("weak_knowledge") or []
            tag = weak[0]["knowledge_tag"] if weak else None
            course = (snapshot.get("student") or {}).get("course")
            questions = _random_questions_sync(stage=None, course=course, knowledge_tag=tag, question_type=None, limit=5)
            content["remediation_questions"] = [{"id": item["id"], "question_text": item["question_text"], "difficulty": item["difficulty"]} for item in questions]
            content["remediation_target"] = {"course": course, "knowledge_tag": tag, "limit": len(questions)}
            db.execute(text("UPDATE teaching_artifacts SET content_json=:content WHERE id=:id"), {"content": json.dumps(content, ensure_ascii=False), "id": artifact_id})
        db.commit()
    return {"id": artifact_id, "type": payload.kind, "title": title, "content": content, "status": "draft", "usage": usage.model_dump()}


def artifacts_sync(teacher_id: int, artifact_type: str | None = None) -> dict[str, Any]:
    clause = " AND artifact_type=:type" if artifact_type else ""
    params: dict[str, Any] = {"teacher": teacher_id}
    if artifact_type:
        params["type"] = artifact_type
    with SessionLocal() as db:
        rows = db.execute(text(f"SELECT id,artifact_type,class_id,student_id,assignment_id,title,content_json,status,created_at,updated_at FROM teaching_artifacts WHERE teacher_id=:teacher{clause} ORDER BY updated_at DESC LIMIT 100"), params).mappings().all()
    return {"items": [{**dict(row), "id": int(row["id"]), "class_id": int(row["class_id"]) if row["class_id"] else None, "student_id": int(row["student_id"]) if row["student_id"] else None, "assignment_id": int(row["assignment_id"]) if row["assignment_id"] else None, "created_at": row["created_at"].isoformat(), "updated_at": row["updated_at"].isoformat()} for row in rows], "total": len(rows)}


def confirm_artifact_sync(teacher_id: int, artifact_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        artifact = db.execute(
            text("SELECT * FROM teaching_artifacts WHERE id=:id AND teacher_id=:teacher AND status='draft' LIMIT 1"),
            {"id": artifact_id, "teacher": teacher_id},
        ).mappings().first()
        if not artifact:
            raise HTTPException(status_code=404, detail="草稿不存在或已处理。")
        result = db.execute(text("UPDATE teaching_artifacts SET status='confirmed' WHERE id=:id AND teacher_id=:teacher AND status='draft'"), {"id": artifact_id, "teacher": teacher_id})
        if not result.rowcount:
            raise HTTPException(status_code=404, detail="草稿不存在或已处理。")
        if artifact["artifact_type"] == "remediation" and artifact["student_id"]:
            raw_content = artifact["content_json"]
            if isinstance(raw_content, str):
                try:
                    raw_content = json.loads(raw_content)
                except json.JSONDecodeError:
                    raw_content = {}
            target = (raw_content or {}).get("remediation_target") or {}
            course = target.get("course") or ""
            tag = target.get("knowledge_tag") or ""
            limit = max(1, min(5, int(target.get("limit") or 5)))
            db.execute(
                text("INSERT INTO user_notifications (user_id,type,title,content,action_url) VALUES (:student,'remediation','教师为你准备了补救任务',:content,:url)"),
                {"student": int(artifact["student_id"]), "content": f"围绕“{tag or course}”完成 {limit} 道递进练习；任务已经教师确认。", "url": f"/practice?course={course}&knowledge_tag={tag}&limit={limit}"},
            )
        db.commit()
    return {"id": artifact_id, "status": "confirmed"}


def generate_pregrade_sync(teacher_id: int, record_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT DISTINCT pr.id,pr.answer_text,pr.answer_steps,pr.score,pr.review_status,
                       q.question_text,q.standard_answer,q.analysis_text,q.solution_steps,q.knowledge_tag
                FROM practice_records pr JOIN questions q ON q.id=pr.question_id
                JOIN class_members cm ON cm.student_id=pr.user_id AND cm.status='active'
                JOIN classes c ON c.id=cm.class_id AND c.teacher_id=:teacher AND c.status='active'
                WHERE pr.id=:record LIMIT 1
                """
            ),
            {"teacher": teacher_id, "record": record_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="作答不存在或不属于当前教师。")
    base_score = float(row["score"] or 0)
    answer_length = len(str(row["answer_text"] or ""))
    suggested = base_score if row["score"] is not None else min(85.0, max(20.0, answer_length / 2))
    fallback = PregradePayload(suggested_score=suggested, reason="依据标准答案与学生可见作答形成参考分，需教师终审。", issues=[], feedback_draft="请核对第一处与标准步骤不同的位置，并补充所用定理的适用条件。")
    pregrade, usage = call_llm_json(
        [{"role": "system", "content": "你是预批改助手。只给参考分、理由、问题步骤和评语草稿；不得声称成绩已经生效。"}, {"role": "user", "content": json.dumps({"record": dict(row), "teacher_memory": teacher_memory_context_sync(teacher_id, knowledge_tag=str(row["knowledge_tag"]))}, ensure_ascii=False, default=str)[:24000]}],
        PregradePayload, fallback=fallback, agent_name="ai_pregrade", temperature=0.1, max_tokens=1500,
    )
    data = pregrade.model_dump()
    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO ai_pregrades (record_id,teacher_id,suggested_score,reason,issues_json,status)
                VALUES (:record,:teacher,:score,:reason,:issues,'draft')
                ON DUPLICATE KEY UPDATE suggested_score=VALUES(suggested_score),reason=VALUES(reason),
                  issues_json=VALUES(issues_json),status='draft',reviewed_at=NULL
                """
            ),
            {"record": record_id, "teacher": teacher_id, "score": data["suggested_score"], "reason": data["reason"], "issues": json.dumps(data["issues"], ensure_ascii=False)},
        )
        pregrade_id = int(db.execute(text("SELECT id FROM ai_pregrades WHERE record_id=:record"), {"record": record_id}).scalar())
        db.commit()
    return {"id": pregrade_id, "record_id": record_id, **data, "status": "draft", "score_applied": False, "usage": usage.model_dump()}


def decide_pregrade_sync(teacher_id: int, pregrade_id: int, payload: PregradeDecisionRequest) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.execute(text("SELECT * FROM ai_pregrades WHERE id=:id AND teacher_id=:teacher LIMIT 1"), {"id": pregrade_id, "teacher": teacher_id}).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="预批改草稿不存在。")
        if row["status"] != "draft":
            raise HTTPException(status_code=409, detail="该预批改草稿已经处理。")
        db.execute(text("UPDATE ai_pregrades SET status=:status,reviewed_at=NOW() WHERE id=:id"), {"status": payload.action, "id": pregrade_id})
        db.commit()
    if payload.action == "rejected":
        return {"id": pregrade_id, "status": "rejected", "score_applied": False}
    score = payload.score if payload.score is not None else float(row["suggested_score"])
    feedback = (payload.feedback or str(row["reason"])).strip()
    result = _grade_sync(teacher_id, int(row["record_id"]), ReviewRequest(score=score, feedback=feedback, correction_required=payload.correction_required))
    return {"id": pregrade_id, "status": "accepted", "score_applied": True, "review": result}
