import hashlib
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ...database.session import SessionLocal, settings
from ...security import current_session_user
from ...storage import StorageError, get_storage


router = APIRouter(prefix="/api", tags=["answer-uploads"])

MAX_FILES_PER_REQUEST = 5
MAX_NOTE_FILES_PER_REQUEST = 10
MAX_NOTE_FILE_BYTES = 20 * 1024 * 1024
MAX_NOTE_TOTAL_BYTES = 60 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
NOTE_FILE_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
}
NOTE_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ZIP_OFFICE_EXTENSIONS = {".docx", ".xlsx", ".pptx"}
LEGACY_OFFICE_EXTENSIONS = {".doc", ".xls", ".ppt"}


def _active_user_exists(user_id: int, role: str | None = None) -> bool:
    with SessionLocal() as db:
        return bool(
            db.execute(
                text("SELECT 1 FROM users WHERE id = :user_id AND (:role IS NULL OR role = :role) AND status = 1 LIMIT 1"),
                {"user_id": user_id, "role": role},
            ).first()
        )


def _normalize_image(raw: bytes) -> tuple[bytes, str, str, int, int]:
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        with Image.open(BytesIO(raw)) as probe:
            image_format = str(probe.format or "").upper()
            if image_format not in ALLOWED_FORMATS:
                raise HTTPException(status_code=415, detail="仅支持 JPEG、PNG 或 WebP 图片。")
            probe.verify()

        with Image.open(BytesIO(raw)) as source:
            image = ImageOps.exif_transpose(source)
            image.load()
            width, height = image.size
            if width < 32 or height < 32:
                raise HTTPException(status_code=422, detail="图片尺寸过小，请上传清晰的作答图片。")
            if width * height > MAX_IMAGE_PIXELS:
                raise HTTPException(status_code=413, detail="图片像素过大，请压缩后重试。")

            output = BytesIO()
            has_alpha = image.mode in {"RGBA", "LA"} or "transparency" in image.info
            if has_alpha:
                image.convert("RGBA").save(output, format="PNG", optimize=True)
                extension, mime_type = ".png", "image/png"
            else:
                image.convert("RGB").save(output, format="JPEG", quality=92, optimize=True)
                extension, mime_type = ".jpg", "image/jpeg"
            return output.getvalue(), extension, mime_type, width, height
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=415, detail="图片文件无效或已损坏。") from exc


def _store_upload(
    *,
    user_id: int,
    original_name: str,
    normalized: bytes,
    extension: str,
    mime_type: str,
    width: int,
    height: int,
    folder: str = "answers",
) -> dict[str, Any]:
    now = datetime.now()
    relative_dir = Path(folder) / f"{now:%Y}" / f"{now:%m}"
    filename = f"{uuid.uuid4().hex}{extension}"
    relative_path = relative_dir / filename
    storage_key = relative_path.as_posix()
    try:
        get_storage().save(storage_key, normalized, mime_type)
    except StorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    digest = hashlib.sha256(normalized).hexdigest()

    try:
        with SessionLocal() as db:
            result = db.execute(
                text(
                    """
                    INSERT INTO uploaded_files (
                      user_id, original_name, storage_key, mime_type, size_bytes,
                      sha256, width, height
                    )
                    VALUES (
                      :user_id, :original_name, :storage_key, :mime_type, :size_bytes,
                      :sha256, :width, :height
                    )
                    """
                ),
                {
                    "user_id": user_id,
                    "original_name": (original_name or "作答图片")[:255],
                    "storage_key": storage_key,
                    "mime_type": mime_type,
                    "size_bytes": len(normalized),
                    "sha256": digest,
                    "width": width,
                    "height": height,
                },
            )
            file_id = int(result.lastrowid)
            db.commit()
    except SQLAlchemyError as exc:
        try:
            get_storage().delete(storage_key)
        except StorageError:
            pass
        raise HTTPException(status_code=503, detail="图片记录保存失败，请稍后重试。") from exc

    return {
        "id": file_id,
        "name": original_name or "作答图片",
        "mime_type": mime_type,
        "size_bytes": len(normalized),
        "width": width,
        "height": height,
        "url": f"/api/files/{file_id}",
    }


def _prepare_note_file(raw: bytes, original_name: str) -> tuple[bytes, str, str, int, int]:
    safe_name = Path(original_name or "笔记附件").name
    extension = Path(safe_name).suffix.lower()
    if extension in NOTE_IMAGE_EXTENSIONS:
        return _normalize_image(raw)
    if extension not in NOTE_FILE_TYPES:
        raise HTTPException(
            status_code=415,
            detail="仅支持图片、PDF、Word、Excel、PPT、TXT、Markdown 或 CSV 文件。",
        )
    if extension == ".pdf" and not raw.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="PDF 文件无效或已损坏。")
    if extension in ZIP_OFFICE_EXTENSIONS and not raw.startswith(b"PK"):
        raise HTTPException(status_code=415, detail="Office 文件无效或已损坏。")
    if extension in LEGACY_OFFICE_EXTENSIONS and not raw.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        raise HTTPException(status_code=415, detail="Office 文件无效或已损坏。")
    if extension in {".txt", ".md", ".csv"} and b"\x00" in raw[:8192]:
        raise HTTPException(status_code=415, detail="文本文件包含无效内容。")
    return raw, extension, NOTE_FILE_TYPES[extension], 0, 0


@router.post("/uploads/answer-images", status_code=status.HTTP_201_CREATED)
async def upload_answer_images(
    user_id: int = Form(ge=1),
    files: list[UploadFile] = File(...),
    current: dict[str, Any] = Depends(current_session_user),
) -> dict[str, Any]:
    if current["role"] != "student" or int(current["id"]) != user_id:
        raise HTTPException(status_code=403, detail="只能为当前登录的学生账号上传作答图片。")
    if not _active_user_exists(user_id, "student"):
        raise HTTPException(status_code=404, detail="学生账号不存在或已停用。")
    if not files or len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(status_code=422, detail=f"每次最多上传 {MAX_FILES_PER_REQUEST} 张图片。")

    prepared: list[tuple[str, bytes, str, str, int, int]] = []
    for file in files:
        raw = await file.read(settings.max_answer_image_bytes + 1)
        original_name = file.filename or "作答图片"
        await file.close()
        if not raw:
            raise HTTPException(status_code=422, detail="不能上传空图片。")
        if len(raw) > settings.max_answer_image_bytes:
            raise HTTPException(status_code=413, detail="单张图片不能超过 8 MB。")
        normalized, extension, mime_type, width, height = _normalize_image(raw)
        prepared.append((original_name, normalized, extension, mime_type, width, height))

    uploaded: list[dict[str, Any]] = []
    for original_name, normalized, extension, mime_type, width, height in prepared:
        uploaded.append(
            _store_upload(
                user_id=user_id,
                original_name=original_name,
                normalized=normalized,
                extension=extension,
                mime_type=mime_type,
                width=width,
                height=height,
            )
        )
    return {"files": uploaded, "max_files": MAX_FILES_PER_REQUEST}


@router.post("/uploads/question-images", status_code=status.HTTP_201_CREATED)
async def upload_question_images(
    files: list[UploadFile] = File(...),
    current: dict[str, Any] = Depends(current_session_user),
) -> dict[str, Any]:
    if current["role"] not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="只有教师账号可以上传题目图片。")
    if not files or len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(status_code=422, detail=f"每次最多上传 {MAX_FILES_PER_REQUEST} 张图片。")
    uploaded: list[dict[str, Any]] = []
    for file in files:
        raw = await file.read(settings.max_answer_image_bytes + 1)
        original_name = file.filename or "题目图片"
        await file.close()
        if not raw:
            raise HTTPException(status_code=422, detail="不能上传空图片。")
        if len(raw) > settings.max_answer_image_bytes:
            raise HTTPException(status_code=413, detail="单张图片不能超过 8 MB。")
        normalized, extension, mime_type, width, height = _normalize_image(raw)
        uploaded.append(
            _store_upload(
                user_id=int(current["id"]), original_name=original_name, normalized=normalized,
                extension=extension, mime_type=mime_type, width=width, height=height, folder="questions",
            )
        )
    return {"files": uploaded, "max_files": MAX_FILES_PER_REQUEST}


@router.post("/uploads/message-images", status_code=status.HTTP_201_CREATED)
async def upload_message_images(
    files: list[UploadFile] = File(...),
    current: dict[str, Any] = Depends(current_session_user),
) -> dict[str, Any]:
    if current["role"] not in {"student", "teacher", "admin"}:
        raise HTTPException(status_code=403, detail="当前账号不能上传消息图片。")
    if not files or len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(status_code=422, detail=f"每次最多上传 {MAX_FILES_PER_REQUEST} 张图片。")
    uploaded: list[dict[str, Any]] = []
    for file in files:
        raw = await file.read(settings.max_answer_image_bytes + 1)
        original_name = file.filename or "消息图片"
        await file.close()
        if not raw:
            raise HTTPException(status_code=422, detail="不能上传空图片。")
        if len(raw) > settings.max_answer_image_bytes:
            raise HTTPException(status_code=413, detail="单张图片不能超过 8 MB。")
        normalized, extension, mime_type, width, height = _normalize_image(raw)
        uploaded.append(
            _store_upload(
                user_id=int(current["id"]), original_name=original_name, normalized=normalized,
                extension=extension, mime_type=mime_type, width=width, height=height, folder="messages",
            )
        )
    return {"files": uploaded, "max_files": MAX_FILES_PER_REQUEST}


@router.post("/uploads/comment-images", status_code=status.HTTP_201_CREATED)
async def upload_comment_images(
    files: list[UploadFile] = File(...),
    current: dict[str, Any] = Depends(current_session_user),
) -> dict[str, Any]:
    if current["role"] not in {"student", "teacher", "admin"}:
        raise HTTPException(status_code=403, detail="当前账号不能上传评论图片。")
    if not files or len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(status_code=422, detail=f"每次最多上传 {MAX_FILES_PER_REQUEST} 张图片。")
    uploaded: list[dict[str, Any]] = []
    for file in files:
        raw = await file.read(settings.max_answer_image_bytes + 1)
        original_name = file.filename or "评论图片"
        await file.close()
        if not raw:
            raise HTTPException(status_code=422, detail="不能上传空图片。")
        if len(raw) > settings.max_answer_image_bytes:
            raise HTTPException(status_code=413, detail="单张图片不能超过 8 MB。")
        normalized, extension, mime_type, width, height = _normalize_image(raw)
        uploaded.append(_store_upload(
            user_id=int(current["id"]), original_name=original_name, normalized=normalized,
            extension=extension, mime_type=mime_type, width=width, height=height, folder="comments",
        ))
    return {"files": uploaded, "max_files": MAX_FILES_PER_REQUEST}


@router.post("/uploads/note-files", status_code=status.HTTP_201_CREATED)
async def upload_note_files(
    user_id: int = Form(ge=1),
    files: list[UploadFile] = File(...),
    current: dict[str, Any] = Depends(current_session_user),
) -> dict[str, Any]:
    if int(current["id"]) != user_id:
        raise HTTPException(status_code=403, detail="只能为当前登录账号上传笔记附件。")
    if not _active_user_exists(user_id):
        raise HTTPException(status_code=404, detail="账号不存在或已停用。")
    if not files or len(files) > MAX_NOTE_FILES_PER_REQUEST:
        raise HTTPException(status_code=422, detail=f"每次最多上传 {MAX_NOTE_FILES_PER_REQUEST} 个附件。")

    prepared: list[tuple[str, bytes, str, str, int, int]] = []
    total_bytes = 0
    for file in files:
        raw = await file.read(MAX_NOTE_FILE_BYTES + 1)
        original_name = Path(file.filename or "笔记附件").name
        await file.close()
        if not raw:
            raise HTTPException(status_code=422, detail="不能上传空文件。")
        if len(raw) > MAX_NOTE_FILE_BYTES:
            raise HTTPException(status_code=413, detail="单个笔记附件不能超过 20 MB。")
        total_bytes += len(raw)
        if total_bytes > MAX_NOTE_TOTAL_BYTES:
            raise HTTPException(status_code=413, detail="单次上传的附件总大小不能超过 60 MB。")
        normalized, extension, mime_type, width, height = _prepare_note_file(raw, original_name)
        prepared.append((original_name, normalized, extension, mime_type, width, height))

    uploaded: list[dict[str, Any]] = []
    for original_name, normalized, extension, mime_type, width, height in prepared:
        uploaded.append(
            _store_upload(
                user_id=user_id,
                original_name=original_name,
                normalized=normalized,
                extension=extension,
                mime_type=mime_type,
                width=width,
                height=height,
                folder="notes",
            )
        )
    return {"files": uploaded, "max_files": MAX_NOTE_FILES_PER_REQUEST}


@router.get("/files/{file_id}")
async def read_uploaded_file(
    file_id: int,
    current: dict[str, Any] = Depends(current_session_user),
) -> Response:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT storage_key, original_name, mime_type, user_id
                FROM uploaded_files
                WHERE id = :file_id
                LIMIT 1
                """
            ),
            {"file_id": file_id},
        ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="文件不存在。")
    can_read = int(row["user_id"]) == int(current["id"])
    if not can_read and current["role"] in {"teacher", "admin"}:
        with SessionLocal() as db:
            can_read = bool(
                db.execute(
                    text(
                        """
                        SELECT 1 FROM class_members AS cm
                        JOIN classes AS c ON c.id=cm.class_id
                        WHERE cm.student_id=:student_id AND cm.status='active'
                          AND c.teacher_id=:teacher_id AND c.status='active' LIMIT 1
                        """
                    ),
                    {"student_id": row["user_id"], "teacher_id": current["id"]},
                ).first()
            )
    if not can_read and current["role"] == "student":
        with SessionLocal() as db:
            can_read = bool(
                db.execute(
                    text(
                        """
                        SELECT 1
                        FROM question_attachments qa
                        JOIN questions q ON q.id=qa.question_id
                        WHERE qa.uploaded_file_id=:file_id
                          AND q.deleted_at IS NULL
                          AND (
                            (q.publish_status='published' AND q.visibility='public')
                            OR EXISTS (
                              SELECT 1
                              FROM assignment_questions aq
                              JOIN assignments a ON a.id=aq.assignment_id
                              JOIN class_members cm ON cm.class_id=a.class_id
                              WHERE aq.question_id=q.id
                                AND a.status IN ('published','closed')
                                AND cm.student_id=:student_id AND cm.status='active'
                            )
                          )
                        LIMIT 1
                        """
                    ),
                    {"file_id": file_id, "student_id": current["id"]},
                ).first()
            )
    if not can_read:
        with SessionLocal() as db:
            can_read = bool(
                db.execute(
                    text(
                        """
                        SELECT 1
                        FROM messages m JOIN conversations c ON c.id=m.conversation_id
                        WHERE m.attachment_ids IS NOT NULL
                          AND JSON_CONTAINS(m.attachment_ids,:file_json,'$')
                          AND (c.participant_a=:user_id OR c.participant_b=:user_id)
                          AND (:is_teacher=0 OR c.relation='teacher_student')
                        LIMIT 1
                        """
                    ),
                    {
                        "file_json": str(file_id),
                        "user_id": int(current["id"]),
                        "is_teacher": 1 if current["role"] in {"teacher", "admin"} else 0,
                    },
                ).first()
            )
    if not can_read:
        with SessionLocal() as db:
            can_read = bool(db.execute(text("""
                SELECT 1 FROM question_comments qc
                WHERE qc.status='active' AND qc.image_ids IS NOT NULL
                  AND JSON_CONTAINS(qc.image_ids,:file_json,'$')
                  AND (
                    qc.user_id=:user_id
                    OR EXISTS (SELECT 1 FROM practice_records pr WHERE pr.question_id=qc.question_id AND pr.user_id=:user_id)
                    OR EXISTS (SELECT 1 FROM questions q WHERE q.id=qc.question_id AND q.created_by=:user_id)
                  )
                LIMIT 1
            """), {"file_json": str(file_id), "user_id": int(current["id"])}).first())
    if not can_read:
        raise HTTPException(status_code=403, detail="你没有权限查看这个文件。")

    try:
        content = get_storage().read(str(row["storage_key"]))
    except StorageError as exc:
        status_code = 404 if str(exc) == "文件不存在。" else 503
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    mime_type = str(row["mime_type"])
    disposition = "inline" if mime_type.startswith("image/") or mime_type == "application/pdf" else "attachment"
    encoded_name = quote(str(row["original_name"]), safe="")
    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Cache-Control": "private, max-age=3600",
            "Content-Disposition": f"{disposition}; filename=download; filename*=UTF-8''{encoded_name}",
        },
    )


@router.delete("/uploads/{file_id}")
async def delete_unlinked_upload(
    file_id: int,
    current: dict[str, Any] = Depends(current_session_user),
) -> dict[str, bool]:
    user_id = int(current["id"])
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT uf.storage_key
                FROM uploaded_files AS uf
                LEFT JOIN answer_attachments AS aa ON aa.uploaded_file_id = uf.id
                LEFT JOIN question_attachments AS qa ON qa.uploaded_file_id = uf.id
                LEFT JOIN note_attachments AS na ON na.uploaded_file_id = uf.id
                WHERE uf.id = :file_id AND uf.user_id = :user_id
                  AND aa.id IS NULL AND qa.id IS NULL AND na.id IS NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM messages m
                    WHERE m.attachment_ids IS NOT NULL
                      AND JSON_CONTAINS(m.attachment_ids,:file_json,'$')
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM question_comments qc
                    WHERE qc.image_ids IS NOT NULL
                      AND JSON_CONTAINS(qc.image_ids,:file_json,'$')
                  )
                LIMIT 1
                """
            ),
            {"file_id": file_id, "user_id": user_id, "file_json": str(file_id)},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=409, detail="文件不存在，或已绑定到内容记录。")
        db.execute(text("DELETE FROM uploaded_files WHERE id = :file_id"), {"file_id": file_id})
        db.commit()

    try:
        get_storage().delete(str(row["storage_key"]))
    except StorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"deleted": True}
