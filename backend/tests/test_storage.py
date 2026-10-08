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
            storage.check()
            storage.save("answers/2026/09/test.txt", b"hello", "text/plain")

            self.assertEqual(storage.read("answers/2026/09/test.txt"), b"hello")

            storage.delete("answers/2026/09/test.txt")
            self.assertFalse((root / "uploads/answers/2026/09/test.txt").exists())

    def test_supabase_storage_uses_private_object_api(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.method == "GET":
                return httpx.Response(200, content=b"stored")
            return httpx.Response(200, json={})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        storage = SupabaseStorage(
            url="https://example.supabase.co",
            service_role_key="secret",
            bucket="private-files",
            client=client,
        )

        storage.save("notes/中文.txt", b"stored", "text/plain")
        self.assertEqual(storage.read("notes/中文.txt"), b"stored")
        storage.delete("notes/中文.txt")
        storage.check()

        self.assertEqual([request.method for request in requests], ["POST", "GET", "DELETE", "GET"])
        self.assertTrue(all(request.headers["authorization"] == "Bearer secret" for request in requests))
        self.assertTrue(requests[0].url.path.endswith("/private-files/notes/中文.txt"))
        self.assertTrue(requests[-1].url.path.endswith("/storage/v1/bucket/private-files"))


if __name__ == "__main__":
    unittest.main()
