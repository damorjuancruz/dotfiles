#!/usr/bin/env python3
"""Colector del historial de Chrome (solo lectura, sobre una copia del SQLite).

Agrupa las visitas del día en sesiones por dominio (se corta una sesión cuando pasan más
de `session_gap_minutes` sin visitar ese dominio) y extrae keys de Jira, URLs de PRs e
issues de GitHub y doctype/docname de ERPNext. Los dominios de `deny_domains` se
descartan por completo.

Ruido que no es uso real y se descarta antes de agrupar:
  - aperturas automáticas de apps instaladas (PWA como Teams u Outlook que se abren al iniciar
    la sesión): visitas con transición AUTO_BOOKMARK sin visita de origen;
  - restauración de pestañas al abrir Chrome: ráfagas de recargas (transición RELOAD) de al
    menos `restore_min_domains` sitios distintos en `restore_window_seconds`;
  - sitios de `ignore_domains`, cuyo uso real se ve en otra fuente (Teams: los mensajes).

Uso: python scripts/collectors/chrome.py [--date AAAA-MM-DD]
"""

from __future__ import annotations

import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import common  # noqa: E402

SOURCE = "chrome"
CHROME_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)
MAX_TITLES = 5
GH_RX = re.compile(r"^/([^/]+/[^/]+)/(pull|issues)/(\d+)")
SKIP_SCHEMES = ("chrome", "chrome-extension", "about", "devtools", "data", "blob")
CORE_MASK = 0xFF
AUTO_BOOKMARK = 2
RELOAD = 8


def to_chrome_time(dt: datetime) -> int:
    return int((dt - CHROME_EPOCH).total_seconds() * 1_000_000)


def from_chrome_time(us: int) -> datetime:
    return CHROME_EPOCH + timedelta(microseconds=us)


def read_visits(history: Path, start: datetime, end: datetime) -> list[tuple]:
    """Copia el History (Chrome lo mantiene bloqueado) y lee las visitas del rango."""
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "History"
        shutil.copy2(history, copy)
        con = sqlite3.connect(f"file:{copy}?mode=ro", uri=True)
        try:
            rows = con.execute(
                "SELECT v.visit_time, u.url, u.title, v.transition, v.from_visit FROM visits v JOIN urls u ON v.url = u.id "
                "WHERE v.visit_time >= ? AND v.visit_time < ? ORDER BY v.visit_time",
                (to_chrome_time(start), to_chrome_time(end)),
            ).fetchall()
        finally:
            con.close()
    return [(from_chrome_time(t), url, title or "", tr, fv) for t, url, title, tr, fv in rows]


def drop_noise(visits: list[tuple], cfg: dict) -> tuple[list[tuple], dict]:
    """Saca las aperturas automáticas de apps y las restauraciones de pestañas. Las visitas
    sin transición (tuplas de 3) quedan como están. Devuelve (visitas, cuántas se sacaron)."""
    src = cfg["sources"]["chrome"]
    min_domains, window = src.get("restore_min_domains", 4), timedelta(seconds=src.get("restore_window_seconds", 30))
    core = lambda v: (v[3] & CORE_MASK) if len(v) > 3 and v[3] is not None else None  # noqa: E731
    reloads = [v for v in visits if core(v) == RELOAD]
    restored: set[int] = set()
    for i, v in enumerate(reloads):
        burst = [w for w in reloads[i:] if w[0] - v[0] <= window]
        if len({domain_of(w[1]) for w in burst}) >= min_domains:
            restored.update(id(w) for w in burst)
    out, dropped = [], {"apertura de app": 0, "restauración de pestañas": 0}
    for v in visits:
        if core(v) == AUTO_BOOKMARK and not (len(v) > 4 and v[4]):
            dropped["apertura de app"] += 1
        elif id(v) in restored:
            dropped["restauración de pestañas"] += 1
        else:
            out.append(v)
    return out, dropped


def domain_of(url: str) -> str:
    host = urlparse(url).hostname or ""
    return host.removeprefix("www.")


def is_denied(domain: str, deny: list[str]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in deny)


def url_hints(url: str, title: str, key_rx, erp_host: str | None) -> dict:
    p = urlparse(url)
    hints: dict = {"issue_keys": common.find_issue_keys(f"{unquote(p.path)} {p.query} {title}", key_rx)}
    if p.hostname and p.hostname.endswith("github.com"):
        m = GH_RX.match(p.path)
        if m:
            hints["github"] = f"{m.group(1)}#{m.group(3)}" + (" (PR)" if m.group(2) == "pull" else "")
    if erp_host and p.hostname == erp_host:
        parts = [unquote(x) for x in p.path.split("/") if x]
        if len(parts) >= 2 and parts[0] == "app":
            hints["doctype"] = parts[1]
            if len(parts) >= 3:
                hints["docname"] = parts[2]
    if p.hostname and "atlassian.net" in p.hostname:
        q = parse_qs(p.query)
        for k in q.get("selectedIssue", []):
            hints["issue_keys"] += [x for x in common.find_issue_keys(k, key_rx) if x not in hints["issue_keys"]]
    return hints


def group_sessions(visits, cfg: dict, tz) -> list[dict]:
    src = cfg["sources"]["chrome"]
    gap = timedelta(minutes=src["session_gap_minutes"])
    deny = [d.lower() for d in src["deny_domains"]] + [d.lower() for d in src.get("ignore_domains", [])]
    key_rx = common.issue_key_regex(list(cfg["projects"]))
    erp_host = urlparse(cfg["erpnext"].get("url") or "").hostname

    groups: list[dict] = []
    open_by_domain: dict[str, dict] = {}
    for ts, url, title, *_ in visits:
        scheme = urlparse(url).scheme
        if scheme in SKIP_SCHEMES:
            continue
        domain = domain_of(url) if scheme != "file" else "archivo local"
        if not domain or is_denied(domain.lower(), deny):
            continue
        hints = url_hints(url, title, key_rx, erp_host)
        g = open_by_domain.get(domain)
        if not g or ts - g["end"] > gap:
            g = {"domain": domain, "start": ts, "end": ts, "count": 0, "titles": [], "keys": [], "github": [], "docs": []}
            groups.append(g)
            open_by_domain[domain] = g
        g["end"], g["count"] = ts, g["count"] + 1
        t = " ".join(title.split())
        if t and t not in g["titles"]:
            g["titles"].append(t)
        g["keys"] += [k for k in hints["issue_keys"] if k not in g["keys"]]
        if hints.get("github") and hints["github"] not in g["github"]:
            g["github"].append(hints["github"])
        if hints.get("doctype"):
            doc = f"{hints['doctype']} {hints.get('docname', '')}".strip()
            if doc not in g["docs"]:
                g["docs"].append(doc)

    events = []
    for g in groups:
        s, e = g["start"].astimezone(tz), g["end"].astimezone(tz)
        titles = g["titles"][:MAX_TITLES]
        more = len(g["titles"]) - len(titles)
        detail = " · ".join(titles) + (f" (+{more})" if more > 0 else "")
        hints = {"domain": g["domain"], "issue_keys": g["keys"], "github": g["github"][:10], "erp_docs": g["docs"][:10]}
        events.append(common.Event(
            SOURCE, s.isoformat(), e.isoformat(), f"{g['domain']} ({g['count']} visitas)", detail[:400],
            hints, "weak", id=common.make_event_id(SOURCE, g["domain"], s.isoformat()),
        ).to_dict())
    return events


def collect(cfg: dict, env: dict, day: date, visits=None) -> dict:
    tz = common.get_tz(cfg)
    if visits is None:
        history = common.expand_path(cfg["sources"]["chrome"]["history_path"])
        if not history.exists():
            return {"source": SOURCE, "status": "error", "message": f"no existe {history}", "events": []}
        d_start, d_end = common.day_bounds(day, tz)
        try:
            visits = read_visits(history, d_start, d_end)
        except (sqlite3.Error, OSError) as e:
            return {"source": SOURCE, "status": "error", "message": str(e), "events": []}
    visits, dropped = drop_noise(visits, cfg)
    events = group_sessions(visits, cfg, tz)
    res = {"source": SOURCE, "status": "ok", "visits": len(visits), "events": events}
    if any(dropped.values()):
        res["messages"] = ["descartadas: " + ", ".join(f"{n} por {k}" for k, n in dropped.items() if n)]
    return res


if __name__ == "__main__":
    sys.exit(common.collector_main(collect, __doc__))
