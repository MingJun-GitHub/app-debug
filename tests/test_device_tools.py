import unittest
from pathlib import Path
from unittest.mock import patch

from device_tools import DeviceToolError, capture_screenshot


PNG = b"\x89PNG\r\n\x1a\n" + b"screenshot"


class DeviceScreenshotTest(unittest.TestCase):
    @patch("device_tools._run_bytes")
    def test_android_uses_adb_exec_out(self, run_bytes):
        run_bytes.return_value = PNG
        image = capture_screenshot("android", {
            "udid": "R5CT521TJEZ",
            "simulator": False,
        })

        self.assertEqual(image, PNG)
        run_bytes.assert_called_once_with(
            ["adb", "-s", "R5CT521TJEZ", "exec-out", "screencap", "-p"],
            timeout=30,
        )

    @patch("device_tools._run_text")
    def test_ios_physical_writes_devicectl_capture(self, run_text):
        def fake_run(command, timeout):
            destination = Path(command[command.index("--destination") + 1])
            destination.write_bytes(PNG)
            return ""

        run_text.side_effect = fake_run
        image = capture_screenshot("ios", {
            "udid": "device-udid",
            "simulator": False,
        })

        self.assertEqual(image, PNG)
        command = run_text.call_args.args[0]
        self.assertEqual(command[:6], [
            "xcrun", "devicectl", "device", "capture", "screenshot", "--device",
        ])
        self.assertIn("device-udid", command)

    @patch("device_tools._run_text")
    def test_ios_simulator_uses_simctl_screenshot(self, run_text):
        def fake_run(command, timeout):
            destination = Path(command[-1])
            destination.write_bytes(PNG)
            return ""

        run_text.side_effect = fake_run
        image = capture_screenshot("ios", {
            "udid": "simulator-udid",
            "simulator": True,
        })

        self.assertEqual(image, PNG)
        command = run_text.call_args.args[0]
        self.assertEqual(command[:5], [
            "xcrun", "simctl", "io", "simulator-udid", "screenshot",
        ])

    @patch("device_tools._run_bytes")
    def test_invalid_image_is_rejected(self, run_bytes):
        run_bytes.return_value = b"not-a-png"
        with self.assertRaisesRegex(DeviceToolError, "不是 PNG"):
            capture_screenshot("android", {
                "udid": "serial",
                "simulator": False,
            })

    def test_rejects_unknown_platform(self):
        with self.assertRaisesRegex(DeviceToolError, "不支持的平台"):
            capture_screenshot("windows", {"udid": "device"})


if __name__ == "__main__":
    unittest.main()
