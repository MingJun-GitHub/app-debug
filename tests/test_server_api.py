import json
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

import server
from app_debug.sessions import SessionStore


class ServerSessionApiTest(unittest.TestCase):
    def test_session_list_snapshot_and_export(self):
        with tempfile.TemporaryDirectory() as temp:
            previous_store = server._sessions
            store = SessionStore(temp)
            server._sessions = store
            store.create(
                platform="ios",
                session_id="session123456",
                action="lint",
                configuration="Debug",
                project={"displayName": "BloomchicStore", "commit": "abc"},
                device={"name": "iPhone"},
                artifact={"name": "BloomchicStore.app"},
            )
            store.append_log(
                "ios",
                "session123456",
                "error: /src/Feature.swift:9 access_token=secret",
            )
            store.complete(
                platform="ios",
                session_id="session123456",
                status="error",
                exit_code=1,
                elapsed=1.2,
                lines=["error: /src/Feature.swift:9 access_token=secret"],
            )
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{httpd.server_port}"
            try:
                with urllib.request.urlopen(f"{base}/api/ios/sessions") as response:
                    listed = json.loads(response.read())
                self.assertEqual(listed["sessions"][0]["id"], "session123456")

                payload = json.dumps({
                    "context": {
                        "app": {
                            "environment": {"name": "test", "site": "Shopify-US"},
                            "ids": {"distinctId": "person@example.com"},
                        }
                    }
                }).encode()
                request = urllib.request.Request(
                    f"{base}/api/ios/sessions/session123456/snapshot",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request) as response:
                    snapshot = json.loads(response.read())
                self.assertEqual(len(snapshot["session"]["snapshots"]), 1)

                with urllib.request.urlopen(
                    f"{base}/api/ios/sessions/session123456/export?format=markdown"
                ) as response:
                    exported = json.loads(response.read())
                self.assertIn("# App Debug Diagnostic", exported["content"])
                self.assertNotIn("secret", exported["content"])
                self.assertNotIn("person@example.com", exported["content"])
            finally:
                httpd.shutdown()
                httpd.server_close()
                server._sessions = previous_store


if __name__ == "__main__":
    unittest.main()

