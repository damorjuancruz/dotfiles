import unittest
from datetime import date
from pathlib import Path

from collectors import jira
from lib import common

CFG = common.load_config(Path(__file__).resolve().parent.parent / "config.example.json")
ME = "acc-me"


def issue(key, summary="S", status="En curso", cat="indeterminate", assignee=ME, parent=None):
    return {"key": key, "fields": {
        "summary": summary,
        "status": {"name": status, "statusCategory": {"key": cat}},
        "assignee": {"accountId": assignee, "displayName": "Yo" if assignee == ME else "Otro"},
        "reporter": {"displayName": "R"}, "creator": {"displayName": "C"},
        "parent": {"key": parent} if parent else None,
        "issuetype": {"name": "Tarea"},
        "description": adf("Descripción " + key),
    }}


def adf(text):
    return {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]}


class FakeHttp:
    """Enruta llamadas por (método, path, fragmento de JQL)."""

    def __init__(self):
        self.calls = []

    def __call__(self, url, method="GET", headers=None, params=None, body=None, timeout=30):
        path = url.split(".net", 1)[1]
        self.calls.append((method, path, body, params))
        if path == "/rest/api/3/myself":
            return {"accountId": ME}
        if path == "/rest/api/3/search/jql":
            jql = body["jql"]
            if jql.startswith("worklogAuthor"):
                return {"issues": [issue("SUP-1", "Importador"), issue("OTRO-3", "Fuera de proyectos")], "isLast": True}
            if jql.startswith("assignee"):
                if body.get("nextPageToken") is None:
                    return {"issues": [issue("SUP-1", "Importador")], "nextPageToken": "p2"}
                return {"issues": [issue("ENG-2", "PLC")], "isLast": True}
            if jql.startswith("project in"):
                return {"issues": [issue("SUP-1"), issue("SUP-9", "Ajeno", assignee="x", status="Listo", cat="done")], "isLast": True}
            if jql.startswith("issuekey in (SUP-100"):
                return {"issues": [issue("SUP-101", "Tareas Varias - Reuniones", parent="SUP-100")], "isLast": True}
            if jql == "issuekey = SUP-77":
                return {"issues": [issue("SUP-77", "Mencionada", assignee="x")], "isLast": True}
            if jql == "issuekey = SUP-404":
                raise common.HttpError(400, url, "no existe")
            if jql.startswith("issuekey in updatedBy"):
                return {"issues": [issue("SUP-1", "Importador")], "isLast": True}
            raise AssertionError(f"JQL inesperada: {jql}")
        if path == "/rest/api/3/issue/SUP-1/worklog":
            return {"total": 3, "worklogs": [
                {"id": 1, "author": {"accountId": ME}, "started": "2026-10-05T09:07:00.000-0300", "timeSpentSeconds": 2700, "comment": adf("previo")},
                {"id": 2, "author": {"accountId": "x"}, "started": "2026-10-05T10:00:00.000-0300", "timeSpentSeconds": 600},
                {"id": 3, "author": {"accountId": ME}, "started": "2026-10-04T23:50:00.000-0300", "timeSpentSeconds": 600},
            ]}
        if path == "/rest/api/3/issue/OTRO-3/worklog":
            return {"total": 1, "worklogs": [
                {"id": 4, "author": {"accountId": ME}, "started": "2026-10-05T14:00:00.000-0300", "timeSpentSeconds": 900}]}
        if path == "/rest/api/3/issue/SUP-1/comment":
            return {"total": 1, "comments": [
                {"author": {"accountId": ME}, "created": "2026-10-05T11:00:00.000-0300", "body": adf("Resuelto el bug")}]}
        if path == "/rest/api/3/issue/SUP-1/changelog":
            return {"total": 2, "isLast": True, "values": [
                {"author": {"accountId": ME}, "created": "2026-10-05T11:05:00.000-0300",
                 "items": [{"field": "status", "fromString": "En curso", "toString": "Listo"}]},
                {"author": {"accountId": ME}, "created": "2026-10-05T09:52:00.000-0300",
                 "items": [{"field": "timespent", "fromString": "0", "toString": "2700"}]},
            ]}
        raise AssertionError(f"llamada inesperada {method} {path}")


class TestJira(unittest.TestCase):
    def setUp(self):
        self.http = FakeHttp()
        self.client = jira.JiraClient("https://x.atlassian.net", "a@b.c", "tok", http=self.http)
        self.res = jira.collect(CFG, {}, date(2026, 10, 5), ["SUP-77", "SUP-404", "SUP-1"], client=self.client)

    def test_ok(self):
        self.assertEqual(self.res["status"], "ok", self.res.get("message"))

    def test_worklogs_filtered(self):
        wl = self.res["worklogs"]
        self.assertEqual([w["id"] for w in wl], ["1", "4"])
        self.assertEqual(wl[0]["minutes"], 45)
        self.assertEqual(wl[0]["comment"], "previo")
        self.assertEqual(wl[0]["started"], "2026-10-05T09:07:00-03:00")
        self.assertEqual(wl[1]["issue"], "OTRO-3")

    def test_candidates(self):
        c = {x["key"]: x for x in self.res["candidates"]}
        self.assertEqual(set(c), {"SUP-1", "ENG-2", "SUP-9", "SUP-101", "SUP-77"})
        self.assertEqual(c["SUP-1"]["origin"], ["assigned", "recent"])
        self.assertTrue(c["SUP-1"]["assignee_me"])
        self.assertEqual(c["SUP-9"]["status_category"], "Done")
        self.assertEqual(c["SUP-101"]["parent"], "SUP-100")
        self.assertEqual(c["SUP-77"]["origin"], ["mentioned"])
        self.assertEqual(c["SUP-1"]["description"], "Descripción SUP-1")
        # las asignadas a mí van primero
        self.assertTrue(self.res["candidates"][0]["assignee_me"])

    def test_events(self):
        ev = self.res["events"]
        self.assertEqual(len(ev), 2)
        self.assertIn("Resuelto el bug", ev[0]["detail"])
        self.assertEqual(ev[1]["detail"], "status: En curso → Listo")
        self.assertEqual(ev[0]["weight"], "strong")

    def test_jql(self):
        q = jira.assigned_jql(CFG)
        self.assertIn('(project = ENG AND statusCategory not in ("Done") AND status not in ("programación finalizada"))', q)
        self.assertIn('updatedBy("acc-me", "-30d")', jira.recent_jql(CFG, ME))

    def test_pagination(self):
        assigned = [c for c in self.http.calls if c[1] == "/rest/api/3/search/jql" and c[2]["jql"].startswith("assignee")]
        self.assertEqual(len(assigned), 2)

    def test_missing_token(self):
        res = jira.collect(CFG, {}, date(2026, 10, 5))
        self.assertEqual(res["status"], "error")
        self.assertIn("JIRA_API_TOKEN", res["message"])

    def test_adf(self):
        self.assertEqual(jira.adf_to_text(adf("hola")).strip(), "hola")
        self.assertEqual(jira.adf_to_text(None), "")


if __name__ == "__main__":
    unittest.main()
