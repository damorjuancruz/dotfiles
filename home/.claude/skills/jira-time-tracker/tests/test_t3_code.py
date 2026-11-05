import json
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from collectors import claude_code, t3_code
from lib import common

CFG = common.load_config(Path(__file__).resolve().parent.parent / "config.example.json")
DAY = date(2026, 10, 5)

SCHEMA = """
create table projection_projects (project_id text, title text, workspace_root text);
create table orchestration_v2_projection_threads (thread_id text, project_id text, title text, default_provider text,
  deleted_at text, payload_json text);
create table orchestration_v2_projection_provider_threads (thread_id text, provider text, payload_json text);
create table orchestration_v2_projection_messages (thread_id text, role text, created_at text, payload_json text);
create table orchestration_v2_projection_turn_items (thread_id text, updated_at text);
create table orchestration_v2_projection_runs (thread_id text, requested_at text, completed_at text);
"""


def make_db(path: Path, wt: str) -> None:
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.execute("insert into projection_projects values ('p1', 'app', '/home/u/code/app')")

    def thread(tid, title, provider, branch="", worktree=None, root=None, rel=None, deleted=None):
        payload = {"title": title, "branch": branch, "worktreePath": worktree,
                   "lineage": {"rootThreadId": root or tid, "relationshipToParent": rel}}
        con.execute("insert into orchestration_v2_projection_threads values (?, 'p1', ?, ?, ?, ?)",
                    (tid, title, provider, deleted, json.dumps(payload)))

    thread("t-claude", "SUP-3 importador", "claudeAgent", "feat/x", worktree=wt)
    con.execute("insert into orchestration_v2_projection_provider_threads values ('t-claude', 'claudeAgent', ?)",
                (json.dumps({"nativeThreadRef": {"nativeId": "sess-claude"}}),))
    thread("import:codex:abcdef12-0000", "Reporte de stock", "codex", "feat/SUP-9-stock")
    thread("t-sub", "subagente", "codex", root="import:codex:abcdef12-0000", rel="subagent")
    thread("t-borrado", "borrado", "codex", deleted="2026-10-05T13:00:00.000Z")

    def msg(tid, role, ts, text, by="user"):
        con.execute("insert into orchestration_v2_projection_messages values (?, ?, ?, ?)",
                    (tid, role, ts, json.dumps({"text": text, "createdBy": by})))

    msg("t-claude", "user", "2026-10-05T12:00:00.000Z", "lo cubre claude_code")
    msg("import:codex:abcdef12-0000", "user", "2026-10-05T13:00:00.000Z", "armá el reporte de stock")
    msg("import:codex:abcdef12-0000", "assistant", "2026-10-05T13:02:00.000Z", "listo", by="agent")
    msg("t-sub", "user", "2026-10-05T13:10:00.000Z", "prompt del agente padre", by="agent")
    con.execute("insert into orchestration_v2_projection_turn_items values ('import:codex:abcdef12-0000', '2026-10-05T13:20:00.000Z')")
    con.execute("insert into orchestration_v2_projection_runs values ('import:codex:abcdef12-0000', '2026-10-05T14:00:00.000Z', '2026-10-05T14:05:00.000Z')")
    msg("import:codex:abcdef12-0000", "user", "2026-10-04T13:00:00.000Z", "ayer")
    msg("t-borrado", "user", "2026-10-05T13:00:00.000Z", "no cuenta")
    con.commit()
    con.close()


class TestT3Code(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.wt = str(self.dir / ".t3" / "worktrees" / "app" / "t3-1")
        make_db(self.dir / "state.sqlite", self.wt)
        self.cfg = {**CFG, "sources": {**CFG["sources"], "t3_code": {
            "enabled": True, "db_path": str(self.dir / "state.sqlite"), "idle_gap_minutes": 15}}}

    def tearDown(self):
        self.tmp.cleanup()

    def test_short_id(self):
        self.assertEqual(t3_code.short_id("import:claudeAgent:f66f1b58-a462"), "f66f1b58")
        self.assertEqual(t3_code.short_id("thread:provider:x:native-thread:a%3Aordinal%3A1%3Aa9bb13a5"), "a9bb13a5")
        self.assertEqual(t3_code.short_id("28a08ba7-bf0c"), "28a08ba7")

    def test_claude_sessions(self):
        m = t3_code.claude_sessions(self.cfg)
        self.assertEqual(list(m), ["sess-claude"])
        self.assertEqual(m["sess-claude"]["title"], "SUP-3 importador")
        self.assertEqual(m["sess-claude"]["project"], "app")
        self.assertEqual(t3_code.claude_sessions({**self.cfg, "sources": {**CFG["sources"], "t3_code": {"enabled": False}}}), {})

    def test_collect_non_claude_threads(self):
        res = t3_code.collect(self.cfg, {}, DAY, current_thread="import:codex:abcdef12-0000")
        ev = res["events"]
        # 13:00–13:20 (el subagente puentea) y 14:00–14:05 aparte; el thread de Claude y el borrado no
        self.assertEqual([(e["start"][11:16], e["end"][11:16]) for e in ev], [("10:00", "10:20"), ("11:00", "11:05")])
        self.assertIn("thread T3 Code (codex) en app: Reporte de stock", ev[0]["title"])
        self.assertIn("primer prompt: armá el reporte de stock", ev[0]["detail"])
        self.assertNotIn("agente padre", ev[0]["detail"])
        self.assertEqual(ev[0]["hints"]["issue_keys"], ["SUP-9"])
        self.assertEqual(ev[0]["hints"]["thread"], "abcdef12")
        self.assertTrue(ev[0]["hints"]["current"])
        self.assertIn("1 threads de Claude", res["messages"][0])

    def test_missing_db_is_not_an_error(self):
        cfg = {**self.cfg, "sources": {**CFG["sources"], "t3_code": {
            "enabled": True, "db_path": str(self.dir / "no.sqlite"), "idle_gap_minutes": 15}}}
        res = t3_code.collect(cfg, {}, DAY)
        self.assertEqual((res["status"], res["events"]), ("ok", []))

    def test_claude_code_enrichment(self):
        projects = self.dir / "projects"

        def session(slug, sid, cwd, prompt, entry="sdk-cli"):
            (projects / slug).mkdir(parents=True, exist_ok=True)
            lines = [{"type": "user", "timestamp": "2026-10-05T12:00:00Z", "cwd": cwd, "entrypoint": entry,
                      "message": {"content": prompt}},
                     {"type": "assistant", "timestamp": "2026-10-05T12:03:00Z", "cwd": cwd, "entrypoint": entry}]
            (projects / slug / f"{sid}.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")

        t3dir = self.dir / ".t3"
        session("-x-t3-worktrees-app-t3-1", "sess-claude", self.wt, "seguí con el importador")
        session("-tmp-t3code-claude-title-abc", "sess-title", "/tmp/t3code-claude-title-abc", "Generate a title")
        session("-x-t3-worktrees-app-t3-2", "sess-branch", str(t3dir / "worktrees" / "app" / "t3-2"),
                "You generate concise git branch names.")
        session("-x-t3-worktrees-review-guide-q-checkout", "sess-guide", str(t3dir / "worktrees" / "review-guide-q-checkout"),
                "You prepare a guided tour of change request #45 for a maintainer")
        session("-home-u-code-app", "sess-cli", "/home/u/code/app", "sesión normal", entry="cli")

        cfg = {**self.cfg, "sources": {**self.cfg["sources"], "claude_code": {"projects_dir": str(projects), "idle_gap_minutes": 15}}}
        with mock.patch.object(claude_code, "T3_DIR", t3dir):
            ev = {e["hints"]["session"]: e for e in claude_code.collect(cfg, {}, DAY, current_session="none")["events"]}
        self.assertEqual(sorted(ev), ["sess-cla", "sess-cli", "sess-gui"])
        t3 = ev["sess-cla"]
        self.assertEqual(t3["title"], "thread T3 Code (Claude) en app: SUP-3 importador")
        self.assertEqual(t3["hints"]["t3_thread"], "t-claude")
        self.assertEqual(t3["hints"]["branch"], "feat/x")
        self.assertEqual(t3["hints"]["issue_keys"], ["SUP-3"])
        guide = ev["sess-gui"]
        self.assertEqual((guide["title"], guide["weight"], guide["detail"]), ("guía de revisión de T3 Code del PR #45", "weak", ""))
        self.assertTrue(ev["sess-cli"]["title"].startswith("sesión Claude Code en app"))



class TestSourceLabel(unittest.TestCase):
    def test_labels(self):
        from lib.page import source_label
        self.assertEqual(source_label({"source": "cc", "hints": {"session": "abc"}}), "Claude Code")
        self.assertEqual(source_label({"source": "cc", "hints": {"t3_thread": "x1"}}), "T3 · Claude")
        self.assertEqual(source_label({"source": "t3", "hints": {"provider": "codex"}}), "T3 · codex")
        self.assertEqual(source_label({"source": "gh"}), "GitHub")

if __name__ == "__main__":
    unittest.main()
