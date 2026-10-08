from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ...database.session import SessionLocal
from ...storage import StorageError, get_storage


router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "domain": "math_brain"}


@router.api_route("/ready", methods=["GET", "HEAD"])
def ready() -> dict[str, str]:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        get_storage().check()
    except (SQLAlchemyError, StorageError) as exc:
        raise HTTPException(status_code=503, detail="依赖服务暂时不可用。") from exc
    return {"status": "ready", "database": "ok", "storage": "ok"}
