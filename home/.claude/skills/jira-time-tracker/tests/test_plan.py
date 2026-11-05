import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import plan as P
from lib import common

CFG = common.load_config(Path(__file__).resolve().parent.parent / "config.example.json")
NO_RAW = Path("/nonexistent/raw")

DIGEST = {
    "date": "2026-10-05",
    "range": {
        "start": "2026-10-05T08:55:00-03:00",
        "end": "2026-10-05T13:00:00-03:00",
        "breaks": [{"start": "2026-10-05T11:00:00-03:00", "end": "2026-10-05T11:30:00-03:00"}],
    },
    "worklogs": [
        {"id": "900", "issue": "SUP-5", "started": "2026-10-05T10:07:00.000-0300", "minutes": 45, "comment": "previo"},
    ],
    "candidates": [
        {"key": "SUP-1", "summary": "Importador de remitos", "status": "En curso", "status_category": "In Progress"},
        {"key": "SUP-5", "summary": "Fix stock en POS", "status": "En curso", "status_category": "In Progress"},
        {"key": "ENG-9", "summary": "Tablero PLC", "status": "programación finalizada", "status_category": "In Progress"},
        {"key": "SUP-101", "summary": "Tareas Varias - Reuniones", "status": "Abiertos", "status_category": "To Do"},
    ],
}

PLAN = {
    "date": "2026-10-05",
    "blocks": [
        {"start": "08:55", "end": "09:15", "issue": "SUP-101", "action": "new", "confidence": "alta",
         "sources": ["outlook"], "comments": {"breve": "Daily", "normal": "Daily normal", "detallado": "Daily detallado"}, "evidence": ["outlook:aaa"]},
        {"start": "09:15", "end": "10:05", "issue": "SUP-1", "action": "new", "confidence": "media",
         "sources": ["git", "cc"], "comments": {"breve": "Validación de CUIT", "normal": "Validación de CUIT normal", "detallado": "Validación de CUIT detallado"}, "evidence": ["git:111", "cc:222"]},
        {"start": "10:05", "end": "10:55", "issue": "SUP-5", "action": "adjust", "worklog_id": "900",
         "sources": ["jira"], "comment": "previo"},
        {"start": "10:55", "end": "11:00", "issue": "SUP-1", "action": "new", "confidence": "alta",
         "comments": {"breve": "x", "normal": "x normal", "detallado": "x detallado"}},
        {"start": "11:30", "end": "12:30", "issue": "SUP-1", "action": "new", "confidence": "alta",
         "comments": {"breve": "Tests importador", "normal": "Tests importador normal", "detallado": "Tests importador detallado"}},
    ],
    "gaps": [{"start": "12:30", "end": "13:00", "kind": "open"}],
    "absorbed": [{"time": "12:10", "minutes": 4, "issue": "SUP-7", "note": "chrome: vista del ticket"}],
}


def model(plan=None, digest=None):
    return P.validate(P.build_model(copy.deepcopy(plan or PLAN), copy.deepcopy(digest or DIGEST), CFG))


def fixed_plan():
    p = copy.deepcopy(PLAN)
    # 10:55–11:00 son 5 min: se fusiona con el bloque anterior.
    del p["blocks"][3]
    p["blocks"][2]["end"] = "11:00"
    return p


def confirmed_plan():
    p = fixed_plan()
    for b in p["blocks"]:
        b["confirmed"] = True
    p["gaps"] = [{"start": "12:30", "end": "13:00", "kind": "unworked", "confirmed": True}]
    return p


class TestValidate(unittest.TestCase):
    def test_short_block_detected(self):
        m = model()
        self.assertTrue(any("dura 5 min" in e for e in m.errors), m.errors)

    def test_valid_plan(self):
        m = model(fixed_plan())
        self.assertEqual(m.errors, [])

    def test_misaligned(self):
        p = fixed_plan()
        p["blocks"][0]["end"] = "09:13"
        p["blocks"][1]["start"] = "09:13"
        m = model(p)
        self.assertTrue(any("no está alineado" in e for e in m.errors))

    def test_overlap(self):
        p = fixed_plan()
        p["blocks"][0]["end"] = "09:30"
        m = model(p)
        self.assertTrue(any("se superponen" in e for e in m.errors))

    def test_uncovered(self):
        p = fixed_plan()
        p["gaps"] = []
        m = model(p)
        self.assertIn("tiempo sin cubrir 12:30–13:00", m.errors)

    def test_break_counts_as_covered(self):
        m = model(fixed_plan())
        self.assertFalse(any("11:00–11:30" in e for e in m.errors))

    def test_missing_existing_worklog(self):
        p = fixed_plan()
        p["blocks"][2] = {"start": "10:05", "end": "11:00", "issue": "SUP-5", "action": "new", "confidence": "alta"}
        m = model(p)
        self.assertTrue(any("falta el worklog existente 900" in e for e in m.errors))
        self.assertTrue(any("tiempo sin cubrir" not in e for e in m.errors))

    def test_existing_cannot_change_issue(self):
        p = fixed_plan()
        p["blocks"][2]["issue"] = "SUP-1"
        m = model(p)
        self.assertTrue(any("nunca se cambia de incidencia" in e for e in m.errors))

    def test_existing_with_moved_time_requires_adjust(self):
        p = fixed_plan()
        p["blocks"][2]["action"] = "existing"
        m = model(p)
        self.assertTrue(any("usar action 'adjust'" in e for e in m.errors))

    def test_existing_unaligned_is_warning(self):
        d = copy.deepcopy(DIGEST)
        d["range"]["breaks"] = []
        p = {
            "blocks": [
                {"start": "08:55", "end": "10:07", "issue": "SUP-1", "action": "new", "confidence": "alta"},
                {"start": "10:07", "end": "10:52", "issue": "SUP-5", "action": "existing", "worklog_id": "900"},
            ],
            "gaps": [{"start": "10:52", "end": "13:00", "kind": "unworked"}],
        }
        m = model(p, d)
        self.assertTrue(any("no está alineado a 5 min" in e for e in m.errors))  # el 'new' termina en 10:07
        self.assertTrue(any("worklog existente no alineado" in w for w in m.warnings))

    def test_excluded_status(self):
        p = fixed_plan()
        p["blocks"][-1]["issue"] = "ENG-9"
        m = model(p)
        self.assertTrue(any("estado excluido" in e for e in m.errors))

    def test_unknown_project(self):
        p = fixed_plan()
        p["blocks"][-1]["issue"] = "XYZ-1"
        m = model(p)
        self.assertTrue(any("no pertenece a los proyectos" in e for e in m.errors))

    def test_no_range_start(self):
        d = copy.deepcopy(DIGEST)
        d["range"]["start"] = None
        m = model(fixed_plan(), d)
        self.assertTrue(any("sin checkin" in e for e in m.errors))
        p = fixed_plan()
        p["start"] = "08:55"
        self.assertEqual(model(p, d).errors, [])

    def test_new_issue_ref(self):
        p = confirmed_plan()
        p["new_issues"] = [{"ref": "NEW-1", "project": "SUP", "type": "Tarea", "summary": "Algo nuevo"}]
        p["blocks"][-1]["issue"] = "NEW-1"
        m = model(p)
        self.assertEqual(m.errors, [])
        with self.assertRaisesRegex(ValueError, "usa NEW-1"):
            P.ops(m, P.compute_variants(m, NO_RAW))


def ops_for(plan, digest=None):
    m = model(plan, digest)
    return P.ops(m, P.compute_variants(m, NO_RAW))


def base_mode(p):
    p["modes"] = {"group": False, "lunch": False}
    return p


class TestOps(unittest.TestCase):
    def test_ops(self):
        result = ops_for(base_mode(confirmed_plan()))
        self.assertEqual([o["op"] for o in result], ["create", "create", "update", "create"])
        upd = result[2]
        self.assertEqual(upd["worklogId"], "900")
        self.assertEqual(upd["started"], "2026-10-05T10:05:00.000-0300")
        self.assertEqual(upd["timeSpent"], "55m")
        self.assertEqual(upd["commentBody"], "previo")
        self.assertEqual(result[0]["commentBody"], "Daily normal")
        self.assertEqual(result[3]["timeSpent"], "1h")
        self.assertEqual(result[0]["cloudId"], CFG["jira"]["cloud_id"])

    def test_ops_levels(self):
        p = base_mode(confirmed_plan())
        p["levels"] = {"b1": "nada", "b2": "detallado"}
        result = ops_for(p)
        self.assertEqual(result[0]["commentBody"], "")
        self.assertEqual(result[1]["commentBody"], "Validación de CUIT detallado")

    def test_ops_default_modes_use_lunch_gap(self):
        # config.example: agrupar y almuerzo activos; el almuerzo cae en el hueco no trabajado.
        m = model(confirmed_plan())
        vs = P.compute_variants(m, NO_RAW)
        self.assertEqual(vs["group+lunch"]["lunch"]["mode"], "gap")
        self.assertEqual(len(P.ops(m, vs)), 4)

    def test_ops_refuses_invalid(self):
        with self.assertRaises(ValueError):
            ops_for(base_mode(copy.deepcopy(PLAN)))

    def test_ops_requires_confirmation(self):
        with self.assertRaisesRegex(ValueError, "sin confirmar por el usuario: 08:55 SUP-101, 09:15 SUP-1"):
            ops_for(base_mode(fixed_plan()))

    def test_ops_requires_resolved_gaps(self):
        p = base_mode(confirmed_plan())
        p["gaps"][0]["kind"] = "open"
        with self.assertRaisesRegex(ValueError, r"huecos sin resolver.*: 12:30"):
            ops_for(p)

    def test_ops_requires_comments(self):
        p = base_mode(confirmed_plan())
        del p["blocks"][1]["comments"]
        with self.assertRaisesRegex(ValueError, "no tiene comentarios"):
            ops_for(p)

    def test_pending_and_existing_auto_confirmed(self):
        p = fixed_plan()
        p["blocks"][2] = {"start": "10:05", "end": "11:00", "issue": "SUP-5", "action": "adjust", "worklog_id": "900"}
        p["blocks"][0]["confirmed"] = True
        self.assertEqual([r.n for r in P.pending(model(p))], [2, 3, 5, 6])
        d = copy.deepcopy(DIGEST)
        d["worklogs"][0]["started"] = "2026-10-05T10:05:00.000-0300"
        d["worklogs"][0]["minutes"] = 55
        p["blocks"][2]["action"] = "existing"
        self.assertEqual([r.n for r in P.pending(model(p, d))], [2, 5, 6])


class TestIds(unittest.TestCase):
    def test_ids_assigned_and_stable(self):
        p = fixed_plan()
        self.assertTrue(P.ensure_ids(p))
        self.assertEqual([b["id"] for b in p["blocks"]], ["b1", "b2", "b3", "b4"])
        self.assertEqual(p["gaps"][0]["id"], "g1")
        self.assertFalse(P.ensure_ids(p))
        new_plan, _, _ = P.edit(p, copy.deepcopy(DIGEST), CFG, ["split b2 09:40"])
        self.assertEqual(sorted(b["id"] for b in new_plan["blocks"]), ["b1", "b2", "b3", "b4", "b5"])


def edited(ops, plan=None):
    new_plan, changed, m = P.edit(plan or confirmed_plan(), copy.deepcopy(DIGEST), CFG, ops)
    rows = {r.n: (r.kind, common.fmt_hm(r.start), common.fmt_hm(r.end), r.data.get("issue"), P.is_confirmed(r))
            for r in m.rows}
    return new_plan, changed, m, rows


class TestEdit(unittest.TestCase):
    # filas de confirmed_plan(): 1 SUP-101 08:55–09:15 · 2 SUP-1 09:15–10:05 · 3 SUP-5 (adjust) 10:05–11:00
    #                            4 salida 11:00–11:30 · 5 SUP-1 11:30–12:30 · 6 no trabajado 12:30–13:00

    def test_original_untouched_on_error(self):
        p = confirmed_plan()
        before = copy.deepcopy(p)
        with self.assertRaises(P.EditError):
            P.edit(p, DIGEST, CFG, ["confirm 1", "extend 3 +10"])  # 3 limita con la salida
        self.assertEqual(p, before)

    def test_extend_end_moves_next(self):
        _, changed, m, rows = edited(["extend 1 +10"])
        self.assertEqual(rows[1], ("block", "08:55", "09:25", "SUP-101", False))
        self.assertEqual(rows[2], ("block", "09:25", "10:05", "SUP-1", False))
        self.assertEqual(changed, [1, 2])
        self.assertEqual(m.errors, [])

    def test_extend_start_and_shrink(self):
        _, _, m, rows = edited(["extend 2 +10 start", "extend 2 -5"])
        self.assertEqual(rows[1][1:3], ("08:55", "09:05"))
        self.assertEqual(rows[2][1:3], ("09:05", "10:00"))
        self.assertEqual(rows[3][1:3], ("10:00", "11:00"))

    def test_not_multiple_of_slot(self):
        with self.assertRaisesRegex(P.EditError, "múltiplo"):
            edited(["extend 1 +7"])

    def test_existing_back_to_original_time(self):
        d = copy.deepcopy(DIGEST)
        d["worklogs"][0].update(started="2026-10-05T10:10:00.000-0300", minutes=50)
        p, _, m = P.edit(confirmed_plan(), d, CFG, ["extend 3 -5 start"])
        wl = next(b for b in p["blocks"] if b.get("worklog_id") == "900")
        self.assertEqual((wl["action"], wl["start"], wl["end"]), ("existing", "10:10", "11:00"))
        self.assertEqual(m.errors, [])

    def test_split_and_merge(self):
        p, changed, m, rows = edited(["split 2 09:40 issue=sup-7"])
        self.assertEqual(rows[2][1:4], ("09:15", "09:40", "SUP-1"))
        self.assertEqual(rows[3][1:5], ("09:40", "10:05", "SUP-7", False))
        _, _, m2, rows2 = edited(["merge 2 3"], p)
        self.assertEqual(rows2[2][1:4], ("09:15", "10:05", "SUP-1"))

    def test_merge_reflows_rows_between(self):
        p = confirmed_plan()
        p["blocks"][1]["end"] = "09:35"
        p["blocks"].insert(2, {"start": "09:35", "end": "10:05", "issue": "SUP-101", "action": "new",
                               "confidence": "alta", "comment": "c", "confirmed": True})
        _, changed, m, rows = edited(["merge 1 3"], p)
        self.assertEqual(rows[1][1:4], ("08:55", "09:45", "SUP-101"))
        self.assertEqual(rows[2][1:4], ("09:45", "10:05", "SUP-1"))
        self.assertEqual(m.errors, [])

    def test_merge_across_break_fails(self):
        with self.assertRaisesRegex(P.EditError, "salida"):
            edited(["merge 2 5"])

    def test_move(self):
        _, _, m, rows = edited(["move 1 after 2"])
        self.assertEqual(rows[1][1:4], ("08:55", "09:45", "SUP-1"))
        self.assertEqual(rows[2][1:4], ("09:45", "10:05", "SUP-101"))

    def test_absorb_both(self):
        _, _, m, rows = edited(["absorb 2"])
        self.assertEqual(rows[1][1:4], ("08:55", "09:40", "SUP-101"))
        self.assertEqual(rows[2][1:4], ("09:40", "11:00", "SUP-5"))
        self.assertEqual(m.errors, [])

    def test_absorb_existing_worklog_fails(self):
        with self.assertRaisesRegex(P.EditError, "worklog existente"):
            edited(["absorb 3"])

    def test_unworked_and_assign(self):
        p, _, m, rows = edited(["unworked 5"])
        self.assertEqual(rows[5][0], "gap")
        self.assertTrue(rows[5][4])
        _, _, m2, rows2 = edited(["assign 5 sup-9"], p)
        self.assertEqual(rows2[5], ("block", "11:30", "12:30", "SUP-9", False))

    def test_set_and_confirm(self):
        p, _, m, _ = edited(["set 2 confidence=baja sources=git,cc fixed=true", "unconfirm 2", "confirm 2"])
        b = next(b for b in p["blocks"] if b["start"] == "09:15")
        self.assertEqual((b["confidence"], b["fixed"]), ("baja", True))
        self.assertEqual(b["sources"], ["git", "cc"])
        self.assertTrue(b["confirmed"])

    def test_set_issue_on_existing_fails(self):
        with self.assertRaisesRegex(P.EditError, "no se cambia de incidencia"):
            edited(["set 3 issue=SUP-1"])

    def test_numbering_is_from_before_the_call(self):
        _, _, m, rows = edited(["split 1 09:05", "confirm 2"])
        # el 2 de antes (SUP-1) queda confirmado; la parte nueva del split queda pendiente
        self.assertEqual(rows[2][3:5], ("SUP-101", False))
        self.assertEqual(rows[3][3:5], ("SUP-1", True))

    def test_summary(self):
        _, changed, m, _ = edited(["extend 1 +10"])
        out = P.edit_summary(m, changed)
        self.assertIn("b1 · 08:55–09:25 SUP-101", out)
        self.assertIn("pendientes: b1 b2", out)

    def test_ids_as_refs(self):
        _, _, m, rows = edited(["extend b1 +10", "confirm b1"])
        self.assertEqual(rows[1], ("block", "08:55", "09:25", "SUP-101", True))

    def test_replace_new_ref(self):
        p = confirmed_plan()
        p["new_issues"] = [{"ref": "NEW-1", "project": "SUP", "type": "Tarea", "summary": "Algo"}]
        p["blocks"][-1]["issue"] = "NEW-1"
        p["followup"] = {"NEW-1": {"transition_id": "11"}}
        new_plan, _, m = P.edit(p, copy.deepcopy(DIGEST), CFG, ["replace NEW-1 sup-77"])
        self.assertEqual(new_plan["blocks"][-1]["issue"], "SUP-77")
        self.assertEqual(new_plan["new_issues"], [])
        self.assertIn("SUP-77", new_plan["followup"])
        self.assertNotIn("created", new_plan)

    def test_replace_created_is_recorded(self):
        p = confirmed_plan()
        p["new_issues"] = [{"ref": "NEW-1", "project": "SUP", "type": "Tarea", "summary": "Algo", "decision": "create"}]
        p["blocks"][-1]["issue"] = "NEW-1"
        new_plan, _, _ = P.edit(p, copy.deepcopy(DIGEST), CFG, ["replace NEW-1 SUP-77"])
        self.assertEqual(new_plan["created"], ["SUP-77"])


class TestNewIssue(unittest.TestCase):
    SPEC = {"project": "SUP", "type": "Tarea", "summary": "Migración de remitos", "similar": ["SUP-1"],
            "fields": [{"key": "description", "name": "Descripción", "value": "x"}], "blocks": ["b2", "b4"]}

    def test_adds_draft_and_moves_blocks(self):
        p = confirmed_plan()
        p["confirmed_rows"] = ["b2", "b1"]
        new_plan, ref, m = P.add_new_issue(p, copy.deepcopy(DIGEST), CFG, copy.deepcopy(self.SPEC))
        self.assertEqual(ref, "NEW-1")
        self.assertEqual(m.errors, [])
        by_id = {b["id"]: b for b in new_plan["blocks"]}
        self.assertEqual((by_id["b2"]["issue"], by_id["b4"]["issue"]), ("NEW-1", "NEW-1"))
        self.assertEqual(new_plan["new_issues"][0]["summary"], "Migración de remitos")
        self.assertNotIn("blocks", new_plan["new_issues"][0])
        self.assertEqual(new_plan["confirmed_rows"], ["b1"])
        self.assertNotIn("new_issues", p)
        _, ref2, _ = P.add_new_issue(new_plan, copy.deepcopy(DIGEST), CFG, {**self.SPEC, "blocks": ["b1"]})
        self.assertEqual(ref2, "NEW-2")

    def test_rejects_existing_worklog_and_missing_fields(self):
        with self.assertRaises(P.EditError):
            P.add_new_issue(confirmed_plan(), DIGEST, CFG, {**self.SPEC, "blocks": ["b3"]})
        with self.assertRaises(P.EditError):
            P.add_new_issue(confirmed_plan(), DIGEST, CFG, {**self.SPEC, "summary": ""})
        with self.assertRaises(P.EditError):
            P.add_new_issue(confirmed_plan(), DIGEST, CFG, {**self.SPEC, "blocks": []})


class TestFollowupRound(unittest.TestCase):
    TRANS = [{"id": "11", "name": "Comenzar", "to": "En curso", "fields": []},
             {"id": "31", "name": "Resolver", "to": "Resuelto", "fields": []}]

    def test_match_transition(self):
        self.assertEqual(P.match_transition(self.TRANS, "31")["name"], "Resolver")
        self.assertEqual(P.match_transition(self.TRANS, "en curso")["id"], "11")
        self.assertEqual(P.match_transition(self.TRANS, "resolver")["id"], "31")
        self.assertIsNone(P.match_transition(self.TRANS, "Cerrado"))

    def test_followup_round(self):
        plan = {"created": ["SUP-77"], "followup": {"SUP-1": {"transition_id": "5"}}}
        meta = {"SUP-77": {"status": "Abierto", "transitions": self.TRANS}}
        out = P.followup_round(plan, meta, ["sup-77=En curso", "SUP-1=x"])
        self.assertEqual(plan["stage"], "followup")
        self.assertEqual(plan["followup"], {"SUP-77": {"transition_id": "11", "transition": "Comenzar",
                                                       "to": "En curso", "fields": {}}})
        self.assertIn("SUP-77 · Abierto · transiciones: 11: Comenzar → En curso; 31: Resolver → Resuelto", out)
        self.assertIn("! SUP-1 no es una incidencia creada en esta sesión", out)
        out = P.followup_round(plan, meta, ["SUP-77=Cerrado"])
        self.assertEqual(plan["followup"], {})
        self.assertTrue(any("no coincide" in line for line in out))


class TestFetchMeta(unittest.TestCase):
    def test_cache_only_valid_the_same_day(self):
        from datetime import date
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "jira_meta.json"
            common.write_json(path, {"fetched": "2026-10-28", "issues": {"SUP-1": {"status": "viejo"}}})
            with mock.patch.object(P.jira, "JiraClient"), \
                    mock.patch.object(P.jira, "fetch_issue_meta", return_value={"SUP-1": {"status": "nuevo"}}) as f:
                meta = P.fetch_meta(CFG, {"JIRA_API_TOKEN": "t"}, ["SUP-1"], path, today=date(2026, 10, 29))
                self.assertEqual(meta["SUP-1"]["status"], "nuevo")
                meta = P.fetch_meta(CFG, {"JIRA_API_TOKEN": "t"}, ["SUP-1"], path, today=date(2026, 10, 29))
                self.assertEqual(f.call_count, 1)
                P.fetch_meta(CFG, {"JIRA_API_TOKEN": "t"}, ["SUP-1"], path, refresh=True, today=date(2026, 10, 29))
                self.assertEqual(f.call_count, 2)
            self.assertEqual(common.read_json(path)["fetched"], "2026-10-29")


class TestExpandAndCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "raw").mkdir()
        common.write_json(self.dir / "raw" / "git_local.json", {"source": "git_local", "events": [
            {"id": "git:111", "source": "git", "start": "2026-10-05T12:20:00Z", "end": "2026-10-05T12:20:00Z",
             "title": "commit abc123: valida CUIT", "detail": "", "hints": {"repo": "erp", "issue_keys": ["SUP-1"]}},
        ]})
        common.write_json(self.dir / "plan.json", confirmed_plan())
        common.write_json(self.dir / "digest.json", DIGEST)
        self.cfg_path = Path(__file__).resolve().parent.parent / "config.example.json"

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = P.main(["--config", str(self.cfg_path), "--plan", str(self.dir / "plan.json"),
                           "--digest", str(self.dir / "digest.json"), *args])
        return code, buf.getvalue()

    def test_expand(self):
        code, out = self.run_cli("expand", "b2")
        self.assertEqual(code, 0)
        self.assertIn("[git] 09:20 commit abc123: valida CUIT", out)
        self.assertIn("? cc:222 (no encontrado en raw/)", out)
        self.assertIn("Comentario breve: Validación de CUIT", out)
        self.assertEqual(self.run_cli("expand", "2")[1], out)

    def test_validate_cli(self):
        code, out = self.run_cli("validate")
        self.assertEqual(code, 0)
        self.assertIn("OK (4 bloques", out)

    def test_edit_cli(self):
        code, out = self.run_cli("edit", "extend 1 +10")
        self.assertEqual(code, 0)
        self.assertIn("b1 · 08:55–09:25 SUP-101", out)
        saved = common.read_json(self.dir / "plan.json")
        self.assertEqual(saved["blocks"][0]["end"], "09:25")
        code, out = self.run_cli("edit", "extend 3 +10")
        self.assertEqual(code, 1)
        self.assertIn("no se guardó nada", out)

    def test_ops_cli(self):
        code, out = self.run_cli("ops")
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)), 4)

    def test_comments_cli(self):
        p = confirmed_plan()
        del p["blocks"][1]["comments"]
        common.write_json(self.dir / "plan.json", p)
        code, out = self.run_cli("build", "--no-jira")
        self.assertEqual(code, 1)
        self.assertIn("Faltan comentarios", out)
        self.assertIn("b2 · 09:15–10:05 · SUP-1 Importador de remitos", out)
        self.assertFalse((self.dir / "review.html").exists())
        with mock.patch("sys.stdin", io.StringIO('{"b2": {"breve": "a", "normal": "b"}}')):
            code, out = self.run_cli("comments")
        self.assertEqual(code, 1)
        self.assertIn("los tres niveles", out)
        with mock.patch("sys.stdin", io.StringIO('{"b2": {"breve": "a", "normal": "b", "detallado": "c"}}')):
            code, out = self.run_cli("comments")
        self.assertEqual(code, 0)
        self.assertIn("no falta ninguno", out)

    def test_build_cli(self):
        code, out = self.run_cli("build", "--no-jira", "--note", "Hola")
        self.assertEqual(code, 0, out)
        self.assertIn("ronda 1, variante inicial group+lunch", out)
        self.assertIn("almuerzo 12:30–13:00 (en el hueco g1)", out)
        html = (self.dir / "review.html").read_text()
        self.assertIn("<title>Horas del lunes 05/10</title>", html)
        blob = html.split('<script id="jtt-data" type="application/json">')[1].split("</script>")[0]
        data = json.loads(blob)
        self.assertEqual(data["note"], "Hola")
        self.assertEqual(set(data["variants"]), {"base", "lunch", "group", "group+lunch"})
        self.assertEqual(data["blocks"]["b2"]["evidence"], ["git:111"])
        self.assertIn("git:111", data["events"])
        self.assertEqual(data["blocks"]["b3"]["original"], "10:07–10:52")

    def test_review_cli(self):
        state = {"round": 1, "modes": {"group": False, "lunch": False}, "confirmed": {"b1": False},
                 "levels": {"b2": "breve"}, "notes": {"b2": "esto era SUP-9"}, "global_note": "todo bien",
                 "absorb": {}, "gaps": {}, "action": "review", "sent": True}
        with mock.patch("sys.stdin", io.StringIO(json.dumps(state))):
            code, out = self.run_cli("review", "-")
        self.assertEqual(code, 0)
        self.assertIn("[b2 · 09:15–10:05 · SUP-1 Importador de remitos] esto era SUP-9", out)
        self.assertIn("[general] todo bien", out)
        self.assertIn("ACCIÓN: review", out)
        saved = common.read_json(self.dir / "plan.json")
        self.assertEqual(saved["round"], 2)
        self.assertEqual(saved["modes"], {"group": False, "lunch": False})
        self.assertEqual(saved["levels"], {"b2": "breve"})
        self.assertFalse(saved["blocks"][0]["confirmed"])
        self.assertNotIn("b1", saved["confirmed_rows"])

    def test_review_load(self):
        state = {"round": 1, "modes": {"group": True, "lunch": True}, "action": "load", "sent": True,
                 "followup": {"SUP-1": {"transition_id": "31", "transition": "Resolver", "to": "Resuelto",
                                        "fields": {"resolution": "Listo"}, "comment": "Se corrigió", "publish": True}}}
        common.write_json(self.dir / "page_state.json", state)
        code, out = self.run_cli("review")
        self.assertIn("Listo para cargar: 4 operaciones", out)
        self.assertIn("transición SUP-1: Resolver (id 31)", out)
        self.assertIn("comentario de resolución en SUP-1: Se corrigió", out)

    def test_review_rejects_stale_or_unsent_state(self):
        for st, msg in (({"round": 1, "action": "review"}, "todavía no dice que se envió"),
                        ({"round": 0, "action": "review", "sent": True}, "es de la ronda 0 y el plan está en la 1")):
            common.write_json(self.dir / "state.json", st)
            code, out = self.run_cli("review", str(self.dir / "state.json"))
            self.assertEqual(code, 1)
            self.assertIn(msg, out)
        self.assertNotIn("round", common.read_json(self.dir / "plan.json"))

    def test_review_reassign(self):
        state = {"round": 1, "action": "review", "sent": True, "confirmed": {"b2": True},
                 "reassign": {"b1": "SUP-5", "b2": "new:1", "b4": "new:1"},
                 "new_requests": {"1": {"hint": "migración de remitos"}}}
        common.write_json(self.dir / "state.json", state)
        code, out = self.run_cli("review", str(self.dir / "state.json"))
        self.assertEqual(code, 0)
        self.assertIn("✓ set b1 issue=SUP-5", out)
        self.assertIn("nueva 1 → b2 09:15–10:05 (hoy en SUP-1), b4 11:30–12:30 (hoy en SUP-1): «migración de remitos»", out)
        saved = common.read_json(self.dir / "plan.json")
        self.assertEqual(saved["blocks"][0]["issue"], "SUP-5")
        with mock.patch("sys.stdin", io.StringIO(json.dumps({
                "project": "SUP", "type": "Tarea", "summary": "Migración", "blocks": ["b2", "b4"]}))):
            code, out = self.run_cli("new-issue")
        self.assertEqual(code, 0, out)
        self.assertIn("NEW-1: Migración · bloques b2, b4", out)

    def test_followup_round_cli(self):
        code, out = self.run_cli("build", "--followup", "--no-jira")
        self.assertEqual(code, 1)
        self.assertIn("No hay incidencias creadas", out)
        p = common.read_json(self.dir / "plan.json")
        p["created"] = ["SUP-1"]
        p["round"] = 2
        common.write_json(self.dir / "plan.json", p)
        code, out = self.run_cli("build", "--followup", "--no-jira", "--note", "Elegí el estado")
        self.assertEqual(code, 0, out)
        html = (self.dir / "review.html").read_text()
        data = json.loads(html.split('<script id="jtt-data" type="application/json">')[1].split("</script>")[0])
        self.assertEqual((data["stage"], data["followup_keys"]), ("followup", ["SUP-1"]))
        self.assertEqual(common.read_json(self.dir / "plan.json")["stage"], "followup")
        state = {"round": 2, "action": "apply", "sent": True, "followup": {"SUP-1": {"transition_id": "11", "transition": "Comenzar",
                                                                      "to": "En curso", "fields": {}}}}
        common.write_json(self.dir / "state.json", state)
        code, out = self.run_cli("review", str(self.dir / "state.json"))
        self.assertIn("ACCIÓN: apply", out)
        self.assertIn("transición SUP-1: Comenzar (id 11)", out)
        self.assertNotIn("Listo para cargar", out)


if __name__ == "__main__":
    unittest.main()
