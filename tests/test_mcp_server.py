import unittest
from unittest.mock import patch

import mcp_server


class McpServerTest(unittest.TestCase):
    def test_initialize_and_tool_list(self):
        initialized = mcp_server._handle({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        })
        tools = mcp_server._handle({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        })
        self.assertEqual(initialized["result"]["serverInfo"]["name"], "app-debug")
        names = {tool["name"] for tool in tools["result"]["tools"]}
        self.assertIn("start_action", names)
        self.assertIn("get_session", names)
        self.assertIn("match_route", names)
        self.assertIn("read_source", names)

    def test_guarded_action_requires_confirmation(self):
        with self.assertRaisesRegex(RuntimeError, "confirm=true"):
            mcp_server._start_action({
                "platform": "ios",
                "action": "install",
                "confirm": False,
            })

    @patch("mcp_server._json_request")
    def test_validation_action_does_not_require_confirmation(self, request):
        request.return_value = {"jobId": "job-1", "sessionId": "session-1"}
        result = mcp_server._start_action({
            "platform": "android",
            "action": "test",
        })
        self.assertEqual(result["jobId"], "job-1")

    @patch("mcp_server._json_request")
    def test_tool_response_wraps_text(self, request):
        request.return_value = {
            "sessions": [],
            "distinctId": "[REDACTED]",
        }
        response = mcp_server._handle({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "list_sessions",
                "arguments": {"platform": "ios"},
            },
        })
        self.assertFalse(response["result"]["isError"])
        self.assertEqual(response["result"]["content"][0]["type"], "text")


if __name__ == "__main__":
    unittest.main()

