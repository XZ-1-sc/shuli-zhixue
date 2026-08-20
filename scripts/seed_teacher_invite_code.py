import hashlib

from sqlalchemy import text

from backend.app.database.session import SessionLocal, settings


def main() -> None:
    invite_code = settings.teacher_invite_code.strip()
    if not invite_code:
        raise SystemExit("TEACHER_INVITE_CODE 未配置，未写入邀请码。")

    code_hash = hashlib.sha256(invite_code.encode("utf-8")).hexdigest()
    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO teacher_invite_codes (code_hash, label)
                VALUES (:code_hash, :label)
                ON DUPLICATE KEY UPDATE label = VALUES(label), updated_at = CURRENT_TIMESTAMP
                """
            ),
            {"code_hash": code_hash, "label": "由原 TEACHER_INVITE_CODE 迁移"},
        )
        db.commit()
    print("教师邀请码已安全散列并写入 teacher_invite_codes。")


if __name__ == "__main__":
    main()
