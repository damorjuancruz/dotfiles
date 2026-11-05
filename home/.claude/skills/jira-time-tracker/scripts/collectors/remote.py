#!/usr/bin/env python3
"""Colector de máquinas remotas por SSH (para entornos remotos de T3 Code, VPS, etc.).

T3 Code no copia a la base local los threads de un entorno remoto: cada entorno es un servidor
T3 con su propia statev2.sqlite, y los transcripts de Claude y los repos también están en esa
máquina. Por eso este colector, para cada host de `sources.remote.hosts`:

  1. copia scripts/collectors, scripts/lib y scripts/remote_collect.py a REMOTE_DIR en el host
     (tar por SSH; pisa lo anterior, así siempre corre la misma versión que la local);
  2. corre remote_collect.py con python3 y le pasa por stdin la config local, con las fuentes
     git_local, claude_code y t3_code (los overrides del host pisan los de la config local);
  3. junta los eventos: conservan su fuente (git, cc, t3), el título lleva el host adelante,
     `hints.host` dice de qué máquina vienen y el id se recalcula para no chocar con los locales.

Requiere SSH sin contraseña (clave o agente; corre con BatchMode) y Python 3.11+ en el remoto.

Uso: python scripts/collectors/remote.py [--date AAAA-MM-DD]
"""

from __future__ import annotations

import copy
import io
import json
import subprocess
import sys
import tarfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import common  # noqa: E402

SOURCE = "remote"
SCRIPTS = Path(__file__).resolve().parent.parent
REMOTE_DIR = ".cache/jira-time-tracker-remote"  # relativo al home remoto
REMOTE_SOURCES = ("git_local", "claude_code", "t3_code")


def bundle() -> bytes:
    """tar.gz con lo que necesita remote_collect.py (sin __pycache__)."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name in ("collectors", "lib", "remote_collect.py"):
            tar.add(SCRIPTS / name, arcname=name, filter=lambda t: None if "__pycache__" in t.name else t)
    return buf.getvalue()


def ssh(host: dict, command: str, data: bytes, timeout: int) -> subprocess.CompletedProcess:
    args = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", *host.get("ssh_options", []), host["ssh"], command]
    return subprocess.run(args, input=data, capture_output=True, timeout=timeout)


def remote_config(cfg: dict, host: dict) -> dict:
    """La config local con solo las fuentes remotas, cada una con los overrides del host."""
    rcfg = copy.deepcopy(cfg)
    for name, src in rcfg["sources"].items():
        if name in REMOTE_SOURCES:
            src.update(host.get(name) or {})
        else:
            src["enabled"] = False
    return rcfg


def collect_host(cfg: dict, host: dict, day: date) -> dict:
    timeout = int(host.get("timeout_seconds", 120))
    push = ssh(host, f"rm -rf ~/{REMOTE_DIR} && mkdir -p ~/{REMOTE_DIR} && tar xzf - -C ~/{REMOTE_DIR}", bundle(), timeout)
    if push.returncode:
        raise RuntimeError(f"no se pudo copiar los scripts: {push.stderr.decode(errors='replace').strip()[:200]}")
    req = {"day": day.isoformat(), "cfg": remote_config(cfg, host)}
    run = ssh(host, f"python3 ~/{REMOTE_DIR}/remote_collect.py", json.dumps(req).encode(), timeout)
    if run.returncode:
        raise RuntimeError(f"falló remote_collect.py: {run.stderr.decode(errors='replace').strip()[-300:]}")
    return json.loads(run.stdout)


def collect(cfg: dict, env: dict, day: date) -> dict:
    hosts = cfg["sources"]["remote"].get("hosts") or []
    events, messages, failed = [], [], 0
    for host in hosts:
        label = host.get("label") or host["ssh"]
        try:
            results = collect_host(cfg, host, day)
        except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as e:
            failed += 1
            messages.append(f"{label}: {e}"[:300])
            continue
        for name, res in results.items():
            evs = res.get("events", [])
            note = res.get("message") or "; ".join(res.get("messages") or [])
            messages.append(f"{label} {name} {res.get('status')} ({len(evs)} ev)" + (f" [{note[:120]}]" if note else ""))
            for ev in evs:
                ev["id"] = common.make_event_id(ev["source"], label, ev["id"])
                ev["title"] = f"[{label}] {ev['title']}"
                ev.setdefault("hints", {})["host"] = label
                ev["hints"].pop("current", None)  # la sesión actual siempre es local
                events.append(ev)
    status = "error" if hosts and failed == len(hosts) else "ok"
    return {"source": SOURCE, "status": status, "events": sorted(events, key=lambda e: e["start"]),
            "messages": messages or ["sin hosts configurados"]}


if __name__ == "__main__":
    sys.exit(common.collector_main(collect, __doc__))
