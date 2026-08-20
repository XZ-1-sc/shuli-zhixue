import asyncio
import io
from typing import Any, Literal

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status

from ...database.repositories.teacher_questions import (
    _audit_question_import_preview_sync,
    _change_question_status_sync,
    _commit_question_import_sync,
    _copy_question_sync,
    _create_question_sync,
    _question_detail_sync,
    _questions_sync,
    _random_questions_sync,
    _update_question_sync,
)
from ...security import require_teacher
from ...utils.question_document_parser import QuestionDocumentError, parse_question_document
from ..teacher_schemas import QUESTION_TYPES, QuestionImportCommitRequest, QuestionWriteRequest


router = APIRouter(prefix="/api/teacher", tags=["teacher-workflow"])


@router.get("/questions")
async def questions(
    scope: Literal["all", "mine", "public"] = "all",
    search: str | None = Query(default=None, max_length=160),
    stage: str | None = Query(default=None, max_length=16),
    course: str | None = Query(default=None, max_length=128),
    question_type: str | None = Query(default=None, max_length=32),
    publish_status: str | None = Query(default=None, max_length=32),
    include_legacy: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=5, le=100),
    current: dict[str, Any] = Depends(require_teacher),
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _questions_sync,
        int(current["id"]),
        scope,
        search,
        stage,
        course,
        question_type,
        publish_status,
        include_legacy,
        page,
        page_size,
    )


@router.get("/questions/random")
async def random_questions(
    count: int = Query(default=10, ge=1, le=50),
    stage: str | None = Query(default=None, max_length=16),
    course: str | None = Query(default=None, max_length=128),
    question_type: str | None = Query(default=None, max_length=32),
    current: dict[str, Any] = Depends(require_teacher),
) -> dict[str, Any]:
    if question_type and question_type not in QUESTION_TYPES:
        raise HTTPException(status_code=422, detail="题型参数不正确。")
    return await asyncio.to_thread(_random_questions_sync, int(current["id"]), count, stage, course, question_type)


@router.get("/questions/{question_id}")
async def question_detail(question_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_question_detail_sync, int(current["id"]), question_id)


@router.post("/questions", status_code=status.HTTP_201_CREATED)
async def create_question(payload: QuestionWriteRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_create_question_sync, int(current["id"]), payload)


@router.post("/questions/{question_id}/copy", status_code=status.HTTP_201_CREATED)
async def copy_question(question_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_copy_question_sync, int(current["id"]), question_id)


@router.put("/questions/{question_id}")
async def update_question(question_id: int, payload: QuestionWriteRequest, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_update_question_sync, int(current["id"]), question_id, payload)


@router.post("/questions/{question_id}/publish")
async def publish_question(question_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_change_question_status_sync, int(current["id"]), question_id, "published")


@router.post("/questions/{question_id}/archive")
async def archive_question(question_id: int, current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    return await asyncio.to_thread(_change_question_status_sync, int(current["id"]), question_id, "archived")


async def _read_question_import(file: UploadFile) -> tuple[bytes, str]:
    filename = file.filename or "未命名文件"
    raw = await file.read(15 * 1024 * 1024 + 1)
    await file.close()
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="导入文件不能超过 15 MB。")
    if not raw:
        raise HTTPException(status_code=422, detail="上传文件为空。")
    return raw, filename


@router.get("/question-imports/template")
async def question_import_template(current: dict[str, Any] = Depends(require_teacher)) -> Response:
    del current
    rows = [
        {
            "题型": "选择题",
            "阶段": "大一",
            "课程": "高等数学（上）",
            "知识点": "函数极限",
            "细分标签": "极限运算",
            "难度": 2,
            "题干": "当 x 趋于 0 时，sin(x)/x 的极限是（ ）。",
            "选项A": "0",
            "选项B": "1",
            "选项C": "不存在",
            "选项D": "无穷大",
            "正确答案": "B",
            "标准答案": "B",
            "解析": "利用重要极限 lim(x→0) sin(x)/x = 1。",
            "关键步骤": "识别重要极限|直接代入结论",
            "常见错误": "误认为可直接代入得到 0/0",
            "错因标签": "重要极限",
            "分值": 5,
        },
        {
            "题型": "计算题",
            "阶段": "大一",
            "课程": "高等数学（上）",
            "知识点": "导数",
            "细分标签": "复合函数求导",
            "难度": 3,
            "题干": "求函数 y=sin(x²) 的导数。",
            "选项A": "",
            "选项B": "",
            "选项C": "",
            "选项D": "",
            "正确答案": "",
            "标准答案": "y'=2x cos(x²)",
            "解析": "令 u=x²，使用复合函数链式法则。",
            "关键步骤": "令 u=x²|外层求导|乘以内层导数",
            "常见错误": "遗漏内层导数 2x",
            "错因标签": "链式法则",
            "分值": 10,
        },
    ]
    buffer = io.BytesIO()
    pd.DataFrame(rows).to_excel(buffer, index=False, engine="openpyxl")
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="math-question-import-template.xlsx"'},
    )


@router.post("/question-imports/preview")
async def preview_question_import(
    file: UploadFile = File(...),
    default_stage: str = Form(default=""),
    default_course: str = Form(default=""),
    default_knowledge_tag: str = Form(default=""),
    default_fine_tag: str = Form(default=""),
    default_difficulty: int = Form(default=3),
    current: dict[str, Any] = Depends(require_teacher),
) -> dict[str, Any]:
    raw, filename = await _read_question_import(file)
    defaults = {
        "stage": default_stage,
        "course": default_course,
        "knowledge_tag": default_knowledge_tag,
        "fine_tag": default_fine_tag,
        "difficulty": max(1, min(5, default_difficulty)),
    }
    try:
        result = await asyncio.to_thread(parse_question_document, raw, filename, defaults)
    except QuestionDocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await asyncio.to_thread(
        _audit_question_import_preview_sync,
        int(current["id"]),
        filename,
        result["total_detected"],
        result["valid_count"],
    )
    return result


@router.post("/question-imports/commit", status_code=status.HTTP_201_CREATED)
async def commit_question_import(
    payload: QuestionImportCommitRequest,
    current: dict[str, Any] = Depends(require_teacher),
) -> dict[str, Any]:
    return await asyncio.to_thread(_commit_question_import_sync, int(current["id"]), payload)


@router.post("/question-imports", status_code=status.HTTP_201_CREATED)
async def import_questions(file: UploadFile = File(...), current: dict[str, Any] = Depends(require_teacher)) -> dict[str, Any]:
    """Compatibility endpoint for older clients; new clients preview before committing."""
    raw, filename = await _read_question_import(file)
    try:
        preview = await asyncio.to_thread(parse_question_document, raw, filename, {})
    except QuestionDocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    valid = [item for item in preview["questions"] if item["valid"]]
    if not valid:
        raise HTTPException(status_code=422, detail="文件中没有通过校验的题目，请使用预览导入检查错误。")
    request = QuestionImportCommitRequest(questions=valid, source_file_name=filename)
    return await asyncio.to_thread(_commit_question_import_sync, int(current["id"]), request)
