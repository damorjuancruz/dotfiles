#!/usr/bin/env python3
"""Modo setup: chequeo de dependencias y descubrimiento de datos para armar config.json.

Uso:
  setup.py check                         dependencias, credenciales y conectividad
  setup.py discover [--projects SIT,SAI] propone un config.json a partir de lo que encuentra

`discover` no escribe nada: imprime un JSON propuesto que el agente revisa con el
usuario antes de guardarlo. Sin JIRA_API_TOKEN, los datos de Jira (accountId, estados,
tipos de incidencia) los completa el agente consultando el MCP de Atlassian.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collectors import chrome, git_local, jira  # noqa: E402
from lib import common  # noqa: E402

OK, WARN, FAIL = "✓", "!", "✗"


def _run(*cmd: str) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return p.returncode, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)


# --------------------------------------------------------------------------- check


def check() -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    add = lambda status, name, msg="": rows.append((status, name, msg))  # noqa: E731

    v = sys.version_info
    add(OK if v >= (3, 11) else FAIL, "python", f"{v.major}.{v.minor}.{v.micro} (se requiere ≥ 3.11)")
    add(OK if shutil.which("git") else FAIL, "git", shutil.which("git") or "no instalado")
    if shutil.which("gh"):
        code, out = _run("gh", "auth", "status")
        add(OK if code == 0 else FAIL, "gh", "autenticado" if code == 0 else out.splitlines()[0] if out else "no autenticado")
    else:
        add(FAIL, "gh", "no instalado (fuente github deshabilitada)")

    cfg_path = common.CONFIG_DIR / common.CONFIG_FILE
    cfg = None
    try:
        cfg = common.load_config()
        add(OK, "config.json", str(cfg_path))
    except common.ConfigMissing:
        add(WARN, "config.json", f"no existe {cfg_path} (correr discover y armarlo)")
    except common.ConfigError as e:
        add(FAIL, "config.json", str(e))

    env_path = common.CONFIG_DIR / common.ENV_FILE
    env = common.load_env()
    if env_path.exists():
        mode = stat.S_IMODE(env_path.stat().st_mode)
        add(OK if mode & 0o077 == 0 else WARN, ".env", f"{env_path} (permisos {oct(mode)}{'' if mode & 0o077 == 0 else ' → chmod 600'})")
    else:
        add(WARN, ".env", f"no existe {env_path}")
    for k in common.ENV_KEYS:
        add(OK if env.get(k) else WARN, k, "presente" if env.get(k) else "falta")

    if cfg:
        if env.get("JIRA_API_TOKEN"):
            try:
                me = jira.JiraClient(cfg["jira"]["site"], cfg["jira"]["email"], env["JIRA_API_TOKEN"]).get("/rest/api/3/myself")
                add(OK, "jira", f"{me.get('displayName')} ({me.get('accountId')})")
            except (common.HttpError, OSError) as e:
                add(FAIL, "jira", str(e)[:200])
        if env.get("ERPNEXT_API_KEY") and env.get("ERPNEXT_API_SECRET") and cfg["erpnext"].get("url"):
            try:
                r = common.http_json(cfg["erpnext"]["url"].rstrip("/") + "/api/method/frappe.auth.get_logged_user",
                                     headers=common.frappe_auth(env["ERPNEXT_API_KEY"], env["ERPNEXT_API_SECRET"]))
                user = (r or {}).get("message")
                expected = cfg["erpnext"].get("user")
                add(OK if user == expected else WARN, "erpnext", f"usuario {user}" + ("" if user == expected else f" (config dice {expected})"))
            except (common.HttpError, OSError) as e:
                add(FAIL, "erpnext", str(e)[:200])
        src = cfg["sources"]
        hist = common.expand_path(src["chrome"]["history_path"])
        add(OK if hist.exists() else WARN, "chrome", str(hist) if hist.exists() else f"no existe {hist}")
        cc = common.expand_path(src["claude_code"]["projects_dir"])
        add(OK if cc.is_dir() else WARN, "claude_code", str(cc))
        roots = [r for r in src["git_local"]["roots"] if common.expand_path(r).is_dir()]
        add(OK if roots else WARN, "git roots", ", ".join(roots) or "ninguna raíz existe")
    return rows


# --------------------------------------------------------------------------- discover


def discover_local() -> dict:
    info: dict = {}
    code, tz = _run("timedatectl", "show", "-p", "Timezone", "--value")
    info["timezone"] = tz if code == 0 and tz else os.environ.get("TZ", "America/Argentina/Buenos_Aires")

    emails = []
    for args in (("git", "config", "--global", "user.email"),):
        code, out = _run(*args)
        if code == 0 and out:
            emails.append(out)
    info["git_emails"] = emails

    if shutil.which("gh"):
        code, out = _run("gh", "api", "user", "--jq", ".login")
        info["github_user"] = out if code == 0 else None
        code, out = _run("gh", "api", "user/orgs", "--jq", ".[].login")
        info["github_orgs"] = out.splitlines() if code == 0 and out else []

    roots = [r for r in ("~/code", "~/src", "~/projects", "~/dev", "~/repos") if common.expand_path(r).is_dir()]
    info["git_roots"] = roots
    repos = git_local.discover_repos(roots, 5) if roots else []
    info["git_repos"] = len(repos)
    # emails usados en commits recientes de los repos locales (para detectar el corporativo)
    seen: Counter = Counter()
    for repo in repos[:40]:
        code, out = _run("git", "-C", str(repo), "log", "--all", "--since=60 days ago", "--format=%ae", "-n", "200")
        if code == 0:
            seen.update(line for line in out.splitlines() if line)
    info["recent_commit_emails"] = seen.most_common(8)

    hist = common.expand_path(common.DEFAULTS["sources"]["chrome"]["history_path"])
    info["chrome_history"] = str(hist) if hist.exists() else None
    if hist.exists():
        end = datetime.now().astimezone()
        try:
            visits = chrome.read_visits(hist, end - timedelta(days=14), end)
            domains = Counter(chrome.domain_of(u) for _, u, _ in visits if chrome.domain_of(u))
            info["chrome_top_domains"] = domains.most_common(40)
        except Exception as e:  # noqa: BLE001
            info["chrome_top_domains_error"] = str(e)
    return info


def discover_jira(cfg_like: dict, token: str, projects: list[str]) -> dict:
    client = jira.JiraClient(cfg_like["site"], cfg_like["email"], token)
    me = client.get("/rest/api/3/myself")
    out: dict = {"account_id": me["accountId"], "display_name": me.get("displayName"), "projects": {}}
    for key in projects:
        types = client.get(f"/rest/api/3/project/{key}/statuses")
        statuses: dict[str, str] = {}
        issue_types = []
        for t in types:
            issue_types.append({"name": t["name"], "subtask": t.get("subtask", False)})
            for s in t.get("statuses", []):
                cat = jira.CATEGORY_NAMES.get((s.get("statusCategory") or {}).get("key"), "?")
                statuses[s["name"]] = cat
        out["projects"][key] = {"issue_types": issue_types, "statuses": statuses}
    return out


def propose_config(local: dict, jira_info: dict | None, projects: list[str], email: str | None, site: str | None) -> dict:
    example = json.loads((Path(__file__).resolve().parent.parent / "config.example.json").read_text())
    cfg = {
        "timezone": local.get("timezone"),
        "jira": {"site": site, "cloud_id": None, "email": email,
                 "account_id": (jira_info or {}).get("account_id")},
        "erpnext": {"url": None, "user": email},
        "identity": {
            # Solo el email global: recent_commit_emails incluye a compañeros, el agente pregunta cuáles son propios.
            "git_emails": local.get("git_emails", []),
            "github_user": local.get("github_user"),
            "github_orgs": local.get("github_orgs", []),
        },
        "projects": {},
        "misc_issues": {"parent": None, "subtasks": {}},
        "sources": example["sources"],
        "rules": example["rules"],
        "review": example["review"],
    }
    cfg["sources"]["git_local"]["roots"] = local.get("git_roots") or ["~/code"]
    for key in projects:
        p = {"excluded_status_categories": ["Done"], "excluded_statuses": [], "agent_notes": ""}
        cfg["projects"][key] = p
    return cfg


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    p_d = sub.add_parser("discover")
    p_d.add_argument("--projects", default="", help="keys de proyectos Jira separadas por coma")
    p_d.add_argument("--site", help="https://<sitio>.atlassian.net")
    p_d.add_argument("--email", help="email de la cuenta Atlassian/ERPNext")
    args = ap.parse_args()

    if args.cmd == "check":
        rows = check()
        w = max(len(n) for _, n, _ in rows)
        for status, name, msg in rows:
            print(f"{status} {name.ljust(w)}  {msg}")
        return 1 if any(s == FAIL for s, _, _ in rows) else 0

    projects = [p.strip().upper() for p in args.projects.split(",") if p.strip()]
    local = discover_local()
    jira_info = None
    token = common.load_env().get("JIRA_API_TOKEN")
    if token and args.site and args.email and projects:
        try:
            jira_info = discover_jira({"site": args.site, "email": args.email}, token, projects)
        except (common.HttpError, OSError) as e:
            jira_info = {"error": str(e)[:300]}
    result = {
        "local": local,
        "jira": jira_info or "sin JIRA_API_TOKEN/--site/--email/--projects: completar accountId, estados y tipos con el MCP de Atlassian",
        "proposed_config": propose_config(local, jira_info if jira_info and "error" not in jira_info else None,
                                          projects, args.email, args.site),
    }
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
