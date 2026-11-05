#!/usr/bin/env python3
"""Colector git local (solo lectura).

Descubre repos y worktrees bajo las raíces configuradas (más los worktrees de esos repos que
están en otro lado, como los de T3 Code) y trae del día:
  - commits de los emails configurados (todas las refs, sin duplicados entre worktrees).
    Los commits reescritos hoy (amend/rebase de commits de días anteriores) se marcan
    como "reescrito" y no como commit nuevo;
  - sesiones de actividad del reflog de HEAD: cada operación (commit, amend, rebase,
    reset, checkout...) es una marca de actividad. Se agrupan por branch: un cambio de
    branch abre una sesión nueva, y dentro de la misma branch se corta tras
    `session_gap_minutes` sin operaciones. Así se detecta, por ejemplo, horas de amends
    que `git log` no muestra (solo queda alcanzable la última versión).

Uso: python scripts/collectors/git_local.py [--date AAAA-MM-DD]
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import common  # noqa: E402

SOURCE = "git"
SKIP_DIRS = {"node_modules", ".venv", "venv", "__pycache__", ".cache", "dist", "build", ".next", "site-packages", ".tox"}
CHECKOUT_RX = re.compile(r"^checkout: moving from (\S+) to (\S+)$")
RETURNING_RX = re.compile(r"returning to refs/heads/(\S+)")
SHA_RX = re.compile(r"^[0-9a-f]{7,40}\^?$")
DETACHED = "(detached)"
REFLOG_LIMIT = "2000"
SEP = "\x1f"


def discover_repos(roots: list[str], max_depth: int) -> list[Path]:
    """Directorios con `.git` (directorio o archivo, en el caso de worktrees y submódulos)."""
    found: list[Path] = []
    for root in roots:
        base = common.expand_path(root)
        if not base.is_dir():
            continue
        base_depth = len(base.parts)
        for dirpath, dirnames, filenames in os.walk(base):
            path = Path(dirpath)
            if ".git" in dirnames or ".git" in filenames:
                found.append(path)
            if len(path.parts) - base_depth >= max_depth:
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
    return sorted(set(found))


def linked_worktrees(repos: list[Path], roots: list[str]) -> dict[Path, str]:
    """Worktrees de los repos encontrados que quedan fuera de las raíces (por ejemplo los que crea
    T3 Code en ~/.t3/worktrees), con su etiqueta `repo@worktree`. Sus commits ya salen del repo
    principal, pero cada worktree tiene su propio reflog de HEAD."""
    known = {r.resolve() for r in repos}
    extra: dict[Path, str] = {}
    for repo in repos:
        if not (repo / ".git").is_dir():
            continue
        try:
            out = run_git(repo, "worktree", "list", "--porcelain")
        except (RuntimeError, subprocess.TimeoutExpired):
            continue
        for line in out.splitlines():
            if not line.startswith("worktree "):
                continue
            path = Path(line[len("worktree "):])
            if path.resolve() in known or not path.is_dir():
                continue
            known.add(path.resolve())
            extra[path] = f"{repo_label(repo, roots)}@{path.name}"
    return extra


def run_git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip()[:300])
    return proc.stdout


def repo_label(repo: Path, roots: list[str]) -> str:
    for root in roots:
        base = common.expand_path(root)
        try:
            rel = repo.relative_to(base)
        except ValueError:
            continue
        return str(rel) if rel.parts else base.name
    return str(repo)


def parse_log(output: str) -> list[dict]:
    commits = []
    for line in output.splitlines():
        parts = line.split(SEP)
        if len(parts) < 5:
            continue
        sha, author_date, commit_date, source, subject = parts[:5]
        commits.append({"sha": sha, "author_date": author_date, "commit_date": commit_date,
                        "source": source, "subject": subject})
    return commits


def clean_ref(ref: str) -> str:
    for prefix in ("refs/heads/", "refs/remotes/origin/", "refs/remotes/", "refs/tags/"):
        if ref.startswith(prefix):
            return ref[len(prefix):]
    return ref


def parse_reflog(output: str) -> list[dict]:
    """Líneas `%gd<SEP>%gs` (con --date=iso-strict), de la más nueva a la más vieja.

    Devuelve las entradas en orden cronológico con la operación normalizada."""
    entries = []
    for line in output.splitlines():
        if SEP not in line:
            continue
        selector, subject = line.split(SEP, 1)
        if "@{" not in selector:
            continue
        ts = selector.split("@{", 1)[1].rstrip("}")
        entries.append({"ts": ts, "subject": subject, "op": reflog_op(subject)})
    entries.reverse()
    return entries


def reflog_op(subject: str) -> str:
    """'commit (amend): x' → 'amend'; 'rebase -i (pick): x' → 'rebase'; 'checkout: ...' → 'checkout'."""
    head = subject.split(":", 1)[0].strip()
    if head == "commit (amend)":
        return "amend"
    if head.startswith("rebase"):
        return "rebase"
    word = head.split(" ", 1)[0].lower()
    return word or "otro"


def initial_branch(entries: list[dict], current: str | None) -> str | None:
    """Branch anterior a la primera entrada: el origen del primer checkout o, si no hay
    ninguno, la branch actual de HEAD."""
    for e in entries:
        m = CHECKOUT_RX.match(e["subject"])
        if m:
            return DETACHED if SHA_RX.match(m.group(1)) else m.group(1)
    return current


def track_branches(entries: list[dict], initial: str | None = None) -> None:
    """Asigna a cada entrada la branch en la que ocurrió.

    Durante un rebase, HEAD queda detached pero el trabajo es de la branch que se rebasea,
    así que se conserva la branch previa hasta el `returning to refs/heads/X` final."""
    branch = initial
    in_rebase = False
    for e in entries:
        subj, op = e["subject"], e["op"]
        m = CHECKOUT_RX.match(subj)
        if op == "rebase":
            if "(start)" in subj:
                in_rebase = True
            r = RETURNING_RX.search(subj)
            if r:
                branch, in_rebase = r.group(1), False
            elif "(abort)" in subj or "(finish)" in subj:
                in_rebase = False
        elif m and not in_rebase:
            target = m.group(2)
            e["branch_before"] = branch
            branch = DETACHED if SHA_RX.match(target) else target
        e["branch"] = branch or DETACHED


def sessions(entries: list[dict], gap_minutes: int, tz) -> list[dict]:
    """Agrupa entradas (ya filtradas al día) por branch y huecos de inactividad."""
    out: list[dict] = []
    for e in entries:
        ts = common.parse_iso(e["ts"]).astimezone(tz)
        cur = out[-1] if out else None
        if cur and cur["branch"] == e["branch"] and (ts - cur["end"]).total_seconds() <= gap_minutes * 60:
            cur["end"] = ts
            cur["ops"][e["op"]] = cur["ops"].get(e["op"], 0) + 1
        else:
            out.append({"start": ts, "end": ts, "branch": e["branch"], "ops": {e["op"]: 1}})
    return out


def collect(cfg: dict, env: dict, day: date) -> dict:
    tz = common.get_tz(cfg)
    src = cfg["sources"]["git_local"]
    emails = cfg["identity"]["git_emails"]
    if not emails:
        return {"source": SOURCE, "status": "error", "message": "identity.git_emails vacío", "events": []}
    key_rx = common.issue_key_regex(list(cfg["projects"]))
    d_start, d_end = common.day_bounds(day, tz)
    since, until = d_start.isoformat(), d_end.isoformat()

    repos = discover_repos(src["roots"], src["max_depth"])
    extra = linked_worktrees(repos, src["roots"])
    repos += list(extra)
    events: list[dict] = []
    seen_shas: set[str] = set()
    messages: list[str] = []
    author_args = [f"--author={e}" for e in emails]
    for repo in repos:
        label = extra.get(repo) or repo_label(repo, src["roots"])
        path_keys = common.find_issue_keys(label, key_rx)
        try:
            log = run_git(repo, "log", "--all", "--source", f"--since={since}", f"--until={until}",
                          *author_args, f"--format=%H{SEP}%aI{SEP}%cI{SEP}%S{SEP}%s")
            reflog = run_git(repo, "reflog", "show", "--date=iso-strict", f"--format=%gd{SEP}%gs", "HEAD", "-n", REFLOG_LIMIT)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            messages.append(f"{label}: {e}")
            continue

        for c in parse_log(log):
            if c["sha"] in seen_shas:
                continue
            seen_shas.add(c["sha"])
            ts = common.parse_iso(c["commit_date"]).astimezone(tz)
            if not d_start <= ts < d_end:
                continue
            branch = clean_ref(c["source"])
            keys = common.find_issue_keys(f"{c['subject']} {branch}", key_rx) or path_keys
            rewritten = common.parse_iso(c["author_date"]) < d_start
            kind, weight = ("reescrito (amend/rebase)", "normal") if rewritten else ("commit", "strong")
            events.append(common.Event(
                SOURCE, ts.isoformat(), ts.isoformat(), f"{kind} {c['sha'][:7]} en {label}: {c['subject']}",
                "", {"repo": label, "branch": branch, "issue_keys": keys}, weight,
                id=common.make_event_id(SOURCE, c["sha"]),
            ).to_dict())

        entries = parse_reflog(reflog)
        try:
            current = run_git(repo, "symbolic-ref", "--short", "-q", "HEAD").strip() or None
        except RuntimeError:
            current = None
        track_branches(entries, initial_branch(entries, current))
        today = [e for e in entries if d_start <= common.parse_iso(e["ts"]) < d_end]
        for ses in sessions(today, src["session_gap_minutes"], tz):
            n_ops = sum(ses["ops"].values())
            ops_s = ", ".join(f"{n} {op}" for op, n in sorted(ses["ops"].items(), key=lambda kv: -kv[1]))
            keys = common.find_issue_keys(ses["branch"], key_rx) or path_keys
            events.append(common.Event(
                SOURCE, ses["start"].isoformat(), ses["end"].isoformat(),
                f"actividad git en {label} ({ses['branch']}): {n_ops} operaciones", ops_s,
                {"repo": label, "branch": ses["branch"] if ses["branch"] != DETACHED else "", "issue_keys": keys},
                "weak", id=common.make_event_id(SOURCE, label, ses["start"].isoformat()),
            ).to_dict())

    return {
        "source": SOURCE,
        "status": "partial" if messages else "ok",
        "messages": messages,
        "repos_scanned": len(repos),
        "events": sorted(events, key=lambda e: e["start"]),
    }


if __name__ == "__main__":
    sys.exit(common.collector_main(collect, __doc__))
