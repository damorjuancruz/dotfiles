"""Sugerencias de cambio de estado para las incidencias que ya existen y tienen horas en el día.

No mira la actividad de los días siguientes: consulta el estado actual, que ya la refleja.
  - Vínculos de cada incidencia (`links_from_blocks`): las branches y los PRs de los eventos que
    el plan usa como evidencia de sus bloques. Es la asignación que ya hizo el agente, así que
    funciona aunque las branches y los PRs no mencionen la key.
  - PRs (GitHub): los de esos eventos, los abiertos desde esas branches y los que mencionan la
    key en las orgs configuradas. Solo cuentan los del usuario (`identity.github_user`) o los
    que nombran la key: revisar el PR de otra persona no dice nada del estado de la incidencia.
  - Último commit propio posterior al día en esas branches, o con la key en el mensaje.
  - Último worklog de la incidencia y estado de sus subtareas (lo trae jira.fetch_issue_meta).

Regla (`suggest`):
  - Ya resuelta → nada (con aviso: la carga de horas puede fallar si el workflow la bloquea).
  - Terminada (PR mergeado y ninguno abierto, o todas las subtareas resueltas) → "resolver", pero solo si el día
    que se carga es el último con actividad conocida (merge, commits, worklogs). Si hubo
    actividad después, queda una nota y la resolución se sugiere al cargar ese día.
  - PR abierto (no borrador) → pasar a revisión.
  - "Por hacer" con horas en el día → pasar a en curso.
Siempre es una sugerencia: la página la muestra como aviso y el usuario decide.
"""

from __future__ import annotations

import re
import subprocess
import urllib.parse
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from lib import common

DONE_RX = re.compile(r"resuel|resolv|done|finaliz|termin|cerr|clos|complet|listo|hecho", re.I)
REVIEW_RX = re.compile(r"revis|review|qa\b|test|prueba|valida", re.I)
PROGRESS_RX = re.compile(r"curso|progres|desarroll|trabaj|start|inici", re.I)
RESOLUTION_RX = re.compile(r"listo|hecho|done|fixed|resuel|finaliz|complet", re.I)
PR_URL_RX = re.compile(r"github\.com/([^/\s]+/[^/\s#]+)/pull/(\d+)")
BASE_BRANCHES = {"main", "master", "develop", "dev", "staging", "production", "release", "HEAD"}


# --------------------------------------------------------------------------- vínculos


def links_from_blocks(blocks: Iterable[tuple[str, list[str]]], events: dict[str, dict]) -> dict[str, dict]:
    """{key: {"prs": [(repo, n)], "branches": [(repo, branch)]}} a partir de los bloques del plan
    (incidencia, ids de evidencia) y los eventos crudos del día."""
    out: dict[str, dict] = {}
    for key, evidence in blocks:
        link = out.setdefault(key, {"prs": [], "branches": []})
        for eid in evidence:
            h = (events.get(eid) or {}).get("hints") or {}
            # Solo PRs de eventos propios de GitHub: una visita en Chrome no vincula el PR.
            m = PR_URL_RX.search(h.get("url") or "")
            if m and (m.group(1), int(m.group(2))) not in link["prs"]:
                link["prs"].append((m.group(1), int(m.group(2))))
            branch, repo = h.get("branch"), h.get("repo")
            if branch and repo and branch not in BASE_BRANCHES and (repo, branch) not in link["branches"]:
                link["branches"].append((repo, branch))
    return out


def _full_names(repo: str, orgs: list[str]) -> list[str]:
    """Nombres de GitHub posibles de un repo: tal cual si ya es org/repo; si es una etiqueta local
    (`grainvision-web` o `grainvision-web@t3-1`), con cada org configurada."""
    if "/" in repo and not repo.startswith(("/", "~")):
        return [repo]
    name = Path(repo.split("@", 1)[0]).name
    return [f"{o}/{name}" for o in orgs]


# --------------------------------------------------------------------------- señales


def _pr(item: dict, repo: str) -> dict:
    pr = item.get("pull_request") or {}
    merged = pr.get("merged_at") or item.get("merged_at")
    state = "merged" if merged else item.get("state", "open")
    return {"repo": repo, "number": item.get("number"), "title": item.get("title", ""), "state": state,
            "draft": bool(item.get("draft")), "merged_at": merged, "url": item.get("html_url"),
            "author": (item.get("user") or {}).get("login")}


def find_prs(cfg: dict, key: str, link: dict, api: Callable[[str], Any]) -> list[dict]:
    """PRs de la incidencia: los que mencionan la key, más los de la evidencia y sus branches
    (solo si son del usuario)."""
    found: dict[tuple[str, int], dict] = {}
    orgs = cfg["identity"].get("github_orgs") or []
    me = (cfg["identity"].get("github_user") or "").lower()

    def call(path: str) -> Any:
        try:
            return api(path)
        except RuntimeError:
            return None

    q = " ".join([key, "is:pr", *(f"org:{o}" for o in orgs)])
    rx = re.compile(rf"\b{re.escape(key)}\b", re.I)
    for it in (call(f"/search/issues?per_page=20&q={urllib.parse.quote(q)}") or {}).get("items", []):
        if rx.search(f"{it.get('title', '')} {it.get('body') or ''}"):
            repo = "/".join((it.get("repository_url") or "").split("/")[-2:])
            found[(repo, it["number"])] = _pr(it, repo)

    def mine(p: dict) -> bool:
        return not me or (p.get("author") or "").lower() == me

    for repo, n in link.get("prs", []):
        if (repo, n) not in found:
            item = call(f"/repos/{repo}/pulls/{n}")
            if item and mine(_pr(item, repo)):
                found[(repo, n)] = _pr(item, repo)
    for repo, branch in link.get("branches", []):
        for full in _full_names(repo, orgs):
            owner = full.split("/", 1)[0]
            head = urllib.parse.quote(f"{owner}:{branch}")
            items = call(f"/repos/{full}/pulls?state=all&per_page=5&head={head}") or []
            for item in items:
                p = _pr(item, full)
                if (full, p["number"]) not in found and mine(p):
                    found[(full, p["number"])] = p
            if items:
                break
    return list(found.values())


def last_commit(repos: dict[str, Path], key: str, branches: list[tuple[str, str]], since: datetime,
                emails: list[str]) -> str | None:
    """Fecha ISO del último commit propio desde `since` en las branches vinculadas, o con la key
    en el mensaje. `repos` es {etiqueta local: ruta}."""
    authors = [f"--author={e}" for e in emails]
    best: datetime | None = None

    def git(repo: Path, *args: str) -> str:
        try:
            p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=30)
            return p.stdout if p.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            return ""

    by_repo: dict[Path, list[str]] = {}
    for repo, branch in branches:
        name = Path(repo.split("@", 1)[0]).name
        for label, path in repos.items():
            if Path(label.split("@", 1)[0]).name == name:
                by_repo.setdefault(path, []).append(branch)
    for path in repos.values():
        out = git(path, "log", "--all", f"--since={since.isoformat()}", "-i", f"--grep={key}", *authors, "--format=%cI")
        refs = []
        for b in by_repo.get(path, []):
            refs += [r for r in (f"refs/heads/{b}", f"refs/remotes/origin/{b}")
                     if git(path, "rev-parse", "--verify", "--quiet", r).strip()]
        if refs:
            out += git(path, "log", *refs, f"--since={since.isoformat()}", *authors, "--format=%cI")
        for line in out.split():
            dt = common.parse_iso(line)
            if best is None or dt > best:
                best = dt
    return best.isoformat() if best else None


def gather(cfg: dict, keys: list[str], day: date, links: dict[str, dict],
           api: Callable[[str], Any] | None = None, repos: dict[str, Path] | None = None) -> dict[str, dict]:
    """{key: {"prs": [...], "last_commit": iso | None}} para las keys dadas."""
    from collectors import git_local, github  # import tardío: lib no depende de los colectores

    api = api or github.gh_api
    if repos is None:
        src = cfg["sources"]["git_local"]
        found = git_local.discover_repos(src["roots"], src["max_depth"]) if src.get("enabled") else []
        extra = git_local.linked_worktrees(found, src["roots"]) if found else {}
        repos = {git_local.repo_label(r, src["roots"]): r for r in found}
        repos.update({label: r for r, label in extra.items()})
    _, d_end = common.day_bounds(day, common.get_tz(cfg))
    gh_on = cfg["sources"]["github"].get("enabled")
    out = {}
    for k in keys:
        link = links.get(k) or {}
        out[k] = {
            "prs": find_prs(cfg, k, link, api) if gh_on else [],
            "last_commit": last_commit(repos, k, link.get("branches", []), d_end,
                                       cfg["identity"].get("git_emails") or []),
            "branches": [f"{r}:{b}" for r, b in link.get("branches", [])],
        }
    return out


# --------------------------------------------------------------------------- regla


def _pick(transitions: list[dict], category: str | None, rx: re.Pattern | None) -> dict | None:
    """La transición que mejor encaja: por categoría destino y nombre; si no hay categoría, solo nombre."""
    pool = [t for t in transitions if category is None or t.get("to_category") == category]
    if rx:
        named = [t for t in pool if rx.search(f"{t.get('to') or ''} {t.get('name') or ''}")]
        if named:
            return named[0]
        if category is None:
            return None
    return pool[0] if pool else None


def _fields(t: dict) -> dict:
    out = {}
    for f in t.get("fields") or []:
        if f["key"] == "resolution" and f.get("allowed"):
            out["resolution"] = next((a for a in f["allowed"] if RESOLUTION_RX.search(a)), "")
    return {k: v for k, v in out.items() if v}


def _local_day(iso: str | None, tz) -> date | None:
    return common.parse_iso(iso).astimezone(tz).date() if iso else None


def suggest(meta: dict, sig: dict, day: date, tz) -> dict:
    """{"suggestion": {...} | None, "note": str | None} para una incidencia con horas en `day`."""
    if meta.get("error"):
        return {"suggestion": None, "note": None}
    cat = meta.get("category")
    if cat == "done":
        return {"suggestion": None,
                "note": f"ya está en «{meta.get('status')}»: si el workflow no deja cargar horas ahí, "
                        "reabrila o pasá las horas a otra incidencia"}
    transitions = meta.get("transitions") or []
    prs = sig.get("prs") or []
    merged = sorted((p for p in prs if p.get("merged_at")), key=lambda p: p["merged_at"])
    open_prs = [p for p in prs if p.get("state") == "open" and not p.get("draft")]
    subtasks = meta.get("subtasks") or []

    finished, finished_day = None, None
    if merged and not any(p.get("state") == "open" for p in prs):
        p = merged[-1]
        finished_day = _local_day(p["merged_at"], tz)
        finished = f"PR #{p['number']} mergeado el {finished_day:%d/%m}"
    elif subtasks and all(s.get("category") == "done" for s in subtasks):
        finished, finished_day = "todas las subtareas están resueltas", day

    note, target, reason = None, None, None
    if finished:
        later = {"commits": _local_day(sig.get("last_commit"), tz), "horas": _local_day(meta.get("last_worklog"), tz)}
        later = {k: v for k, v in later.items() if v and v > day}
        last = max([finished_day, *later.values()])
        if last <= day:
            target, reason = "done", finished
        else:
            what = (f"hay {' y '.join(f'{k} hasta el {v:%d/%m}' for k, v in later.items())}" if later
                    else "fue después de este día")
            note = f"{finished}; {what}: la resolución se sugiere al cargar el {last:%d/%m}"
    if not target and open_prs and not (meta.get("status") and REVIEW_RX.search(meta["status"])):
        p = open_prs[-1]
        if _pick(transitions, None, REVIEW_RX):
            target, reason = "review", f"PR #{p['number']} abierto"
    if not target and cat == "new":
        target, reason = "progress", "tiene horas en este día y sigue sin empezar"

    t = None
    if target == "done":
        t = _pick(transitions, "done", DONE_RX)
    elif target == "review":
        t = _pick(transitions, None, REVIEW_RX)
    elif target == "progress":
        t = _pick([x for x in transitions if not REVIEW_RX.search(f"{x.get('to') or ''} {x.get('name') or ''}")],
                  "indeterminate", PROGRESS_RX)
    if target and not t:
        note = "; ".join(filter(None, [note, f"{reason}, pero ninguna transición disponible lo refleja"]))
    sugg = {"transition_id": t["id"], "transition": t["name"], "to": t["to"], "fields": _fields(t),
            "reason": reason, "by": "script"} if t else None
    return {"suggestion": sugg, "note": note}
