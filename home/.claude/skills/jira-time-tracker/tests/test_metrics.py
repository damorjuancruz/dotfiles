"""Métricas de uso: rondas, primera propuesta contra final, costo de la sesión y reporte."""

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import metrics as report_cli
import plan as P
from lib import common
from lib import metrics as M

from tests.test_plan import CFG, DIGEST, NO_RAW, confirmed_plan


class TestMetrics(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.patches = [mock.patch.object(common, "STATE_ROOT", self.root),
                        mock.patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": ""})]
        for p in self.patches:
            p.start()
        self.day = common.parse_day("2026-10-05", common.get_tz(CFG))
        self.sdir = common.state_dir(self.day)

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_review_metrics_counts_without_text(self):
        p = confirmed_plan()
        P.ensure_ids(p)
        st = {"round": 1, "action": "review", "confirmed": {"b1": True, "b2": False},
              "notes": {"b2": "esto era otra cosa", "b3": " "}, "global_note": "x",
              "reassign": {"b2": "SUP-9"}, "absorb": {"b4": True}, "gaps": {"g1": {"action": "unworked"}},
              "levels": {"b1": "breve"}, "texts": {"b1": "Daily breve editado"}}
        m = M.review_metrics(p, st)
        self.assertEqual((m["confirmed"], m["notes"], m["reassigned"], m["absorbed"]), (1, 1, 1, 1))
        self.assertEqual(m["gaps"], {"unworked": 1})
        self.assertEqual(m["texts_edited"], 1)
        self.assertGreater(m["text_similarity_avg"], 0.3)
        self.assertNotIn("esto era otra cosa", json.dumps(m))

    def test_attribution_diff(self):
        first = confirmed_plan()
        P.ensure_ids(first)
        final = copy.deepcopy(first)
        final["blocks"][1]["issue"] = "SUP-9"              # 50 min de confianza media cambian
        final["blocks"] = [b for b in final["blocks"] if b["id"] != "b4"]  # 60 min absorbidos
        d = M.attribution_diff(first, final)
        self.assertEqual((d["moved_minutes"], d["removed_minutes"]), (50, 60))
        self.assertEqual(d["by_confidence"]["media"]["moved"], 50)
        self.assertEqual(d["proposed_minutes"], 20 + 50 + 60)
        self.assertAlmostEqual(d["accuracy"], round(1 - 110 / 130, 3))

    def test_session_usage(self):
        proj = self.root / "projects" / "-x"
        (proj / "sid" / "subagents").mkdir(parents=True)
        def a(ts, model, n, extra=None):
            return json.dumps({"type": "assistant", "timestamp": ts, **(extra or {}),
                               "message": {"model": model, "usage": {"input_tokens": n, "cache_read_input_tokens": 10,
                                                                     "output_tokens": 1}}})
        (proj / "sid.jsonl").write_text("\n".join([a("2026-10-05T10:00:00Z", "opus", 5),
                                                    a("2026-10-05T12:00:00Z", "opus", 7),
                                                    a("2026-10-05T12:01:00Z", "opus", 9, {"forkedFrom": {"sessionId": "p"}})]))
        (proj / "sid" / "subagents" / "a.jsonl").write_text(a("2026-10-05T12:05:00Z", "haiku", 3))
        u = M.session_usage("sid", common.parse_iso("2026-10-05T11:00:00Z"), self.root / "projects")
        self.assertEqual(u["main"]["opus"]["turns"], 1)
        self.assertEqual(u["main"]["opus"]["input"], 7)
        self.assertEqual(u["subagents"][0]["haiku"]["turns"], 1)

    def test_close_writes_summary_and_report(self):
        p = confirmed_plan()
        P.ensure_ids(p)
        common.write_json(self.sdir / "plan.json", p)
        common.write_json(self.sdir / M.FIRST_PLAN, p)
        M.update(self.sdir, "build", {"count": 2, "first_at": "2026-10-05T18:00:00-03:00", "failed": 1})
        M.append(self.sdir, "rounds", {"round": 1, "notes": 2, "levels": {"breve": 3}, "texts_edited": 1})
        M.error(self.sdir, "build", "faltan comentarios")
        rec = P.close_run(self.sdir, p, copy.deepcopy(DIGEST), CFG, NO_RAW, "load")
        self.assertTrue((self.sdir / "runs" / str(rec["n"]) / M.FILE).exists())
        lines = (self.root / M.GLOBAL).read_text().splitlines()
        self.assertEqual(len(lines), 1)
        summary = json.loads(lines[0])
        self.assertEqual((summary["rounds"], summary["builds"], summary["outcome"]), (1, 2, "load"))
        self.assertEqual(summary["attribution"]["accuracy"], 1.0)
        text = report_cli.report(report_cli.read())
        self.assertIn("2026-10-05", text)
        self.assertIn("breve 3", text)
        self.assertIn("1× build: faltan comentarios", text)

    def test_report_empty(self):
        self.assertIn("Sin métricas", report_cli.report([]))


if __name__ == "__main__":
    unittest.main()
