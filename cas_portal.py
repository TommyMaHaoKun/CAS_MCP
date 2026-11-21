"""Client for the first-party forms used by the WFLA student CAS portal."""

from html import escape
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


BASE_URL = "http://101.227.232.33:8001/"
FORM_PAGES = {"record": "AddRecord", "reflection": "AddReflection"}
LIST_PAGES = {"record": "GetRecordList", "reflection": "GetReflectionList"}
SAVE_PAGES = {"record": "SaveRecord", "reflection": "SaveReflection"}

RECORD_FIELDS = {
    "Id": "id", "GroupName": "club", "ActivityDateStr": "date", "Theme": "theme",
    "CDuration": "c_hours", "ADuration": "a_hours", "SDuration": "s_hours",
    "IsConfirmStr": "confirmation",
}
REFLECTION_FIELDS = {
    "Id": "id", "GroupName": "club", "CreateTimeStr": "created_at", "Title": "title",
    "OutcomeStr": "outcomes", "EvaluateStr": "evaluation",
}


class PortalError(Exception):
    """A portal request did not complete successfully."""


class LoginRequired(PortalError):
    """The portal redirected this request to the login form."""


class SaveRejected(PortalError):
    """The portal explicitly rejected the save before reporting success."""


class CasPortal:
    def __init__(self, credentials, base_url: str = BASE_URL):
        self.credentials = credentials
        self.base_url = base_url.rstrip("/") + "/"
        self.session = requests.Session()
        # The school login is HTTP. Connect to the school directly.
        self.session.trust_env = False
        self.username = None

    def _url(self, path: str) -> str:
        return urljoin(self.base_url, path)

    def _request(self, method: str, path: str, **kwargs):
        try:
            response = self.session.request(
                method, self._url(path), timeout=(5, 15), allow_redirects=False, **kwargs
            )
        except requests.RequestException:
            raise PortalError("School portal request timed out or could not connect.") from None
        if 300 <= response.status_code < 400:
            target = urlsplit(response.headers.get("Location", "")).path.lower()
            if target == "/home/login":
                raise LoginRequired("The school session expired or login is required.")
            raise PortalError("The school portal returned an unexpected redirect.")
        if not response.ok:
            raise PortalError(f"The school portal returned HTTP {response.status_code}.")
        return response

    def _post(self, path: str, data: dict, referer: str) -> dict:
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Origin": self.base_url.rstrip("/"),
            "Referer": self._url(referer),
        }
        response = self._request("POST", path, data=data, headers=headers)
        try:
            result = response.json()
        except ValueError:
            raise PortalError("The school portal returned an unexpected response format.") from None
        if not isinstance(result, dict) or "ResultType" not in result:
            raise PortalError("The school portal response has no result code.")
        return result

    @staticmethod
    def _ok(result: dict) -> bool:
        return str(result["ResultType"]) == "0"

    def _login(self, username: str, password: str) -> None:
        self.username = None
        self.session.cookies.clear()
        login_page = "Home/Login?ReturnUrl=%2F"
        self._request("GET", login_page)
        result = self._post("Home/Login", {"code": username, "password": password}, login_page)
        if not self._ok(result):
            raise PortalError("School login was rejected. Check the saved WFLA credentials.")
        self.username = username

    def _read(self, operation):
        username, password = self.credentials()
        if self.username != username:
            self._login(username, password)
        try:
            return operation()
        except LoginRequired:
            self._login(username, password)
            return operation()

    def clubs(self, kind: str) -> dict[str, str]:
        """Map exact display names to current group IDs on the relevant add form."""
        path = f"Stu/Cas/{FORM_PAGES[kind]}"
        response = self._read(lambda: self._request("GET", path))
        html = BeautifulSoup(response.content, "html.parser")
        selector = html.select_one("select[name=GroupId]")
        if selector is None:
            raise PortalError("The school add form no longer exposes a club selector.")
        clubs = {}
        for option in selector.select("option[value]:not([disabled])"):
            value = option["value"]
            name = option.get_text(" ", strip=True)
            if value and name:
                if name in clubs and clubs[name] != value:
                    raise PortalError("The school form contains ambiguous club names.")
                clubs[name] = value
        return clubs

    def entries(self, kind: str, group_id: str, page: int, page_size: int, include_text: bool) -> dict:
        path = f"Stu/Cas/{LIST_PAGES[kind]}"
        query = {"groupId": group_id, "pageIndex": page, "pageSize": page_size}
        referer = f"Stu/Cas/{'Record' if kind == 'record' else 'Reflection'}List"
        result = self._read(lambda: self._post(path, query, referer))
        if not self._ok(result):
            raise PortalError("The school portal rejected the list request.")
        data = result.get("Data")
        if not isinstance(data, dict) or not isinstance(data.get("List"), list):
            raise PortalError("The school portal returned an unexpected list format.")
        fields = RECORD_FIELDS if kind == "record" else REFLECTION_FIELDS
        text_fields = {"Reflection": "description"} if kind == "record" else {
            "Summary": "summary", "Content": "content",
        }
        items = []
        for row in data["List"]:
            item = {local: row.get(remote) for remote, local in fields.items()}
            if include_text:
                for remote, local in text_fields.items():
                    value = row.get(remote)
                    if isinstance(value, str) and remote == "Content":
                        value = BeautifulSoup(value, "html.parser").get_text("\n", strip=True)
                    item[local] = value
            items.append(item)
        return {"total": data.get("TotalCount"), "page": page, "page_size": page_size, "entries": items}

    def save(self, kind: str, group_id: str, entry: dict) -> dict:
        """Send a single create request using the session already opened during preflight."""
        form = {"id": "0", "GroupId": group_id}
        if kind == "record":
            form.update({
                "ActivityDate": entry["date"], "Theme": entry["theme"],
                "CDuration": entry["c_hours"], "ADuration": entry["a_hours"],
                "SDuration": entry["s_hours"], "Reflection": entry["description"],
            })
        else:
            content = entry["content"].replace("\r\n", "\n").replace("\r", "\n")
            form.update({
                "Title": entry["title"], "Summary": entry["summary"],
                "Content": escape(content).replace("\n", "<br />\r\n"),
                "outcome": ",".join(entry["outcome_ids"]),
            })
        path = f"Stu/Cas/{SAVE_PAGES[kind]}"
        referer = f"Stu/Cas/{FORM_PAGES[kind]}"
        result = self._post(path, form, referer)
        if not self._ok(result):
            raise SaveRejected(str(result.get("Message") or "The school rejected this entry.")[:300])
        data = result.get("Data")
        item_id = data.get("Id") if isinstance(data, dict) else None
        return {"school_id": item_id} if isinstance(item_id, (str, int)) else {}
