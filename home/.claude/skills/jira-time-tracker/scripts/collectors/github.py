#!/usr/bin/env python3
"""Colector GitHub vía `gh` (solo lectura).

Toma los eventos del usuario (push, branches, PRs, reviews y comentarios) del día.
Con `sources.github.only_orgs` (default) solo cuenta repos de `identity.github_orgs`;
los personales y los de otros usuarios se descartan.
El payload de PullRequestEvent viene recortado, así que el título de cada PR se pide
aparte (una vez por PR).

Uso: python scripts/collectors/github.py [--date AAAA-MM-DD]
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import common  # noqa: E402

SOURCE = "gh"
MAX_PAGES = 3


def gh_api(path: str) -> Any:
    proc = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip()[:300])
    return json.loads(proc.stdout or "null")


def _ref(ref: str | None) -> str:
    return (ref or "").removeprefix("refs/heads/")


def _excerpt(body: str | None, n: int = 200) -> str:
    return " ".join((body or "").split())[:n]


def event_to_dict(ev: dict, tz, key_rx, pr_title: Callable[[str, int], dict]) -> dict | None:
    t, repo, p = ev.get("type"), ev["repo"]["name"], ev.get("payload") or {}
    ts = common.parse_iso(ev["created_at"]).astimezone(tz).isoformat()
    hints: dict[str, Any] = {"repo": repo}
    weight, detail = "normal", ""

    if t == "PushEvent":
        branch = _ref(p.get("ref"))
        title, weight = f"push a {repo}:{branch}", "weak"
        hints["branch"] = branch
    elif t in ("CreateEvent", "DeleteEvent"):
        if p.get("ref_type") != "branch":
            return None
        verb = "creó" if t == "CreateEvent" else "borró"
        title, weight = f"{verb} branch {repo}:{p.get('ref')}", "weak"
        hints["branch"] = p.get("ref")
    elif t in ("PullRequestEvent", "PullRequestReviewEvent", "PullRequestReviewCommentEvent"):
        pr = p.get("pull_request") or {}
        number = p.get("number") or pr.get("number")
        info = pr_title(repo, number) if number else {}
        pr_name = f"PR #{number} {info.get('title') or pr.get('title') or ''}".strip()
        hints["branch"] = (pr.get("head") or {}).get("ref") or info.get("branch")
        hints["url"] = info.get("url") or pr.get("html_url")
        hints["pr_author"] = info.get("author")
        if t == "PullRequestEvent":
            title = f"{p.get('action')} {pr_name} en {repo}"
        elif t == "PullRequestReviewEvent":
            review = p.get("review") or {}
            title = f"review ({review.get('state', '').lower()}) de {pr_name} en {repo}"
            detail = _excerpt(review.get("body"))
        else:
            title = f"comentario de review en {pr_name} en {repo}"
            detail = _excerpt((p.get("comment") or {}).get("body"))
        weight = "strong"
    elif t == "IssueCommentEvent":
        issue = p.get("issue") or {}
        kind = "PR" if issue.get("pull_request") else "issue"
        title = f"comentario en {kind} #{issue.get('number')} {issue.get('title', '')} en {repo}".strip()
        detail = _excerpt((p.get("comment") or {}).get("body"))
        hints["url"] = issue.get("html_url")
        weight = "strong"
    elif t == "IssuesEvent":
        issue = p.get("issue") or {}
        title = f"{p.get('action')} issue #{issue.get('number')} {issue.get('title', '')} en {repo}".strip()
        hints["url"] = issue.get("html_url")
    else:
        return None

    hints["issue_keys"] = common.find_issue_keys(f"{title} {hints.get('branch') or ''} {detail}", key_rx)
    return common.Event(SOURCE, ts, ts, title, detail, hints, weight,
                        id=common.make_event_id(SOURCE, ev.get("id"), ts)).to_dict()


def collect(cfg: dict, env: dict, day: date, api: Callable[[str], Any] = gh_api) -> dict:
    tz = common.get_tz(cfg)
    user = cfg["identity"].get("github_user")
    if not user:
        return {"source": SOURCE, "status": "error", "message": "falta identity.github_user", "events": []}
    key_rx = common.issue_key_regex(list(cfg["projects"]))
    d_start, d_end = common.day_bounds(day, tz)

    cache: dict[tuple[str, int], dict] = {}

    def pr_title(repo: str, number: int) -> dict:
        if (repo, number) not in cache:
            try:
                pr = api(f"/repos/{repo}/pulls/{number}")
                cache[(repo, number)] = {"title": pr.get("title"), "branch": (pr.get("head") or {}).get("ref"),
                                         "url": pr.get("html_url"), "author": (pr.get("user") or {}).get("login")}
            except RuntimeError:
                cache[(repo, number)] = {}
        return cache[(repo, number)]

    raw: list[dict] = []
    try:
        for page in range(1, MAX_PAGES + 1):
            batch = api(f"/users/{user}/events?per_page=100&page={page}") or []
            raw += batch
            oldest = min((common.parse_iso(e["created_at"]) for e in batch), default=None)
            if len(batch) < 100 or (oldest and oldest < d_start):
                break
    except RuntimeError as e:
        return {"source": SOURCE, "status": "error", "message": str(e), "events": []}

    orgs = {o.lower() for o in cfg["identity"].get("github_orgs") or []}
    only_orgs = cfg["sources"]["github"].get("only_orgs", True)
    messages = []
    if only_orgs and not orgs:
        messages.append("only_orgs activo pero identity.github_orgs está vacío: no se filtra por organización")
    skipped: set[str] = set()

    events = []
    for ev in raw:
        if not d_start <= common.parse_iso(ev["created_at"]) < d_end:
            continue
        owner = ev["repo"]["name"].split("/", 1)[0].lower()
        if only_orgs and orgs and owner not in orgs:
            skipped.add(ev["repo"]["name"])
            continue
        d = event_to_dict(ev, tz, key_rx, pr_title)
        if d:
            events.append(d)
    if skipped:
        messages.append("repos fuera de las organizaciones, ignorados: " + ", ".join(sorted(skipped)))
    return {"source": SOURCE, "status": "ok", "messages": messages,
            "events": sorted(events, key=lambda e: e["start"])}


if __name__ == "__main__":
    sys.exit(common.collector_main(collect, __doc__))
