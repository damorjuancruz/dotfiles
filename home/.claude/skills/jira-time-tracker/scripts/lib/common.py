"""Utilidades compartidas por los scripts de jira-time-tracker.

Solo stdlib. Los scripts se ejecutan como `python scripts/<script>.py`, por lo que
`scripts/` queda en sys.path y este módulo se importa como `from lib import common`.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

APP = "jira-time-tracker"

SKILL_DIR = Path(__file__).resolve().parents[2]


def default_config_dir(skill_dir: Path = SKILL_DIR) -> Path:
    """Config del `.claude` más cercano que contiene el skill.

    <x>/.claude/skills/jira-time-tracker           → <x>/.claude/jira-time-tracker
    ~/.claude/skills/synced/<bucket>/jira-time-tracker → ~/.claude/jira-time-tracker
    Fuera de cualquier `.claude` se usa ~/.config/jira-time-tracker."""
    for d in skill_dir.parents:
        if d.name == ".claude":
            return d / APP
    return Path.home() / ".config" / APP


CONFIG_DIR = Path(os.environ.get("JTL_CONFIG_DIR") or default_config_dir())
STATE_ROOT = Path(os.environ.get("JTL_STATE_DIR") or CONFIG_DIR / "state")

CONFIG_FILE = "config.json"
ENV_FILE = ".env"

# Valores por defecto: el config.json del usuario solo necesita lo que difiere.
DEFAULTS: dict[str, Any] = {
    "timezone": "America/Argentina/Buenos_Aires",
    "jira": {"site": None, "cloud_id": None, "email": None, "account_id": None},
    "erpnext": {"url": None, "user": None},
    "identity": {"git_emails": [], "github_user": None, "github_orgs": []},
    "projects": {},
    "misc_issues": {"parent": None, "subtasks": {}},
    "sources": {
        "jira": {"enabled": True},
        "erpnext": {"enabled": True},
        "git_local": {"enabled": True, "roots": ["~/code"], "max_depth": 5, "session_gap_minutes": 15},
        "github": {"enabled": True, "only_orgs": True},
        "claude_code": {
            "enabled": True,
            "projects_dir": "~/.claude/projects",
            "idle_gap_minutes": 15,
        },
        "t3_code": {
            "enabled": True,
            "db_path": "~/.t3/userdata/statev2.sqlite",
            "idle_gap_minutes": 15,
        },
        # Máquinas remotas por SSH (entornos remotos de T3 Code, VPS): corre ahí git_local,
        # claude_code y t3_code. Cada host: {"ssh": "alias", "label"?, "timeout_seconds"?,
        # "ssh_options"?, "git_local"?: {"roots": [...]}, "claude_code"?: {...}, "t3_code"?: {...}}.
        "remote": {"enabled": False, "hosts": []},
        "chrome": {
            "enabled": True,
            "history_path": "~/.config/google-chrome/Default/History",
            "session_gap_minutes": 10,
            "deny_domains": [
                "youtube.com", "facebook.com", "instagram.com", "x.com", "twitter.com", "reddit.com",
                "netflix.com", "web.whatsapp.com", "mail.google.com", "play.hbomax.com", "disneyplus.com",
                "primevideo.com", "spotify.com", "tiktok.com", "mercadolibre.com.ar",
            ],
        },
        "outlook": {"enabled": True},
        "teams": {"enabled": True},
        "sharepoint": {"enabled": True},
        "google_drive": {"enabled": True},
    },
    "rules": {
        "slot_minutes": 5,
        "min_block_minutes": 10,
        "candidates_lookback_days": 30,
    },
    # Modos de la revisión: valores iniciales de los toggles de la página y nivel de comentario.
    "review": {
        "group": True,
        "lunch": True,
        "lunch_minutes": 30,
        "lunch_window": ["12:30", "14:00"],
        "comment_level": "normal",
    },
}

COMMENT_LEVELS = ("nada", "breve", "normal", "detallado")

PROJECT_DEFAULTS: dict[str, Any] = {
    "excluded_status_categories": ["Done"],
    "excluded_statuses": [],
    "agent_notes": "",
}

REQUIRED_KEYS = [("timezone",), ("jira", "site"), ("jira", "email")]

ENV_KEYS = ("JIRA_API_TOKEN", "ERPNEXT_API_KEY", "ERPNEXT_API_SECRET")


class ConfigMissing(Exception):
    """No existe config.json: el skill debe entrar en modo setup."""


class ConfigError(Exception):
    """El config.json existe pero es inválido."""


# --------------------------------------------------------------------------- config


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_config(path: Path | None = None) -> dict:
    path = Path(path) if path else CONFIG_DIR / CONFIG_FILE
    if not path.exists():
        raise ConfigMissing(f"No existe {path}. Ejecutá el modo setup del skill.")
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path} no es JSON válido: {e}") from e
    cfg = _deep_merge(DEFAULTS, raw)
    cfg["projects"] = {
        key: _deep_merge(PROJECT_DEFAULTS, proj or {}) for key, proj in cfg["projects"].items()
    }
    errors = validate_config(cfg)
    if errors:
        raise ConfigError("Config inválido:\n  - " + "\n  - ".join(errors))
    return cfg


def validate_config(cfg: dict) -> list[str]:
    errors = []
    for keys in REQUIRED_KEYS:
        node: Any = cfg
        for k in keys:
            node = node.get(k) if isinstance(node, dict) else None
        if not node:
            errors.append(f"falta '{'.'.join(keys)}'")
    if not cfg.get("projects"):
        errors.append("'projects' debe tener al menos un proyecto")
    try:
        ZoneInfo(cfg.get("timezone") or "")
    except Exception:
        errors.append(f"timezone inválida: {cfg.get('timezone')!r}")
    rules = cfg.get("rules", {})
    slot, min_block = rules.get("slot_minutes"), rules.get("min_block_minutes")
    if not (isinstance(slot, int) and slot > 0):
        errors.append("rules.slot_minutes debe ser un entero > 0")
    elif not (isinstance(min_block, int) and min_block >= slot and min_block % slot == 0):
        errors.append("rules.min_block_minutes debe ser múltiplo de slot_minutes")
    rv = cfg.get("review", {})
    if rv.get("comment_level") not in COMMENT_LEVELS:
        errors.append(f"review.comment_level debe ser uno de {', '.join(COMMENT_LEVELS)}")
    window = rv.get("lunch_window") or []
    if not (len(window) == 2 and all(re.fullmatch(r"\d{2}:\d{2}", str(w)) for w in window) and window[0] < window[1]):
        errors.append("review.lunch_window debe ser [\"HH:MM\", \"HH:MM\"] con inicio < fin")
    lm = rv.get("lunch_minutes")
    if isinstance(slot, int) and slot > 0 and not (isinstance(lm, int) and lm > 0 and lm % slot == 0):
        errors.append("review.lunch_minutes debe ser múltiplo de slot_minutes")
    return errors


def load_env(path: Path | None = None) -> dict[str, str]:
    """Lee KEY=VALUE del .env; las variables de entorno reales tienen prioridad."""
    path = Path(path) if path else CONFIG_DIR / ENV_FILE
    env: dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip().removeprefix("export ").strip()
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            env[k] = v
    for k in ENV_KEYS:
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def expand_path(p: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(p)))


# --------------------------------------------------------------------------- tiempo


def get_tz(cfg: dict) -> ZoneInfo:
    return ZoneInfo(cfg["timezone"])


def parse_iso(s: str) -> datetime:
    """Parsea ISO 8601 incluyendo 'Z' y offsets sin ':' (formato Jira: -0300)."""
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    m = re.search(r"([+-])(\d{2})(\d{2})$", s)
    if m:
        s = s[: m.start()] + f"{m.group(1)}{m.group(2)}:{m.group(3)}"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        raise ValueError(f"datetime sin zona horaria: {s!r}")
    return dt


def day_bounds(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """[00:00 del día, 00:00 del día siguiente) en hora local."""
    start = datetime.combine(day, time.min, tzinfo=tz)
    return start, start + timedelta(days=1)


def round_up(dt: datetime, minutes: int = 5) -> datetime:
    floored = round_down(dt, minutes)
    return floored if floored == dt else floored + timedelta(minutes=minutes)


def round_down(dt: datetime, minutes: int = 5) -> datetime:
    dt = dt.replace(second=0, microsecond=0)
    return dt - timedelta(minutes=dt.minute % minutes)


def fmt_hm(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def fmt_duration(minutes: int) -> str:
    """90 -> '1h30m', 60 -> '1h', 25 -> '25m'."""
    h, m = divmod(int(minutes), 60)
    if h and m:
        return f"{h}h{m:02d}m"
    return f"{h}h" if h else f"{m}m"


def jira_time_spent(minutes: int) -> str:
    """Formato aceptado por Jira en timeSpent: '1h 30m'."""
    h, m = divmod(int(minutes), 60)
    return " ".join(p for p in (f"{h}h" if h else "", f"{m}m" if m else "") if p) or "0m"


def jira_started(dt: datetime) -> str:
    """Formato de 'started' de Jira: 2026-10-05T09:00:00.000-0300."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000%z")


def parse_day(s: str | None, tz: ZoneInfo) -> date:
    return date.fromisoformat(s) if s else datetime.now(tz).date()


# --------------------------------------------------------------------------- estado


def state_dir(day: date, create: bool = True) -> Path:
    d = STATE_ROOT / day.isoformat()
    if create:
        (d / "raw").mkdir(parents=True, exist_ok=True)
    return d


def raw_dir(day: date, create: bool = True) -> Path:
    return state_dir(day, create) / "raw"


def read_json(path: Path, default: Any = None) -> Any:
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text())


def write_json(path: Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n")
    tmp.replace(path)


# --------------------------------------------------------------------------- eventos

WEIGHTS = ("strong", "normal", "weak")


@dataclass
class Event:
    """Evento de actividad normalizado que emite cada colector."""

    source: str
    start: str  # ISO 8601 local con offset
    end: str  # ISO 8601 local con offset (igual a start si es puntual)
    title: str
    detail: str = ""
    hints: dict[str, Any] = field(default_factory=dict)
    weight: str = "normal"
    id: str = ""

    def __post_init__(self) -> None:
        if self.weight not in WEIGHTS:
            raise ValueError(f"weight inválido: {self.weight}")
        if not self.id:
            self.id = make_event_id(self.source, self.start, self.title)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["hints"] = {k: v for k, v in self.hints.items() if v not in (None, "", [])}
        return d


def split_by_gap(stamps: list[tuple], gap: timedelta) -> list[list[tuple]]:
    """Ordena marcas (tuplas que empiezan con su datetime) y las corta en tramos donde pasa más
    de `gap` entre una y la siguiente."""
    out: list[list[tuple]] = []
    for s in sorted(stamps, key=lambda x: x[0]):
        if out and s[0] - out[-1][-1][0] <= gap:
            out[-1].append(s)
        else:
            out.append([s])
    return out


def prompts_detail(prompts: list[str], chars: int = 160) -> str:
    """'primer prompt: … | último prompt: … | N prompts' de un tramo de sesión de agente."""
    if not prompts:
        return ""
    parts = [f"primer prompt: {prompts[0][:chars]}"]
    if len(prompts) > 1:
        parts.append(f"último prompt: {prompts[-1][:chars]}")
    return " | ".join(parts + [f"{len(prompts)} prompts"])


def make_event_id(source: str, *parts: Any) -> str:
    h = hashlib.sha1("\x1f".join(str(p) for p in parts).encode()).hexdigest()[:8]
    return f"{source}:{h}"


def issue_key_regex(project_keys: list[str]) -> re.Pattern:
    """Detecta keys tipo SIT-123 en textos y branches (case-insensitive: 'iea-sit-325')."""
    alts = "|".join(re.escape(k) for k in sorted(project_keys, key=len, reverse=True))
    return re.compile(rf"(?<![A-Za-z0-9])({alts})[-_ ]?(\d+)(?![0-9])", re.IGNORECASE)


def find_issue_keys(text: str | None, pattern: re.Pattern) -> list[str]:
    if not text:
        return []
    seen: list[str] = []
    for proj, num in pattern.findall(text):
        key = f"{proj.upper()}-{int(num)}"
        if key not in seen:
            seen.append(key)
    return seen


# --------------------------------------------------------------------------- HTTP


class HttpError(Exception):
    def __init__(self, status: int, url: str, body: str):
        super().__init__(f"HTTP {status} en {url}: {body[:300]}")
        self.status, self.url, self.body = status, url, body


def basic_auth(user: str, secret: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{secret}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def frappe_auth(key: str, secret: str) -> dict[str, str]:
    return {"Authorization": f"token {key}:{secret}"}


def http_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    body: Any = None,
    timeout: float = 30,
) -> Any:
    if params:
        clean = {k: v for k, v in params.items() if v is not None}
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(clean, doseq=True)
    data = None
    hdrs = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        data = json.dumps(body).encode()
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        with e:  # cierra la respuesta de error
            body = e.read().decode(errors="replace")
        raise HttpError(e.code, url, body) from e
    return json.loads(raw) if raw else None


# --------------------------------------------------------------------------- CLI de colectores


def collector_main(collect, doc: str | None) -> int:
    """`python scripts/collectors/<fuente>.py [--date AAAA-MM-DD]`: imprime el resultado del colector."""
    ap = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date")
    args = ap.parse_args()
    cfg = load_config()
    result = collect(cfg, load_env(), parse_day(args.date, get_tz(cfg)))
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if result["status"] != "error" else 1
