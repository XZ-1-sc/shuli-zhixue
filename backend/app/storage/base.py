from abc import ABC, abstractmethod


class StorageError(RuntimeError):
    """Raised when an object cannot be read from or written to storage."""


class ObjectStorage(ABC):
    @abstractmethod
    def save(self, key: str, content: bytes, mime_type: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def read(self, key: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_configured(self) -> bool:
        raise NotImplementedError
