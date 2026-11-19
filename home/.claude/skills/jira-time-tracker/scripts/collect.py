#!/usr/bin/env python3
"""Corre los colectores habilitados y arma el digest del día.

  - Cada colector escribe <state>/<fecha>/raw/<fuente>.json (con sus eventos completos).
  - Las keys de Jira mencionadas por las otras fuentes se agregan como candidatas en una
    segunda pasada.
  - Las sesiones de agente (cc, t3, también las remotas) y el uso de la página de revisión del
    skill (jtt) se cruzan entre sí para el trabajo en paralelo (ver mark_parallel).
  - <state>/<fecha>/digest.json es lo que usa plan.py.
  - Por stdout sale el digest en texto compacto: es lo único que lee el agente.

Uso: python scripts/collect.py [--date AAAA-MM-DD] [--only git_local,chrome] [--reuse] [--refresh jira]
  --reuse    no vuelve a correr colectores cuyo raw/<fuente>.json ya existe (útil al iterar).
  --refresh  vuelve a correr solo esas fuentes y reutiliza el resto (implica --reuse).
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collectors import chrome, claude_code, erpnext, git_local, github, jira, remote, review_page, t3_code  # noqa: E402
from lib import common, metrics  # noqa: E402

LOCAL_COLLECTORS = {
    "erpnext": erpnext.collect,
    "git_local": git_local.collect,
    "github": github.collect,
    "claude_code": claude_code.collect,
    "t3_code": t3_code.collect,
    "remote": remote.collect,
    "chrome": chrome.collect,
    "review_page": review_page.collect,
}
MCP_SOURCES = ("outlook", "mail", "teams", "sharepoint", "google_drive")
DETAIL_CHARS = 140
AGENT_SOURCES = ("cc", "t3", "jtt")


# --------------------------------------------------------------------------- keys


def mentioned_keys(results: dict[str, dict]) -> list[str]:
    keys: list[str] = []
    for res in results.values():
        for ev in res.get("events", []):
            h = ev.get("hints") or {}
            for k in h.get("issue_keys", []):
                if k not in keys:
                    keys.append(k)
    return keys


# --------------------------------------------------------------------------- digest


# --------------------------------------------------------------------------- paralelo


def mark_parallel(timeline: list[dict], interaction_minutes: int) -> None:
    """Cruza las sesiones de agente que se pisan en el tiempo.

    Interacción: los `interaction_minutes` previos a cada prompt del usuario (leer la respuesta
    y escribir), más los tramos de `hints.activity_spans` (uso real de la página de revisión,
    fuente jtt). El resto del tramo de la sesión es trabajo autónomo del agente.

    Un trabajo autónomo cuenta para su incidencia salvo cuando, en ese mismo horario, el usuario
    interactúa con otra sesión: ese tiempo queda "tapado" y es de la sesión con interacción.

    Agrega a cada evento de agente (en hints, en ISO):
      interactive          tramos de interacción propios;
      shadowed             [{start, end, by: [ids]}] trabajo autónomo tapado por otra sesión;
      parallel_interaction ids de otras sesiones con interacción en el mismo horario.
    """
    win = timedelta(minutes=interaction_minutes)
    agents = []
    for ev in timeline:
        if ev.get("source") not in AGENT_SOURCES:
            continue
        h = ev.setdefault("hints", {})
        span = [(common.parse_iso(ev["start"]), common.parse_iso(ev["end"]))]
        inter = common.merge_spans([(t - win, t) for t in map(common.parse_iso, h.get("prompt_times", []))]
                                   + [(common.parse_iso(s), common.parse_iso(e)) for s, e in h.get("activity_spans", [])])
        agents.append((ev, span, inter))
    for ev, span, inter in agents:
        auto = common.subtract_spans(span, inter)
        shadowed, parallel = [], []
        for other, _, o_inter in agents:
            if other is ev:
                continue
            for s, e in common.intersect_spans(auto, o_inter):
                shadowed.append({"start": s.isoformat(), "end": e.isoformat(), "by": [other["id"]]})
            if common.intersect_spans(inter, o_inter):
                parallel.append(other["id"])
        merged: list[dict] = []
        for sh in sorted(shadowed, key=lambda x: x["start"]):
            if merged and sh["start"] <= merged[-1]["end"]:
                merged[-1]["end"] = max(merged[-1]["end"], sh["end"])
                merged[-1]["by"] = list(dict.fromkeys(merged[-1]["by"] + sh["by"]))
            else:
                merged.append(sh)
        h = ev["hints"]
        h["interactive"] = [[s.isoformat(), e.isoformat()] for s, e in inter]
        h["shadowed"] = merged
        h["parallel_interaction"] = parallel


def link_review_sessions(timeline: list[dict]) -> None:
    """Une cada tramo de uso de la página (jtt) con las sesiones del agente que corrían el skill:
    misma sesión de Claude Code o mismo thread de T3. Lo anota en `hints.agent_events`."""
    for ev in timeline:
        if ev.get("source") != "jtt":
            continue
        h = ev.setdefault("hints", {})
        ids = [o["id"] for o in timeline if o.get("source") in ("cc", "t3") and (
            (h.get("session") and (o.get("hints") or {}).get("session") == h["session"])
            or (h.get("t3_thread") and h["t3_thread"] in ((o.get("hints") or {}).get("t3_thread"),
                                                          (o.get("hints") or {}).get("thread"))))]
        if ids:
            h["agent_events"] = ids


def build_digest(day: date, cfg: dict, results: dict[str, dict], now: datetime) -> dict:
    tz = common.get_tz(cfg)
    erp = results.get("erpnext") or {}
    rng = erp.get("range")
    if not rng:
        is_today = now.astimezone(tz).date() == day
        end = common.round_down(now.astimezone(tz), cfg["rules"]["slot_minutes"]).isoformat() if is_today else None
        rng = {"start": None, "end": end, "end_source": "now" if is_today else None, "breaks": [], "checkins": []}
    rng = dict(rng)
    runs = common.load_runs(day)
    since = common.loaded_until(runs)
    if since:
        # Tanda siguiente del mismo día: se planifica desde el fin de la última tanda cargada.
        rng["from"] = since
        rng["breaks"] = [b for b in rng.get("breaks", []) if common.parse_iso(b["end"]) > common.parse_iso(since)]
        lunch_run = next((r["n"] for r in runs if r.get("outcome") == "load" and r.get("lunch")), None)
        if lunch_run:
            rng["lunch_done_in"] = lunch_run
    jr = results.get("jira") or {}
    timeline = sorted((ev for res in results.values() for ev in res.get("events", [])
                       if not since or common.parse_iso(ev["end"]) > common.parse_iso(since)),
                      key=lambda e: (e["start"], e["source"]))
    mark_parallel(timeline, cfg["rules"]["interaction_minutes"])
    link_review_sessions(timeline)
    return {
        "date": day.isoformat(),
        "generated_at": now.astimezone(tz).isoformat(timespec="seconds"),
        "range": rng,
        "runs": runs,
        "sources": {
            src: {k: v for k, v in {"status": res.get("status"), "message": res.get("message"),
                                     "messages": res.get("messages"), "events": len(res.get("events", []))}.items() if v}
            for src, res in results.items()
        },
        "mcp_sources": [s for s in MCP_SOURCES if cfg["sources"].get(s, {}).get("enabled")],
        "worklogs": jr.get("worklogs", []),
        "candidates": jr.get("candidates", []),
        "misc_issues": cfg["misc_issues"],
        "projects": cfg["projects"],
        "timeline": timeline,
    }


def active_keys(d: dict) -> set[str]:
    """Keys con actividad en el día: mencionadas en la línea de tiempo o con worklogs."""
    keys = {w["issue"] for w in d.get("worklogs", [])}
    for ev in d.get("timeline", []):
        h = ev.get("hints") or {}
        keys.update(h.get("issue_keys", []))
    return keys


def _hm(iso: str | None, tz) -> str:
    return common.fmt_hm(common.parse_iso(iso).astimezone(tz)) if iso else "?"


def _spans_hm(spans: list, tz, limit: int = 6) -> str:
    parts = [f"{_hm(s, tz)}–{_hm(e, tz)}" for s, e in spans[:limit]]
    return ",".join(parts) + ("…" if len(spans) > limit else "")


def _parallel_tags(h: dict, tz) -> list[str]:
    """Etiquetas de reparto entre sesiones en paralelo. La interacción propia no se lista: se
    deduce de la hora de cada prompt, que va en las líneas de abajo."""
    if not h.get("interactive"):
        tags = ["sin prompts: autónoma"]
    elif not h.get("prompts"):  # interacción sin prompts listados (uso de la página, fuente jtt)
        tags = [f"interacción {_spans_hm(h['interactive'], tz)}"]
    else:
        tags = []
    by: dict[str, int] = {}
    for sh in h.get("shadowed", []):
        mins = int((common.parse_iso(sh["end"]) - common.parse_iso(sh["start"])).total_seconds() // 60)
        for i in sh["by"]:
            by[i] = by.get(i, 0) + mins
    if by:
        tags.append("tapada " + ", ".join(f"{m} min por {i}" for i, m in by.items()))
    if h.get("parallel_interaction"):
        tags.append(f"interacción simultánea con {','.join(h['parallel_interaction'])}")
    return tags


def render_digest(d: dict, tz) -> str:
    day = date.fromisoformat(d["date"])
    rng = d["range"]
    out = [f"DIGEST {day.strftime('%d/%m/%Y')} (generado {_hm(d['generated_at'], tz)})"]
    line = f"Rango: entrada {_hm(rng.get('start'), tz) if rng.get('start') else 'SIN CHECKIN'}"
    line += f" · corte {_hm(rng.get('end'), tz) if rng.get('end') else 'SIN CORTE'}"
    if rng.get("end_source"):
        line += f" ({'checkout' if rng['end_source'] == 'checkout' else 'hora actual'})"
    if rng.get("from"):
        line += f" · TANDA {len(d.get('runs', [])) + 1}: planificar desde {_hm(rng['from'], tz)}"
    if rng.get("breaks"):
        line += " · salidas: " + ", ".join(f"{_hm(b['start'], tz)}–{_hm(b['end'], tz)}" for b in rng["breaks"])
    out.append(line)
    for r in d.get("runs", []):
        what = {"load": "cargada", "cancel": "cancelada"}.get(r.get("outcome"), r.get("outcome"))
        out.append(f"Tanda {r['n']} {what}: {_hm(r.get('from'), tz) if r.get('from') else '?'}–"
                   f"{_hm(r.get('until'), tz) if r.get('until') else '?'}"
                   + (" · almuerzo descontado ahí" if r.get("lunch") else ""))
    if rng.get("checkins"):
        out.append("Checkins: " + ", ".join(f"{c['log_type']} {_hm(c['time'], tz)}" for c in rng["checkins"]))

    src_parts = []
    for name, s in d["sources"].items():
        part = f"{name} {s.get('status')}"
        if s.get("events"):
            part += f" ({s['events']} ev)"
        msg = s.get("message") or "; ".join(s.get("messages") or [])
        if msg:
            part += f" [{msg[:160]}]"
        src_parts.append(part)
    out.append("Fuentes: " + " · ".join(src_parts))
    if d["mcp_sources"]:
        out.append("Fuentes MCP a consultar por el agente: " + ", ".join(d["mcp_sources"]))

    out += ["", "Worklogs existentes del día:"]
    if not d["worklogs"]:
        out.append("  (ninguno)")
    since = common.parse_iso(rng["from"]) if rng.get("from") else None
    for w in d["worklogs"]:
        s = common.parse_iso(w["started"]).astimezone(tz)
        e = s + timedelta(minutes=w["minutes"])
        comment = f' "{w["comment"][:80]}"' if w.get("comment") else ""
        before = " [tanda anterior: no va en el plan]" if since and e <= since else ""
        out.append(f"  id={w['id']} {w['issue']} {common.fmt_hm(s)}–{common.fmt_hm(e)} ({common.fmt_duration(w['minutes'])}){comment}{before}")

    active = active_keys(d)
    misc = {k for k in [d["misc_issues"].get("parent"), *d["misc_issues"].get("subtasks", {}).values()] if k}
    excl = {k: (p["excluded_status_categories"], p["excluded_statuses"]) for k, p in d["projects"].items()}
    def excluded(c: dict) -> bool:
        cats, sts = excl.get(c["key"].split("-")[0], ([], []))
        return c.get("status_category") in cats or c.get("status") in sts

    shown, compact, closed = [], [], []
    for c in d["candidates"]:
        is_active, origins = c["key"] in active, set(c.get("origin", []))
        if is_active or c["key"] in misc:
            shown.append((c, is_active))
        elif excluded(c):
            closed.append(c)
        elif not c.get("assignee_me") and origins <= {"recent"}:
            compact.append(c)
        else:
            shown.append((c, is_active))

    out += ["", "Candidatas (★ asignada a mí · ✗ estado excluido · ● con actividad hoy, con extracto de la descripción):"]
    for c, is_active in shown:
        mark = "✗" if excluded(c) else ("★" if c.get("assignee_me") else " ")
        extra = []
        if c.get("parent"):
            extra.append(f"padre {c['parent']}")
        if not c.get("assignee_me"):
            extra.append(f"asignada {c.get('assignee') or '—'}")
        extra.append(f"origen {','.join(c.get('origin', []))}")
        dot = "●" if is_active else " "
        out.append(f"  {mark}{dot} {c['key']} [{c.get('status')}] {c.get('summary', '')[:70]} · {' · '.join(extra)}")
        if is_active and c.get("description"):
            out.append(f"       ↳ {c['description']}")
    if closed:
        out.append("  Excluidas (cerradas o finalizadas) sin actividad hoy: " + ", ".join(c["key"] for c in closed))
    if compact:
        out.append("  Recientes sin actividad hoy (no asignadas): "
                   + ", ".join(f"{c['key']} {c.get('summary', '')[:40]}" for c in compact))

    out += ["", "Línea de tiempo (id entre llaves para usar como evidencia):"]
    for ev in d["timeline"]:
        s, e = _hm(ev["start"], tz), _hm(ev["end"], tz)
        when = s if s == e else f"{s}–{e}"
        h = ev.get("hints") or {}
        tags = []
        keys = h.get("issue_keys", [])
        if keys:
            tags.append(",".join(keys))
        if h.get("branch"):
            tags.append(f"br={h['branch']}")
        for k in ("github", "erp_docs"):
            if h.get(k):
                tags.append(f"{k}={';'.join(h[k][:3])}")
        if h.get("doctype"):
            tags.append(f"doc={h['doctype']} {h.get('docname', '')}".strip())
        if h.get("current"):
            tags.append("SESIÓN ACTUAL")
        if h.get("agent_events"):
            tags.append(f"sesión del skill {','.join(h['agent_events'][:4])}")
        if ev["source"] in AGENT_SOURCES:
            tags += _parallel_tags(h, tz)
        prompts = h.get("prompts") or []
        detail = f" | {' '.join(ev['detail'].split())[:DETAIL_CHARS]}" if ev.get("detail") and not prompts else ""
        tag_s = f" [{' · '.join(tags)}]" if tags else ""
        out.append(f"  {when:<11} {ev['source']:<6} {ev['title'][:110]}{tag_s}{detail} {{{ev['id']}}}")
        for p in prompts:
            out.append(f"       {_hm(p['at'], tz)}  «{p['text']}»")
    return "\n".join(out)


# --------------------------------------------------------------------------- main


def run(cfg: dict, env: dict, day: date, only: list[str] | None, reuse: bool, now: datetime,
        refresh: list[str] | None = None) -> dict:
    raw = common.raw_dir(day)
    enabled = [s for s in LOCAL_COLLECTORS if cfg["sources"].get(s, {}).get("enabled") and (not only or s in only)]
    results: dict[str, dict] = {}
    durations: dict[str, float] = {}

    def run_one(name: str, collect) -> dict:
        path = raw / f"{name}.json"
        if reuse and name not in (refresh or []) and path.exists():
            return common.read_json(path)
        t0 = time.monotonic()
        try:
            return collect()
        except Exception as e:  # un colector roto no debe cortar el resto
            return {"source": name, "status": "error", "message": f"{type(e).__name__}: {e}"[:300], "events": []}
        finally:
            durations[name] = time.monotonic() - t0

    for name in enabled:
        results[name] = run_one(name, lambda: LOCAL_COLLECTORS[name](cfg, env, day))
    # Jira va al final: suma como candidatas las keys que mencionan las otras fuentes.
    if cfg["sources"]["jira"]["enabled"] and (not only or "jira" in only):
        results["jira"] = run_one("jira", lambda: jira.collect(cfg, env, day, mentioned_keys(results)))

    for name, res in results.items():
        common.write_json(raw / f"{name}.json", res)
    digest = build_digest(day, cfg, results, now)
    common.write_json(common.state_dir(day) / "digest.json", digest)
    digest["_durations"] = durations
    return digest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date")
    ap.add_argument("--only", help="lista de fuentes separadas por coma")
    ap.add_argument("--reuse", action="store_true")
    ap.add_argument("--refresh", help="fuentes a volver a correr (el resto se reutiliza)")
    args = ap.parse_args()
    try:
        cfg = common.load_config()
    except (common.ConfigMissing, common.ConfigError) as e:
        print(e, file=sys.stderr)
        return 3
    tz = common.get_tz(cfg)
    day = common.parse_day(args.date, tz)
    only = [s.strip() for s in args.only.split(",")] if args.only else None
    refresh = [s.strip() for s in args.refresh.split(",")] if args.refresh else None
    digest = run(cfg, common.load_env(), day, only, args.reuse or bool(refresh), datetime.now(tz), refresh)
    durations = digest.pop("_durations", {})
    text = render_digest(digest, tz)
    print(text)
    if not refresh:  # un --refresh (por ejemplo después de cargar) no es una recolección nueva
        metrics.update(common.state_dir(day), "collect", metrics.collect_metrics(digest, durations, len(text)))
    sdir = common.state_dir(day, create=False)
    if (sdir / "plan.json").exists():
        st = common.read_json(sdir / "page_state.json", {}) or {}
        plan = common.read_json(sdir / "plan.json", {}) or {}
        print(f"\n! TANDA ABIERTA: hay un plan.json sin cerrar (ronda {plan.get('round', 1)}, "
              f"etapa {plan.get('stage') or 'sin build'}, última acción de la página: {st.get('action') or 'ninguna'}"
              + (f", creadas {', '.join(plan['created'])}" if plan.get("created") else "") + ")")
    print(f"\n(digest: {common.state_dir(day) / 'digest.json'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
