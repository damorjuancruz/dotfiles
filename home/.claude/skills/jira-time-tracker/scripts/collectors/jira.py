#!/usr/bin/env python3
"""Colector Jira (REST, solo lectura).

Trae del día:
  - worklogs del usuario en cualquier proyecto (paginados, sin el límite de 20 del MCP);
  - comentarios y cambios (transiciones, asignaciones) hechos por el usuario → eventos;
  - incidencias candidatas con datos mínimos.

Uso: python scripts/collectors/jira.py [--date AAAA-MM-DD] [--keys SIT-1,SAI-2]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import common  # noqa: E402

SOURCE = "jira"
FIELDS = ["summary", "status", "assignee", "reporter", "creator", "parent", "issuetype", "project", "description"]
DESCRIPTION_CHARS = 200
CATEGORY_NAMES = {"new": "To Do", "indeterminate": "In Progress", "done": "Done"}


class JiraClient:
    def __init__(self, site: str, email: str, token: str, http: Callable[..., Any] = common.http_json):
        self.base = site.rstrip("/")
        self.headers = common.basic_auth(email, token)
        self.http = http

    def get(self, path: str, params: dict | None = None) -> Any:
        return self.http(self.base + path, headers=self.headers, params=params)

    def post(self, path: str, body: dict) -> Any:
        # POST de búsqueda: no modifica nada en Jira.
        return self.http(self.base + path, method="POST", headers=self.headers, body=body)

    def search(self, jql: str, fields: list[str], limit: int = 500) -> list[dict]:
        issues: list[dict] = []
        token = None
        while True:
            body: dict[str, Any] = {"jql": jql, "fields": fields, "maxResults": 100}
            if token:
                body["nextPageToken"] = token
            data = self.post("/rest/api/3/search/jql", body)
            issues += data.get("issues", [])
            token = data.get("nextPageToken")
            if not token or data.get("isLast") or len(issues) >= limit:
                return issues[:limit]

    def paged(self, path: str, key: str, params: dict | None = None) -> list[dict]:
        out: list[dict] = []
        start = 0
        while True:
            data = self.get(path, {**(params or {}), "startAt": start, "maxResults": 100})
            items = data.get(key, [])
            out += items
            start += len(items)
            if not items or start >= data.get("total", 0) or data.get("isLast"):
                return out


# --------------------------------------------------------------------------- helpers


def adf_to_text(node: Any) -> str:
    """Texto plano aproximado de un documento ADF."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(adf_to_text(n) for n in node)
    t = node.get("type")
    if t == "text":
        return node.get("text", "")
    if t == "hardBreak":
        return "\n"
    if t == "mention":
        return node.get("attrs", {}).get("text", "")
    inner = adf_to_text(node.get("content", []))
    return inner + "\n" if t in ("paragraph", "heading", "listItem") else inner


def _q(values: list[str]) -> str:
    return ", ".join(json.dumps(v, ensure_ascii=False) for v in values)


def assigned_jql(cfg: dict) -> str:
    clauses = []
    for key, proj in cfg["projects"].items():
        parts = [f"project = {key}"]
        if proj["excluded_status_categories"]:
            parts.append(f"statusCategory not in ({_q(proj['excluded_status_categories'])})")
        if proj["excluded_statuses"]:
            parts.append(f"status not in ({_q(proj['excluded_statuses'])})")
        clauses.append("(" + " AND ".join(parts) + ")")
    return "assignee = currentUser() AND (" + " OR ".join(clauses) + ")"


def recent_jql(cfg: dict, account_id: str) -> str:
    days = cfg["rules"]["candidates_lookback_days"]
    projects = ", ".join(cfg["projects"])
    # updatedBy() exige el accountId literal: no acepta currentUser().
    return (f'project in ({projects}) AND (issuekey in updatedBy("{account_id}", "-{days}d") '
            f'OR worklogAuthor = currentUser() AND worklogDate >= "-{days}d")')


def candidate_from_issue(issue: dict, account_id: str, origin: str) -> dict:
    f = issue.get("fields", {})
    status = f.get("status") or {}
    cat = (status.get("statusCategory") or {}).get("key")
    assignee = f.get("assignee") or {}
    parent = f.get("parent") or {}
    return {
        "key": issue["key"],
        "summary": f.get("summary", ""),
        "type": (f.get("issuetype") or {}).get("name"),
        "status": status.get("name"),
        "status_category": CATEGORY_NAMES.get(cat, cat),
        "assignee": assignee.get("displayName"),
        "assignee_me": assignee.get("accountId") == account_id,
        "reporter": (f.get("reporter") or {}).get("displayName"),
        "creator": (f.get("creator") or {}).get("displayName"),
        "description": " ".join(adf_to_text(f.get("description")).split())[:DESCRIPTION_CHARS],
        "parent": parent.get("key"),
        "origin": [origin],
    }


def _merge_candidates(target: dict[str, dict], issues: list[dict], account_id: str, origin: str) -> None:
    for issue in issues:
        c = candidate_from_issue(issue, account_id, origin)
        if c["key"] in target:
            if origin not in target[c["key"]]["origin"]:
                target[c["key"]]["origin"].append(origin)
        else:
            target[c["key"]] = c


def fetch_candidates(client: JiraClient, cfg: dict, account_id: str, extra_keys: list[str] = ()) -> list[dict]:
    cands: dict[str, dict] = {}
    _merge_candidates(cands, client.search(assigned_jql(cfg), FIELDS), account_id, "assigned")
    _merge_candidates(cands, client.search(recent_jql(cfg, account_id), FIELDS), account_id, "recent")
    misc = cfg["misc_issues"]
    misc_keys = [k for k in [misc.get("parent"), *misc.get("subtasks", {}).values()] if k]
    if misc_keys:
        _merge_candidates(cands, client.search(f"issuekey in ({', '.join(misc_keys)})", FIELDS), account_id, "misc")
    extra = [k for k in extra_keys if k not in cands]
    for c in fetch_issues_by_keys(client, extra, account_id):
        cands[c["key"]] = c
    return sorted(cands.values(), key=lambda c: (not c["assignee_me"], c["key"]))


def fetch_issues_by_keys(client: JiraClient, keys: list[str], account_id: str) -> list[dict]:
    """Segunda pasada de collect.py: keys mencionadas por otras fuentes que no eran candidatas.

    Busca de a una porque `issuekey in (...)` falla entero si alguna key no existe."""
    out: dict[str, dict] = {}
    for k in keys:
        try:
            _merge_candidates(out, client.search(f"issuekey = {k}", FIELDS), account_id, "mentioned")
        except common.HttpError:
            continue
    return list(out.values())


def _in_day(ts: str, start: datetime, end: datetime) -> bool:
    return start <= common.parse_iso(ts) < end


def fetch_worklogs(client: JiraClient, day: date, tz, account_id: str) -> list[dict]:
    d_start, d_end = common.day_bounds(day, tz)
    issues = client.search(f'worklogAuthor = currentUser() AND worklogDate = "{day.isoformat()}"', ["summary"])
    out = []
    params = {"startedAfter": int(d_start.timestamp() * 1000) - 1, "startedBefore": int(d_end.timestamp() * 1000)}
    for issue in issues:
        for w in client.paged(f"/rest/api/3/issue/{issue['key']}/worklog", "worklogs", params):
            if (w.get("author") or {}).get("accountId") != account_id or not _in_day(w["started"], d_start, d_end):
                continue
            started = common.parse_iso(w["started"]).astimezone(tz)
            out.append({
                "id": str(w["id"]),
                "issue": issue["key"],
                "summary": issue["fields"].get("summary", ""),
                "started": started.isoformat(),
                "minutes": round(int(w.get("timeSpentSeconds", 0)) / 60),
                "comment": " ".join(adf_to_text(w.get("comment")).split()),
            })
    return sorted(out, key=lambda w: w["started"])


def fetch_activity(client: JiraClient, day: date, tz, account_id: str) -> list[dict]:
    """Comentarios y cambios del usuario en el día → eventos."""
    d_start, d_end = common.day_bounds(day, tz)
    nxt = day + timedelta(days=1)
    jql = f'issuekey in updatedBy("{account_id}", "{day.isoformat()}", "{nxt.isoformat()}")'
    events: list[dict] = []
    for issue in client.search(jql, ["summary"]):
        key, summary = issue["key"], issue["fields"].get("summary", "")
        for c in client.paged(f"/rest/api/3/issue/{key}/comment", "comments"):
            if (c.get("author") or {}).get("accountId") != account_id or not _in_day(c["created"], d_start, d_end):
                continue
            ts = common.parse_iso(c["created"]).astimezone(tz).isoformat()
            text = " ".join(adf_to_text(c.get("body")).split())
            events.append(common.Event(SOURCE, ts, ts, f"comentario en {key}: {summary}", text[:300],
                                       {"issue_keys": [key]}, "strong").to_dict())
        for h in client.paged(f"/rest/api/3/issue/{key}/changelog", "values"):
            if (h.get("author") or {}).get("accountId") != account_id or not _in_day(h["created"], d_start, d_end):
                continue
            ts = common.parse_iso(h["created"]).astimezone(tz).isoformat()
            changes = [f"{i.get('field')}: {i.get('fromString') or '∅'} → {i.get('toString') or '∅'}"
                       for i in h.get("items", []) if i.get("field") not in ("WorklogId", "timespent", "timeestimate", "RemainingEstimate", "worklogId")]
            if not changes:
                continue
            events.append(common.Event(SOURCE, ts, ts, f"cambio en {key}: {summary}", "; ".join(changes)[:300],
                                       {"issue_keys": [key]}, "strong").to_dict())
    return sorted(events, key=lambda e: e["start"])


def transition_fields(t: dict) -> list[dict]:
    """Campos que pide la pantalla de una transición: los obligatorios y `resolution`."""
    out = []
    for key, f in (t.get("fields") or {}).items():
        if not (f.get("required") or key == "resolution"):
            continue
        allowed = [v.get("name") or v.get("value") for v in f.get("allowedValues") or []]
        out.append({"key": key, "name": f.get("name", key), "required": bool(f.get("required")),
                    "allowed": [a for a in allowed if a]})
    return out


def fetch_issue_meta(client: JiraClient, keys: list[str]) -> dict[str, dict]:
    """Estado actual y transiciones disponibles de cada incidencia.

    Jira solo devuelve las transiciones que el usuario puede ejecutar (permisos y condiciones
    del workflow). Una key que falla queda con `error` y no corta el resto."""
    out: dict[str, dict] = {}
    for k in keys:
        try:
            issue = client.get(f"/rest/api/3/issue/{k}", {"fields": "summary,status"})
            trans = client.get(f"/rest/api/3/issue/{k}/transitions", {"expand": "transitions.fields"})
        except (common.HttpError, OSError) as e:
            out[k] = {"error": str(e)[:200]}
            continue
        f = issue.get("fields", {})
        status = f.get("status") or {}
        out[k] = {
            "summary": f.get("summary", ""),
            "status": status.get("name"),
            "status_category": CATEGORY_NAMES.get((status.get("statusCategory") or {}).get("key")),
            "transitions": [{"id": str(t["id"]), "name": t.get("name"), "to": (t.get("to") or {}).get("name"),
                             "fields": transition_fields(t)} for t in trans.get("transitions", [])],
        }
    return out


# --------------------------------------------------------------------------- entrada


def collect(cfg: dict, env: dict, day: date, extra_keys: list[str] = (), client: JiraClient | None = None) -> dict:
    tz = common.get_tz(cfg)
    if client is None:
        token = env.get("JIRA_API_TOKEN")
        if not token:
            return {"source": SOURCE, "status": "error", "message": "falta JIRA_API_TOKEN en .env", "events": []}
        client = JiraClient(cfg["jira"]["site"], cfg["jira"]["email"], token)
    try:
        me = client.get("/rest/api/3/myself")
        account_id = me["accountId"]
        return {
            "source": SOURCE,
            "status": "ok",
            "account_id": account_id,
            "worklogs": fetch_worklogs(client, day, tz, account_id),
            "candidates": fetch_candidates(client, cfg, account_id, extra_keys),
            "events": fetch_activity(client, day, tz, account_id),
        }
    except (common.HttpError, OSError, KeyError) as e:
        return {"source": SOURCE, "status": "error", "message": str(e)[:500], "events": []}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date")
    ap.add_argument("--keys", default="", help="keys extra a incluir como candidatas")
    args = ap.parse_args()
    cfg = common.load_config()
    day = common.parse_day(args.date, common.get_tz(cfg))
    keys = [k.strip().upper() for k in args.keys.split(",") if k.strip()]
    result = collect(cfg, common.load_env(), day, keys)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
