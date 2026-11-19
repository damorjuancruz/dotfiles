#!/usr/bin/env python3
"""Colector del uso de la página de revisión del propio skill (solo lectura).

Mientras el usuario revisa sus horas casi no escribe en el chat: trabaja en la página que sirve
server.py. La página avisa al servidor, a lo sumo una vez por minuto, cuando hay uso real
(mouse, teclado, scroll) con la pestaña visible, y el servidor anota cada aviso, envío y pedido
en <STATE_ROOT>/activity/<fecha real>.jsonl (ver server.py).

Este colector lee el archivo del día y arma tramos de uso: se corta un tramo cuando pasan más
de `idle_gap_minutes` sin avisos (el usuario se fue o dejó la página de fondo). Cada aviso cubre
el minuto siguiente. Los tramos cuentan como interacción (`hints.activity_spans`, ver
collect.mark_parallel) y llevan la sesión de Claude Code o el thread de T3 que levantó el
servidor.

Uso: python scripts/collectors/review_page.py [--date AAAA-MM-DD]
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import common  # noqa: E402

SOURCE = "jtt"
PING = timedelta(minutes=1)


def activity_file(day: date) -> Path:
    return common.STATE_ROOT / "activity" / f"{day.isoformat()}.jsonl"


def read_records(path: Path) -> list[dict]:
    out = []
    if not path.exists():
        return out
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict) and rec.get("at"):
                out.append(rec)
    return out


def collect(cfg: dict, env: dict, day: date, path: Path | None = None) -> dict:
    tz = common.get_tz(cfg)
    src = cfg["sources"]["review_page"]
    d_start, d_end = common.day_bounds(day, tz)
    gap = timedelta(minutes=src["idle_gap_minutes"])

    by_review: dict[str, list] = defaultdict(list)
    for rec in read_records(path or activity_file(day)):
        try:
            ts = common.parse_iso(rec["at"]).astimezone(tz)
        except (TypeError, ValueError):
            continue
        if d_start <= ts < d_end:
            by_review[str(rec.get("review_date") or "")].append((ts, rec))

    events = []
    for review_date, stamps in by_review.items():
        try:
            label = date.fromisoformat(review_date).strftime("%d/%m")
        except ValueError:
            label = review_date or "?"
        for seg in common.split_by_gap(stamps, gap):
            start, end = seg[0][0], min(seg[-1][0] + PING, d_end)
            kinds = defaultdict(int)
            for _, rec in seg:
                kinds[rec.get("kind") or "input"] += 1
            last = seg[-1][1]
            hints = {"review_date": review_date, "session": last.get("session"), "t3_thread": last.get("t3_thread"),
                     "activity_spans": [[start.isoformat(), end.isoformat()]]}
            detail = f"{kinds['input']} avisos de uso" + "".join(
                f", {kinds[k]} {name}" for k, name in (("send", "envíos"), ("ask", "pedidos de comentario")) if kinds[k])
            events.append(common.Event(
                SOURCE, start.isoformat(), end.isoformat(), f"revisión de horas del {label} en la página del skill",
                detail, hints, "normal", id=common.make_event_id(SOURCE, review_date, start.isoformat()),
            ).to_dict())
    return {"source": SOURCE, "status": "ok", "events": sorted(events, key=lambda e: e["start"])}


if __name__ == "__main__":
    sys.exit(common.collector_main(collect, __doc__))
