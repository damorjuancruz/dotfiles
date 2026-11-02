#!/usr/bin/env python3
"""Colector ERPNext / Frappe (REST, solo lectura).

Trae del día, para el usuario configurado:
  - Employee Checkin → rango del día (entrada, corte, salidas intermedias);
  - Version (modificaciones de documentos), Comment, Communication y Activity Log → eventos.

Cada doctype se consulta por separado: si el usuario no tiene permiso sobre alguno,
se informa en `messages` y se sigue con el resto.

Uso: python scripts/collectors/erpnext.py [--date AAAA-MM-DD]
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
import urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import common  # noqa: E402

SOURCE = "erp"
MERGE_GAP_MINUTES = 10
SKIP_COMMENT_TYPES = {"Like"}


class FrappeClient:
    def __init__(self, url: str, key: str, secret: str, http: Callable[..., Any] = common.http_json):
        self.base = url.rstrip("/")
        self.headers = common.frappe_auth(key, secret)
        self.http = http

    def list(self, doctype: str, filters: list, fields: list[str], order_by: str = "creation asc") -> list[dict]:
        data = self.http(
            f"{self.base}/api/resource/{urllib.parse.quote(doctype)}",
            headers=self.headers,
            params={
                "filters": json.dumps(filters),
                "fields": json.dumps(fields),
                "order_by": order_by,
                "limit_page_length": 0,
            },
        )
        return (data or {}).get("data", [])


def parse_frappe_dt(value: str, tz) -> datetime:
    """Frappe devuelve datetimes naive en la zona horaria del sistema."""
    return datetime.fromisoformat(str(value)).replace(tzinfo=tz)


def _day_filter(field: str, day: date) -> list[list]:
    nxt = day + timedelta(days=1)
    return [[field, ">=", f"{day.isoformat()} 00:00:00"], [field, "<", f"{nxt.isoformat()} 00:00:00"]]


# --------------------------------------------------------------------------- rango


def compute_range(checkins: list[dict], day: date, tz, now: datetime, slot: int) -> dict:
    """Entrada = primer IN redondeado hacia arriba; corte = ahora (o el último OUT) hacia abajo.

    Si `log_type` falta, se asume alternancia IN/OUT empezando por IN."""
    logs = sorted(checkins, key=lambda c: c["time"])
    typed = []
    for i, c in enumerate(logs):
        lt = (c.get("log_type") or "").upper() or ("IN" if i % 2 == 0 else "OUT")
        typed.append((lt, parse_frappe_dt(c["time"], tz)))

    first_in = next((t for lt, t in typed if lt == "IN"), None)
    rng: dict[str, Any] = {
        "start": common.round_up(first_in, slot).isoformat() if first_in else None,
        "end": None,
        "end_source": None,
        "breaks": [],
        "checkins": [{"log_type": lt, "time": t.isoformat()} for lt, t in typed],
    }

    for (lt_a, t_a), (lt_b, t_b) in zip(typed, typed[1:]):
        if lt_a == "OUT" and lt_b == "IN" and (first_in is None or t_a > first_in):
            b_start, b_end = common.round_down(t_a, slot), common.round_up(t_b, slot)
            if b_end > b_start:
                rng["breaks"].append({"start": b_start.isoformat(), "end": b_end.isoformat()})

    last_lt, last_t = typed[-1] if typed else (None, None)
    is_today = now.astimezone(tz).date() == day
    if last_lt == "OUT" and (not is_today or last_t <= now):
        rng["end"], rng["end_source"] = common.round_down(last_t, slot).isoformat(), "checkout"
    elif is_today:
        rng["end"], rng["end_source"] = common.round_down(now.astimezone(tz), slot).isoformat(), "now"
    return rng


# --------------------------------------------------------------------------- eventos


def _version_fields(data: Any) -> list[str]:
    try:
        d = json.loads(data) if isinstance(data, str) else (data or {})
    except json.JSONDecodeError:
        return []
    names = [c[0] for c in d.get("changed", []) if c]
    names += [f"+{r[0]}" for r in d.get("added", []) if r]
    names += [f"-{r[0]}" for r in d.get("removed", []) if r]
    names += [f"{r[0]}.*" for r in d.get("row_changed", []) if r]
    return names


def merge_doc_events(items: list[tuple[datetime, str, str, list[str]]], tz) -> list[dict]:
    """Agrupa guardados consecutivos del mismo documento (huecos ≤ MERGE_GAP_MINUTES)."""
    groups: list[dict] = []
    open_by_doc: dict[tuple[str, str], dict] = {}
    for ts, doctype, docname, fields in sorted(items, key=lambda x: x[0]):
        g = open_by_doc.get((doctype, docname))
        if g and ts - g["end"] <= timedelta(minutes=MERGE_GAP_MINUTES):
            g["end"], g["count"] = ts, g["count"] + 1
            g["fields"] += [f for f in fields if f not in g["fields"]]
        else:
            g = {"start": ts, "end": ts, "doctype": doctype, "docname": docname, "count": 1, "fields": list(fields)}
            groups.append(g)
            open_by_doc[(doctype, docname)] = g
    events = []
    for g in groups:
        detail = f"{g['count']} guardado(s)"
        if g["fields"]:
            detail += "; campos: " + ", ".join(g["fields"][:12])
        events.append(common.Event(
            SOURCE, g["start"].isoformat(), g["end"].isoformat(),
            f"editó {g['doctype']} {g['docname']}", detail,
            {"doctype": g["doctype"], "docname": g["docname"]}, "normal",
        ).to_dict())
    return events


def collect(cfg: dict, env: dict, day: date, client: FrappeClient | None = None, now: datetime | None = None) -> dict:
    tz = common.get_tz(cfg)
    erp = cfg["erpnext"]
    user = erp.get("user")
    result: dict[str, Any] = {"source": SOURCE, "status": "ok", "messages": [], "events": [], "range": None}
    if not erp.get("url") or not user:
        return {**result, "status": "error", "message": "faltan erpnext.url / erpnext.user en config"}
    if client is None:
        key, secret = env.get("ERPNEXT_API_KEY"), env.get("ERPNEXT_API_SECRET")
        if not key or not secret:
            return {**result, "status": "error", "message": "faltan ERPNEXT_API_KEY / ERPNEXT_API_SECRET en .env"}
        client = FrappeClient(erp["url"], key, secret)
    now = now or datetime.now(tz)
    slot = cfg["rules"]["slot_minutes"]

    def safe(doctype: str, filters: list, fields: list[str], order_by: str = "creation asc") -> list[dict]:
        try:
            return client.list(doctype, filters, fields, order_by)
        except (common.HttpError, OSError) as e:
            status = getattr(e, "status", "")
            result["messages"].append(f"{doctype}: no se pudo leer ({status or e})")
            return []

    # Checkins → rango
    employees = safe("Employee", [["user_id", "=", user]], ["name", "employee_name"])
    if employees:
        emp = employees[0]["name"]
        checkins = safe("Employee Checkin", [["employee", "=", emp], *_day_filter("time", day)],
                        ["name", "time", "log_type"], "time asc")
        result["employee"] = emp
        result["range"] = compute_range(checkins, day, tz, now, slot)
        if not checkins:
            result["messages"].append("sin checkins en el día")
    else:
        result["messages"].append(f"no se encontró Employee con user_id={user}")
        result["range"] = compute_range([], day, tz, now, slot)

    # Versiones → ediciones agrupadas por documento
    versions = safe("Version", [["owner", "=", user], *_day_filter("creation", day)],
                    ["ref_doctype", "docname", "creation", "data"])
    items = [(parse_frappe_dt(v["creation"], tz), v["ref_doctype"], v["docname"], _version_fields(v.get("data")))
             for v in versions]
    events = merge_doc_events(items, tz)

    for c in safe("Comment", [["owner", "=", user], *_day_filter("creation", day)],
                  ["comment_type", "reference_doctype", "reference_name", "content", "creation"]):
        if c.get("comment_type") in SKIP_COMMENT_TYPES:
            continue
        ts = parse_frappe_dt(c["creation"], tz).isoformat()
        events.append(common.Event(
            SOURCE, ts, ts, f"{(c.get('comment_type') or 'Comment').lower()} en {c.get('reference_doctype')} {c.get('reference_name')}",
            common_text(c.get("content"))[:200],
            {"doctype": c.get("reference_doctype"), "docname": c.get("reference_name")}, "normal",
        ).to_dict())

    for m in safe("Communication", [["sender", "=", user], *_day_filter("communication_date", day)],
                  ["subject", "reference_doctype", "reference_name", "communication_date", "communication_medium", "sent_or_received"],
                  "communication_date asc"):
        ts = parse_frappe_dt(m["communication_date"], tz).isoformat()
        events.append(common.Event(
            SOURCE, ts, ts, f"{(m.get('communication_medium') or 'comunicación').lower()} enviado: {m.get('subject') or ''}".strip(),
            "", {"doctype": m.get("reference_doctype"), "docname": m.get("reference_name")}, "normal",
        ).to_dict())

    for a in safe("Activity Log", [["user", "=", user], *_day_filter("creation", day)],
                  ["subject", "operation", "reference_doctype", "reference_name", "creation"]):
        ts = parse_frappe_dt(a["creation"], tz).isoformat()
        events.append(common.Event(
            SOURCE, ts, ts, common_text(a.get("subject") or a.get("operation") or "actividad")[:120], "",
            {"doctype": a.get("reference_doctype"), "docname": a.get("reference_name")}, "weak",
        ).to_dict())

    result["events"] = sorted(events, key=lambda e: e["start"])
    if any("no se pudo leer" in m for m in result["messages"]):
        result["status"] = "partial"
    return result


def common_text(html: str | None) -> str:
    """Texto plano de un fragmento HTML de Frappe."""
    text = re.sub(r"<[^>]+>", " ", html or "")
    return " ".join(html_mod.unescape(text).split())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date")
    args = ap.parse_args()
    cfg = common.load_config()
    day = common.parse_day(args.date, common.get_tz(cfg))
    result = collect(cfg, common.load_env(), day)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if result["status"] in ("ok", "partial") else 1


if __name__ == "__main__":
    sys.exit(main())
