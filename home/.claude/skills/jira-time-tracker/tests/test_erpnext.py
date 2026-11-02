import json
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from collectors import erpnext
from lib import common

CFG = common.load_config(Path(__file__).resolve().parent.parent / "config.example.json")
TZ = ZoneInfo(CFG["timezone"])
DAY = date(2026, 10, 5)


def now(h, m):
    return datetime(2026, 10, 5, h, m, tzinfo=TZ)


class FakeClient:
    def __init__(self, data, forbidden=()):
        self.data, self.forbidden, self.calls = data, set(forbidden), []

    def list(self, doctype, filters, fields, order_by="creation asc"):
        self.calls.append((doctype, filters))
        if doctype in self.forbidden:
            raise common.HttpError(403, doctype, "forbidden")
        return self.data.get(doctype, [])


DATA = {
    "Employee": [{"name": "HR-EMP-0042", "employee_name": "Yo"}],
    "Employee Checkin": [
        {"name": "c1", "time": "2026-10-05 08:53:12", "log_type": "IN"},
        {"name": "c2", "time": "2026-10-05 12:31:00", "log_type": "OUT"},
        {"name": "c3", "time": "2026-10-05 13:28:40", "log_type": "IN"},
    ],
    "Version": [
        {"ref_doctype": "Sales Invoice", "docname": "SINV-1", "creation": "2026-10-05 09:00:00",
         "data": json.dumps({"changed": [["due_date", "a", "b"]]})},
        {"ref_doctype": "Sales Invoice", "docname": "SINV-1", "creation": "2026-10-05 09:06:00",
         "data": json.dumps({"changed": [["po_no", "a", "b"]], "row_changed": [["items", 0, "x", []]]})},
        {"ref_doctype": "Sales Invoice", "docname": "SINV-1", "creation": "2026-10-05 10:30:00", "data": "{}"},
        {"ref_doctype": "Item", "docname": "IT-9", "creation": "2026-10-05 09:03:00", "data": "no-json"},
    ],
    "Comment": [
        {"comment_type": "Comment", "reference_doctype": "Issue", "reference_name": "ISS-1",
         "content": "<p>Ya está &amp; listo</p>", "creation": "2026-10-05 11:00:00"},
        {"comment_type": "Like", "reference_doctype": "Issue", "reference_name": "ISS-1",
         "content": "", "creation": "2026-10-05 11:01:00"},
    ],
    "Communication": [
        {"subject": "Re: remitos", "reference_doctype": "Issue", "reference_name": "ISS-1",
         "communication_date": "2026-10-05 11:10:00", "communication_medium": "Email"},
    ],
}


class TestRange(unittest.TestCase):
    def test_today_with_break(self):
        r = erpnext.compute_range(DATA["Employee Checkin"], DAY, TZ, now(17, 42), 5)
        self.assertEqual(r["start"], "2026-10-05T08:55:00-03:00")
        self.assertEqual(r["end"], "2026-10-05T17:40:00-03:00")
        self.assertEqual(r["end_source"], "now")
        self.assertEqual(r["breaks"], [{"start": "2026-10-05T12:30:00-03:00", "end": "2026-10-05T13:30:00-03:00"}])

    def test_checked_out_today(self):
        logs = DATA["Employee Checkin"] + [{"time": "2026-10-05 17:21:00", "log_type": "OUT"}]
        r = erpnext.compute_range(logs, DAY, TZ, now(19, 0), 5)
        self.assertEqual(r["end"], "2026-10-05T17:20:00-03:00")
        self.assertEqual(r["end_source"], "checkout")

    def test_past_day_without_out(self):
        r = erpnext.compute_range(DATA["Employee Checkin"][:1], DAY, TZ, datetime(2026, 10, 6, 9, 0, tzinfo=TZ), 5)
        self.assertEqual(r["start"], "2026-10-05T08:55:00-03:00")
        self.assertIsNone(r["end"])

    def test_no_checkins(self):
        r = erpnext.compute_range([], DAY, TZ, now(17, 0), 5)
        self.assertIsNone(r["start"])
        self.assertEqual(r["end"], "2026-10-05T17:00:00-03:00")

    def test_missing_log_type_alternates(self):
        logs = [{"time": "2026-10-05 09:00:00"}, {"time": "2026-10-05 12:00:00"}, {"time": "2026-10-05 13:00:00"}]
        r = erpnext.compute_range(logs, DAY, TZ, now(18, 0), 5)
        self.assertEqual(len(r["breaks"]), 1)


class TestCollect(unittest.TestCase):
    def test_collect(self):
        client = FakeClient(DATA, forbidden={"Activity Log"})
        res = erpnext.collect(CFG, {}, DAY, client=client, now=now(17, 42))
        self.assertEqual(res["status"], "partial")
        self.assertIn("Activity Log: no se pudo leer (403)", res["messages"])
        self.assertEqual(res["employee"], "HR-EMP-0042")
        titles = [e["title"] for e in res["events"]]
        self.assertEqual(titles, [
            "editó Sales Invoice SINV-1",
            "editó Item IT-9",
            "editó Sales Invoice SINV-1",
            "comment en Issue ISS-1",
            "email enviado: Re: remitos",
        ])
        first = res["events"][0]
        self.assertEqual(first["end"], "2026-10-05T09:06:00-03:00")
        self.assertEqual(first["detail"], "2 guardado(s); campos: due_date, po_no, items.*")
        self.assertEqual(res["events"][3]["detail"], "Ya está & listo")
        # filtros por usuario y día
        version_filters = dict((d, f) for d, f in client.calls)["Version"]
        self.assertIn(["owner", "=", CFG["erpnext"]["user"]], version_filters)
        self.assertIn(["creation", "<", "2026-10-06 00:00:00"], version_filters)

    def test_no_employee(self):
        res = erpnext.collect(CFG, {}, DAY, client=FakeClient({}), now=now(17, 0))
        self.assertTrue(any("no se encontró Employee" in m for m in res["messages"]))
        self.assertIsNone(res["range"]["start"])

    def test_missing_credentials(self):
        res = erpnext.collect(CFG, {}, DAY)
        self.assertEqual(res["status"], "error")
        self.assertIn("ERPNEXT_API_KEY", res["message"])


if __name__ == "__main__":
    unittest.main()
