import tempfile
import unittest
from pathlib import Path

import httpx

from backend.app.storage.local import LocalStorage
from backend.app.storage.supabase import SupabaseStorage


class StorageTests(unittest.TestCase):
    def test_local_storage_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            storage = LocalStorage("uploads", base_dir=root)
            storage.save("answers/test.txt", b"hello", "text/plain")
            self.assertEqual(storage.read("answers/test.txt"), b"hello")
            storage.delete("answers/test.txt")
            self.assertFalse((root / "uploads/answers/test.txt").exists())

    def test_supabase_storage_uses_private_object_api(self) -> None:
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, content=b"stored")

        storage = SupabaseStorage(
            url="https://example.supabase.co", service_role_key="secret", bucket="private-files",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        storage.save("notes/test.txt", b"stored", "text/plain")
        self.assertEqual(storage.read("notes/test.txt"), b"stored")
        storage.delete("notes/test.txt")
        self.assertEqual([request.method for request in requests], ["POST", "GET", "DELETE"])


if __name__ == "__main__":
    unittest.main()
