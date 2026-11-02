import copy
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import plan as P
from lib import common, variants

CFG = common.load_config(Path(__file__).resolve().parent.parent / "config.example.json")
TZ = ZoneInfo("America/Argentina/Buenos_Aires")
DIGEST = {"date": "2026-10-05", "range": {"start": "2026-10-05T09:00:00-03:00", "end": "2026-10-05T18:00:00-03:00",
                                          "breaks": []}, "worklogs": [], "candidates": []}
COMMENTS = {"breve": "b", "normal": "n", "detallado": "d"}


def blk(start, end, issue, **kw):
    return {"start": start, "end": end, "issue": issue, "action": "new", "confidence": "alta",
            "comments": dict(COMMENTS), "confirmed": True, **kw}


# A y B alternados toda la jornada, una reunión fija a las 10:00 y C a la tarde.
DAY = {"date": "2026-10-05", "blocks": [
    blk("09:00", "10:00", "SUP-1"),
    blk("10:00", "10:30", "SUP-101", fixed=True),
    blk("10:30", "11:30", "SUP-2"),
    blk("11:30", "12:30", "SUP-1"),
    blk("12:30", "13:30", "SUP-2"),
    blk("13:30", "14:30", "SUP-1"),
    blk("14:30", "16:00", "SUP-3"),
    blk("16:00", "17:00", "SUP-2"),
    blk("17:00", "18:00", "SUP-1"),
]}


def t(hm):
    h, m = map(int, hm.split(":"))
    return datetime(2026, 10, 5, h, m, tzinfo=TZ)


# Actividad continua salvo 13:00–13:30, que cae dentro del bloque de SUP-2.
QUIET_13 = [(t("09:00"), t("13:00")), (t("13:30"), t("18:00"))]


def compute(plan=None, events=QUIET_13, digest=None):
    m = P.validate(P.build_model(copy.deepcopy(plan or DAY), copy.deepcopy(digest or DIGEST), CFG))
    assert m.errors == [], m.errors
    return m, variants.compute(m, events)


def layout(v):
    return [(common.fmt_hm(r["start"]), common.fmt_hm(r["end"]), r.get("issue") or r["kind"]) for r in v["rows"]]


SHARED = {"date": "2026-10-05", "blocks": [
    blk("09:00", "09:35", "SUP-1"),
    blk("09:35", "09:55", "SUP-2"),
    blk("09:55", "10:55", "SUP-1"),
    blk("10:55", "11:05", "SUP-3"),
    blk("11:05", "11:45", "SUP-1"),
    blk("11:45", "12:10", "SUP-2"),
    blk("12:10", "12:30", "SUP-1"),
    blk("12:30", "13:00", "SUP-2"),
    blk("13:00", "13:40", "SUP-1"),
]}
SHARED_EVENTS = [(t("09:00"), t("12:10")), (t("12:40"), t("13:40"))]



class TestLunch(unittest.TestCase):
    def test_discount_from_least_active_issue(self):
        _, vs = compute()
        v = vs["lunch"]
        self.assertEqual(v["errors"], [])
        self.assertEqual(v["lunch"]["discounts"], {"SUP-2": 30})
        self.assertEqual(v["totals"], {"SUP-1": 240, "SUP-101": 30, "SUP-2": 150, "SUP-3": 90})
        self.assertIn(("13:00", "13:30", "lunch"), layout(v))
        self.assertIn(("12:30", "13:00", "SUP-2"), layout(v))

    def test_split_window_is_shared(self):
        # Sin actividad 12:15–12:45: la ventana válida más tranquila arranca 12:30 y cae
        # entera en SUP-2; con 12:20–12:50 de silencio se reparte 10/20 entre SUP-1 y SUP-2.
        events = [(t("09:00"), t("12:20")), (t("12:50"), t("18:00"))]
        _, vs = compute(events=events)
        self.assertEqual(vs["lunch"]["lunch"]["window"], (t("12:30"), t("13:00")))
        plan = copy.deepcopy(DAY)
        plan["blocks"][3]["end"] = "12:40"
        plan["blocks"][4]["start"] = "12:40"
        events = [(t("09:00"), t("12:30")), (t("13:00"), t("18:00"))]
        _, vs = compute(plan, events)
        self.assertEqual(vs["lunch"]["lunch"]["discounts"], {"SUP-1": 10, "SUP-2": 20})
        self.assertEqual(vs["lunch"]["errors"], [])

    def test_existing_gap_is_used(self):
        plan = copy.deepcopy(DAY)
        plan["blocks"][4] = blk("12:30", "13:00", "SUP-2")
        plan["gaps"] = [{"start": "13:00", "end": "13:30", "kind": "unworked"}]
        _, vs = compute(plan)
        self.assertEqual(vs["lunch"]["lunch"]["mode"], "gap")
        self.assertEqual(vs["lunch"]["lunch"]["discounts"], {})
        self.assertEqual(vs["lunch"]["totals"], vs["base"]["totals"])
        self.assertIn(("13:00", "13:30", "lunch"), layout(vs["lunch"]))

    def test_never_leaves_short_blocks(self):
        plan = copy.deepcopy(DAY)
        plan["blocks"][4] = blk("12:30", "13:05", "SUP-2")
        plan["blocks"][5]["start"] = "13:05"
        _, vs = compute(plan, [(t("09:00"), t("12:35")), (t("13:05"), t("18:00"))])
        for r in vs["lunch"]["rows"]:
            if r["kind"] == "block":
                self.assertGreaterEqual(variants.minutes(r), 10)
        self.assertEqual(vs["lunch"]["errors"], [])

    def test_no_window(self):
        plan = copy.deepcopy(DAY)
        plan["blocks"][4]["fixed"] = True
        plan["blocks"][5]["fixed"] = True
        _, vs = compute(plan)
        self.assertEqual(vs["lunch"]["lunch"]["mode"], "none")
        self.assertTrue(vs["lunch"]["warnings"])
        self.assertEqual(vs["lunch"]["rows"], vs["base"]["rows"])


class TestGroup(unittest.TestCase):
    def test_group_keeps_totals_and_fixed(self):
        _, vs = compute()
        v = vs["group"]
        self.assertEqual(v["errors"], [])
        self.assertEqual(v["totals"], vs["base"]["totals"])
        self.assertEqual(layout(v), [
            ("09:00", "10:00", "SUP-1"),
            ("10:00", "10:30", "SUP-101"),
            ("10:30", "13:30", "SUP-2"),
            ("13:30", "16:30", "SUP-1"),
            ("16:30", "18:00", "SUP-3"),
        ])
        self.assertEqual(v["rows"][2]["ids"], ["b3", "b5", "b8"])
        self.assertEqual(v["rows"][2]["key"], "b3+b5+b8")

    def test_group_and_lunch(self):
        # El almuerzo se descuenta de SUP-2 (13:00–13:30 sin actividad) aunque al agrupar
        # SUP-2 quede a la mañana; el hueco queda dentro de 12:30–14:00.
        _, vs = compute()
        v = vs["group+lunch"]
        self.assertEqual(v["errors"], [])
        self.assertEqual(v["totals"], {"SUP-1": 240, "SUP-101": 30, "SUP-2": 150, "SUP-3": 90})
        self.assertEqual(layout(v), [
            ("09:00", "10:00", "SUP-1"),
            ("10:00", "10:30", "SUP-101"),
            ("10:30", "13:00", "SUP-2"),
            ("13:00", "13:30", "lunch"),
            ("13:30", "16:30", "SUP-1"),
            ("16:30", "18:00", "SUP-3"),
        ])

    def test_fewer_worklogs(self):
        _, vs = compute()
        count = {k: sum(r["kind"] == "block" for r in v["rows"]) for k, v in vs.items()}
        self.assertEqual(count, {"base": 9, "lunch": 9, "group": 5, "group+lunch": 5})


class TestProvenance(unittest.TestCase):
    def test_src_tracks_minutes_per_block(self):
        # Caso real: la incidencia cruza el almuerzo y cede tiempo a otra al agrupar; cada fila
        # tiene que decir exactamente cuántos minutos toma de cada bloque.
        plan = SHARED
        digest = copy.deepcopy(DIGEST)
        digest["range"]["end"] = "2026-10-05T13:40:00-03:00"
        m, vs = compute(plan, SHARED_EVENTS, digest)
        base_minutes = {r.data["id"]: r.minutes for r in m.rows if r.kind == "block"}
        for name, v in vs.items():
            self.assertEqual(v["errors"], [], name)
            used = {}
            for r in v["rows"]:
                if r["kind"] == "block":
                    self.assertEqual(sum(r["src"].values()), variants.minutes(r), (name, r["key"]))
                    self.assertEqual(r["ids"], list(r["src"]))
                    for i, mins in r["src"].items():
                        used[i] = used.get(i, 0) + mins
            cut = (v["lunch"] or {}).get("cut_ids") or {}
            self.assertEqual(used, {i: mm - cut.get(i, 0) for i, mm in base_minutes.items() if mm - cut.get(i, 0)}, name)

    def test_take_src(self):
        taken, left = variants.take_src({"b1": 30, "b2": 60}, 40, from_end=True)
        self.assertEqual((taken, left), ({"b2": 40}, {"b1": 30, "b2": 20}))
        taken, left = variants.take_src({"b1": 30, "b2": 60}, 40, from_end=False)
        self.assertEqual((taken, left), ({"b1": 30, "b2": 10}, {"b2": 50}))


# Estructura del día real que mostró el problema (20/10): SIT-415 queda en tres filas que
# comparten bloques al agrupar con almuerzo.
DAY20 = {"date": "2026-10-05", "blocks": [
    blk("09:10", "09:25", "SUP-7"), blk("09:25", "09:45", "SUP-2"), blk("09:45", "10:00", "SUP-3"),
    blk("10:00", "10:10", "SUP-1"), blk("10:20", "10:55", "SUP-1"), blk("10:55", "11:15", "SUP-2"),
    blk("11:15", "12:15", "SUP-1"), blk("12:15", "12:25", "SUP-3"), blk("12:25", "13:05", "SUP-1"),
    blk("13:05", "13:30", "SUP-2"), blk("13:30", "13:50", "SUP-1"), blk("13:50", "14:20", "SUP-2"),
    blk("14:20", "15:00", "SUP-1"), blk("15:00", "15:15", "SUP-4"),
], "gaps": [{"start": "10:10", "end": "10:20", "kind": "open"}]}
DAY20_DIGEST = {"date": "2026-10-05", "range": {"start": "2026-10-05T09:10:00-03:00",
                                                "end": "2026-10-05T15:15:00-03:00", "breaks": []},
                "worklogs": [], "candidates": []}
DAY20_EVENTS = [(t("09:10"), t("12:35")), (t("13:05"), t("15:15"))]


def unconfirmed(plan):
    p = copy.deepcopy(plan)
    for b in p["blocks"]:
        b.pop("confirmed", None)
    p["modes"] = {"group": True, "lunch": True}
    return p


class TestRowConfirmation(unittest.TestCase):
    def setUp(self):
        self.digest = copy.deepcopy(DIGEST)
        self.digest["range"]["end"] = "2026-10-05T13:40:00-03:00"

    def test_keys_unique_per_variant(self):
        for name, v in compute(DAY20, DAY20_EVENTS, DAY20_DIGEST)[1].items():
            keys = [r["key"] for r in v["rows"] if r["kind"] == "block"]
            self.assertEqual(len(keys), len(set(keys)), name)

    def test_rows_sharing_a_block_confirm_independently(self):
        plan = unconfirmed(DAY20)
        m, vs = compute(plan, DAY20_EVENTS, DAY20_DIGEST)
        rows = [r for r in vs["group+lunch"]["rows"] if r["kind"] == "block"]
        shared = [(a, b) for a in rows for b in rows if a is not b and set(a["ids"]) & set(b["ids"])]
        self.assertTrue(shared, "el escenario tiene que tener filas que comparten un bloque")
        a, b = shared[0]
        plan["confirmed_rows"] = [a["key"]]
        m, vs = compute(plan, DAY20_EVENTS, DAY20_DIGEST)
        self.assertTrue(P.row_confirmed(m, a))
        self.assertFalse(P.row_confirmed(m, b))
        plan["confirmed_rows"] = [r["key"] for r in rows]
        plan["gaps"][0]["kind"] = "unworked"
        plan["levels"] = {r["key"]: "nada" for r in rows}
        m, vs = compute(plan, DAY20_EVENTS, DAY20_DIGEST)
        self.assertEqual(len(P.ops(m, vs)), len(rows))

    def test_edit_drops_confirmation_of_touched_rows(self):
        plan = unconfirmed(SHARED)
        plan["confirmed_rows"] = ["b1", "b2+b6", "b3+b5"]
        new_plan, _, _ = P.edit(plan, copy.deepcopy(self.digest), CFG, ["set b3 issue=SUP-9"])
        self.assertEqual(new_plan["confirmed_rows"], ["b1", "b2+b6"])


class TestOverrides(unittest.TestCase):
    def test_valid_override_used(self):
        plan = copy.deepcopy(DAY)
        plan["variant_overrides"] = {"group": [
            {"start": "09:00", "end": "10:00", "ids": ["b1"]},
            {"start": "10:00", "end": "10:30", "ids": ["b2"]},
            {"start": "10:30", "end": "13:30", "ids": ["b4", "b6", "b9"]},
            {"start": "13:30", "end": "15:00", "ids": ["b7"]},
            {"start": "15:00", "end": "18:00", "ids": ["b3", "b5", "b8"]},
        ]}
        _, vs = compute(plan)
        self.assertTrue(vs["group"]["override"], vs["group"]["warnings"])
        self.assertEqual(vs["group"]["rows"][2]["issue"], "SUP-1")

    def test_override_breaking_totals_is_ignored(self):
        plan = copy.deepcopy(DAY)
        plan["variant_overrides"] = {"group": [
            {"start": "09:00", "end": "10:00", "ids": ["b1"]},
            {"start": "10:00", "end": "10:30", "ids": ["b2"]},
            {"start": "10:30", "end": "14:30", "ids": ["b4", "b6", "b9"]},
            {"start": "14:30", "end": "16:00", "ids": ["b7"]},
            {"start": "16:00", "end": "18:00", "ids": ["b3", "b5", "b8"]},
        ]}
        _, vs = compute(plan)
        self.assertFalse(vs["group"]["override"])
        self.assertIn("total de SUP-1", vs["group"]["warnings"][0])

    def test_check_detects_moved_fixed(self):
        m, vs = compute()
        rows = copy.deepcopy(vs["group"]["rows"])
        rows[1]["start"], rows[1]["end"] = t("10:05"), t("10:35")
        errors = variants.check(rows, m, vs["base"]["totals"], False)
        self.assertTrue(any("parte fija" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
