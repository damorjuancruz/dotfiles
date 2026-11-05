#!/usr/bin/env python3
"""Servidor local de la página de revisión.

Sirve <state>/review.html (la genera `plan.py build`), guarda lo que el usuario hace en la
página en <state>/page_state.json y le avisa al agente escribiendo eventos en
<state>/server.log. El agente los recibe con `watch` (Monitor) o `wait` (Bash en segundo plano);
los dos llevan la cuenta de lo que ya mostraron en <state>/server.offset, así que un evento no
se pierde aunque el watcher se corte o se reinicie la sesión.

Cuando `plan.py build` reescribe review.html, la página se recarga sola (SSE). El servidor corre
desacoplado de la sesión del agente y se apaga solo después de MAX_HOURS.

Uso:
  server.py [--date AAAA-MM-DD] start        levanta el servidor (o reusa el que está vivo) e imprime la URL
  server.py [--date ...] status
  server.py [--date ...] stop
  server.py [--date ...] watch               un evento por línea, sin terminar (para Monitor)
  server.py [--date ...] wait                espera el próximo evento, lo imprime y termina
  server.py [--date ...] ask ID              muestra el pedido ID que mandó la página
  server.py [--date ...] reply ID < texto    responde el pedido ID; la página lo recibe al instante
  server.py [--date ...] serve               (interno) corre el servidor en primer plano

Eventos (una línea cada uno, con la hora adelante):
  ENVIADO ronda=N acción=X     el usuario mandó la ronda: correr `plan.py review`
  PEDIDO aN comentario KEY     la página pide un comentario de resolución: `ask aN` y `reply aN`
  ERROR ...                    error interno del servidor
  SERVIDOR CAÍDO / DETENIDO    (solo watch/wait) el servidor no responde o se detuvo
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import common  # noqa: E402

INFO = "server.json"
LOG = "server.log"
OFFSET = "server.offset"
ERR = "server.err"
PAGE = "review.html"
PAGE_STATE = "page_state.json"
ASKS = "asks"
MAX_HOURS = 16
MAX_BODY = 5_000_000
ACTIONS = ("review", "load", "cancel", "apply", "apply_more", "done")


# --------------------------------------------------------------------------- utilidades


def log_event(sdir: Path, text: str) -> None:
    line = f"{datetime.now().strftime('%H:%M:%S')} {' '.join(str(text).split())}\n"
    with open(sdir / LOG, "a", encoding="utf-8") as f:
        f.write(line)


def page_build(sdir: Path) -> str:
    """Identifica la versión de review.html: la página se recarga cuando cambia."""
    try:
        return str((sdir / PAGE).stat().st_mtime_ns)
    except FileNotFoundError:
        return ""


def ask_path(sdir: Path, ask_id: str) -> Path | None:
    if not ask_id.startswith("a") or not ask_id[1:].isdigit():
        return None
    return sdir / ASKS / f"{ask_id}.json"


def list_asks(sdir: Path) -> list[dict]:
    d = sdir / ASKS
    if not d.exists():
        return []
    out = [common.read_json(p) for p in d.glob("a*.json")]
    return sorted((a for a in out if a), key=lambda a: int(a["id"][1:]))


def health(info: dict | None, timeout: float = 2.0) -> bool:
    if not info or not info.get("port"):
        return False
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{info['port']}/api/health", timeout=timeout) as r:
            return json.loads(r.read()).get("pid") == info.get("pid")
    except (OSError, ValueError, urllib.error.URLError):
        return False


def port_free(port: int) -> bool:
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # como el servidor: TIME_WAIT no lo ocupa
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def page_url(info: dict) -> str:
    return f"http://127.0.0.1:{info['port']}/?t={info['token']}"


# --------------------------------------------------------------------------- servidor


class App:
    def __init__(self, sdir: Path, token: str):
        self.sdir, self.token = sdir, token
        self.cond = threading.Condition()
        self.seq = 0
        self.events: list[tuple[int, str, dict]] = []
        self.write_lock = threading.Lock()

    def publish(self, name: str, data: dict) -> None:
        with self.cond:
            self.seq += 1
            self.events = [*self.events[-99:], (self.seq, name, data)]
            self.cond.notify_all()

    def watch_page(self) -> None:
        last = page_build(self.sdir)
        while True:
            time.sleep(0.5)
            cur = page_build(self.sdir)
            if cur and cur != last:
                last = cur
                self.publish("reload", {"build": cur})

    def save_state(self, st: dict) -> None:
        with self.write_lock:
            common.write_json(self.sdir / PAGE_STATE, st)

    def new_ask(self, body: dict) -> dict:
        with self.write_lock:
            n = max([int(a["id"][1:]) for a in list_asks(self.sdir)] or [0]) + 1
            ask = {"id": f"a{n}", "kind": str(body.get("kind") or "comment"), "issue": str(body.get("issue") or ""),
                   "prompt": str(body.get("prompt") or ""), "at": datetime.now().isoformat(timespec="seconds"),
                   "reply": None}
            common.write_json(self.sdir / ASKS / f"{ask['id']}.json", ask)
        return ask

    def set_reply(self, ask_id: str, text: str) -> dict | None:
        path = ask_path(self.sdir, ask_id)
        with self.write_lock:
            ask = common.read_json(path) if path else None
            if not ask:
                return None
            ask["reply"] = text
            common.write_json(path, ask)
        return ask


def make_handler(app: App):
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "jira-time-tracker"

        def log_message(self, *a):
            pass

        # ---- helpers
        def _send(self, code: int, body: bytes = b"", ctype: str = "application/json; charset=utf-8") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if body and self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, data, code: int = 200) -> None:
            self._send(code, json.dumps(data, ensure_ascii=False).encode())

        def _query(self) -> dict:
            return urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)

        def _authorized(self) -> bool:
            token = self.headers.get("X-JTT-Token") or (self._query().get("t") or [""])[0]
            if not secrets.compare_digest(token, app.token):
                return False
            origin = self.headers.get("Origin")
            return not origin or origin == f"http://{self.headers.get('Host')}"

        def _body(self) -> dict | None:
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > MAX_BODY:
                return None
            try:
                data = json.loads(self.rfile.read(n))
            except (ValueError, UnicodeDecodeError):
                return None
            return data if isinstance(data, dict) else None

        def _route(self) -> str:
            return urllib.parse.urlsplit(self.path).path

        # ---- métodos
        def do_GET(self):
            route = self._route()
            if route == "/api/health":
                return self._json({"ok": True, "pid": os.getpid()})
            if not self._authorized():
                return self._send(403, b"forbidden", "text/plain")
            try:
                if route == "/":
                    return self._page()
                if route == "/api/state":
                    return self._json(common.read_json(app.sdir / PAGE_STATE))
                if route == "/api/asks":
                    return self._json(list_asks(app.sdir))
                if route == "/api/events":
                    return self._events()
            except (BrokenPipeError, ConnectionResetError):
                return
            except Exception as e:  # noqa: BLE001 — se informa al agente y se sigue sirviendo
                log_event(app.sdir, f"ERROR GET {route}: {e!r}")
                return self._send(500, b"error", "text/plain")
            self._send(404, b"not found", "text/plain")

        def do_PUT(self):
            if self._route() != "/api/state":
                return self._send(404, b"not found", "text/plain")
            if not self._authorized():
                return self._send(403, b"forbidden", "text/plain")
            st = self._body()
            if st is None:
                return self._send(400, b"bad request", "text/plain")
            app.save_state(st)
            self._json({"ok": True})

        def do_POST(self):
            route = self._route()
            if not self._authorized():
                return self._send(403, b"forbidden", "text/plain")
            body = self._body()
            if body is None:
                return self._send(400, b"bad request", "text/plain")
            try:
                if route == "/api/send":
                    if not body.get("sent") or body.get("action") not in ACTIONS:
                        return self._send(400, b"falta sent/action", "text/plain")
                    app.save_state(body)
                    log_event(app.sdir, f"ENVIADO ronda={body.get('round')} acción={body['action']}")
                    return self._json({"ok": True})
                if route == "/api/ask":
                    ask = app.new_ask(body)
                    log_event(app.sdir, f"PEDIDO {ask['id']} comentario {ask['issue']}")
                    return self._json({"id": ask["id"]})
                if route == "/api/reply":
                    ask = app.set_reply(str(body.get("id") or ""), str(body.get("text") or ""))
                    if not ask:
                        return self._send(404, b"no existe ese pedido", "text/plain")
                    app.publish("reply", {"id": ask["id"], "issue": ask["issue"], "text": ask["reply"]})
                    return self._json({"ok": True})
            except Exception as e:  # noqa: BLE001
                log_event(app.sdir, f"ERROR POST {route}: {e!r}")
                return self._send(500, b"error", "text/plain")
            self._send(404, b"not found", "text/plain")

        def _page(self):
            try:
                html = (app.sdir / PAGE).read_text()
            except FileNotFoundError:
                return self._send(503, "Todavía no hay página de revisión: falta correr plan.py build.".encode(),
                                  "text/plain; charset=utf-8")
            boot = f'<script>window.JTT_BUILD = {json.dumps(page_build(app.sdir))};</script>'
            at = html.find("<script")
            html = html[:at] + boot + html[at:] if at >= 0 else boot + html
            self._send(200, html.encode(), "text/html; charset=utf-8")

        def _events(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            with app.cond:
                seen = app.seq
            self.wfile.write(f"retry: 2000\nevent: hello\ndata: {json.dumps({'build': page_build(app.sdir)})}\n\n".encode())
            self.wfile.flush()
            while True:
                with app.cond:
                    app.cond.wait_for(lambda: app.seq > seen, timeout=15)
                    pending = [e for e in app.events if e[0] > seen]
                    seen = app.seq
                if pending:
                    for _, name, data in pending:
                        self.wfile.write(f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode())
                else:
                    self.wfile.write(b": ping\n\n")
                self.wfile.flush()

    return Handler


def serve(sdir: Path) -> int:
    info = common.read_json(sdir / INFO)
    if not info:
        print(f"No existe {sdir / INFO}: usá `start`.", file=sys.stderr)
        return 3
    app = App(sdir, info["token"])
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", int(info["port"])), make_handler(app))
    httpd.daemon_threads = True
    info.update(pid=os.getpid(), started=datetime.now().isoformat(timespec="seconds"))
    common.write_json(sdir / INFO, info)
    os.chmod(sdir / INFO, 0o600)
    threading.Thread(target=app.watch_page, daemon=True).start()
    threading.Timer(MAX_HOURS * 3600, httpd.shutdown).start()
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=httpd.shutdown).start())
    log_event(sdir, f"INICIADO {page_url(info).split('?')[0]}")
    try:
        httpd.serve_forever()
    finally:
        log_event(sdir, "DETENIDO")
    return 0


# --------------------------------------------------------------------------- comandos


def cmd_start(sdir: Path) -> int:
    info = common.read_json(sdir / INFO) or {}
    if health(info):
        print(f"Servidor ya activo (pid {info['pid']}).\nURL: {page_url(info)}")
        return 0
    port = info.get("port")
    if not port or not port_free(int(port)):
        port = free_port()
    info = {"port": int(port), "token": info.get("token") or secrets.token_urlsafe(18)}
    common.write_json(sdir / INFO, info)
    os.chmod(sdir / INFO, 0o600)
    with open(sdir / ERR, "a") as err:
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--dir", str(sdir), "serve"],
                         stdin=subprocess.DEVNULL, stdout=err, stderr=err, cwd=str(sdir), start_new_session=True)
    for _ in range(50):
        time.sleep(0.1)
        info = common.read_json(sdir / INFO) or {}
        if info.get("pid") and health(info):
            print(f"Servidor activo (pid {info['pid']}).\nURL: {page_url(info)}")
            return 0
    print(f"✗ el servidor no arrancó; ver {sdir / ERR}")
    return 1


def cmd_status(sdir: Path) -> int:
    info = common.read_json(sdir / INFO)
    if health(info):
        print(f"activo (pid {info['pid']}) · {page_url(info)}")
        return 0
    print("detenido")
    return 1


def cmd_stop(sdir: Path) -> int:
    info = common.read_json(sdir / INFO) or {}
    if health(info):
        os.kill(int(info["pid"]), signal.SIGTERM)
        for _ in range(30):
            if not health(info, timeout=0.3):
                break
            time.sleep(0.1)
    (sdir / INFO).unlink(missing_ok=True)
    print("Servidor detenido.")
    return 0


def follow(sdir: Path, once: bool) -> int:
    """Imprime los eventos nuevos del log. Sin `once` no termina salvo que el servidor caiga."""
    log, off_path = sdir / LOG, sdir / OFFSET
    try:
        off = int(off_path.read_text().strip() or 0)
    except (FileNotFoundError, ValueError):
        off = 0
    misses, next_check = 0, 0.0
    while True:
        size = log.stat().st_size if log.exists() else 0
        if size < off:
            off = 0
        if size > off:
            with open(log, "rb") as f:
                f.seek(off)
                chunk = f.read()
            end = chunk.rfind(b"\n") + 1
            lines = [ln for ln in chunk[:end].decode("utf-8", "replace").splitlines()
                     if ln.split(" ", 1)[-1].split(" ", 1)[0] in ("ENVIADO", "PEDIDO", "ERROR")]
            off += end
            off_path.write_text(str(off))
            for ln in lines:
                print(ln, flush=True)
            if once and lines:
                return 0
        if time.monotonic() >= next_check:
            next_check = time.monotonic() + 3
            info = common.read_json(sdir / INFO)
            if not info:
                print("SERVIDOR DETENIDO", flush=True)
                return 1
            misses = 0 if health(info) else misses + 1
            if misses >= 2:
                print(f"SERVIDOR CAÍDO: no responde en el puerto {info.get('port')}; correr `server.py start`", flush=True)
                return 1
        time.sleep(0.5)


def cmd_ask(sdir: Path, ask_id: str) -> int:
    path = ask_path(sdir, ask_id)
    ask = common.read_json(path) if path else None
    if not ask:
        print(f"✗ no existe el pedido {ask_id}")
        return 1
    print(f"Pedido {ask['id']} ({ask['kind']} para {ask['issue']}, {ask['at']}). Respondé con "
          f"`server.py reply {ask['id']}` y el texto por stdin. Prompt de la página:\n\n{ask['prompt']}")
    return 0


def cmd_reply(sdir: Path, ask_id: str, text: str) -> int:
    info = common.read_json(sdir / INFO) or {}
    if not health(info):
        print("✗ el servidor no está activo: correr `server.py start` y repetir")
        return 1
    req = urllib.request.Request(f"http://127.0.0.1:{info['port']}/api/reply", method="POST",
                                 data=json.dumps({"id": ask_id, "text": text.strip()}).encode(),
                                 headers={"Content-Type": "application/json", "X-JTT-Token": info["token"]})
    try:
        with urllib.request.urlopen(req, timeout=5):
            pass
    except urllib.error.HTTPError as e:
        with e:
            print(f"✗ {e.code}: {e.read().decode(errors='replace')}")
        return 1
    print(f"Respuesta enviada a la página ({ask_id}).")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="día (AAAA-MM-DD); por defecto hoy")
    ap.add_argument("--dir", help=argparse.SUPPRESS)
    ap.add_argument("--config", help="ruta a config.json")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("start", "status", "stop", "watch", "wait", "serve"):
        sub.add_parser(name)
    sub.add_parser("ask").add_argument("id")
    sub.add_parser("reply").add_argument("id")
    args = ap.parse_args(argv)

    if args.dir:
        sdir = Path(args.dir)
    else:
        try:
            cfg = common.load_config(Path(args.config) if args.config else None)
        except (common.ConfigMissing, common.ConfigError) as e:
            print(e, file=sys.stderr)
            return 3
        sdir = common.state_dir(common.parse_day(args.date, common.get_tz(cfg)))
    sdir.mkdir(parents=True, exist_ok=True)

    commands = {
        "serve": serve, "start": cmd_start, "status": cmd_status, "stop": cmd_stop,
        "watch": lambda d: follow(d, once=False), "wait": lambda d: follow(d, once=True),
        "ask": lambda d: cmd_ask(d, args.id), "reply": lambda d: cmd_reply(d, args.id, sys.stdin.read()),
    }
    return commands[args.cmd](sdir)


if __name__ == "__main__":
    sys.exit(main())
