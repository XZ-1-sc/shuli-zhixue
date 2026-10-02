from urllib.parse import quote

import httpx

from .base import ObjectStorage, StorageError


class SupabaseStorage(ObjectStorage):
    def __init__(self, *, url: str, service_role_key: str, bucket: str, client: httpx.Client | None = None) -> None:
        self.url = url.rstrip("/")
        self.service_role_key = service_role_key
        self.bucket = bucket.strip()
        self.client = client or httpx.Client(timeout=60.0)

    def _object_url(self, key: str) -> str:
        return f"{self.url}/storage/v1/object/{quote(self.bucket, safe='')}/{quote(key.lstrip('/'), safe='/')}"

    def _bucket_url(self) -> str:
        return f"{self.url}/storage/v1/bucket/{quote(self.bucket, safe='')}"

    def _headers(self) -> dict[str, str]:
        return {"apikey": self.service_role_key, "Authorization": f"Bearer {self.service_role_key}"}

    def _ensure_configured(self) -> None:
        if not self.is_configured():
            raise StorageError("Supabase 文件存储配置不完整。")

    def save(self, key: str, content: bytes, mime_type: str) -> None:
        self._ensure_configured()
        try:
            response = self.client.post(
                self._object_url(key),
                headers=self._headers() | {"Content-Type": mime_type, "x-upsert": "false"},
                content=content,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise StorageError("文件上传到云存储失败。") from exc

    def read(self, key: str) -> bytes:
        self._ensure_configured()
        try:
            response = self.client.get(self._object_url(key), headers=self._headers())
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise StorageError("文件不存在。") from exc
            raise StorageError("从云存储读取文件失败。") from exc
        except httpx.HTTPError as exc:
            raise StorageError("从云存储读取文件失败。") from exc

    def delete(self, key: str) -> None:
        self._ensure_configured()
        try:
            response = self.client.delete(self._object_url(key), headers=self._headers())
            if response.status_code != 404:
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise StorageError("从云存储删除文件失败。") from exc

    def is_configured(self) -> bool:
        return bool(self.url and self.service_role_key and self.bucket)

    def check(self) -> None:
        self._ensure_configured()
        try:
            response = self.client.get(self._bucket_url(), headers=self._headers())
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise StorageError("Supabase 文件存储暂时不可用。") from exc
