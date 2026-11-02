import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from lib import common

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
EXAMPLE = Path(__file__).resolve().parent.parent / "config.example.json"


def local(h, m, s=0):
    return datetime(2026, 10, 5, h, m, s, tzinfo=TZ)


class TestRounding(unittest.TestCase):
    def test_round_up(self):
        self.assertEqual(common.round_up(local(8, 53)), local(8, 55))
        self.assertEqual(common.round_up(local(8, 55)), local(8, 55))
        self.assertEqual(common.round_up(local(8, 55, 1)), local(9, 0))
        self.assertEqual(common.round_up(local(8, 58)), local(9, 0))

    def test_round_down(self):
        self.assertEqual(common.round_down(local(17, 42)), local(17, 40))
        self.assertEqual(common.round_down(local(17, 40)), local(17, 40))
        self.assertEqual(common.round_down(local(17, 44, 59)), local(17, 40))

    def test_round_hour_boundary(self):
        self.assertEqual(common.round_up(local(23, 57)).date(), date(2026, 10, 6))


class TestTime(unittest.TestCase):
    def test_parse_iso_variants(self):
        z = common.parse_iso("2026-10-05T12:00:00.000Z")
        jira = common.parse_iso("2026-10-05T09:00:00.000-0300")
        colon = common.parse_iso("2026-10-05T09:00:00-03:00")
        self.assertEqual(z, jira)
        self.assertEqual(jira, colon)

    def test_parse_iso_naive_rejected(self):
        with self.assertRaises(ValueError):
            common.parse_iso("2026-10-05T09:00:00")

    def test_to_local(self):
        utc = common.parse_iso("2026-10-05T13:13:44.655Z")
        self.assertEqual(common.fmt_hm(common.to_local(utc, TZ)), "10:13")

    def test_day_bounds(self):
        start, end = common.day_bounds(date(2026, 10, 5), TZ)
        self.assertEqual(start, local(0, 0))
        self.assertEqual((end - start).total_seconds(), 86400)

    def test_formats(self):
        self.assertEqual(common.fmt_duration(90), "1h30m")
        self.assertEqual(common.fmt_duration(60), "1h")
        self.assertEqual(common.fmt_duration(25), "25m")
        self.assertEqual(common.fmt_duration(65), "1h05m")
        self.assertEqual(common.jira_time_spent(90), "1h 30m")
        self.assertEqual(common.jira_time_spent(60), "1h")
        self.assertEqual(common.jira_time_spent(10), "10m")
        self.assertEqual(common.jira_started(local(9, 5)), "2026-10-05T09:05:00.000-0300")


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, data):
        p = self.dir / "config.json"
        p.write_text(json.dumps(data))
        return p

    def test_missing(self):
        with self.assertRaises(common.ConfigMissing):
            common.load_config(self.dir / "config.json")

    def test_example_is_valid(self):
        cfg = common.load_config(EXAMPLE)
        self.assertIn("SUP", cfg["projects"])

    def test_defaults_merged(self):
        cfg = common.load_config(self.write({
            "jira": {"site": "https://x.atlassian.net", "email": "a@b.c"},
            "projects": {"ABC": {"excluded_statuses": ["Raro"]}},
            "sources": {"chrome": {"enabled": False}},
        }))
        self.assertEqual(cfg["rules"]["slot_minutes"], 5)
        self.assertEqual(cfg["projects"]["ABC"]["excluded_status_categories"], ["Done"])
        self.assertEqual(cfg["projects"]["ABC"]["excluded_statuses"], ["Raro"])
        self.assertFalse(cfg["sources"]["chrome"]["enabled"])
        self.assertEqual(cfg["sources"]["chrome"]["session_gap_minutes"], 10)

    def test_invalid(self):
        with self.assertRaises(common.ConfigError) as ctx:
            common.load_config(self.write({
                "timezone": "Mars/Base",
                "projects": {},
                "rules": {"min_block_minutes": 7},
            }))
        msg = str(ctx.exception)
        self.assertIn("jira.site", msg)
        self.assertIn("projects", msg)
        self.assertIn("timezone", msg)
        self.assertIn("min_block_minutes", msg)

    def test_env(self):
        p = self.dir / ".env"
        p.write_text('# comentario\nJIRA_API_TOKEN="abc"\nexport ERPNEXT_API_KEY=k\n\nBAD\n')
        env = common.load_env(p)
        self.assertEqual(env["JIRA_API_TOKEN"], "abc")
        self.assertEqual(env["ERPNEXT_API_KEY"], "k")
        self.assertNotIn("BAD", env)


class TestConfigDir(unittest.TestCase):
    def test_inside_dot_claude_skills(self):
        self.assertEqual(common.default_config_dir(Path("/home/u/cowork/.claude/skills/jira-time-tracker")),
                         Path("/home/u/cowork/.claude/jira-time-tracker"))

    def test_synced_bucket(self):
        self.assertEqual(common.default_config_dir(Path("/home/u/.claude/skills/synced/abc_123/jira-time-tracker")),
                         Path("/home/u/.claude/jira-time-tracker"))

    def test_outside_dot_claude(self):
        self.assertEqual(common.default_config_dir(Path("/home/u/code/jira-time-tracker")),
                         Path.home() / ".config" / "jira-time-tracker")


class TestIssueKeys(unittest.TestCase):
    def setUp(self):
        self.rx = common.issue_key_regex(["SIT", "SAI"])

    def test_find(self):
        self.assertEqual(common.find_issue_keys("fix SIT-12 y sai-3013", self.rx), ["SIT-12", "SAI-3013"])
        self.assertEqual(common.find_issue_keys("worktrees/iea-sit-325", self.rx), ["SIT-325"])
        self.assertEqual(common.find_issue_keys("feat/SIT_44-algo", self.rx), ["SIT-44"])
        self.assertEqual(common.find_issue_keys("SIT-1 SIT-1", self.rx), ["SIT-1"])

    def test_no_false_positives(self):
        self.assertEqual(common.find_issue_keys("VISIT-12 SITE-3 xSIT-4", self.rx), [])
        self.assertEqual(common.find_issue_keys(None, self.rx), [])


class TestEvent(unittest.TestCase):
    def test_event(self):
        e = common.Event("git", "2026-10-05T09:00:00-03:00", "2026-10-05T09:00:00-03:00", "commit",
                         hints={"issue_keys": ["SIT-1"], "repo": "", "branch": None})
        d = e.to_dict()
        self.assertTrue(d["id"].startswith("git:"))
        self.assertEqual(d["hints"], {"issue_keys": ["SIT-1"]})

    def test_bad_weight(self):
        with self.assertRaises(ValueError):
            common.Event("git", "a", "a", "t", weight="huge")


if __name__ == "__main__":
    unittest.main()
