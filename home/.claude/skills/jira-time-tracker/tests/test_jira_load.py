"""Carga en Jira por script (`plan.py load`) con un Jira falso."""

import copy
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

import plan as P
from lib import common, jira_load

from tests.test_plan import CFG, DIGEST, NO_RAW, confirmed_plan


class FakeJira:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on
        self.n = 0

    def __call__(self, url, method="GET", headers=None, params=None, body=None, timeout=30):
        path = url.split(".net", 1)[-1] if ".net" in url else url
        self.calls.append((method, path, body))
        if self.fail_on and self.fail_on(method, path):
            raise common.HttpError(400, url, '{"errorMessages":["no se puede"]}')
        if path.endswith("/issuetypes") and method == "GET":
            return {"issueTypes": [{"id": "10", "name": "Tarea"}]}
        if "/issuetypes/10" in path:
            return {"fields": [{"fieldId": "description", "schema": {"type": "string", "system": "description"}},
                               {"fieldId": "reporter", "schema": {"type": "user"}},
                               {"fieldId": "customfield_1", "schema": {"type": "option"}}]}
        if path.startswith("/rest/api/3/user/search"):
            return [{"accountId": "acc-h", "displayName": "Héctor Molina", "accountType": "atlassian"},
                    {"accountId": "qm:1", "displayName": "Héctor Molina", "accountType": "customer"}]
        if method == "POST" and path == "/rest/api/3/issue":
            return {"key": "SUP-900"}
        if method in ("POST", "PUT") and "/worklog" in path:
            self.n += 1
            return {"id": str(1000 + self.n)}
        return {}


def load_plan():
    p = confirmed_plan()
    p["modes"] = {"group": False, "lunch": False}
    p["new_issues"] = [{"ref": "NEW-1", "project": "SUP", "type": "Tarea", "summary": "Alta", "decision": "create",
                        "fields": [{"key": "description", "value": "- uno\n- dos"},
                                   {"key": "reporter", "value": "Héctor Molina"},
                                   {"key": "customfield_1", "value": "IEA"}]}]
    p["blocks"][1]["issue"] = "NEW-1"
    p["followup"] = {"SUP-1": {"transition_id": "31", "to": "Resuelto", "fields": {"resolution": "Listo"},
                               "comment": "Se corrigió.", "publish": True}}
    p["round"] = 2
    p["load_approved"] = 2
    P.ensure_ids(p)
    return p


class TestJiraLoad(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.plan_path = self.dir / "plan.json"

    def tearDown(self):
        self.tmp.cleanup()

    def run_load(self, plan, fake):
        writer = jira_load.Writer("https://x.atlassian.net", "a@b.c", "t", http=fake)
        common.write_json(self.plan_path, plan)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = P.cmd_load(plan, self.plan_path, copy.deepcopy(DIGEST), CFG, NO_RAW, date(2026, 10, 5),
                              writer=writer, env={"JIRA_API_TOKEN": "t"})
        return code, buf.getvalue()

    def test_full_load(self):
        fake = FakeJira()
        code, out = self.run_load(load_plan(), fake)
        self.assertEqual(code, 0, out)
        self.assertIn("✓ crear NEW-1 → SUP-900", out)
        create = next(b for m, p, b in fake.calls if m == "POST" and p == "/rest/api/3/issue")
        f = create["fields"]
        self.assertEqual(f["reporter"], {"accountId": "acc-h"})       # no el cliente qm:
        self.assertEqual(f["customfield_1"], {"value": "IEA"})
        self.assertEqual(f["description"]["content"][0]["type"], "bulletList")
        self.assertEqual(f["assignee"], {"accountId": CFG["jira"]["account_id"]})
        wl = [(m, p) for m, p, _ in fake.calls if "/worklog" in p and m in ("POST", "PUT")]
        self.assertEqual(len(wl), 4)
        self.assertIn(("PUT", "/rest/api/3/issue/SUP-5/worklog/900"), wl)
        self.assertIn(("POST", "/rest/api/3/issue/SUP-900/worklog"), wl)
        tr = next(b for m, p, b in fake.calls if p.endswith("/transitions"))
        self.assertEqual(tr, {"transition": {"id": "31"}, "fields": {"resolution": {"name": "Listo"}}})
        saved = common.read_json(self.plan_path)
        self.assertEqual(saved["created"], ["SUP-900"])
        self.assertNotIn("NEW-1", [b["issue"] for b in saved["blocks"]])

    def test_stops_and_resumes(self):
        fake = FakeJira(fail_on=lambda m, p: m == "POST" and p == "/rest/api/3/issue/SUP-1/worklog")
        code, out = self.run_load(load_plan(), fake)
        self.assertEqual(code, 1)
        self.assertIn("✗ worklog SUP-1", out)
        self.assertIn("retoma desde el paso que falló", out)
        done_before = [c for c in fake.calls if c[0] in ("POST", "PUT")]
        fake2 = FakeJira()
        code, out = self.run_load(common.read_json(self.plan_path), fake2)
        self.assertEqual(code, 0, out)
        self.assertIn("(ya estaba hecho)", out)
        self.assertFalse(any(p == "/rest/api/3/issue" for m, p, _ in fake2.calls if m == "POST"))
        writes2 = [c for c in fake2.calls if c[0] in ("POST", "PUT")]
        self.assertLess(len(writes2), len(done_before) + 4)

    def test_requires_approval(self):
        p = load_plan()
        p["load_approved"] = 1
        code, out = self.run_load(p, FakeJira())
        self.assertEqual(code, 1)
        self.assertIn("no hay una carga aprobada", out)

    def test_ambiguous_user_fails(self):
        fake = FakeJira()
        writer = jira_load.Writer("https://x.atlassian.net", "a", "t", http=lambda *a, **k: [
            {"accountId": "1", "displayName": "Ana", "accountType": "atlassian"},
            {"accountId": "2", "displayName": "Ana B", "accountType": "atlassian"}])
        with self.assertRaises(ValueError):
            jira_load.find_user(writer, "An")
        del fake

    def test_text_to_adf(self):
        doc = jira_load.text_to_adf("Intro\n- a\n- b\nCierre")
        self.assertEqual([c["type"] for c in doc["content"]], ["paragraph", "bulletList", "paragraph"])


if __name__ == "__main__":
    unittest.main()
