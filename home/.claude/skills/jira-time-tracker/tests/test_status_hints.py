import unittest
from datetime import date
from zoneinfo import ZoneInfo

from lib import status_hints as H

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
DAY = date(2026, 11, 4)

TRANSITIONS = [
    {"id": "11", "name": "Empezar", "to": "En curso", "to_category": "indeterminate", "fields": []},
    {"id": "21", "name": "Enviar a revisión", "to": "En revisión", "to_category": "indeterminate", "fields": []},
    {"id": "31", "name": "Resolver", "to": "Resuelta", "to_category": "done",
     "fields": [{"key": "resolution", "name": "Resolución", "required": False, "allowed": ["Duplicado", "Listo"]}]},
]


def meta(category="indeterminate", status="En curso", **kw):
    return {"status": status, "category": category, "transitions": TRANSITIONS, **kw}


def pr(state="merged", merged_at="2026-11-04T18:00:00Z", number=45, draft=False):
    return {"repo": "org/app", "number": number, "state": state, "draft": draft,
            "merged_at": merged_at if state == "merged" else None}


class TestSuggest(unittest.TestCase):
    def test_merged_on_last_day_suggests_resolve(self):
        res = H.suggest(meta(), {"prs": [pr()]}, DAY, TZ)
        s = res["suggestion"]
        self.assertEqual((s["transition_id"], s["fields"]), ("31", {"resolution": "Listo"}))
        self.assertIn("PR #45 mergeado el 04/11", s["reason"])

    def test_merged_later_defers_to_merge_day(self):
        res = H.suggest(meta(), {"prs": [pr(merged_at="2026-11-06T15:00:00Z")]}, DAY, TZ)
        self.assertIsNone(res["suggestion"])
        self.assertIn("al cargar el 06/11", res["note"])

    def test_activity_after_merge_defers_to_last_activity(self):
        sig = {"prs": [pr()], "last_commit": "2026-11-07T12:00:00-03:00"}
        res = H.suggest(meta(last_worklog="2026-11-05T10:00:00.000-0300"), sig, DAY, TZ)
        self.assertIsNone(res["suggestion"])
        self.assertIn("commits hasta el 07/11", res["note"])
        self.assertIn("al cargar el 07/11", res["note"])
        # Cargando ese último día ya se sugiere resolver.
        self.assertEqual(H.suggest(meta(), sig, date(2026, 11, 7), TZ)["suggestion"]["transition_id"], "31")

    def test_open_pr_blocks_resolve(self):
        res = H.suggest(meta(), {"prs": [pr(), pr(state="open", number=46)]}, DAY, TZ)
        self.assertEqual(res["suggestion"]["transition_id"], "21")

    def test_open_pr_suggests_review(self):
        res = H.suggest(meta(), {"prs": [pr(state="open")]}, DAY, TZ)
        self.assertEqual(res["suggestion"]["transition_id"], "21")
        # Un borrador no cuenta, y si ya está en revisión no se sugiere nada.
        self.assertIsNone(H.suggest(meta(), {"prs": [pr(state="open", draft=True)]}, DAY, TZ)["suggestion"])
        self.assertIsNone(H.suggest(meta(status="En revisión"), {"prs": [pr(state="open")]}, DAY, TZ)["suggestion"])

    def test_todo_with_hours_suggests_progress(self):
        res = H.suggest(meta(category="new", status="Por hacer"), {}, DAY, TZ)
        self.assertEqual(res["suggestion"]["transition_id"], "11")
        self.assertIsNone(H.suggest(meta(), {}, DAY, TZ)["suggestion"])

    def test_subtasks_done(self):
        m = meta(subtasks=[{"key": "S-2", "category": "done"}, {"key": "S-3", "category": "done"}])
        self.assertEqual(H.suggest(m, {}, DAY, TZ)["suggestion"]["transition_id"], "31")
        m["subtasks"][1]["category"] = "indeterminate"
        self.assertIsNone(H.suggest(m, {}, DAY, TZ)["suggestion"])

    def test_already_done_only_warns(self):
        res = H.suggest(meta(category="done", status="Resuelta"), {"prs": [pr()]}, DAY, TZ)
        self.assertIsNone(res["suggestion"])
        self.assertIn("reabrila", res["note"])

    def test_no_matching_transition(self):
        m = meta(transitions=[TRANSITIONS[0]])
        res = H.suggest(m, {"prs": [pr()]}, DAY, TZ)
        self.assertIsNone(res["suggestion"])
        self.assertIn("ninguna transición", res["note"])

    def test_find_prs_by_key_evidence_and_branch(self):
        calls = []

        def api(path):
            calls.append(path)
            if path.startswith("/search/issues"):
                return {"items": [
                    {"number": 45, "title": "SIT-12 importador", "state": "closed", "user": {"login": "otro"},
                     "pull_request": {"merged_at": "2026-11-04T18:00:00Z"},
                     "repository_url": "https://api.github.com/repos/org/app"},
                    {"number": 46, "title": "otra cosa SIT-120", "state": "open",
                     "repository_url": "https://api.github.com/repos/org/app"}]}
            if path == "/repos/org/app/pulls/50":
                return {"number": 50, "title": "fix", "state": "open", "user": {"login": "yo"}}
            if path == "/repos/org/app/pulls/60":
                return {"number": 60, "title": "de otro", "state": "open", "user": {"login": "otro"}}
            if path.startswith("/repos/org/web/pulls?"):
                return [{"number": 7, "title": "feature", "state": "closed", "merged_at": "2026-11-03T12:00:00Z",
                         "user": {"login": "Yo"}}]
            raise RuntimeError("404")

        cfg = {"identity": {"github_orgs": ["org"], "github_user": "yo"}}
        link = {"prs": [("org/app", 50), ("org/app", 60)], "branches": [("web@t3-1", "feat/x")]}
        prs = H.find_prs(cfg, "SIT-12", link, api)
        # La key explícita cuenta aunque el PR sea de otro; los de la evidencia, solo si son propios.
        self.assertEqual(sorted((p["repo"], p["number"], p["state"]) for p in prs),
                         [("org/app", 45, "merged"), ("org/app", 50, "open"), ("org/web", 7, "merged")])
        self.assertIn("org%3Aorg", calls[0])
        self.assertTrue(any("head=org%3Afeat/x" in c for c in calls))

    def test_links_from_blocks(self):
        events = {
            "gh:1": {"hints": {"repo": "org/app", "branch": "feat/x", "url": "https://github.com/org/app/pull/45"}},
            "chrome:1": {"hints": {"github": ["org/app#45 (PR)", "org/app#46 (PR)"]}},
            "git:1": {"hints": {"repo": "app", "branch": "main"}},
            "git:2": {"hints": {"repo": "app@t3-1", "branch": "feat/y"}},
        }
        links = H.links_from_blocks([("SIT-12", ["gh:1", "chrome:1", "git:1"]), ("SIT-12", ["git:2", "nope"])], events)
        self.assertEqual(links["SIT-12"]["prs"], [("org/app", 45)])  # la visita en Chrome no cuenta
        self.assertEqual(links["SIT-12"]["branches"], [("org/app", "feat/x"), ("app@t3-1", "feat/y")])

if __name__ == "__main__":
    unittest.main()
