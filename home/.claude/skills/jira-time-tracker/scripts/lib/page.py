"""Página de revisión que sirve `server.py`.

`build_data` arma el JSON con todo lo que la página necesita (variantes, bloques, evidencia,
incidencias, transiciones) y `render_html` lo inyecta en la plantilla fija de
`assets/review.html`. El agente nunca escribe HTML: el servidor sirve el archivo que sale de acá.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from lib import common

TEMPLATE = common.SKILL_DIR / "assets" / "review.html"
WEEKDAYS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
MISC_LABEL = "Varias"
DETAIL_CHARS = 400


def misc_label(cfg: dict, issue: str) -> str | None:
    """Las issues de Tareas Varias se muestran por su categoría, sin el prefijo largo del resumen."""
    misc = cfg.get("misc_issues") or {}
    if issue == misc.get("parent"):
        return MISC_LABEL
    for label, key in (misc.get("subtasks") or {}).items():
        if key == issue:
            return f"{MISC_LABEL} · {label}"
    return None


_hm = common.fmt_hm


def _row_json(r: dict) -> dict:
    out = {k: v for k, v in r.items() if k not in ("start", "end")}
    out["start"], out["end"] = _hm(r["start"]), _hm(r["end"])
    out["minutes"] = int((r["end"] - r["start"]).total_seconds() // 60)
    return out


def _lunch_json(info: dict | None) -> dict | None:
    if not info:
        return None
    out = {"mode": info["mode"], "discounts": info.get("discounts", {}), "reason": info.get("reason")}
    for k in ("start", "end"):
        if info.get(k):
            out[k] = _hm(info[k])
    return out


SOURCE_LABELS = {"git": "git", "gh": "GitHub", "cc": "Claude Code", "chrome": "Chrome", "erp": "ERPNext",
                 "outlook": "Outlook", "teams": "Teams", "jira": "Jira"}


def source_label(ev: dict) -> str:
    """Nombre del origen para la página. Una sesión de Claude que corre dentro de T3 Code deja su
    transcript como las de Claude Code (fuente `cc`), pero `hints.t3_thread` la distingue."""
    src, hints = ev.get("source") or "", ev.get("hints") or {}
    if src == "cc" and hints.get("t3_thread"):
        return "T3 · Claude"
    if src == "t3":
        return f"T3 · {hints['provider']}" if hints.get("provider") else "T3 Code"
    return SOURCE_LABELS.get(src, src)


def _event_json(ev: dict, tz) -> dict:
    s = common.parse_iso(ev["start"]).astimezone(tz)
    e = common.parse_iso(ev["end"]).astimezone(tz)
    hints = {k: v for k, v in (ev.get("hints") or {}).items() if v not in (None, "", [], {})}
    return {"source": ev.get("source"), "label": source_label(ev), "start": _hm(s), "end": _hm(e), "title": ev.get("title", ""),
            "detail": " ".join(str(ev.get("detail") or "").split())[:DETAIL_CHARS], "hints": hints}


def issue_info(model, key: str, meta: dict) -> dict:
    cfg = model.cfg
    cand = model.candidate(key) or {}
    ni = model.new_issue(key)
    m = meta.get(key) or {}
    label = misc_label(cfg, key)
    site = (cfg["jira"].get("site") or "").rstrip("/")
    info = {
        "summary": (ni or {}).get("summary") or m.get("summary") or cand.get("summary", ""),
        "label": label,
        "misc": label is not None,
        "new": ni is not None,
        "status": m.get("status") or cand.get("status"),
        "assignee": cand.get("assignee"),
        "assignee_me": cand.get("assignee_me"),
        "description": cand.get("description", ""),
        "url": None if ni else f"{site}/browse/{key}" if site else None,
        "transitions": m.get("transitions", []),
    }
    if m.get("suggestion"):
        info["suggestion"] = m["suggestion"]
    if m.get("status_note"):
        info["status_note"] = m["status_note"]
    if m.get("error"):
        info["meta_error"] = m["error"]
    return info


def build_data(model, vs: dict, meta: dict, raw_events: dict, current: str, warnings: list[str],
               confirmed_rows: list[str] = (), stage: str = "review", followup_keys: list[str] = ()) -> dict:
    """`stage` es "review" (revisión y carga) o "followup" (cambio de estado de las incidencias
    recién creadas, después de cargar)."""
    cfg, plan, tz = model.cfg, model.plan, common.get_tz(model.cfg)
    blocks, gaps, used_events = {}, {}, set()
    for r in model.rows:
        if r.kind == "block":
            b = r.data
            evidence = [e for e in b.get("evidence", []) if e in raw_events]
            used_events.update(evidence)
            blocks[b["id"]] = {
                "issue": b.get("issue"), "start": _hm(r.start), "end": _hm(r.end), "minutes": r.minutes,
                "action": b.get("action"), "confidence": b.get("confidence"), "sources": b.get("sources", []),
                "evidence": evidence, "warn": b.get("warn"), "fixed": bool(b.get("fixed")),
                "comments": b.get("comments") or {}, "comment": b.get("comment"),
            }
            if b.get("action") == "adjust":
                wl = next((w for w in model.digest.get("worklogs", []) if str(w["id"]) == str(b.get("worklog_id"))), None)
                if wl:
                    s = common.parse_iso(wl["started"]).astimezone(tz)
                    blocks[b["id"]]["original"] = f"{_hm(s)}–{_hm(s + timedelta(minutes=int(wl['minutes'])))}"
        elif r.kind == "gap":
            g = r.data
            gaps[g["id"]] = {"kind": g.get("kind", "open"), "note": g.get("note"), "start": _hm(r.start),
                             "end": _hm(r.end), "confirmed": bool(g.get("confirmed"))}

    keys = list(dict.fromkeys(b["issue"] for b in blocks.values() if b.get("issue")))
    issues = {k: issue_info(model, k, meta) for k in keys}
    candidates = []
    active = set(keys)
    misc_keys = {k for k in [cfg["misc_issues"].get("parent"), *cfg["misc_issues"].get("subtasks", {}).values()] if k}
    for c in model.digest.get("candidates", []):
        if c["key"] in active or c.get("assignee_me") or c["key"] in misc_keys or "mentioned" in c.get("origin", []):
            candidates.append({"key": c["key"], "summary": c.get("summary", ""), "label": misc_label(cfg, c["key"])})
            issues.setdefault(c["key"], issue_info(model, c["key"], meta))

    span = None
    if model.range_start and model.range_end:
        breaks = sum(r.minutes for r in model.rows if r.kind == "break")
        span = int((model.range_end - model.range_start).total_seconds() // 60) - breaks

    return {
        "stage": stage,
        "followup_keys": list(followup_keys),
        "date": model.day.isoformat(),
        "day_label": f"{WEEKDAYS[model.day.weekday()]} {model.day.strftime('%d/%m/%Y')}",
        "round": plan.get("round", 1),
        "note": plan.get("note"),
        "range": {"start": _hm(model.range_start) if model.range_start else None,
                  "end": _hm(model.range_end) if model.range_end else None, "work_minutes": span},
        "defaults": {"level": cfg["review"]["comment_level"], "lunch_minutes": cfg["review"]["lunch_minutes"],
                     "lunch_window": cfg["review"]["lunch_window"]},
        "modes": {"group": current in ("group", "group+lunch"), "lunch": current in ("lunch", "group+lunch")},
        "variants": {name: {"rows": [_row_json(r) for r in v["rows"]], "totals": v["totals"],
                            "lunch": _lunch_json(v["lunch"]), "warnings": v["warnings"], "override": v["override"]}
                     for name, v in vs.items()},
        "blocks": blocks,
        "gaps": gaps,
        "group_comments": plan.get("group_comments") or {},
        "confirmed_rows": list(confirmed_rows),
        "levels": plan.get("levels") or {},
        "events": {eid: _event_json(raw_events[eid], tz) for eid in sorted(used_events)},
        "issues": issues,
        "candidates": candidates,
        "new_issues": plan.get("new_issues", []),
        "followup": plan.get("followup") or {},
        "absorbed": plan.get("absorbed", []),
        "warnings": warnings,
    }


def render_html(data: dict, template: Path = TEMPLATE) -> str:
    html = template.read_text()
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    blob = blob.replace("</", "<\\/").replace("<!--", "<\\!--")
    title = f"Horas del {data['day_label'].split()[0].lower()} {data['day_label'].split()[1][:5]}"
    return html.replace("__TITLE__", title).replace("__DATA__", blob)


def write_page(path: Path, data: dict) -> None:
    """Escritura atómica: el servidor recarga la página apenas cambia el archivo."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(render_html(data))
    tmp.replace(path)
