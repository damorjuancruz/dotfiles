"""Carga en Jira de lo que el usuario aprobó en la página (`plan.py load`).

Hace, en orden: crear las incidencias nuevas con decisión "crear", cargar los worklogs de la
variante elegida, y aplicar las transiciones y comentarios de resolución de seguimiento. Usa la
API REST de Jira con JIRA_API_TOKEN, sin pasar por el modelo.

Cada paso se anota en <state>/load_log.json con su resultado. Si un paso falla, la carga para
ahí y el reporte dice qué se hizo y qué no. Al volver a correr, los pasos ya hechos se saltean:
el agente corrige la causa (un campo, un permiso, un estado) y retoma desde donde quedó.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from lib import common

LOG = "load_log.json"
BULLET_RX = re.compile(r"^\s*[-*•]\s+")


# --------------------------------------------------------------------------- texto → ADF


def text_to_adf(text: str) -> dict:
    """Texto plano a Atlassian Document Format: un párrafo por línea, y las líneas seguidas que
    empiezan con «- » van como lista."""
    content: list[dict] = []
    bullets: list[dict] = []

    def flush() -> None:
        if bullets:
            content.append({"type": "bulletList", "content": list(bullets)})
            bullets.clear()

    for line in str(text or "").splitlines():
        if not line.strip():
            flush()
            continue
        if BULLET_RX.match(line):
            item = BULLET_RX.sub("", line).strip()
            bullets.append({"type": "listItem", "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": item}]}]})
        else:
            flush()
            content.append({"type": "paragraph", "content": [{"type": "text", "text": line.strip()}]})
    flush()
    return {"type": "doc", "version": 1, "content": content}


# --------------------------------------------------------------------------- cliente


class Writer:
    """Escrituras en Jira (el JiraClient de los colectores solo lee)."""

    def __init__(self, site: str, email: str, token: str, http: Callable[..., Any] = common.http_json):
        self.base = site.rstrip("/")
        self.headers = common.basic_auth(email, token)
        self.http = http

    def get(self, path: str, params: dict | None = None) -> Any:
        return self.http(self.base + path, headers=self.headers, params=params)

    def send(self, method: str, path: str, body: dict | None = None, params: dict | None = None) -> Any:
        return self.http(self.base + path, method=method, headers=self.headers, body=body, params=params)


# --------------------------------------------------------------------------- campos de incidencias nuevas


def find_user(w: Writer, name: str) -> str:
    """accountId de un usuario de Atlassian por nombre o email. Falla si no hay uno claro (o si
    solo aparecen clientes de Jira Service Management)."""
    users = [u for u in (w.get("/rest/api/3/user/search", {"query": name, "maxResults": 10}) or [])
             if u.get("accountType") == "atlassian" and u.get("active", True)]
    exact = [u for u in users if name.casefold() in (str(u.get("displayName", "")).casefold(),
                                                       str(u.get("emailAddress", "")).casefold())]
    pick = exact if exact else users
    if len(pick) != 1:
        names = ", ".join(u.get("displayName", "?") for u in users) or "ninguno"
        raise ValueError(f"no hay un usuario claro para {name!r} (encontrados: {names})")
    return pick[0]["accountId"]


def create_meta(w: Writer, project: str, issue_type: str) -> tuple[str, dict[str, dict]]:
    """Id del tipo de incidencia y esquema de sus campos ({key: field}) para crear en `project`."""
    types = (w.get(f"/rest/api/3/issue/createmeta/{project}/issuetypes", {"maxResults": 100}) or {})
    types = types.get("issueTypes") or types.get("values") or []
    t = next((x for x in types if str(x.get("name", "")).casefold() == issue_type.casefold()), None)
    if t is None:
        raise ValueError(f"el proyecto {project} no tiene el tipo {issue_type!r} "
                         f"({', '.join(x.get('name', '?') for x in types)})")
    data = w.get(f"/rest/api/3/issue/createmeta/{project}/issuetypes/{t['id']}", {"maxResults": 200}) or {}
    fields = data.get("fields") or data.get("values") or []
    return t["id"], {f.get("fieldId") or f.get("key"): f for f in fields}


def field_value(w: Writer, key: str, value: Any, meta: dict | None) -> Any:
    """Convierte el valor de la página al formato que pide Jira según el esquema del campo."""
    schema = (meta or {}).get("schema") or {}
    kind, items = schema.get("type"), schema.get("items")
    custom = str(schema.get("custom") or "")
    text = str(value).strip() if value is not None else ""
    if key == "description" or custom.endswith(":textarea"):
        return text_to_adf(text)
    if kind == "user" or key in ("reporter", "assignee"):
        return {"accountId": find_user(w, text)}
    if kind == "priority":
        return {"name": text}
    if kind == "option":
        return {"value": text}
    if kind == "number":
        return float(text)
    if kind == "array":
        parts = [x.strip() for x in text.split(",") if x.strip()]
        if items == "option":
            return [{"value": x} for x in parts]
        if items in ("component", "version"):
            return [{"name": x} for x in parts]
        return parts
    if kind in ("issuelink", "issuetype", "project"):
        return {"key": text} if kind != "issuetype" else {"name": text}
    return text


def issue_payload(w: Writer, ni: dict, account_id: str) -> dict:
    type_id, meta = create_meta(w, ni["project"], ni["type"])
    fields: dict[str, Any] = {"project": {"key": ni["project"]}, "issuetype": {"id": type_id},
                              "summary": ni["summary"], "assignee": {"accountId": account_id}}
    if ni.get("parent"):
        fields["parent"] = {"key": ni["parent"]}
    for f in ni.get("fields") or []:
        if f.get("key") in ("summary", "project", "issuetype", "parent") or f.get("value") in (None, ""):
            continue
        if f["key"] == "reporter" and str(f["value"]).strip().casefold() in ("yo", "me", ""):
            continue  # el informador por defecto es quien crea la incidencia
        fields[f["key"]] = field_value(w, f["key"], f["value"], meta.get(f["key"]))
    return {"fields": fields}


# --------------------------------------------------------------------------- pasos


def plan_steps(plan: dict, ops: list[dict] | None, followup_only: bool = False) -> list[dict]:
    """Lista ordenada de pasos: {id, kind, ...}. `ops` son las operaciones de worklog de
    `plan.ops` (None si todavía hay incidencias por crear: se calculan después)."""
    steps = []
    if not followup_only:
        for ni in plan.get("new_issues", []):
            if ni.get("decision") == "create":
                steps.append({"id": f"crear:{ni['ref']}", "kind": "create", "ref": ni["ref"]})
        for op in ops or []:
            steps.append({"id": f"worklog:{op['key']}:{op['issueIdOrKey']}", "kind": "worklog", "op": op})
    rnd = plan.get("round", 1)  # en el seguimiento puede haber varias rondas sobre la misma incidencia
    for key, f in (plan.get("followup") or {}).items():
        if f.get("transition_id"):
            steps.append({"id": f"transición:{key}:{f['transition_id']}:r{rnd}", "kind": "transition", "issue": key, "f": f})
        if f.get("publish") and (f.get("comment") or "").strip():
            steps.append({"id": f"comentario:{key}:r{rnd}", "kind": "comment", "issue": key, "text": f["comment"].strip()})
    return steps


def run_step(w: Writer, step: dict, plan: dict, account_id: str) -> dict:
    kind = step["kind"]
    if kind == "create":
        ni = next(x for x in plan.get("new_issues", []) if x.get("ref") == step["ref"])
        res = w.send("POST", "/rest/api/3/issue", issue_payload(w, ni, account_id))
        return {"key": res["key"]}
    if kind == "worklog":
        op = step["op"]
        minutes = op["minutes"]
        body: dict[str, Any] = {"started": op["started"], "timeSpentSeconds": minutes * 60}
        if op.get("commentBody"):
            body["comment"] = text_to_adf(op["commentBody"])
        if op["op"] == "update":
            res = w.send("PUT", f"/rest/api/3/issue/{op['issueIdOrKey']}/worklog/{op['worklogId']}", body,
                         {"adjustEstimate": "auto"})
        else:
            res = w.send("POST", f"/rest/api/3/issue/{op['issueIdOrKey']}/worklog", body, {"adjustEstimate": "auto"})
        return {"worklog_id": str((res or {}).get("id") or op.get("worklogId") or "")}
    if kind == "transition":
        f = step["f"]
        body = {"transition": {"id": str(f["transition_id"])}}
        extra = {k: ({"name": v} if k == "resolution" else v) for k, v in (f.get("fields") or {}).items() if v}
        if extra:
            body["fields"] = extra
        w.send("POST", f"/rest/api/3/issue/{step['issue']}/transitions", body)
        return {"to": f.get("to")}
    if kind == "comment":
        res = w.send("POST", f"/rest/api/3/issue/{step['issue']}/comment", {"body": text_to_adf(step["text"])})
        return {"comment_id": str((res or {}).get("id") or "")}
    raise ValueError(f"paso desconocido: {kind}")


def describe(step: dict) -> str:
    if step["kind"] == "worklog":
        op = step["op"]
        what = "ajuste" if op["op"] == "update" else "worklog"
        return f"{what} {op['issueIdOrKey']} {op['started'][11:16]} {common.fmt_duration(op['minutes'])}"
    if step["kind"] == "create":
        return f"crear {step['ref']}"
    if step["kind"] == "transition":
        return f"transición {step['issue']} → {step['f'].get('to') or step['f'].get('transition')}"
    return f"comentario de resolución en {step['issue']}"


def run(steps: list[dict], w: Writer, plan: dict, account_id: str, log_path: Path,
        on_created: Callable[[str, str], None] | None = None) -> tuple[list[str], bool]:
    """Ejecuta los pasos que no estén hechos en el log. Para en el primer error.
    Devuelve (líneas de reporte, True si terminó todo)."""
    log = common.read_json(log_path, {}) or {}
    done = log.setdefault("steps", {})
    out = []
    for step in steps:
        prev = done.get(step["id"])
        if prev and prev.get("status") == "ok":
            out.append(f"  = {describe(step)} (ya estaba hecho)")
            continue
        try:
            result = run_step(w, step, plan, account_id)
        except (common.HttpError, ValueError, KeyError) as e:
            done[step["id"]] = {"status": "error", "error": str(e)[:500], "at": datetime.now().isoformat(timespec="seconds")}
            common.write_json(log_path, log)
            out.append(f"  ✗ {describe(step)}: {str(e)[:300]}")
            return out, False
        done[step["id"]] = {"status": "ok", "result": result, "at": datetime.now().isoformat(timespec="seconds")}
        common.write_json(log_path, log)
        out.append(f"  ✓ {describe(step)}" + (f" → {result['key']}" if result.get("key") else ""))
        if step["kind"] == "create" and on_created:
            on_created(step["ref"], result["key"])
    return out, True
