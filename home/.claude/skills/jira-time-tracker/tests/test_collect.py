import json
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import collect
from collectors import chrome, claude_code
from lib import common

CFG = common.load_config(Path(__file__).resolve().parent.parent / "config.example.json")
TZ = ZoneInfo(CFG["timezone"])
DAY = date(2026, 10, 5)


def utc(h, m):
    return datetime(2026, 10, 5, h, m, tzinfo=timezone.utc)


class TestClaudeCode(unittest.TestCase):
    def test_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "-home-u-code-app"
            proj.mkdir()
            sid = "11111111-aaaa"
            lines = [
                {"type": "ai-title", "aiTitle": "SUP-3 importador"},
                {"type": "user", "timestamp": "2026-10-05T12:00:00Z", "cwd": "/home/u/code/app", "gitBranch": "feat/x",
                 "message": {"content": "arreglá el importador"}},
                {"type": "assistant", "timestamp": "2026-10-05T12:05:00Z", "cwd": "/home/u/code/app", "gitBranch": "feat/x"},
                {"type": "user", "timestamp": "2026-10-05T12:06:00Z", "message": {"content": "<command-name>x</command-name>"}},
                {"type": "user", "timestamp": "2026-10-05T12:40:00Z", "cwd": "/home/u/code/app", "gitBranch": "feat/x",
                 "message": {"content": [{"type": "text", "text": "ahora los tests"}]}},
                {"type": "user", "timestamp": "2026-10-04T12:40:00Z", "message": {"content": "ayer"}},
            ]
            (proj / f"{sid}.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\nno-json\n")
            sub = proj / sid / "subagents"
            sub.mkdir(parents=True)
            (sub / "agent-1.jsonl").write_text(json.dumps(
                {"type": "assistant", "timestamp": "2026-10-05T12:20:00Z", "cwd": "/home/u/code/app"}) + "\n")

            cfg = {**CFG, "sources": {**CFG["sources"], "claude_code": {"projects_dir": tmp, "idle_gap_minutes": 15}}}
            res = claude_code.collect(cfg, {}, DAY, current_session=sid)
            ev = res["events"]
            # 12:00–12:20 (con el subagente puenteando) y 12:40 aparte
            self.assertEqual(len(ev), 2)
            self.assertEqual(ev[0]["start"], "2026-10-05T09:00:00-03:00")
            self.assertEqual(ev[0]["end"], "2026-10-05T09:20:00-03:00")
            self.assertIn("primer prompt: arreglá el importador", ev[0]["detail"])
            self.assertEqual(ev[0]["hints"]["issue_keys"], ["SUP-3"])
            self.assertTrue(ev[0]["hints"]["current"])
            # Solo los prompts reales marcan interacción (no el comando de las 12:06).
            self.assertEqual(ev[0]["hints"]["prompt_times"], ["2026-10-05T09:00:00-03:00"])
            self.assertIn("ahora los tests", ev[1]["detail"])


class TestChrome(unittest.TestCase):
    def test_grouping_and_hints(self):
        visits = [
            (utc(12, 0), "https://x.atlassian.net/browse/SUP-12", "[SUP-12] Algo - Jira"),
            (utc(12, 3), "https://x.atlassian.net/jira/your-work?selectedIssue=ENG-4", "Your work"),
            (utc(12, 4), "https://github.com/org/app/pull/7/files", "PR 7"),
            (utc(12, 5), "https://www.youtube.com/watch?v=1", "música"),
            (utc(12, 6), "https://erp.company.com/app/sales-invoice/SINV-0001", "SINV-0001"),
            (utc(12, 30), "https://x.atlassian.net/browse/SUP-12", "[SUP-12] Algo - Jira"),
            (utc(12, 31), "chrome://newtab/", ""),
        ]
        res = chrome.collect(CFG, {}, DAY, visits=visits)
        ev = res["events"]
        domains = [e["hints"]["domain"] for e in ev]
        self.assertEqual(domains, ["x.atlassian.net", "github.com", "erp.company.com", "x.atlassian.net"])
        self.assertEqual(ev[0]["hints"]["issue_keys"], ["SUP-12", "ENG-4"])
        self.assertEqual(ev[0]["end"], "2026-10-05T09:03:00-03:00")
        self.assertEqual(ev[1]["hints"]["github"], ["org/app#7 (PR)"])
        self.assertEqual(ev[2]["hints"]["erp_docs"], ["sales-invoice SINV-0001"])

    def test_read_visits(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "History"
            con = sqlite3.connect(db)
            con.executescript("CREATE TABLE urls (id INTEGER PRIMARY KEY, url TEXT, title TEXT);"
                              "CREATE TABLE visits (id INTEGER PRIMARY KEY, url INTEGER, visit_time INTEGER);")
            con.execute("INSERT INTO urls VALUES (1, 'https://a.com', 'A')")
            con.execute("INSERT INTO visits VALUES (1, 1, ?)", (chrome.to_chrome_time(utc(12, 0)),))
            con.execute("INSERT INTO visits VALUES (2, 1, ?)", (chrome.to_chrome_time(datetime(2026, 10, 4, 12, tzinfo=timezone.utc)),))
            con.commit()
            con.close()
            start, end = common.day_bounds(DAY, TZ)
            v = chrome.read_visits(db, start, end)
            self.assertEqual(v, [(utc(12, 0), "https://a.com", "A")])


class TestDigest(unittest.TestCase):
    def results(self):
        return {
            "erpnext": {"status": "ok", "range": {"start": "2026-10-05T08:55:00-03:00", "end": "2026-10-05T17:40:00-03:00",
                                                  "end_source": "now", "breaks": [], "checkins": [{"log_type": "IN", "time": "2026-10-05T08:53:00-03:00"}]},
                        "events": []},
            "git_local": {"status": "ok", "events": [
                common.Event("git", "2026-10-05T10:00:00-03:00", "2026-10-05T10:00:00-03:00", "commit abc en app: fix",
                             hints={"repo": "app", "branch": "feat/cuit-validation", "issue_keys": []}, weight="strong").to_dict(),
                common.Event("chrome", "2026-10-05T11:00:00-03:00", "2026-10-05T11:00:00-03:00", "jira",
                             hints={"issue_keys": ["SUP-41"]}, weight="weak").to_dict()]},
            "jira": {"status": "ok", "worklogs": [{"id": "9", "issue": "SUP-5", "started": "2026-10-05T11:00:00-03:00", "minutes": 30, "comment": "x"}],
                     "candidates": [
                         {"key": "SUP-1", "summary": "Importador", "status": "En curso", "status_category": "In Progress", "assignee_me": True, "origin": ["assigned"]},
                         {"key": "ENG-9", "summary": "PLC", "status": "programación finalizada", "status_category": "In Progress", "assignee_me": True, "origin": ["recent"]},
                         {"key": "SUP-40", "summary": "Vieja ajena", "status": "En curso", "status_category": "In Progress", "assignee_me": False, "origin": ["recent"]},
                         {"key": "SUP-41", "summary": "Ajena tocada hoy", "status": "En curso", "status_category": "In Progress", "assignee_me": False, "origin": ["recent", "mentioned"], "description": "Detalle del problema"},
                     ], "events": []},
        }

    def test_mentioned_keys(self):
        self.assertEqual(collect.mentioned_keys(self.results()), ["SUP-41"])

    def test_render(self):
        res = self.results()
        d = collect.build_digest(DAY, CFG, res, datetime(2026, 10, 5, 17, 42, tzinfo=TZ))
        text = collect.render_digest(d, TZ)
        self.assertIn("Rango: entrada 08:55 · corte 17:40 (hora actual)", text)
        self.assertIn("id=9 SUP-5 11:00–11:30 (30m)", text)
        self.assertIn("★  SUP-1 [En curso] Importador", text)
        self.assertIn("Recientes sin actividad hoy (no asignadas): SUP-40 Vieja ajena", text)
        self.assertNotIn("  SUP-40 [", text)
        self.assertIn("Excluidas (cerradas o finalizadas) sin actividad hoy: ENG-9", text)
        self.assertIn(" ● SUP-41 [En curso] Ajena tocada hoy", text)
        self.assertIn("↳ Detalle del problema", text)
        self.assertIn("[br=feat/cuit-validation]", text)
        self.assertIn("Fuentes MCP a consultar por el agente: outlook, teams, sharepoint, google_drive", text)

    def test_parallel_sessions(self):
        def ev(src, start, end, prompts, sid):
            return common.Event(src, f"2026-10-05T{start}:00-03:00", f"2026-10-05T{end}:00-03:00", f"sesión {sid}",
                                hints={"prompt_times": [f"2026-10-05T{p}:00-03:00" for p in prompts]},
                                id=f"{src}:{sid}").to_dict()
        # A: prompt 10:00 y trabaja sola hasta 11:00. B: interacción 10:20 y 10:40. C: sin prompts.
        timeline = [ev("cc", "10:00", "11:00", ["10:00"], "a"), ev("t3", "10:15", "10:40", ["10:20", "10:40"], "b"),
                    ev("cc", "10:30", "10:50", [], "c"), ev("git", "10:30", "10:30", [], "g")]
        collect.mark_parallel(timeline, 5)
        a, b, c, g = (e["hints"] for e in timeline)
        self.assertEqual(a["interactive"], [["2026-10-05T09:55:00-03:00", "2026-10-05T10:00:00-03:00"]])
        self.assertEqual([(x["start"][11:16], x["end"][11:16], x["by"]) for x in a["shadowed"]],
                         [("10:15", "10:20", ["t3:b"]), ("10:35", "10:40", ["t3:b"])])
        self.assertEqual([(x["start"][11:16], x["end"][11:16]) for x in c["shadowed"]], [("10:35", "10:40")])
        self.assertEqual(b["shadowed"], [])
        self.assertEqual(b["parallel_interaction"], [])
        self.assertNotIn("shadowed", g)
        text = collect.render_digest({**collect.build_digest(DAY, CFG, {}, datetime(2026, 10, 5, 17, 42, tzinfo=TZ)),
                                      "timeline": timeline}, TZ)
        self.assertIn("interacción 09:55–10:00 · tapada 10:15–10:20 por t3:b · tapada 10:35–10:40 por t3:b", text)
        self.assertIn("sin prompts: autónoma · tapada 10:35–10:40 por t3:b", text)

    def test_t3_and_remote_sessions_cross(self):
        # Thread de Codex en T3 con interacción tapa a una sesión de Claude dentro de T3 (cc con
        # t3_thread) y a una remota; todas cuentan como sesiones de agente.
        def ev(src, prompts, id_, **hints):
            return common.Event(src, "2026-10-05T10:00:00-03:00", "2026-10-05T10:30:00-03:00", id_,
                                hints={"prompt_times": [f"2026-10-05T{p}:00-03:00" for p in prompts], **hints},
                                id=id_).to_dict()
        timeline = [ev("t3", ["10:20"], "t3:codex", provider="codex"),
                    ev("cc", ["10:00"], "cc:t3claude", t3_thread="x1"),
                    ev("cc", [], "cc:remota", host="vps")]
        collect.mark_parallel(timeline, 5)
        for e in timeline[1:]:
            self.assertEqual([(x["start"][11:16], x["end"][11:16], x["by"]) for x in e["hints"]["shadowed"]],
                             [("10:15", "10:20", ["t3:codex"])], e["id"])
        self.assertEqual(timeline[0]["hints"]["shadowed"], [])

    def test_simultaneous_interaction(self):
        timeline = [common.Event("cc", "2026-10-05T10:00:00-03:00", "2026-10-05T10:30:00-03:00", "a",
                                 hints={"prompt_times": ["2026-10-05T10:10:00-03:00"]}, id="cc:a").to_dict(),
                    common.Event("cc", "2026-10-05T10:00:00-03:00", "2026-10-05T10:30:00-03:00", "b",
                                 hints={"prompt_times": ["2026-10-05T10:12:00-03:00"]}, id="cc:b").to_dict()]
        collect.mark_parallel(timeline, 5)
        self.assertEqual(timeline[0]["hints"]["parallel_interaction"], ["cc:b"])
        self.assertEqual(timeline[1]["hints"]["parallel_interaction"], ["cc:a"])

    def test_range_without_erpnext(self):
        d = collect.build_digest(DAY, CFG, {}, datetime(2026, 10, 5, 17, 42, tzinfo=TZ))
        self.assertIsNone(d["range"]["start"])
        self.assertEqual(d["range"]["end"], "2026-10-05T17:40:00-03:00")


if __name__ == "__main__":
    unittest.main()
