#!/usr/bin/env python3
"""Colector de transcripts de Claude Code (solo lectura).

Recorre ~/.claude/projects/<slug>/<sesión>.jsonl (y los subagentes de cada sesión, que
cuentan como actividad de la sesión padre) y arma segmentos de actividad: se corta un
segmento cuando hay más de `idle_gap_minutes` sin mensajes.

Cada segmento lleva cwd, branch, título de la sesión y los prompts reales del usuario
(primero y último, truncados), con la hora de cada prompt en `hints.prompt_times` (para
separar la interacción del trabajo autónomo, ver collect.mark_parallel). La sesión desde la que se corre el skill se marca con
`current: true` en hints.

Las sesiones de Claude que corren dentro de T3 Code también dejan su transcript acá. Para esas,
si la fuente t3_code está activa, el título, el proyecto y el thread salen de T3 (ver
collectors/t3_code.py). Las sesiones que T3 abre solo para generar títulos de threads no son
trabajo y se descartan, igual que las que corre en sus worktrees sin thread asociado (por
ejemplo, para elegir el nombre de una branch). Las guías de revisión de PR que arma T3 sí
quedan, como evidencia débil del PR revisado.

Uso: python scripts/collectors/claude_code.py [--date AAAA-MM-DD]
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors import t3_code  # noqa: E402
from lib import common  # noqa: E402

SOURCE = "cc"
# T3 Code genera los títulos de sus threads con sesiones cortas en /tmp/t3code-claude-title-*.
T3_TITLE_SLUG = "-tmp-t3code-claude-title-"
T3_DIR = Path("~/.t3").expanduser()
T3_REVIEW_GUIDE = re.compile(r"/worktrees/review-guide-")
T3_PR_RX = re.compile(r"change request #(\d+)")


def real_user_text(obj: dict) -> str | None:
    """Texto de un mensaje real del usuario; None si es wrapper de sistema o tool result.

    Mismo criterio que manage-claude-sessions/scripts/list_sessions.py."""
    if obj.get("type") != "user" or obj.get("isSidechain") or obj.get("isMeta"):
        return None
    content = (obj.get("message") or {}).get("content", "")
    text = ""
    if isinstance(content, list):
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text":
                text = c.get("text", "")
                break
    elif isinstance(content, str):
        text = content
    stripped = (text or "").lstrip()
    if not stripped or stripped.startswith("<") or "caveat" in stripped[:120].lower():
        return None
    return " ".join(stripped.split())


def read_session(files: list[Path], d_start: datetime, d_end: datetime, tz) -> dict:
    """Mensajes del día de una sesión (archivo principal + subagentes)."""
    stamps: list[tuple[datetime, str | None, str | None, str | None]] = []  # ts, prompt, cwd, branch
    title = entrypoint = None
    for i, f in enumerate(files):
        is_main = i == 0
        with open(f, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if is_main and o.get("type") == "ai-title" and o.get("aiTitle"):
                    title = o["aiTitle"]
                if is_main and o.get("type") == "custom-title" and o.get("customTitle"):
                    title = o["customTitle"]
                if o.get("type") not in ("user", "assistant") or not o.get("timestamp"):
                    continue
                entrypoint = entrypoint or o.get("entrypoint")
                ts = common.parse_iso(o["timestamp"]).astimezone(tz)
                if not d_start <= ts < d_end:
                    continue
                prompt = real_user_text(o) if is_main else None
                stamps.append((ts, prompt, o.get("cwd"), o.get("gitBranch")))
    stamps.sort(key=lambda s: s[0])
    return {"title": title, "stamps": stamps, "entrypoint": entrypoint}


def session_files(projects_dir: Path, since: datetime) -> dict[str, list[Path]]:
    """{session_id: [archivo principal, subagentes...]} con modificaciones desde `since`."""
    result: dict[str, list[Path]] = {}
    ts = since.timestamp()
    for main in projects_dir.glob("*/*.jsonl"):
        if main.parent.name.startswith(T3_TITLE_SLUG) or main.stat().st_mtime < ts:
            continue
        files = [main]
        sub = main.with_suffix("") / "subagents"
        if sub.is_dir():
            files += sorted(p for p in sub.glob("*.jsonl") if p.stat().st_mtime >= ts)
        result[main.stem] = files
    return result


def collect(cfg: dict, env: dict, day: date, current_session: str | None = None) -> dict:
    tz = common.get_tz(cfg)
    src = cfg["sources"]["claude_code"]
    projects_dir = common.expand_path(src["projects_dir"])
    if not projects_dir.is_dir():
        return {"source": SOURCE, "status": "error", "message": f"no existe {projects_dir}", "events": []}
    current_session = current_session or os.environ.get("CLAUDE_CODE_SESSION_ID")
    t3_threads = t3_code.claude_sessions(cfg)
    key_rx = common.issue_key_regex(list(cfg["projects"]))
    d_start, d_end = common.day_bounds(day, tz)
    gap = timedelta(minutes=src["idle_gap_minutes"])

    events = []
    for sid, files in session_files(projects_dir, d_start).items():
        data = read_session(files, d_start, d_end, tz)
        for seg in common.split_by_gap(data["stamps"], gap):
            prompts = [p for _, p, _, _ in seg if p]
            cwd = Counter(c for _, _, c, _ in seg if c).most_common(1)
            branch = Counter(b for _, _, _, b in seg if b and b != "HEAD").most_common(1)
            cwd_s = cwd[0][0] if cwd else ""
            branch_s = branch[0][0] if branch else ""
            project = Path(cwd_s).name if cwd_s else files[0].parent.name
            t3 = t3_threads.get(sid)
            session_title, weight = data["title"], "normal"
            internal = (t3_threads and not t3 and data["entrypoint"] == "sdk-cli"
                        and cwd_s.startswith(str(T3_DIR) + "/"))
            if internal:
                if not T3_REVIEW_GUIDE.search(cwd_s):
                    continue  # sesión de utilidad de T3 (nombre de branch, etc.)
                pr = T3_PR_RX.search(next((p for _, p, _, _ in data["stamps"] if p), ""))
                project = Path(cwd_s).parent.name if Path(cwd_s).name == "checkout" else project
                title = "guía de revisión de T3 Code" + (f" del PR #{pr.group(1)}" if pr else "")
                prompts, weight = [], "weak"
            elif t3:
                project = t3["project"] or project
                branch_s = branch_s or t3["branch"]
                session_title = t3["title"] or session_title
                title = f"thread T3 Code (Claude) en {project}"
            else:
                title = f"sesión Claude Code en {project}"
            if session_title:
                title += f": {session_title}"
            keys = common.find_issue_keys(" ".join([branch_s, cwd_s, session_title or "", *prompts]), key_rx)
            hints = {"repo": project, "cwd": cwd_s, "branch": branch_s, "issue_keys": keys, "session": sid[:8],
                     "prompt_times": [] if internal else [ts.isoformat() for ts, p, _, _ in seg if p]}
            if t3:
                hints["t3_thread"] = t3_code.short_id(t3["id"])
            if sid == current_session:
                hints["current"] = True
            events.append(common.Event(
                SOURCE, seg[0][0].isoformat(), seg[-1][0].isoformat(), title, common.prompts_detail(prompts),
                hints, weight, id=common.make_event_id(SOURCE, sid, seg[0][0].isoformat()),
            ).to_dict())
    return {"source": SOURCE, "status": "ok", "events": sorted(events, key=lambda e: e["start"])}


if __name__ == "__main__":
    sys.exit(common.collector_main(collect, __doc__))
