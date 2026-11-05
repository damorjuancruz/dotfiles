#!/usr/bin/env python3
"""Colector de threads de T3 Code (solo lectura).

T3 Code guarda sus threads en ~/.t3/userdata/statev2.sqlite. Los threads de Claude
(proveedor `claudeAgent`) también dejan su transcript en ~/.claude/projects, con mucho más
detalle de horarios, así que esa actividad la sigue armando el colector claude_code. Para esos
threads este módulo solo aporta lo que el transcript no tiene (`claude_sessions`): el título del
thread, el proyecto de T3 y el worktree.

Los threads de otros proveedores (Codex, etc.) no dejan transcript de Claude: `collect` arma sus
segmentos de actividad con los mensajes, los ítems de turno y las corridas del thread, y corta
un segmento cuando hay más de `idle_gap_minutes` sin actividad. Los subagentes cuentan como
actividad del thread raíz. El thread desde el que se corre el skill (`T3CODE_THREAD_ID`) se
marca con `current: true` en hints.

Uso: python scripts/collectors/t3_code.py [--date AAAA-MM-DD]
"""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import common  # noqa: E402

SOURCE = "t3"
CLAUDE_PROVIDERS = {"claudeAgent"}


def short_id(thread_id: str) -> str:
    """Ids como `import:claudeAgent:f66f1b58-…` o `thread:provider:…:a9bb…`: el último tramo."""
    return thread_id.rsplit(":", 1)[-1].rsplit("%3A", 1)[-1][:8]


def connect(path: Path) -> sqlite3.Connection:
    """Solo lectura sin copiar la base (pesa decenas de MB) y sin bloquear a T3."""
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        con.execute("select 1 from orchestration_v2_projection_threads limit 1")
    except sqlite3.Error:
        con = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _payload(row) -> dict:
    try:
        return json.loads(row["payload_json"] or "{}")
    except (TypeError, ValueError):
        return {}


def load_threads(con: sqlite3.Connection) -> dict[str, dict]:
    """{thread_id: {id, title, project, cwd, branch, provider, root, subagent, native_ids}}."""
    projects = {r["project_id"]: (r["title"], r["workspace_root"])
                for r in con.execute("select project_id, title, workspace_root from projection_projects")}
    threads: dict[str, dict] = {}
    for r in con.execute("select thread_id, project_id, title, default_provider, deleted_at, payload_json "
                         "from orchestration_v2_projection_threads"):
        p = _payload(r)
        lineage = p.get("lineage") or {}
        proj_title, root_dir = projects.get(r["project_id"], (None, None))
        cwd = p.get("worktreePath") or root_dir or ""
        threads[r["thread_id"]] = {
            "id": r["thread_id"], "title": r["title"] or p.get("title") or "",
            "project": proj_title or (Path(cwd).name if cwd else ""), "cwd": cwd, "branch": p.get("branch") or "",
            "provider": r["default_provider"] or p.get("providerInstanceId") or "",
            "root": lineage.get("rootThreadId") or r["thread_id"],
            "subagent": lineage.get("relationshipToParent") == "subagent",
            "deleted": bool(r["deleted_at"]), "native_ids": [], "providers": set(),
        }
    for r in con.execute("select thread_id, provider, payload_json from orchestration_v2_projection_provider_threads"):
        t = threads.get(r["thread_id"])
        if not t:
            continue
        t["providers"].add(r["provider"])
        native = ((_payload(r).get("nativeThreadRef") or {}).get("nativeId"))
        if native and r["provider"] in CLAUDE_PROVIDERS:
            t["native_ids"].append(native)
    return threads


def db_path(cfg: dict) -> Path | None:
    src = cfg["sources"].get("t3_code") or {}
    if not src.get("enabled"):
        return None
    path = common.expand_path(src.get("db_path") or "~/.t3/userdata/statev2.sqlite")
    return path if path.exists() else None


def claude_sessions(cfg: dict) -> dict[str, dict]:
    """{id de sesión de Claude: thread de T3} para enriquecer el colector claude_code. {} si T3
    no está configurado o no se puede leer."""
    path = db_path(cfg)
    if not path:
        return {}
    try:
        with contextlib.closing(connect(path)) as con:
            threads = load_threads(con)
    except sqlite3.Error:
        return {}
    return {sid: t for t in threads.values() for sid in t["native_ids"]}


def covered_by_claude(t: dict, threads: dict[str, dict]) -> bool:
    """El thread (o su raíz, si es subagente) tiene transcript de Claude Code."""
    root = threads.get(t["root"], t)
    return bool(t["native_ids"] or root["native_ids"] or (t["providers"] | root["providers"]) & CLAUDE_PROVIDERS
                or root["provider"] in CLAUDE_PROVIDERS)


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def activity(con: sqlite3.Connection, start: datetime, end: datetime) -> dict[str, list[tuple[str, str | None]]]:
    """{thread_id: [(timestamp ISO UTC, prompt del usuario o None)]} dentro del rango."""
    lo, hi = _utc(start), _utc(end)
    out: dict[str, list] = defaultdict(list)
    for r in con.execute("select thread_id, role, created_at, payload_json from orchestration_v2_projection_messages "
                         "where created_at >= ? and created_at < ?", (lo, hi)):
        p = _payload(r)
        text = " ".join(str(p.get("text") or "").split())
        prompt = text if r["role"] == "user" and p.get("createdBy", "user") == "user" and text else None
        out[r["thread_id"]].append((r["created_at"], prompt))
    for r in con.execute("select thread_id, updated_at from orchestration_v2_projection_turn_items "
                         "where updated_at >= ? and updated_at < ?", (lo, hi)):
        out[r["thread_id"]].append((r["updated_at"], None))
    for col in ("requested_at", "completed_at"):
        for r in con.execute(f"select thread_id, {col} ts from orchestration_v2_projection_runs "
                             f"where {col} >= ? and {col} < ?", (lo, hi)):
            out[r["thread_id"]].append((r["ts"], None))
    return out


def collect(cfg: dict, env: dict, day: date, current_thread: str | None = None) -> dict:
    tz = common.get_tz(cfg)
    src = cfg["sources"]["t3_code"]
    path = db_path(cfg)
    if not path:  # T3 Code no está instalado en esta máquina: no es un error ni hay nada que contar
        return {"source": SOURCE, "status": "ok", "events": []}
    current_thread = current_thread or os.environ.get("T3CODE_THREAD_ID")
    key_rx = common.issue_key_regex(list(cfg["projects"]))
    d_start, d_end = common.day_bounds(day, tz)
    gap = timedelta(minutes=src["idle_gap_minutes"])
    try:
        with contextlib.closing(connect(path)) as con:
            threads = load_threads(con)
            act = activity(con, d_start, d_end)
    except sqlite3.Error as e:
        return {"source": SOURCE, "status": "error", "message": f"{path}: {e}", "events": []}

    by_root: dict[str, list] = defaultdict(list)
    skipped = 0
    for tid, stamps in act.items():
        t = threads.get(tid)
        if not t or t["deleted"]:
            continue
        if covered_by_claude(t, threads):
            skipped += 1
            continue
        root = t["root"] if t["root"] in threads else tid
        for ts, prompt in stamps:
            # Los prompts de un subagente los escribe el agente padre, no el usuario.
            by_root[root].append((common.parse_iso(ts).astimezone(tz), None if t["subagent"] else prompt))

    events = []
    for root, stamps in by_root.items():
        t = threads[root]
        for seg in common.split_by_gap(stamps, gap):
            prompts = [p for _, p in seg if p]
            keys = common.find_issue_keys(" ".join([t["branch"], t["cwd"], t["title"], *prompts]), key_rx)
            hints = {"repo": t["project"], "cwd": t["cwd"], "branch": t["branch"], "issue_keys": keys,
                     "thread": short_id(root), "provider": t["provider"]}
            if root == current_thread:
                hints["current"] = True
            title = f"thread T3 Code ({t['provider'] or 'sin proveedor'}) en {t['project']}" + (f": {t['title']}" if t["title"] else "")
            events.append(common.Event(
                SOURCE, seg[0][0].isoformat(), seg[-1][0].isoformat(), title, common.prompts_detail(prompts), hints, "normal",
                id=common.make_event_id(SOURCE, root, seg[0][0].isoformat()),
            ).to_dict())
    return {"source": SOURCE, "status": "ok", "events": sorted(events, key=lambda e: e["start"]),
            "messages": [f"{skipped} threads de Claude: su actividad la arma el colector claude_code"] if skipped else []}


if __name__ == "__main__":
    sys.exit(common.collector_main(collect, __doc__))
