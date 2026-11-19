"""Tandas del mismo día, comentarios editados a mano en la página y borradores de incidencias nuevas."""

import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import collect as C
import plan as P
from lib import common, variants

from tests.test_plan import CFG, DIGEST, NO_RAW, confirmed_plan, model


def base_mode(p):
    p["modes"] = {"group": False, "lunch": False}
    return p


def ops_for(p, **kw):
    m = model(p)
    return P.ops(m, P.compute_variants(m, NO_RAW), **kw)


class TestTexts(unittest.TestCase):
    def test_clean_text_keeps_lines(self):
        self.assertEqual(P.clean_text("- uno  dos\n\n-   tres \n"), "- uno dos\n- tres")

    def test_set_comments_keeps_bullets_and_drops_own_text(self):
        p = confirmed_plan()
        P.ensure_ids(p)
        p["texts"] = {"b2": "mío"}
        errs = P.set_comments(p, {"b2": {"breve": "a", "normal": "b", "detallado": "- x\n- y"}})
        self.assertEqual(errs, [])
        self.assertEqual(p["blocks"][1]["comments"]["detallado"], "- x\n- y")
        self.assertNotIn("b2", p["texts"])

    def test_ops_use_own_text_over_level(self):
        p = base_mode(confirmed_plan())
        p["levels"] = {"b1": "nada"}
        p["texts"] = {"b1": "Daily con el equipo", "b2": ""}
        result = ops_for(p)
        self.assertEqual(result[0]["commentBody"], "Daily con el equipo")
        self.assertEqual(result[1]["commentBody"], "")

    def test_review_stores_texts_and_summary(self):
        p = confirmed_plan()
        p["new_issues"] = [{"ref": "NEW-1", "project": "SUP", "type": "Tarea", "summary": "Viejo", "fields": []}]
        p["blocks"][1]["issue"] = "NEW-1"
        P.ensure_ids(p)
        st = {"round": 1, "texts": {"b2": "  texto propio\n- con viñeta "}, "action": "review", "sent": True,
              "new_issues": {"NEW-1": {"decision": "create", "summary": "  Alta   de usuario "}}}
        new_plan, _ = P.apply_review(p, copy.deepcopy(DIGEST), CFG, NO_RAW, st)
        self.assertEqual(new_plan["texts"], {"b2": "texto propio\n- con viñeta"})
        self.assertEqual(new_plan["new_issues"][0]["summary"], "Alta de usuario")


class TestDrafts(unittest.TestCase):
    def plan_with_draft(self):
        p = confirmed_plan()
        p["new_issues"] = [{"ref": "NEW-1", "project": "SUP", "type": "Tarea", "summary": "Viejo",
                            "fields": [{"key": "description", "name": "Descripción", "value": "x"}]}]
        p["blocks"][1]["issue"] = "NEW-1"
        return p

    def test_draft_edits_fields(self):
        new_plan, _, _ = P.edit(self.plan_with_draft(), copy.deepcopy(DIGEST), CFG,
                                ["draft NEW-1 'summary=Alta de usuario' field.reporter=Héctor 'field.description=y z' parent=SUP-1"])
        ni = new_plan["new_issues"][0]
        self.assertEqual((ni["summary"], ni["parent"]), ("Alta de usuario", "SUP-1"))
        fields = {f["key"]: f for f in ni["fields"]}
        self.assertEqual(fields["description"]["value"], "y z")
        self.assertEqual((fields["reporter"]["name"], fields["reporter"]["value"]), ("Informador", "Héctor"))

    def test_draft_errors(self):
        for op in ("draft NEW-9 summary=x", "draft NEW-1 summary=", "draft NEW-1 color=rojo", "draft NEW-1 sin"):
            with self.assertRaises(P.EditError, msg=op):
                P.edit(self.plan_with_draft(), copy.deepcopy(DIGEST), CFG, [op])

    def test_load_check_accepts_pending_creates(self):
        p = base_mode(self.plan_with_draft())
        with self.assertRaises(ValueError):
            ops_for(p, allow_pending_creates=True)  # sin decisión de crear
        p["new_issues"][0]["decision"] = "create"
        self.assertEqual(len(ops_for(p, allow_pending_creates=True)), 4)
        with self.assertRaises(ValueError):
            ops_for(p)  # la carga real necesita la key


class TestRuns(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.patch = mock.patch.object(common, "STATE_ROOT", self.root)
        self.patch.start()
        self.env = mock.patch.dict("os.environ", {"CLAUDE_CODE_SESSION_ID": ""})
        self.env.start()
        self.day = common.parse_day("2026-10-05", common.get_tz(CFG))
        self.sdir = common.state_dir(self.day)

    def tearDown(self):
        self.patch.stop()
        self.env.stop()
        self.tmp.cleanup()

    def test_close_archives_and_next_digest_starts_after(self):
        p = base_mode(confirmed_plan())
        common.write_json(self.sdir / "plan.json", p)
        common.write_json(self.sdir / "page_state.json", {"action": "load"})
        rec = P.close_run(self.sdir, p, copy.deepcopy(DIGEST), CFG, NO_RAW, "load")
        self.assertEqual((rec["n"], rec["outcome"], rec["lunch"]), (1, "load", False))
        self.assertFalse((self.sdir / "plan.json").exists())
        self.assertTrue((self.sdir / "runs" / "1" / "plan.json").exists())
        self.assertTrue((self.sdir / "runs" / "1" / "page_state.json").exists())
        runs = common.load_runs(self.day)
        self.assertEqual(common.loaded_until(runs), "2026-10-05T13:00:00-03:00")

        ev_old = {"id": "git:1", "source": "git", "start": "2026-10-05T12:00:00-03:00", "end": "2026-10-05T12:00:00-03:00", "title": "viejo"}
        ev_new = {"id": "git:2", "source": "git", "start": "2026-10-05T14:00:00-03:00", "end": "2026-10-05T14:00:00-03:00", "title": "nuevo"}
        erp = {"range": {"start": "2026-10-05T08:55:00-03:00", "end": "2026-10-05T18:00:00-03:00",
                         "breaks": [{"start": "2026-10-05T11:00:00-03:00", "end": "2026-10-05T11:30:00-03:00"}],
                         "checkins": []}}
        from datetime import datetime
        d = C.build_digest(self.day, CFG, {"erpnext": erp, "git_local": {"events": [ev_old, ev_new]}},
                           datetime.fromisoformat("2026-10-05T18:00:00-03:00"))
        self.assertEqual(d["range"]["from"], "2026-10-05T13:00:00-03:00")
        self.assertEqual(d["range"]["breaks"], [])
        self.assertEqual([e["id"] for e in d["timeline"]], ["git:2"])
        self.assertEqual(erp["range"]["breaks"][0]["start"], "2026-10-05T11:00:00-03:00")  # no muta el original
        self.assertIn("TANDA 2", C.render_digest(d, common.get_tz(CFG)))

    def test_cancel_does_not_advance(self):
        p = confirmed_plan()
        P.close_run(self.sdir, p, copy.deepcopy(DIGEST), CFG, NO_RAW, "cancel")
        self.assertIsNone(common.loaded_until(common.load_runs(self.day)))

    def test_second_run_validation_and_lunch(self):
        digest = copy.deepcopy(DIGEST)
        digest["range"].update({"from": "2026-10-05T11:30:00-03:00", "breaks": []})
        # El worklog 900 (10:07–10:52) es de la tanda anterior: no hace falta en el plan.
        p = {"date": "2026-10-05", "blocks": [
            {"start": "11:30", "end": "13:00", "issue": "SUP-1", "action": "new", "confidence": "alta",
             "comments": {"breve": "a", "normal": "b", "detallado": "c"}}]}
        m = P.validate(P.build_model(p, digest, CFG))
        self.assertEqual(m.errors, [])
        self.assertIsNone(variants.lunch_skip_reason(m))
        digest["range"]["lunch_done_in"] = 1
        m = P.validate(P.build_model(p, digest, CFG))
        self.assertIn("tanda 1", variants.lunch_skip_reason(m))
        vs = P.compute_variants(m, NO_RAW)
        self.assertEqual(vs["lunch"]["lunch"]["mode"], "none")
        self.assertEqual(vs["lunch"]["errors"], [])

    def test_lunch_window_outside_run(self):
        digest = copy.deepcopy(DIGEST)
        digest["range"]["end"] = "2026-10-05T12:00:00-03:00"
        p = {"date": "2026-10-05", "start": "09:00", "blocks": [
            {"start": "09:00", "end": "12:00", "issue": "SUP-1", "action": "new", "confidence": "alta",
             "comments": {"breve": "a", "normal": "b", "detallado": "c"}}]}
        digest["worklogs"] = []
        digest["range"]["breaks"] = []
        m = P.validate(P.build_model(p, digest, CFG))
        self.assertEqual(m.errors, [])
        self.assertIn("queda fuera de esta tanda", variants.lunch_skip_reason(m))


if __name__ == "__main__":
    unittest.main()
