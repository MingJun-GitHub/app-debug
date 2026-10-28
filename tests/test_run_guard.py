import unittest
from unittest.mock import patch

import server
from device_tools import DeviceToolError


class RunDeviceGuardTest(unittest.TestCase):
    def test_all_resource_actions_require_a_device(self):
        self.assertEqual(
            server.DEVICE_REQUIRED_ACTIONS,
            {"all", "build", "install", "launch", "log", "logs"},
        )
        self.assertNotIn("doctor", server.DEVICE_REQUIRED_ACTIONS)

    @patch("server.list_devices", return_value=[])
    def test_missing_device_is_rejected(self, _list_devices):
        with self.assertRaisesRegex(DeviceToolError, "未检测到"):
            server.require_available_device("android")

    @patch("server.list_devices")
    def test_available_selected_device_is_returned(self, list_devices):
        list_devices.return_value = [{
            "udid": "R5CT521TJEZ",
            "name": "SM S908U1",
            "available": True,
            "simulator": False,
        }]
        with server._device_lock:
            previous_ios = dict(server._selected_devices["ios"])
            previous_android = dict(server._selected_devices["android"])
        try:
            with server._device_lock:
                server._selected_devices["android"] = {
                    "udid": "R5CT521TJEZ",
                    "name": "SM S908U1",
                }
            device = server.require_available_device("android")
        finally:
            with server._device_lock:
                server._selected_devices["ios"] = previous_ios
                server._selected_devices["android"] = previous_android

        self.assertEqual(device["udid"], "R5CT521TJEZ")


if __name__ == "__main__":
    unittest.main()
