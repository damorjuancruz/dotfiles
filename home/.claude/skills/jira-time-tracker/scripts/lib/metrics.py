"""Métricas de uso del skill, para mejorarlo con datos.

Cada tanda junta sus métricas en <state>/<fecha>/metrics.json mientras corre (collect, build,
cada ronda de review, load). Al cerrarla (`plan.py close`), se arma un resumen que compara la
primera propuesta (plan.r1.json) con lo que quedó, suma el costo de la sesión del agente y se
agrega como una línea a <STATE_ROOT>/metrics.jsonl. `metrics.py report` lo analiza.

Solo se guardan cantidades, tipos y tiempos: nunca el texto de notas, mensajes o comentarios.
"""

from __future__ import annotations

import difflib
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path

from lib import common

FILE = "metrics.json"
FIRST_PLAN = "plan.r1.json"
GLOBAL = "metrics.jsonl"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load(sdir: Path) -> dict:
    try:
        return common.read_json(sdir / FILE, {}) or {}
    except ValueError:
        return {}


def update(sdir: Path, section: str, data: dict) -> None:
    """Reemplaza una sección. Nunca falla: las métricas no deben cortar el flujo."""
    try:
        m = load(sdir)
        m.setdefault("started", now_iso())
        m[section] = data
        common.write_json(sdir / FILE, m)
    except Exception:  # noqa: BLE001
        pass


def append(sdir: Path, section: str, item: dict) -> None:
    try:
        m = load(sdir)
        m.setdefault("started", now_iso())
        m.setdefault(section, []).append(item)
        common.write_json(sdir / FILE, m)
    except Exception:  # noqa: BLE001
        pass


# --------------------------------------------------------------------------- recolección y rondas


def collect_metrics(digest: dict, durations: dict[str, float], text_chars: int) -> dict:
    timeline = digest.get("timeline", [])
    return {
        "at": now_iso(),
        "events": dict(Counter(e.get("source") for e in timeline)),
        "sources": {k: {"status": v.get("status"), "seconds": round(durations.get(k, 0), 1),
                        "messages": len(v.get("messages") or []) + (1 if v.get("message") else 0)}
                    for k, v in (digest.get("sources") or {}).items()},
        "digest_chars": text_chars,
        "candidates": len(digest.get("candidates", [])),
        "worklogs_before": len(digest.get("worklogs", [])),
        "run": len(digest.get("runs", [])) + 1,
    }


def text_similarity(a: str, b: str) -> float:
    return round(difflib.SequenceMatcher(None, a or "", b or "").ratio(), 3)


def review_metrics(plan_before: dict, st: dict) -> dict:
    """Lo que el usuario hizo en una ronda de la página (solo cantidades)."""
    blocks = {b.get("id"): b for b in plan_before.get("blocks", [])}
    group = plan_before.get("group_comments") or {}
    sims = []
    for key, text in (st.get("texts") or {}).items():
        lv = (st.get("levels") or {}).get(key) or (plan_before.get("levels") or {}).get(key) or "normal"
        preset = ((blocks.get(key) or {}).get("comments") or group.get(key) or {}).get(lv, "")
        sims.append(text_similarity(preset, text))
    gaps = Counter((g or {}).get("action") for g in (st.get("gaps") or {}).values() if g)
    nis = st.get("new_issues") or {}
    return {
        "at": now_iso(),
        "round": st.get("round"),
        "action": st.get("action"),
        "confirmed": sum(1 for v in (st.get("confirmed") or {}).values() if v),
        "notes": sum(1 for v in (st.get("notes") or {}).values() if isinstance(v, str) and v.strip()),
        "global_note": bool((st.get("global_note") or "").strip()),
        "reassigned": sum(1 for v in (st.get("reassign") or {}).values() if v),
        "new_requested": len(st.get("new_requests") or {}),
        "absorbed": sum(1 for v in (st.get("absorb") or {}).values() if v),
        "gaps": dict(gaps),
        "levels": dict(Counter((st.get("levels") or {}).values())),
        "texts_edited": len(sims),
        "text_similarity_avg": round(sum(sims) / len(sims), 3) if sims else None,
        "new_issue_decisions": dict(Counter((d or {}).get("decision") or "sin decidir" for d in nis.values())),
        "new_issue_notes": sum(1 for d in nis.values() if ((d or {}).get("note") or "").strip()),
        "modes": st.get("modes"),
        "followup_transitions": sum(1 for f in (st.get("followup") or {}).values() if (f or {}).get("transition_id")),
        "followup_comments": sum(1 for f in (st.get("followup") or {}).values() if (f or {}).get("publish")),
        "asked_comments": len(st.get("asks") or {}),
    }


# --------------------------------------------------------------------------- primera propuesta vs final


def _block_minutes(b: dict) -> int:
    h1, m1 = map(int, b["start"].split(":"))
    h2, m2 = map(int, b["end"].split(":"))
    return (h2 * 60 + m2) - (h1 * 60 + m1)


def attribution_diff(first: dict | None, final: dict) -> dict | None:
    """Compara los bloques nuevos de la primera propuesta con el plan final, por id de bloque:
    minutos que quedaron en otra incidencia, que se absorbieron o que se agregaron, desglosado
    por la confianza que tenía cada bloque en la propuesta."""
    if not first:
        return None
    created = set(final.get("created") or [])
    fin = {b.get("id"): b for b in final.get("blocks", [])}
    by_conf: dict[str, dict[str, int]] = {}
    proposed = moved = removed = 0
    for b in first.get("blocks", []):
        if b.get("action") != "new" or not b.get("id"):
            continue
        mins = _block_minutes(b)
        conf = b.get("confidence") or "?"
        c = by_conf.setdefault(conf, {"minutes": 0, "moved": 0, "removed": 0, "blocks": 0})
        c["minutes"] += mins
        c["blocks"] += 1
        proposed += mins
        f = fin.get(b["id"])
        if f is None:
            c["removed"] += mins
            removed += mins
            continue
        same = f.get("issue") == b.get("issue") or (str(b.get("issue", "")).startswith("NEW-") and f.get("issue") in created)
        if not same:
            c["moved"] += mins
            moved += mins
    added = sum(_block_minutes(b) for bid, b in fin.items() if bid and b.get("action") == "new"
                and bid not in {x.get("id") for x in first.get("blocks", [])})
    totals_first = Counter()
    totals_final = Counter()
    for b in first.get("blocks", []):
        if b.get("action") == "new":
            totals_first[b.get("issue")] += _block_minutes(b)
    for b in final.get("blocks", []):
        if b.get("action") == "new":
            totals_final[b.get("issue")] += _block_minutes(b)
    return {
        "proposed_minutes": proposed,
        "moved_minutes": moved,
        "removed_minutes": removed,
        "added_minutes": added,
        "accuracy": round(1 - (moved + removed) / proposed, 3) if proposed else None,
        "by_confidence": by_conf,
        "new_issues_proposed": len(first.get("new_issues") or []),
        "new_issues_created": len(created),
        "issues_first": len(totals_first),
        "issues_final": len(totals_final),
    }


# --------------------------------------------------------------------------- costo de la sesión del agente


def _usage_from(path: Path, since: datetime | None) -> dict:
    out: dict[str, dict[str, int]] = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if o.get("type") != "assistant" or o.get("forkedFrom"):
                    continue
                if since and o.get("timestamp") and common.parse_iso(o["timestamp"]) < since:
                    continue
                msg = o.get("message") or {}
                u = msg.get("usage") or {}
                if not u:
                    continue
                m = out.setdefault(msg.get("model") or "?", {"turns": 0, "input": 0, "cache_read": 0,
                                                             "cache_write": 0, "output": 0})
                m["turns"] += 1
                m["input"] += int(u.get("input_tokens") or 0)
                m["cache_read"] += int(u.get("cache_read_input_tokens") or 0)
                m["cache_write"] += int(u.get("cache_creation_input_tokens") or 0)
                m["output"] += int(u.get("output_tokens") or 0)
    except OSError:
        pass
    return out


def session_usage(session_id: str | None, since: datetime | None, projects_dir: Path | None = None) -> dict | None:
    """Turnos y tokens por modelo de la sesión del skill y de sus subagentes desde `since`."""
    if not session_id:
        return None
    projects_dir = projects_dir or Path("~/.claude/projects").expanduser()
    mains = list(projects_dir.glob(f"*/{session_id}.jsonl"))
    if not mains:
        return None
    main = mains[0]
    subs = sorted((main.with_suffix("") / "subagents").glob("*.jsonl"))
    sub_usage = []
    for s in subs:
        u = _usage_from(s, since)
        if u:
            sub_usage.append(u)
    return {"main": _usage_from(main, since), "subagents": sub_usage, "subagents_count": len(sub_usage)}


# --------------------------------------------------------------------------- cierre


def mcp_summary(raw: Path) -> dict:
    out = {}
    for f in sorted(raw.glob("mcp*.json")) if raw.is_dir() else []:
        try:
            data = common.read_json(f, {}) or {}
        except ValueError:
            out[f.stem] = {"status": "json inválido"}
            continue
        evs = Counter(e.get("source") for e in data.get("events", []))
        for src, c in (data.get("coverage") or {}).items():
            out[src] = {"status": c.get("status"), "queries": c.get("queries"), "events": evs.get(src, 0),
                        "incomplete": len(c.get("incomplete") or []), "error": bool(c.get("error"))}
    return out


def review_minutes(activity_dir: Path, review_date: str) -> int:
    """Minutos con uso real de la página (un aviso por minuto como máximo) para ese día revisado."""
    n = 0
    for f in activity_dir.glob("*.jsonl") if activity_dir.is_dir() else []:
        for line in f.read_text(errors="replace").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("review_date") == review_date and rec.get("kind") == "input":
                n += 1
    return n


def close_summary(sdir: Path, plan: dict, rec: dict, page_state: dict | None) -> dict:
    m = load(sdir)
    first = None
    try:
        first = common.read_json(sdir / FIRST_PLAN)
    except ValueError:
        pass
    started = m.get("started")
    since = common.parse_iso(started) if started else None
    rounds = m.get("rounds", [])
    summary = {
        "date": sdir.name,
        "run": rec.get("n"),
        "outcome": rec.get("outcome"),
        "started": started,
        "closed": rec.get("closed_at"),
        "minutes": round((common.parse_iso(rec["closed_at"]) - since).total_seconds() / 60, 1)
        if since and rec.get("closed_at") else None,
        "rounds": len(rounds),
        "builds": (m.get("build") or {}).get("count"),
        "first_page_at": (m.get("build") or {}).get("first_at"),
        "collect": m.get("collect"),
        "mcp": mcp_summary(sdir / "raw"),
        "attribution": attribution_diff(first, plan),
        "review": {
            "notes": sum(r.get("notes", 0) for r in rounds),
            "reassigned": sum(r.get("reassigned", 0) for r in rounds),
            "absorbed": sum(r.get("absorbed", 0) for r in rounds),
            "texts_edited": (rounds[-1].get("texts_edited") if rounds else 0),
            "text_similarity_avg": (rounds[-1].get("text_similarity_avg") if rounds else None),
            "levels": (rounds[-1].get("levels") if rounds else {}),
            "modes": (page_state or {}).get("modes"),
            "page_minutes": review_minutes(common.STATE_ROOT / "activity", sdir.name),
        },
        "load": m.get("load"),
        "errors": m.get("errors", []),
        "usage": session_usage(os.environ.get("CLAUDE_CODE_SESSION_ID"), since),
    }
    return summary


def append_global(summary: dict) -> None:
    try:
        path = common.STATE_ROOT / GLOBAL
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(summary, ensure_ascii=False) + "\n")
    except OSError:
        pass


def error(sdir: Path, where: str, message: str) -> None:
    append(sdir, "errors", {"at": now_iso(), "where": where, "message": str(message)[:200]})

