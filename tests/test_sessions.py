import json
import tempfile
import unittest
from pathlib import Path

from app_debug.analysis import analyze_lines, error_fingerprint, source_locations
from app_debug.redaction import redact_data, redact_text
from app_debug.route_inventory import route_inventory
from app_debug.sessions import SessionStore


class AnalysisTest(unittest.TestCase):
    def test_groups_repeated_errors_and_extracts_sources(self):
        lines = [
            "2026-10-28 10:00:01 error: timeout request 12345",
            "/Users/me/app/Feature.swift:42",
            "2026-10-28 10:00:02 error: timeout request 98765",
            "warning: deprecated API",
        ]
        result = analyze_lines(lines)
        self.assertEqual(result["errorCount"], 2)
        self.assertEqual(result["warningCount"], 1)
        self.assertEqual(result["sourceLocations"], ["/Users/me/app/Feature.swift:42"])
        self.assertEqual(result["errorGroups"][0]["count"], 2)

    def test_fingerprint_removes_volatile_values(self):
        first = error_fingerprint("error request 12345 id 11111111-1111-1111-1111-111111111111")
        second = error_fingerprint("error request 88888 id 22222222-2222-2222-2222-222222222222")
        self.assertEqual(first, second)


class RedactionTest(unittest.TestCase):
    def test_redacts_credentials_urls_and_emails(self):
        text = (
            'Authorization: Bearer abcdefghijklmnop '
            'access_token=secret-value&q=1 '
            'email user@example.com '
            'push_token: fcm-secret '
            'jwt eyJabcdefgh.abcdefgh.abcdefgh'
        )
        redacted = redact_text(text)
        self.assertNotIn("abcdefghijklmnop", redacted)
        self.assertNotIn("secret-value", redacted)
        self.assertNotIn("user@example.com", redacted)
        self.assertNotIn("fcm-secret", redacted)
        self.assertNotIn("eyJabcdefgh", redacted)
        self.assertIn("[REDACTED", redacted)

    def test_recursively_redacts_data(self):
        payload = {
            "nested": ["password=one", {"api_key": "two"}],
            "udid": "device-identifier",
            "distinctId": "person-id",
        }
        redacted = redact_data(payload)
        self.assertNotIn("one", json.dumps(redacted))
        self.assertNotIn("two", json.dumps(redacted))
        self.assertNotIn("device-identifier", json.dumps(redacted))
        self.assertNotIn("person-id", json.dumps(redacted))

    def test_route_placeholders_are_not_redacted(self):
        text = "bloomchic://app/orders?order_token={order_token}&key={key}"
        self.assertEqual(redact_text(text), text)


class SessionStoreTest(unittest.TestCase):
    def test_persists_session_snapshot_and_diagnostic_export(self):
        with tempfile.TemporaryDirectory() as temp:
            store = SessionStore(temp)
            session = store.create(
                platform="android",
                session_id="abcdef123456",
                action="test",
                configuration="Debug",
                project={
                    "displayName": "BloomAPP",
                    "branch": "feature/test",
                    "commit": "abc123",
                    "dirty": False,
                },
                device={"name": "Pixel", "os": "16"},
                artifact={"name": "app-debug.apk"},
            )
            self.assertEqual(session["status"], "running")
            store.append_log(
                "android",
                "abcdef123456",
                "error: /src/Feature.kt:12 password=not-safe",
            )
            completed = store.complete(
                platform="android",
                session_id="abcdef123456",
                status="error",
                exit_code=1,
                elapsed=2.5,
                lines=["error: /src/Feature.kt:12 password=not-safe"],
                artifact={"name": "new.apk"},
            )
            self.assertEqual(completed["status"], "error")
            self.assertEqual(completed["analysis"]["sourceLocations"], ["/src/Feature.kt:12"])

            store.attach_snapshot(
                "android",
                "abcdef123456",
                {
                    "device": {"name": "Pixel"},
                    "app": {
                        "environment": {"name": "test", "site": "Shopify-US"},
                        "ids": {"distinctId": "user@example.com"},
                    },
                },
            )
            detail = store.get("android", "abcdef123456")
            self.assertEqual(len(detail["snapshots"]), 1)

            listed = store.list("android")
            self.assertEqual(listed[0]["id"], "abcdef123456")
            self.assertNotIn("log", listed[0])

            exported = store.export("android", "abcdef123456", "markdown")
            self.assertIn("# App Debug Diagnostic", exported["content"])
            self.assertIn("Feature.kt:12", exported["content"])
            self.assertNotIn("not-safe", exported["content"])
            self.assertNotIn("user@example.com", exported["content"])

            json_export = store.export("android", "abcdef123456", "json")
            data = json.loads(json_export["content"])
            self.assertEqual(data["id"], "abcdef123456")
            self.assertNotIn("not-safe", json_export["content"])


class RouteInventoryTest(unittest.TestCase):
    def test_reads_android_navigation_deeplinks(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            navigation = project / "app/src/main/res/navigation"
            navigation.mkdir(parents=True)
            (navigation / "main.xml").write_text(
                '<navigation xmlns:android="http://schemas.android.com/apk/res/android" '
                'xmlns:app="http://schemas.android.com/apk/res-auto">'
                '<fragment android:id="@+id/cart">'
                '<deepLink app:uri="bloomchic://app/cart" />'
                '</fragment></navigation>',
                encoding="utf-8",
            )
            inventory = route_inventory("android", str(project))
            self.assertEqual(inventory["count"], 1)
            self.assertEqual(inventory["routes"][0]["pattern"], "bloomchic://app/cart")

    def test_reads_ios_router_patterns(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            source = project / "BloomchicStore/Classes/Main"
            source.mkdir(parents=True)
            (source / "CartRouter.swift").write_text(
                'let route = Route(routePattern: "/products/:handle")\n',
                encoding="utf-8",
            )
            inventory = route_inventory("ios", str(project))
            self.assertEqual(inventory["count"], 1)
            self.assertEqual(inventory["routes"][0]["pattern"], "/products/:handle")


if __name__ == "__main__":
    unittest.main()

