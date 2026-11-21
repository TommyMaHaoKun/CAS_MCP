"""Exercise the MCP tools against a local fixture of the school's HTTP forms."""

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from mcp.shared.memory import create_connected_server_and_client_session

from cas_drafts import DraftStore
from cas_mcp import create_server
from cas_portal import CasPortal


RECORD = {
    "club": "Fixture Club", "date": "2026-11-07", "theme": "Model bridges",
    "description": "We compared two models.", "c_hours": 1.25,
}
REFLECTION = {
    "club": "Conversation", "title": "Learning through testing", "summary": "I revised my design.",
    "content": "I compared A & <B>.\n\nNext time I will measure first.", "outcomes": ["New Skills", "Challenge"],
}


class FixtureHandler(BaseHTTPRequestHandler):
    def send_body(self, data: bytes, content_type: str, cookie: str | None = None):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(data)

    def send_result(self, data=None, *, code=0, cookie=None):
        body = {"ResultType": code, "Data": data}
        self.send_body(json.dumps(body).encode(), "application/json", cookie)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/Home/Login":
            self.send_body(b"Login form", "text/html")
        elif self.headers.get("Cookie") != "fixture=active":
            self.send_response(302)
            self.send_header("Location", "/Home/Login")
            self.end_headers()
        else:
            conversation = '<option value="8">Conversation</option>' if path.endswith("AddReflection") else ""
            html = ('<select name="GroupId"><option value="">Select</option>'
                    f'<option value="7">Fixture Club</option>{conversation}</select>')
            self.send_body(html.encode(), "text/html")

    def do_POST(self):
        path = urlsplit(self.path).path
        size = int(self.headers["Content-Length"])
        form = {key: values[0] for key, values in parse_qs(
            self.rfile.read(size).decode(), keep_blank_values=True
        ).items()}
        if path == "/Home/Login":
            if form == {"code": "fixture-user", "password": "fixture-password"}:
                self.send_result({"Url": "/"}, cookie="fixture=active; Path=/")
            else:
                self.send_result(code=1)
        elif self.headers.get("Cookie") != "fixture=active":
            self.send_response(302)
            self.send_header("Location", "/Home/Login")
            self.end_headers()
        elif path.endswith(("SaveRecord", "SaveReflection")):
            self.server.writes.append((path, form))
            if self.server.lost_response == path:
                self.send_body(b"Unexpected response after accepting form", "text/html")
            else:
                self.send_result({"Id": len(self.server.writes)})
        elif path.endswith("GetRecordList"):
            self.send_result({"TotalCount": 1, "List": [
                {"Id": 1, "Theme": "Model bridges", "StudentNo": "fixture-user", "Reflection": "Draft prose"},
            ]})
        else:
            self.send_error(404)

    def log_message(self, *args):
        pass


class CasMcpTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = DraftStore(Path(self.temp.name) / "drafts.sqlite3")
        self.school = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        self.school.writes = []
        self.school.lost_response = None
        thread = threading.Thread(target=self.school.serve_forever, daemon=True, kwargs={"poll_interval": 0.01})
        thread.start()
        self.addCleanup(self.school.server_close)
        self.addCleanup(thread.join, 3)
        self.addCleanup(self.school.shutdown)
        self.portal = CasPortal(lambda: ("fixture-user", "fixture-password"),
                                f"http://127.0.0.1:{self.school.server_port}/")
        self.addCleanup(self.portal.session.close)

    async def call(self, client, name, arguments=None):
        result = await client.call_tool(name, arguments)
        self.assertFalse(result.isError, result)
        return result.structuredContent

    async def test_review_payload_and_receipts(self):
        server = create_server(self.portal, self.store)
        async with create_connected_server_and_client_session(server) as client:
            clubs = await self.call(client, "cas_list_clubs")
            self.assertEqual(clubs["reflection_clubs"], ["Fixture Club", "Conversation"])
            entries = await self.call(client, "cas_list_entries", {"kind": "record"})
            self.assertNotIn("description", entries["entries"][0])
            self.assertNotIn("StudentNo", entries["entries"][0])
            draft = await self.call(client, "cas_prepare_submission", {
                "records": [RECORD], "reflections": [REFLECTION],
            })
            self.assertEqual(self.school.writes, [])
            receipt = await self.call(client, "cas_submit", {
                "draft_id": draft["draft_id"], "confirmation": "submit_reviewed_draft",
            })
            self.assertEqual(receipt["state"], "submitted")
            self.assertEqual(self.school.writes, [
                ("/Stu/Cas/SaveRecord", {
                    "id": "0", "GroupId": "7", "ActivityDate": "2026-11-07", "Theme": "Model bridges",
                    "CDuration": "1.25", "ADuration": "0", "SDuration": "0",
                    "Reflection": "We compared two models.",
                }),
                ("/Stu/Cas/SaveReflection", {
                    "id": "0", "GroupId": "8", "Title": REFLECTION["title"], "Summary": REFLECTION["summary"],
                    "Content": "I compared A &amp; &lt;B&gt;.<br />\r\n<br />\r\nNext time I will measure first.",
                    "outcome": "2,8",
                }),
            ])
        restarted = create_server(self.portal, self.store)
        async with create_connected_server_and_client_session(restarted) as client:
            result = await self.call(client, "cas_submit", {
                "draft_id": draft["draft_id"], "confirmation": "submit_reviewed_draft",
            })
            self.assertEqual(result, receipt)
            self.assertEqual(len(self.school.writes), 2)

    async def test_missing_receipt_stops_batch_and_survives_retry(self):
        self.school.lost_response = "/Stu/Cas/SaveReflection"
        async with create_connected_server_and_client_session(create_server(self.portal, self.store)) as client:
            draft = await self.call(client, "cas_prepare_submission", {
                "records": [RECORD],
                "reflections": [REFLECTION, {**REFLECTION, "title": "Second reflection"}],
            })
            params = {"draft_id": draft["draft_id"], "confirmation": "submit_reviewed_draft"}
            result = await self.call(client, "cas_submit", params)
            self.assertEqual(result["state"], "stopped")
            self.assertEqual([item["state"] for item in result["receipts"]], ["confirmed", "unknown", "pending"])
            self.assertEqual(await self.call(client, "cas_submit", params), result)
            self.assertEqual(len(self.school.writes), 2)

    async def test_read_only_and_invalid_hours(self):
        async with create_connected_server_and_client_session(
            create_server(self.portal, self.store, read_only=True)
        ) as client:
            invalid = await client.call_tool("cas_prepare_submission", {"records": [{**RECORD, "c_hours": 0}]})
            self.assertTrue(invalid.isError)
            draft = await self.call(client, "cas_prepare_submission", {"records": [RECORD]})
            result = await client.call_tool("cas_submit", {
                "draft_id": draft["draft_id"], "confirmation": "submit_reviewed_draft",
            })
            self.assertTrue(result.isError)
            self.assertEqual(self.school.writes, [])

    async def test_draft_receipts_belong_to_school_login(self):
        server = create_server(self.portal, self.store, profile="alice")
        async with create_connected_server_and_client_session(server) as client:
            clubs = await self.call(client, "cas_list_clubs")
            self.assertEqual(clubs["profile"], "alice")
            draft = await self.call(client, "cas_prepare_submission", {"records": [RECORD]})
            self.portal.credentials = lambda: ("different-user", "fixture-password")
            status = await client.call_tool("cas_submission_status", {"draft_id": draft["draft_id"]})
            self.assertTrue(status.isError)
            self.assertEqual(self.school.writes, [])
