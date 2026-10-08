from pathlib import Path

from .base import ObjectStorage, StorageError


class LocalStorage(ObjectStorage):
    def __init__(self, configured_root: str, *, base_dir: Path) -> None:
        root = Path(configured_root).expanduser()
        self.root = (root if root.is_absolute() else base_dir / root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if path != self.root and self.root not in path.parents:
            raise StorageError("文件存储路径无效。")
        return path

    def save(self, key: str, content: bytes, mime_type: str) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def read(self, key: str) -> bytes:
        path = self._resolve(key)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise StorageError("文件不存在。") from exc

    def delete(self, key: str) -> None:
        self._resolve(key).unlink(missing_ok=True)

    def is_configured(self) -> bool:
        return self.root.is_dir()

    def check(self) -> None:
        if not self.is_configured():
            raise StorageError("本地文件存储不可用。")
