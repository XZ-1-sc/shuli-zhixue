import unittest
from unittest.mock import patch

from aiven_auto_recovery import check_and_recover


class RecoveryTests(unittest.TestCase):
    @patch("aiven_auto_recovery.request")
    def test_only_powers_on_confirmed_off_service(self, request):
        request.side_effect = [
            {"service": {"service_type": "mysql", "plan": "free-1", "state": "POWEROFF", "powered": False}},
            {"service": {"state": "REBUILDING"}},
        ]
        self.assertEqual(check_and_recover("project", "mysql", "token"), "Power-on requested")
        self.assertEqual(request.call_args.args[0], "PUT")
        self.assertEqual(request.call_args.args[3], {"powered": True})

    @patch("aiven_auto_recovery.request")
    def test_running_service_is_not_changed(self, request):
        request.return_value = {
            "service": {"service_type": "mysql", "plan": "free-1", "state": "RUNNING", "powered": True}
        }
        self.assertEqual(check_and_recover("project", "mysql", "token"), "No action needed (RUNNING)")
        self.assertEqual(request.call_count, 1)

    @patch("aiven_auto_recovery.request")
    def test_paid_service_is_not_changed(self, request):
        request.return_value = {
            "service": {"service_type": "mysql", "plan": "business-4", "state": "POWEROFF", "powered": False}
        }
        with self.assertRaises(RuntimeError):
            check_and_recover("project", "mysql", "token")
        self.assertEqual(request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
