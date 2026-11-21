"""Exercise the TSIMS MCP tools against fixture responses, including club writes."""

import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from mcp.shared.memory import create_connected_server_and_client_session

from cas_mcp import create_server
from cas_drafts import DraftStore
from test_cas_mcp import FixtureHandler
from tsims_portal import TsimsPortal


TERMS = {"32": "2026-2027(T1)", "31": "2025-2026(T2)", "22": "2021-2022(T1)"}
CLUB = {
    "Id": 7, "GroupNo": "AC7", "NameC": "历史社", "NameE": "History Club",
    "CategoryName": "Academic", "TeacherName": "Fixture Teacher", "YearName": "2026-2027(1)",
    "LeaderName": "Member", "IsProject": False, "ProjectName": "No", "IsJoinGroup": False,
    "LeaderMember": {"StudentId": 1234}, "RecordCount": 2, "SumC": 1, "SumA": 2, "SumS": 0, "SumCAS": 3,
}
ACTIVITY_LEVELS = {"RecLevel": 2, "RefLevel": 3, "Talk": 4, "Final": 5}


def table(headers, rows):
    headings = "".join(f"<th>{value}</th>" for value in headers)
    body = "".join("<tr>" + "".join(f"<td>{value}</td>" for value in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{headings}</tr></thead><tbody>{body}</tbody></table>"


class TsimsFixtureHandler(FixtureHandler):
    def do_GET(self):
        url = urlsplit(self.path)
        path = url.path
        if path == "/Home/Login" or self.headers.get("Cookie") != "fixture=active":
            return super().do_GET()
        self.server.reads.append((path, parse_qs(url.query)))
        if path == "/Home/StudentInfo":
            body = '<form><input name="id" value="44"></form>'
        elif path in {"/Stu/Exam/Score", "/Stu/Exam/Report", "/Stu/Cas/GroupEvaluate", "/Stu/Timetable/Index/44"}:
            selector = "ddlSchoolYear" if "/Timetable/" in path else "ddlYear"
            current = parse_qs(url.query).get("yearId", [None])[0]
            options = ['<option value="">Please select</option>']
            for term_id, label in TERMS.items():
                selected = " selected" if current == term_id else ""
                options.append(f'<option value="{term_id}"{selected}>{label}</option>')
            body = f'<select id="{selector}">' + "".join(options) + "</select>"
            if path == "/Stu/Exam/Report":
                body += table(
                    ["", "Subject", "Submit Tasks On Time", "Active Participation", "Effort", "Behaviour"],
                    [[1, "History SL", "A", "A", "B", "A"]],
                )
                body += table(["Mid", "Final"], [["B", "-"]])
                body += table(["Special Leave(d)", "Absenteeism(p)", "Lateness"], [[1.5, 2, 0]])
        elif path in {"/Stu/Cas/GroupList", "/Stu/Cas/MyGroup"}:
            body = '<select id="ddlCategory"><option value="">Please select</option><option value="5">Academic</option></select>'
        elif path in {"/Stu/Cas/GroupDetail/7", "/Stu/Cas/GroupDetail/8"}:
            club_id = int(path.rsplit("/", 1)[-1])
            body = '<form><div>历史社 (History Club)</div><div class="mgt20">Study history together.</div></form>'
            if club_id == 7:
                if self.server.joined:
                    body += '<div><button id="btnExit">Exit the club</button></div>'
                else:
                    body += '<div><input id="chkProject" type="checkbox"><button id="btnJoin">Apply to join</button></div>'
        else:
            return self.send_error(404)
        self.send_body(body.encode("utf-8"), "text/html; charset=utf-8")

    def do_POST(self):
        path = urlsplit(self.path).path
        if path == "/Home/Login" or self.headers.get("Cookie") != "fixture=active":
            return super().do_POST()
        form = {key: values[0] for key, values in parse_qs(
            self.rfile.read(int(self.headers["Content-Length"])).decode(), keep_blank_values=True
        ).items()}
        self.server.queries.append((path, form))
        if path == "/Stu/Exam/GetScoreData" and form["yearId"] in TERMS:
            self.send_result([{
                "SubjectName": "History SL", "Score1": "76", "IbScore1": "6", "Score2": "-",
                "ScoreH": "95", "ScoreF": "81" if form["yearId"] == "31" else "-", "IbScoreF": "7",
            }])
        elif path == "/Stu/Exam/GetTokData" and form["yearId"] in TERMS:
            self.send_result({"ShowTok": True, "Tok": {"Mid": "B", "Level": "-", "StudentId": 44}})
        elif path == "/Stu/Timetable/GetTimetableByStudent" and form.get("studentId") == "44":
            lesson = {
                "YearId": 0, "WeekNumber": 1, "LessonNumber": 1, "Id": 89, "ClassId": 12,
                "SubjectName": "History SL", "TeacherName": "Fixture Teacher",
                "ClassRoomNo": "A201", "ClassRoomName": "Classroom",
            }
            self.send_result({
                "WeekList": [{"Value": "1", "Text": "Monday"}, {"Value": "2", "Text": "Tuesday"}],
                "TimetableList": [
                    {"LessonNumber": "1", "TimetableList": [None if form["yearId"] == "22" else lesson, None]},
                    {"LessonNumber": "2", "TimetableList": [None, None]},
                ],
            })
        elif path == "/Stu/Cas/GetGroupList":
            self.send_result({"List": [CLUB], "TotalCount": 25})
        elif path == "/Stu/Cas/GetMyGroupList":
            self.send_result([{**CLUB, "IsJoinGroup": True}])
        elif path == "/Stu/Cas/GetEvaluateData" and form["yearId"] in TERMS:
            self.send_result({
                **ACTIVITY_LEVELS,
                "GroupRecordList": [CLUB, {
                    "RecordCount": 2, "SumC": 1, "SumA": 2, "SumS": 0, "SumCAS": 3,
                }],
                "ReflectionList": [{
                    "Id": 9, "Title": "A history activity", "GroupName": CLUB["NameC"],
                    "CreateTimeDateStr": "2026-06-12", "Evaluate": 4, "EvaluateStr": "Excellent",
                    "OutcomeStr": "New Skills", "Content": "Private draft text.",
                }],
            })
        elif path == "/Stu/Cas/JoinGroup" and form == {"groupid": "7", "IsProject": "true"}:
            self.server.joined = True
            self.server.writes.append((path, form))
            self.send_result()
        else:
            self.send_error(404)


class TsimsMcpTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.store = DraftStore(Path(scratch.name) / "drafts.sqlite3")
        self.school = ThreadingHTTPServer(("127.0.0.1", 0), TsimsFixtureHandler)
        self.school.reads = []
        self.school.queries = []
        self.school.writes = []
        self.school.joined = False
        thread = threading.Thread(target=self.school.serve_forever, daemon=True, kwargs={"poll_interval": 0.01})
        thread.start()
        self.addCleanup(self.school.server_close)
        self.addCleanup(thread.join, 3)
        self.addCleanup(self.school.shutdown)
        self.portal = TsimsPortal(
            lambda: ("fixture-user", "fixture-password"), f"http://127.0.0.1:{self.school.server_port}/"
        )
        self.addCleanup(self.portal.session.close)

    async def call(self, client, name, args=None):
        result = await client.call_tool(name, args)
        self.assertFalse(result.isError, result)
        return result.structuredContent

    async def test_grade_inquiry_and_historical_academic_report(self):
        async with create_connected_server_and_client_session(create_server(self.portal, self.store)) as client:
            invalid = await client.call_tool("tsims_get_grades", {"term": "2099-2100(T1)"})
            self.assertTrue(invalid.isError)
            self.assertIn("Available options", invalid.content[0].text)
            self.assertEqual(self.school.queries, [])

            grades = await self.call(client, "tsims_get_grades")
            self.assertEqual(grades["term"], TERMS["32"])
            self.assertEqual(grades["subjects"][0]["exams"][:2], [
                {"exam": 1, "score_100": "76", "score_7": "6"},
                {"exam": 2, "score_100": None, "score_7": None},
            ])
            self.assertEqual(grades["tok"], {"mid": "B", "level": None})
            report = await self.call(client, "tsims_get_academic_report", {"term": "2025-2026 (T2)"})
            self.assertEqual(report["term"], TERMS["31"])
            self.assertIn(("/Stu/Exam/Report", {"yearId": ["31"]}), self.school.reads)
            self.assertEqual(report["subjects"][0]["final"], "81")
            self.assertEqual(report["classroom_performance"][0]["effort"], "B")
            self.assertEqual(report["tok"], {"mid": "B", "final": None})
            self.assertEqual(report["attendance"], {"special_leave_days": "1.5", "absence_periods": "2", "lateness": "0"})
            self.assertEqual(report["cas"], {"activities": 2, "reflection": 3, "form_teacher_evaluation": 4})

    async def test_timetable_preserves_empty_slots_and_uses_the_signed_in_student(self):
        async with create_connected_server_and_client_session(create_server(self.portal, self.store)) as client:
            timetable = await self.call(client, "tsims_get_timetable")
            self.assertEqual(timetable["term"], TERMS["32"])
            self.assertEqual(timetable["periods"], [1, 2])
            self.assertEqual(timetable["weekdays"], [{"number": 1, "name": "Monday"}, {"number": 2, "name": "Tuesday"}])
            self.assertEqual(timetable["lessons"], [{
                "weekday": "Monday", "weekday_number": 1, "period": 1, "id": 89, "class_id": 12,
                "subject": "History SL", "teacher": "Fixture Teacher", "room_number": "A201", "room_name": "Classroom",
            }])
            self.assertIn(("/Stu/Timetable/GetTimetableByStudent", {"yearId": "32", "studentId": "44"}), self.school.queries)
            past = await self.call(client, "tsims_get_timetable", {"term": TERMS["22"]})
            self.assertEqual(past["lessons"], [])
            self.assertEqual(past["periods"], [1, 2])

    async def test_club_catalog_membership_and_evaluation(self):
        async with create_connected_server_and_client_session(create_server(self.portal, self.store)) as client:
            catalog = await self.call(client, "tsims_list_clubs", {
                "name": "History", "category": "academic", "page": 2, "page_size": 5,
            })
            self.assertEqual(catalog["total"], 25)
            self.assertFalse(catalog["clubs"][0]["joined"])
            self.assertNotIn("LeaderMember", catalog["clubs"][0])
            self.assertEqual(self.school.queries[-1], ("/Stu/Cas/GetGroupList", {
                "name": "History", "yearId": "", "categoryId": "5", "page": "2", "limit": "5",
            }))
            details = await self.call(client, "tsims_get_club_details", {"club_id": 7})
            self.assertTrue(details["can_apply"])
            self.assertEqual(details["descriptions"], ["Study history together."])
            memberships = await self.call(client, "tsims_list_my_clubs", {"category": "Academic"})
            self.assertEqual(memberships["clubs"][0]["position"], "Member")
            self.assertFalse(memberships["clubs"][0]["project"])
            evaluation = await self.call(client, "tsims_get_cas_evaluation", {"term": TERMS["31"]})
            self.assertEqual(evaluation["totals"]["total_hours"], 3)
            self.assertEqual(len(evaluation["clubs"]), 1)
            self.assertEqual(evaluation["reflections"][0]["evaluation"], "Excellent")
            self.assertNotIn("content", evaluation["reflections"][0])
            self.assertEqual(evaluation["evaluation"]["overall"], 5)
            self.assertEqual(self.school.writes, [])

    async def test_club_application_requires_confirmation_and_checks_membership(self):
        async with create_connected_server_and_client_session(create_server(self.portal, self.store, read_only=True)) as client:
            blocked = await client.call_tool("tsims_apply_to_club", {"club_id": 7, "confirmation": "apply_to_join"})
            self.assertTrue(blocked.isError)
            self.assertIn("read-only", blocked.content[0].text)

        async with create_connected_server_and_client_session(create_server(self.portal, self.store)) as client:
            missing = await client.call_tool("tsims_apply_to_club", {"club_id": 7})
            self.assertTrue(missing.isError)
            closed = await client.call_tool("tsims_apply_to_club", {"club_id": 8, "confirmation": "apply_to_join"})
            self.assertTrue(closed.isError)
            self.assertIn("not accepting", closed.content[0].text)
            self.assertEqual(self.school.writes, [])

            params = {"club_id": 7, "confirmation": "apply_to_join", "project": True}
            receipt = await self.call(client, "tsims_apply_to_club", params)
            self.assertEqual(receipt["status"], "submitted")
            self.assertEqual((await self.call(client, "tsims_apply_to_club", params))["status"], "already_joined")
            self.assertEqual(self.school.writes, [("/Stu/Cas/JoinGroup", {"groupid": "7", "IsProject": "true"})])
