import subprocess
import tempfile
import unittest
from pathlib import Path

from project_settings import (
    apply_settings,
    default_settings,
    load_settings,
    project_info,
    settings_payload,
    update_project_path,
)


class ProjectSettingsTest(unittest.TestCase):
    def test_validates_ios_project_and_reads_git_branch(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            (project / "Sample.xcworkspace").mkdir()
            subprocess.run(["git", "init", "-b", "feature/debug-ui"], cwd=project, check=True, capture_output=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "--allow-empty", "-m", "init"],
                cwd=project,
                check=True,
                capture_output=True,
            )

            info = project_info("ios", str(project))

        self.assertTrue(info["valid"])
        self.assertEqual(info["displayName"], "Sample")
        self.assertEqual(info["git"]["branch"], "feature/debug-ui")
        self.assertEqual(info["git"]["repoName"], project.name)
        self.assertFalse(info["git"]["dirty"])

    def test_rejects_android_directory_without_gradle(self):
        with tempfile.TemporaryDirectory() as temp:
            info = project_info("android", temp)
        self.assertFalse(info["valid"])
        self.assertIn("gradlew", "；".join(info["errors"]))

    def test_saves_and_loads_project_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "ios"
            project.mkdir()
            (project / "Sample.xcodeproj").mkdir()
            config = root / "settings.json"
            settings = default_settings()

            updated, info = update_project_path(
                settings,
                "ios",
                str(project),
                config_path=config,
            )
            loaded, error = load_settings(config)
            payload = settings_payload(updated, config_path=config)

        self.assertTrue(info["valid"])
        self.assertIsNone(error)
        self.assertEqual(loaded["projects"]["ios"]["path"], str(project.resolve()))
        self.assertEqual(payload["configPath"], str(config.resolve()))

    def test_apply_settings_updates_project_and_log_paths(self):
        settings = default_settings()
        runtimes = {
            "ios": {"project": Path("/old/ios"), "log": Path("/old/ios.log")},
            "android": {"project": Path("/old/android"), "log": Path("/old/android.log")},
        }
        apply_settings(runtimes, settings)
        self.assertEqual(
            runtimes["ios"]["project"],
            Path(settings["projects"]["ios"]["path"]).expanduser().resolve(),
        )
        self.assertEqual(
            runtimes["android"]["log"],
            Path(settings["projects"]["android"]["path"]).expanduser().resolve()
            / "log"
            / "decoded.log",
        )


if __name__ == "__main__":
    unittest.main()
