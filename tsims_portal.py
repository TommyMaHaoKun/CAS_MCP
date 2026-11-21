"""Read student records and use the club application form in TSIMS."""

import re
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from cas_portal import CasPortal, LoginRequired, PortalError, SaveRejected


SCORE_PAGE = "Stu/Exam/Score"
REPORT_PAGE = "Stu/Exam/Report"
EVALUATION_PAGE = "Stu/Cas/GroupEvaluate"
CLUB_CATALOG_PAGE = "Stu/Cas/GroupList"
MY_CLUBS_PAGE = "Stu/Cas/MyGroup"

CLUB_FIELDS = {
    "Id": "id", "GroupNo": "code", "NameC": "name_zh", "NameE": "name_en",
    "CategoryName": "category", "TeacherName": "teacher", "YearName": "term",
}
CAS_HOURS_FIELDS = {
    "RecordCount": "record_count", "SumC": "c_hours", "SumA": "a_hours",
    "SumS": "s_hours", "SumCAS": "total_hours",
}
CAS_EVALUATION_FIELDS = {
    "RecLevel": "activities", "RefLevel": "reflection", "Talk": "form_teacher_evaluation",
}
PARTICIPATION_COLUMNS = {
    "Subject": "subject", "Submit Tasks On Time": "submits_tasks_on_time",
    "Active Participation": "active_participation", "Effort": "effort", "Behaviour": "behaviour",
}
TOK_COLUMNS = {"Mid": "mid", "Final": "final"}
ATTENDANCE_COLUMNS = {
    "Special Leave(d)": "special_leave_days", "Absenteeism(p)": "absence_periods", "Lateness": "lateness",
}
TIMETABLE_FIELDS = {
    "Id": "id", "ClassId": "class_id", "SubjectName": "subject", "TeacherName": "teacher",
    "ClassRoomNo": "room_number", "ClassRoomName": "room_name",
}


def fields(row: dict, mapping: dict[str, str]) -> dict:
    return {name: row.get(key) for key, name in mapping.items()}


def object_rows(value, section: str) -> list[dict]:
    rows = value.get("List") if isinstance(value, dict) else value
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise PortalError(f"TSIMS returned an unexpected {section} list.")
    return rows


def selectable_options(html: BeautifulSoup, selector: str) -> dict[str, str]:
    select = html.select_one(selector)
    if select is None:
        raise PortalError("TSIMS no longer displays the expected term or category selector.")
    return {
        option.get_text(" ", strip=True): option["value"]
        for option in select.select("option[value]:not([disabled])")
        if option["value"] and option.get_text(strip=True)
    }


def resolve_option(options: dict[str, str], label: str, kind: str) -> str:
    key = re.sub(r"\s+", "", label).casefold()
    for name in options:
        if re.sub(r"\s+", "", name).casefold() == key:
            return name
    raise ValueError(f"Unknown {kind} {label!r}. Available options: {', '.join(options)}.")


def score_value(value):
    return None if isinstance(value, str) and value.strip() in {"", "-"} else value


def report_table(html: BeautifulSoup, columns: dict[str, str]) -> list[dict]:
    for table in html.select("table"):
        headings = [cell.get_text(" ", strip=True) for cell in table.select("thead th")]
        if not columns.keys() <= set(headings):
            continue
        rows = []
        for row in table.select("tbody tr"):
            cells = row.find_all("td", recursive=False)
            if len(cells) != len(headings):
                raise PortalError("TSIMS returned an unexpected Academic Report table row.")
            values = dict(zip(headings, (score_value(cell.get_text(" ", strip=True)) for cell in cells)))
            rows.append(fields(values, columns))
        return rows
    return []


class TsimsPortal(CasPortal):
    def _page(self, path: str, params: dict | None = None) -> BeautifulSoup:
        response = self._read(lambda: self._request("GET", path, params=params))
        return BeautifulSoup(response.content, "html.parser")

    def _data(self, path: str, form: dict, referer: str):
        result = self._read(lambda: self._post(path, form, referer))
        if not self._ok(result):
            raise PortalError(str(result.get("Message") or "TSIMS rejected the query.")[:300])
        return result.get("Data")

    def _term(self, path: str, selector: str, requested: str | None) -> dict:
        options = selectable_options(self._page(path), selector)
        if not options:
            raise PortalError("TSIMS does not list any terms for this module.")
        label = resolve_option(options, requested, "term") if requested else next(iter(options))
        return {"term": label, "term_id": options[label], "available_terms": list(options)}

    def _scores(self, term_id: str, referer: str) -> list[dict]:
        rows = object_rows(self._data("Stu/Exam/GetScoreData", {"yearId": term_id}, referer), "score")
        return [
            {
                "subject": row["SubjectName"],
                "exams": [
                    {"exam": number, "score_100": score_value(row.get(f"Score{number}")),
                     "score_7": score_value(row.get(f"IbScore{number}"))}
                    for number in range(1, 5)
                ],
                "homework": score_value(row.get("ScoreH")),
                "final": score_value(row.get("ScoreF")),
                "final_level": score_value(row.get("IbScoreF")),
            }
            for row in rows
        ]

    def grades(self, term: str | None) -> dict:
        selection = self._term(SCORE_PAGE, "#ddlYear", term)
        term_id = selection["term_id"]
        tok = self._data("Stu/Exam/GetTokData", {"yearId": term_id}, SCORE_PAGE)
        published_tok = tok.get("Tok") if isinstance(tok, dict) and tok.get("ShowTok") else None
        return {
            **selection,
            "subjects": self._scores(term_id, SCORE_PAGE),
            "tok": (
                {name: score_value(published_tok.get(key)) for key, name in {"Mid": "mid", "Level": "level"}.items()}
                if isinstance(published_tok, dict) else None
            ),
        }

    def academic_report(self, term: str | None) -> dict:
        selection = self._term(REPORT_PAGE, "#ddlYear", term)
        term_id = selection["term_id"]
        params = {"yearId": term_id}
        html = self._page(REPORT_PAGE, params)
        selected = html.select_one("#ddlYear option[selected]")
        if selected is None or selected.get("value") != term_id:
            raise PortalError("TSIMS did not return the requested Academic Report term.")
        referer = f"{REPORT_PAGE}?{urlencode(params)}"
        evaluation = self._evaluation_data(term_id, referer)
        tok = report_table(html, TOK_COLUMNS)
        attendance = report_table(html, ATTENDANCE_COLUMNS)
        return {
            **selection,
            "subjects": self._scores(term_id, referer),
            "classroom_performance": report_table(html, PARTICIPATION_COLUMNS),
            "tok": tok[0] if tok else None,
            "attendance": attendance[0] if attendance else None,
            "cas": fields(evaluation, CAS_EVALUATION_FIELDS),
        }

    def timetable(self, term: str | None) -> dict:
        node = self._page("Home/StudentInfo").select_one("input[name=id]")
        student_id = node.get("value", "") if node else ""
        if not isinstance(student_id, str) or not re.fullmatch(r"[0-9]+", student_id):
            raise PortalError("TSIMS did not provide the active student's timetable identifier.")
        page = f"Stu/Timetable/Index/{student_id}"
        selection = self._term(page, "#ddlSchoolYear", term)
        term_id = selection["term_id"]
        data = self._data("Stu/Timetable/GetTimetableByStudent", {"yearId": term_id, "studentId": student_id}, page)
        if not isinstance(data, dict):
            raise PortalError("TSIMS returned an unexpected timetable.")
        weekdays = object_rows(data.get("WeekList"), "timetable weekday")
        period_rows = object_rows(data.get("TimetableList"), "timetable period")
        try:
            days = {int(day["Value"]): day["Text"] for day in weekdays}
            periods = []
            lessons = []
            for row in period_rows:
                period = int(row["LessonNumber"])
                cells = row["TimetableList"]
                if not isinstance(cells, list) or len(cells) != len(days):
                    raise ValueError("Invalid timetable row width.")
                periods.append(period)
                for weekday, cell in zip(days, cells):
                    if cell is None:
                        continue
                    if (
                        str(cell.get("YearId", 0)) not in {"0", term_id}
                        or int(cell["WeekNumber"]) != weekday
                        or int(cell["LessonNumber"]) != period
                    ):
                        raise ValueError("A timetable cell did not match its term, weekday, or period.")
                    lessons.append({
                        "weekday": days[weekday], "weekday_number": weekday, "period": period,
                        **fields(cell, TIMETABLE_FIELDS),
                    })
        except (AttributeError, KeyError, TypeError, ValueError):
            raise PortalError("TSIMS returned an invalid timetable grid for the requested term.") from None
        return {
            **selection,
            "source": self._url(page),
            "weekdays": [{"number": day, "name": name} for day, name in sorted(days.items())],
            "periods": sorted(periods),
            "lessons": sorted(lessons, key=lambda lesson: (lesson["weekday_number"], lesson["period"])),
        }

    def _category(self, page: str, category: str | None) -> tuple[str, list[str]]:
        options = selectable_options(self._page(page), "#ddlCategory")
        category_id = options[resolve_option(options, category, "club category")] if category else ""
        return category_id, list(options)

    def club_catalog(self, name: str | None, category: str | None, page: int, page_size: int) -> dict:
        category_id, categories = self._category(CLUB_CATALOG_PAGE, category)
        data = self._data("Stu/Cas/GetGroupList", {
            "name": name or "", "categoryId": category_id, "yearId": "", "page": page, "limit": page_size,
        }, CLUB_CATALOG_PAGE)
        rows = object_rows(data, "club catalog")
        return {
            "page": page, "page_size": page_size, "total": data.get("TotalCount") if isinstance(data, dict) else len(rows),
            "categories": categories,
            "clubs": [{**fields(row, CLUB_FIELDS), "joined": row.get("IsJoinGroup")} for row in rows],
        }

    def club_details(self, club_id: int) -> dict:
        page = f"Stu/Cas/GroupDetail/{club_id}"
        html = self._page(page)
        form = html.select_one("form")
        heading = form.find("div", recursive=False) if form else None
        if heading is None:
            raise PortalError("TSIMS did not return the club details page.")
        descriptions = []
        for section in heading.find_next_siblings("div"):
            if "group-title" in section.get("class", []) or section.select_one("button, input, a"):
                break
            text = section.get_text("\n", strip=True)
            if text:
                descriptions.append(text)
        join = html.select_one("#btnJoin")
        return {
            "id": club_id,
            "name": heading.get_text(" ", strip=True),
            "descriptions": descriptions,
            "can_apply": join is not None and not join.has_attr("disabled"),
            "joined": html.select_one("#btnExit") is not None,
            "can_mark_project": html.select_one("#chkProject:not([disabled])") is not None,
        }

    def apply_to_club(self, club_id: int, project: bool) -> dict:
        club = self.club_details(club_id)
        identity = {"club_id": club_id, "club": club["name"]}
        if club["joined"]:
            return {**identity, "status": "already_joined"}
        if not club["can_apply"]:
            raise SaveRejected("TSIMS is not accepting applications for this club.")
        if project and not club["can_mark_project"]:
            raise SaveRejected("TSIMS does not offer the CAS Project option for this application.")
        try:
            result = self._post("Stu/Cas/JoinGroup", {
                "groupid": club_id, "IsProject": str(project).lower(),
            }, f"Stu/Cas/GroupDetail/{club_id}")
        except LoginRequired:
            raise
        except PortalError:
            raise PortalError("The application result is unknown. Check My Clubs before retrying.") from None
        if not self._ok(result):
            raise SaveRejected(str(result.get("Message") or "TSIMS rejected the club application.")[:300])
        return {**identity, "status": "submitted", "project": project}

    def my_clubs(self, category: str | None) -> dict:
        category_id, categories = self._category(MY_CLUBS_PAGE, category)
        rows = object_rows(self._data("Stu/Cas/GetMyGroupList", {"categoryId": category_id}, MY_CLUBS_PAGE), "My Clubs")
        return {
            "categories": categories,
            "clubs": [
                {
                    **fields(row, CLUB_FIELDS),
                    "position": row.get("LeaderName"), "project": row.get("IsProject"),
                    "project_label": row.get("ProjectName"),
                }
                for row in rows
            ],
        }

    def _evaluation_data(self, term_id: str, referer: str) -> dict:
        data = self._data("Stu/Cas/GetEvaluateData", {"yearId": term_id}, referer)
        if not isinstance(data, dict):
            raise PortalError("TSIMS returned an unexpected CAS evaluation.")
        return data

    def cas_evaluation(self, term: str | None) -> dict:
        selection = self._term(EVALUATION_PAGE, "#ddlYear", term)
        data = self._evaluation_data(selection["term_id"], EVALUATION_PAGE)
        records = object_rows(data.get("GroupRecordList"), "CAS activity")
        reflections = object_rows(data.get("ReflectionList"), "CAS reflection evaluation")
        return {
            **selection,
            "clubs": [
                {**fields(row, CLUB_FIELDS), **fields(row, CAS_HOURS_FIELDS),
                 "position": row.get("LeaderName"), "project_label": row.get("ProjectName")}
                for row in records[:-1]
            ],
            "totals": fields(records[-1], CAS_HOURS_FIELDS) if records else None,
            "reflections": [
                fields(row, {
                    "Id": "id", "Title": "title", "GroupName": "club", "CreateTimeDateStr": "date",
                    "EvaluateStr": "evaluation", "Evaluate": "evaluation_value", "OutcomeStr": "learning_outcomes",
                })
                for row in reflections
            ],
            "evaluation": {**fields(data, CAS_EVALUATION_FIELDS), "overall": data.get("Final")},
        }
