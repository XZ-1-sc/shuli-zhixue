from functools import lru_cache

from ..database.session import BACKEND_DIR, settings
from .base import ObjectStorage, StorageError
from .local import LocalStorage
from .supabase import SupabaseStorage


@lru_cache(maxsize=1)
def get_storage() -> ObjectStorage:
    backend = settings.storage_backend.strip().lower()
    if backend == "local":
        return LocalStorage(settings.upload_dir, base_dir=BACKEND_DIR)
    if backend == "supabase":
        return SupabaseStorage(
            url=settings.supabase_url,
            service_role_key=settings.supabase_service_role_key,
            bucket=settings.supabase_bucket,
        )
    raise StorageError(f"不支持的文件存储类型：{settings.storage_backend}")


__all__ = ["ObjectStorage", "StorageError", "get_storage"]
