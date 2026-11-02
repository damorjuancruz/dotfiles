#!/usr/bin/env python3
"""Núcleo determinista del plan del día.

El agente escribe <state>/<fecha>/plan.json (el plan base) una sola vez; este script lo
valida, deriva las variantes (agrupar / almuerzo), arma la página de revisión que se publica
como artifact, aplica lo que el usuario decidió en ella y emite las operaciones de carga.

Uso:
  plan.py [--date AAAA-MM-DD] validate
  plan.py [--date ...] build [--note "texto para el usuario"] [--refresh-jira]
  plan.py [--date ...] build --followup [--suggest KEY=TRANSICIÓN ...] [--note "..."]
  plan.py [--date ...] comments < comentarios.json
  plan.py [--date ...] new-issue < borrador.json
  plan.py [--date ...] review [estado.json]
  plan.py [--date ...] edit "OP" ["OP" ...]
  plan.py [--date ...] expand N|ID
  plan.py [--date ...] ops
  plan.py [--date ...] url https://claude.ai/...

Formato de plan.json (horas locales "HH:MM"; los `id` los asigna el script):
  {
    "date": "2026-10-05",
    "blocks": [{"id"?, "start", "end", "issue", "summary"?, "action": "new|existing|adjust",
                "worklog_id"?, "confidence": "alta|media|baja", "sources": [...],
                "evidence": [event ids], "warn"?: "...", "fixed"?: bool,
                "comments": {"breve", "normal", "detallado"},  # bloques nuevos
                "comment"?: "...",                              # worklogs existentes (del usuario)
                "confirmed"?: bool}],
    "gaps": [{"id"?, "start", "end", "kind": "open|unworked", "note"?, "confirmed"?: bool}],
    "absorbed": [{"time", "minutes", "issue"?, "note"}],
    "new_issues": [{"ref": "NEW-1", "project", "type", "summary", "parent"?, "similar": [keys],
                    "fields": [{"key", "name", "value", "options"?: [...], "required"?: bool}]}],
    "group_comments": {"b2+b5": {"breve", "normal", "detallado"}},
    "confirmed_rows"?: ["b2+b5", ...],  # filas confirmadas en la página (key de fila de variante)
    "variant_overrides"?: {"group": [{"start", "end", "ids": [...]} | {"start", "end", "lunch": true}
                                     | {"start", "end", "gap": "g1"}]}
  }
El resto de las claves (modes, levels, followup, created, stage, round, note, artifact_url) las
escribe el script. `new-issue` agrega un borrador NEW-n después de la primera escritura:
  {"project", "type", "summary", "parent"?, "similar", "fields", "blocks": ["b3", "b5"]}
"""

from __future__ import annotations

import argparse
import copy
import json
import shlex
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collectors import jira  # noqa: E402
from lib import common, page, variants  # noqa: E402

ACTIONS = ("new", "existing", "adjust")
CONFIDENCES = ("alta", "media", "baja")
GAP_KINDS = ("open", "unworked")
LEVELS = ("breve", "normal", "detallado")


@dataclass
class Row:
    """Fila de la tabla: bloque de trabajo, hueco o salida registrada en el checkin."""

    kind: str  # block | gap | break
    start: datetime
    end: datetime
    data: dict[str, Any] = field(default_factory=dict)
    n: int = 0

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


@dataclass
class Model:
    day: date
    cfg: dict
    plan: dict
    digest: dict
    range_start: datetime | None
    range_end: datetime | None
    rows: list[Row]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def blocks(self) -> list[Row]:
        return [r for r in self.rows if r.kind == "block"]

    def candidate(self, key: str) -> dict | None:
        for c in self.digest.get("candidates", []):
            if c.get("key") == key:
                return c
        return None

    def new_issue(self, ref: str) -> dict | None:
        for ni in self.plan.get("new_issues", []):
            if ni.get("ref") == ref:
                return ni
        return None


# --------------------------------------------------------------------------- carga


def _parse_hm(value: str, day: date, tz) -> datetime:
    try:
        h, m = (int(x) for x in str(value).split(":"))
    except ValueError as e:
        raise ValueError(f"hora inválida {value!r} (se espera HH:MM)") from e
    if h == 24 and m == 0:
        return datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=tz)
    return datetime(day.year, day.month, day.day, h, m, tzinfo=tz)


def ensure_ids(plan: dict) -> bool:
    """Asigna ids estables a bloques (b1, b2…) y huecos (g1…). Devuelve True si agregó alguno."""
    changed = False
    for key, prefix in (("blocks", "b"), ("gaps", "g")):
        items = plan.get(key, [])
        used = {x["id"] for x in items if x.get("id")}
        n = max((variants.block_id_order(i)[0] for i in used), default=0)
        for x in items:
            if not x.get("id"):
                n += 1
                x["id"] = f"{prefix}{n}"
                changed = True
    return changed


def build_model(plan: dict, digest: dict, cfg: dict) -> Model:
    ensure_ids(plan)
    tz = common.get_tz(cfg)
    day = date.fromisoformat(plan.get("date") or digest["date"])
    rng = digest.get("range") or {}
    r_start = common.parse_iso(rng["start"]).astimezone(tz) if rng.get("start") else None
    r_end = common.parse_iso(rng["end"]).astimezone(tz) if rng.get("end") else None
    # El plan puede corregir el rango (p.ej. sin checkin, el usuario dicta la entrada).
    if plan.get("start"):
        r_start = _parse_hm(plan["start"], day, tz)
    if plan.get("end"):
        r_end = _parse_hm(plan["end"], day, tz)

    model = Model(day, cfg, plan, digest, r_start, r_end, [])
    for i, b in enumerate(plan.get("blocks", []), 1):
        try:
            model.rows.append(Row("block", _parse_hm(b["start"], day, tz), _parse_hm(b["end"], day, tz), b))
        except (KeyError, ValueError) as e:
            model.errors.append(f"bloque #{i} del JSON ({b.get('issue', '?')}): {e}")
    for i, g in enumerate(plan.get("gaps", []), 1):
        try:
            model.rows.append(Row("gap", _parse_hm(g["start"], day, tz), _parse_hm(g["end"], day, tz), g))
        except (KeyError, ValueError) as e:
            model.errors.append(f"hueco #{i} del JSON: {e}")
    for br in rng.get("breaks", []):
        model.rows.append(Row("break", common.parse_iso(br["start"]).astimezone(tz),
                              common.parse_iso(br["end"]).astimezone(tz), br))
    model.rows.sort(key=lambda r: (r.start, r.end))
    for n, row in enumerate(model.rows, 1):
        row.n = n
    return model


# --------------------------------------------------------------------------- confirmación


def is_confirmed(row: Row) -> bool:
    """Las salidas del checkin y los worklogs existentes sin cambios no se revisan."""
    if row.kind == "break":
        return True
    if row.kind == "block" and row.data.get("action") == "existing":
        return True
    return bool(row.data.get("confirmed"))


def pending(model: Model) -> list[Row]:
    return [r for r in model.rows if not is_confirmed(r)]


# --------------------------------------------------------------------------- validación


def _is_excluded(cand: dict | None, cfg: dict) -> bool:
    if not cand:
        return False
    proj = cfg["projects"].get(cand["key"].split("-")[0])
    if not proj:
        return False
    return (cand.get("status_category") in proj["excluded_status_categories"]
            or cand.get("status") in proj["excluded_statuses"])


def validate(model: Model) -> Model:
    cfg, E, W = model.cfg, model.errors, model.warnings
    slot = cfg["rules"]["slot_minutes"]
    min_block = cfg["rules"]["min_block_minutes"]
    existing = {str(w["id"]): w for w in model.digest.get("worklogs", [])}
    new_refs = {ni.get("ref") for ni in model.plan.get("new_issues", [])}
    projects = set(cfg["projects"])
    tz = common.get_tz(cfg)

    if model.range_start is None:
        E.append("no hay hora de entrada (sin checkin): definí 'start' en el plan con la hora que indique el usuario")
    if model.range_end is None:
        E.append("no hay hora de corte: definí 'end' en el plan")

    seen_wl: dict[str, int] = {}
    for row in model.rows:
        tag = f"#{row.n}"
        if row.end <= row.start:
            E.append(f"{tag}: fin {common.fmt_hm(row.end)} no es posterior al inicio {common.fmt_hm(row.start)}")
            continue
        if row.kind == "gap":
            if row.data.get("kind", "open") not in GAP_KINDS:
                E.append(f"{tag}: kind de hueco inválido {row.data.get('kind')!r} (open|unworked)")
            continue
        if row.kind != "block":
            continue

        b = row.data
        action, issue = b.get("action"), b.get("issue")
        tag = f"#{row.n} ({issue})"
        if action not in ACTIONS:
            E.append(f"{tag}: action inválida {action!r} ({'|'.join(ACTIONS)})")
            continue
        if not issue:
            E.append(f"{tag}: falta 'issue'")
            continue
        if b.get("confidence", "alta") not in CONFIDENCES and action != "existing":
            E.append(f"{tag}: confidence inválida {b.get('confidence')!r} ({'|'.join(CONFIDENCES)})")

        aligned = row.start.minute % slot == 0 and row.end.minute % slot == 0
        if action == "existing":
            if not aligned:
                W.append(f"{tag}: worklog existente no alineado a {slot} min; considerar proponer 'adjust'")
            if row.minutes < min_block:
                W.append(f"{tag}: worklog existente de {row.minutes} min (< {min_block})")
        else:
            if not aligned:
                E.append(f"{tag}: {common.fmt_hm(row.start)}–{common.fmt_hm(row.end)} no está alineado a {slot} min")
            if row.minutes < min_block:
                E.append(f"{tag}: dura {row.minutes} min, el mínimo es {min_block}")
            if action == "new" and not all((b.get("comments") or {}).get(lv, "").strip() for lv in LEVELS):
                W.append(f"{tag}: faltan comentarios ({'/'.join(LEVELS)})")

        if action in ("existing", "adjust"):
            wid = str(b.get("worklog_id") or "")
            if wid not in existing:
                E.append(f"{tag}: worklog_id {wid or '(vacío)'} no está entre los worklogs existentes del día")
            else:
                seen_wl[wid] = seen_wl.get(wid, 0) + 1
                orig = existing[wid]
                if orig.get("issue") != issue:
                    E.append(f"{tag}: el worklog {wid} es de {orig.get('issue')}; nunca se cambia de incidencia")
                o_start = common.parse_iso(orig["started"]).astimezone(tz)
                o_end = o_start + timedelta(minutes=int(orig["minutes"]))
                same = (o_start.replace(second=0, microsecond=0) == row.start and o_end.replace(second=0, microsecond=0) == row.end)
                if action == "existing" and not same:
                    E.append(f"{tag}: horario distinto al original ({common.fmt_hm(o_start)}–{common.fmt_hm(o_end)}); usar action 'adjust'")
                if action == "adjust" and same:
                    W.append(f"{tag}: marcado 'adjust' pero no cambia nada; usar 'existing'")
        elif b.get("worklog_id"):
            E.append(f"{tag}: un bloque 'new' no lleva worklog_id")

        if issue in new_refs:
            pass
        elif issue.split("-")[0] not in projects and action == "new":
            E.append(f"{tag}: {issue} no pertenece a los proyectos configurados ({', '.join(sorted(projects))})")
        else:
            cand = model.candidate(issue)
            if cand is None and action == "new":
                W.append(f"{tag}: {issue} no está entre las candidatas; verificar que exista y esté abierta")
            elif _is_excluded(cand, cfg) and action == "new":
                E.append(f"{tag}: {issue} está en estado excluido ({cand.get('status')})")

    for wid, w in existing.items():
        if seen_wl.get(wid, 0) == 0:
            E.append(f"falta el worklog existente {wid} ({w.get('issue')}): debe figurar como 'existing' o 'adjust'")
        elif seen_wl[wid] > 1:
            E.append(f"el worklog existente {wid} aparece {seen_wl[wid]} veces")

    for ni in model.plan.get("new_issues", []):
        if not any(r.data.get("issue") == ni.get("ref") for r in model.blocks):
            W.append(f"incidencia nueva {ni.get('ref')} sin bloques asignados")

    _check_overlaps_and_coverage(model)
    return model


def _check_overlaps_and_coverage(model: Model) -> None:
    rows = sorted((r for r in model.rows if r.end > r.start), key=lambda r: r.start)
    for a, b in zip(rows, rows[1:]):
        if b.start < a.end:
            model.errors.append(f"#{a.n} y #{b.n} se superponen ({common.fmt_hm(b.start)}–{common.fmt_hm(min(a.end, b.end))})")

    if model.range_start is None or model.range_end is None:
        return
    cursor = model.range_start
    for r in rows:
        if r.end <= model.range_start or r.start >= model.range_end:
            if r.kind == "block":
                model.warnings.append(f"#{r.n}: fuera del rango del día ({common.fmt_hm(model.range_start)}–{common.fmt_hm(model.range_end)})")
            continue
        if r.start > cursor:
            model.errors.append(f"tiempo sin cubrir {common.fmt_hm(cursor)}–{common.fmt_hm(r.start)}")
        cursor = max(cursor, r.end)
    if cursor < model.range_end:
        model.errors.append(f"tiempo sin cubrir {common.fmt_hm(cursor)}–{common.fmt_hm(model.range_end)}")


# --------------------------------------------------------------------------- expand / ops


def load_raw_events(raw: Path) -> dict[str, dict]:
    events: dict[str, dict] = {}
    if raw.is_dir():
        for f in sorted(raw.glob("*.json")):
            data = common.read_json(f, {}) or {}
            for ev in data.get("events", []):
                events[ev["id"]] = ev
    return events


def activity(events: dict[str, dict], tz) -> list[tuple[datetime, datetime]]:
    out = []
    for ev in events.values():
        try:
            out.append((common.parse_iso(ev["start"]).astimezone(tz), common.parse_iso(ev["end"]).astimezone(tz)))
        except (KeyError, ValueError):
            continue
    return out


def find_row(model: Model, ref: str | int) -> Row | None:
    """Fila por número (de la numeración actual) o por id (b3, g1)."""
    ref = str(ref)
    if ref.isdigit():
        return next((r for r in model.rows if r.n == int(ref)), None)
    return next((r for r in model.rows if r.data.get("id") == ref), None)


def expand(model: Model, ref: str, raw: Path) -> str:
    row = find_row(model, ref)
    if row is None:
        return f"No existe la fila {ref}."
    tz = common.get_tz(model.cfg)
    out = [f"{row.data.get('id', '#' + str(row.n))} {common.fmt_hm(row.start)}–{common.fmt_hm(row.end)} "
           f"({common.fmt_duration(row.minutes)}) · {row.kind}"]
    if row.kind == "block":
        b = row.data
        out.append(f"Incidencia: {b.get('issue')} · acción {b.get('action')} · confianza {b.get('confidence', '—')}")
        if b.get("comment"):
            out.append(f"Comentario: {b['comment']}")
        for lv in LEVELS:
            if (b.get("comments") or {}).get(lv):
                out.append(f"Comentario {lv}: {b['comments'][lv]}")
    ids = row.data.get("evidence", [])
    if not ids:
        out.append("(sin evidencia referenciada)")
        return "\n".join(out)
    events = load_raw_events(raw)
    out.append("Evidencia:")
    for eid in ids:
        ev = events.get(eid)
        if ev is None:
            out.append(f"  ? {eid} (no encontrado en raw/)")
            continue
        s = common.parse_iso(ev["start"]).astimezone(tz)
        e = common.parse_iso(ev["end"]).astimezone(tz)
        when = common.fmt_hm(s) if s == e else f"{common.fmt_hm(s)}–{common.fmt_hm(e)}"
        out.append(f"  [{ev['source']}] {when} {ev['title']}")
        if ev.get("detail"):
            out.append(f"      {' '.join(str(ev['detail']).split())[:160]}")
        hints = ev.get("hints") or {}
        if hints:
            out.append("      " + " · ".join(f"{k}={v}" for k, v in hints.items()))
    return "\n".join(out)


# --------------------------------------------------------------------------- variantes


def modes(plan: dict, cfg: dict) -> dict:
    m = plan.get("modes") or {}
    return {"group": bool(m.get("group", cfg["review"]["group"])), "lunch": bool(m.get("lunch", cfg["review"]["lunch"]))}


def variant_name(m: dict) -> str:
    return {(False, False): "base", (False, True): "lunch", (True, False): "group", (True, True): "group+lunch"}[
        (m["group"], m["lunch"])]


def compute_variants(model: Model, raw: Path) -> dict[str, dict]:
    return variants.compute(model, activity(load_raw_events(raw), common.get_tz(model.cfg)))


def row_comments(model: Model, row: dict) -> dict | None:
    """Los tres niveles de comentario de una fila de variante (None si faltan)."""
    if len(row["ids"]) == 1:
        b = find_row(model, row["ids"][0])
        c = (b.data.get("comments") if b else None) or {}
    else:
        c = (model.plan.get("group_comments") or {}).get(row.get("comment_key", row["key"])) or {}
    return c if all((c.get(lv) or "").strip() for lv in LEVELS) else None


def level_of(model: Model, key: str) -> str:
    return (model.plan.get("levels") or {}).get(key) or model.cfg["review"]["comment_level"]


def row_confirmed(model: Model, r: dict) -> bool:
    """Una fila se confirma por su key. Los worklogs existentes sin cambios no se revisan, y una
    fila que es exactamente un bloque entero también vale confirmada si el bloque lo está."""
    if r["kind"] != "block":
        return True
    b = find_row(model, r["ids"][0])
    if b is None:
        return False
    if b.data.get("action") == "existing":
        return True
    if r["key"] in set(model.plan.get("confirmed_rows") or []):
        return True
    whole = len(r["ids"]) == 1 and (r.get("src") or {}).get(r["ids"][0], b.minutes) == b.minutes
    return whole and is_confirmed(b)


def confirmed_keys(model: Model, vs: dict[str, dict]) -> list[str]:
    return sorted({r["key"] for v in vs.values() for r in v["rows"] if r["kind"] == "block" and row_confirmed(model, r)})


def missing_comments(model: Model, vs: dict[str, dict]) -> list[dict]:
    """Filas nuevas (de cualquier variante) sin sus tres comentarios, sin repetir key."""
    out, seen = [], set()
    for name in variants.VARIANTS:
        for r in vs[name]["rows"]:
            ck = r.get("comment_key", r["key"])
            if r["kind"] != "block" or r.get("fixed") or ck in seen:
                continue
            seen.add(ck)
            if row_comments(model, r) is None:
                out.append(r)
    return out


def ops(model: Model, vs: dict[str, dict]) -> list[dict]:
    if model.errors:
        raise ValueError("el plan tiene errores de validación; corregirlos antes de cargar")
    name = variant_name(modes(model.plan, model.cfg))
    var = vs[name]
    if var["errors"]:
        raise ValueError(f"la variante {name} tiene errores: " + "; ".join(var["errors"]))
    by_id = {r.data.get("id"): r for r in model.rows if r.kind in ("block", "gap")}
    unconfirmed, open_gaps = [], []
    for r in var["rows"]:
        if r["kind"] == "block" and not row_confirmed(model, r):
            unconfirmed.append(f"{common.fmt_hm(r['start'])} {r['issue']}")
        if r["kind"] == "gap" and r["gap_kind"] == "open":
            open_gaps.append(common.fmt_hm(r["start"]))
    if unconfirmed:
        raise ValueError("hay filas sin confirmar por el usuario: " + ", ".join(unconfirmed))
    if open_gaps:
        raise ValueError("hay huecos sin resolver (asignarlos o marcarlos 'unworked'): " + ", ".join(open_gaps))
    new_refs = {ni.get("ref") for ni in model.plan.get("new_issues", [])}
    result = []
    for r in var["rows"]:
        if r["kind"] != "block" or r.get("action") == "existing":
            continue
        if r["issue"] in new_refs:
            raise ValueError(f"{r['key']} usa {r['issue']}: crear la incidencia y reemplazar la referencia con "
                             f"`edit \"replace {r['issue']} KEY\"`")
        minutes = int((r["end"] - r["start"]).total_seconds() // 60)
        if r.get("fixed") and r.get("action") == "adjust":
            b = by_id[r["ids"][0]].data
            comment = b.get("comment") or ""
        else:
            level = level_of(model, r["key"])
            comments = row_comments(model, r)
            if level != "nada" and comments is None:
                raise ValueError(f"{r['key']} ({r['issue']}) no tiene comentarios")
            comment = "" if level == "nada" else comments[level]
        op = {
            "key": r["key"],
            "op": "update" if r.get("action") == "adjust" else "create",
            "cloudId": model.cfg["jira"].get("cloud_id"),
            "issueIdOrKey": r["issue"],
            "started": common.jira_started(r["start"]),
            "timeSpent": common.jira_time_spent(minutes),
            "commentBody": comment.strip(),
        }
        if r.get("action") == "adjust":
            op["worklogId"] = str(by_id[r["ids"][0]].data["worklog_id"])
        result.append(op)
    return result


# --------------------------------------------------------------------------- edición

EDIT_HELP = """Operaciones de `plan.py edit` sobre el plan base. N = id de la fila (b3, g1) o su número
en el orden actual; todas las operaciones de una llamada usan la numeración previa a la llamada:

  confirm N [N...]            marca filas como confirmadas por el usuario
  unconfirm N [N...]          las vuelve a dejar pendientes
  set N campo=valor [...]     campos: issue, confidence, summary, warn, note, fixed (true|false),
                              sources (lista con comas), evidence (lista con comas)
  extend N ±MIN [start]       mueve el fin (o el inicio con `start`) y corre el borde del
                              vecino contiguo; ej. `extend 4 +10`, `extend 4 -5 start`
  time N HH:MM-HH:MM          fija el horario de N y corre los bordes de los vecinos contiguos
  merge A B                   suma la duración de B a A, elimina B y reacomoda las filas
                              entre ambos (sin salidas del checkin en el medio)
  move A after B              mueve A detrás de B y reacomoda las filas intermedias
  split N HH:MM [issue=KEY]   parte N en dos; la segunda parte queda pendiente
  absorb N [prev|next|both]   elimina N y reparte su tiempo en los vecinos (default both)
  unworked N                  convierte el bloque o hueco en 'no trabajado' (confirmado)
  assign N KEY                convierte un hueco en un bloque nuevo de KEY (pendiente)
  replace REF KEY             reemplaza una incidencia nueva (NEW-1) por su key real en todo el plan

Los comentarios de los bloques se cargan con `plan.py comments`, no con `edit`.

Toda fila cuyo horario cambia queda sin confirmar. Un worklog existente que se mueve pasa a
'adjust' (y vuelve a 'existing' si recupera su horario original)."""

EDITABLE = {"issue", "confidence", "summary", "warn", "note", "fixed"}
LIST_FIELDS = {"sources", "evidence"}


class EditError(Exception):
    pass


def _hm(dt: datetime) -> str:
    return common.fmt_hm(dt)


class Editor:
    """Aplica operaciones sobre un Model ya construido y deja plan.json consistente."""

    def __init__(self, model: Model):
        self.m = model
        self.slot = model.cfg["rules"]["slot_minutes"]
        self.tz = common.get_tz(model.cfg)
        self.by_n = {r.n: r for r in model.rows}
        self.by_id = {r.data["id"]: r for r in model.rows if r.data.get("id")}
        self.changed: list[Row] = []
        self.touched: set[str] = set()
        self.originals = {}
        for w in model.digest.get("worklogs", []):
            s = common.parse_iso(w["started"]).astimezone(self.tz).replace(second=0, microsecond=0)
            self.originals[str(w["id"])] = (s, s + timedelta(minutes=int(w["minutes"])))

    # -- helpers
    def row(self, n: str | int) -> Row:
        r = self.by_id.get(str(n))
        if r is None:
            try:
                r = self.by_n[int(n)]
            except (ValueError, KeyError):
                raise EditError(f"no existe la fila {n}")
        if r not in self.m.rows:
            raise EditError(f"la fila #{n} ya fue eliminada en esta llamada")
        return r

    def editable(self, r: Row) -> Row:
        if r.kind == "break":
            raise EditError(f"#{r.n} es una salida registrada en el checkin: no se modifica")
        return r

    def ordered(self) -> list[Row]:
        return sorted(self.m.rows, key=lambda x: (x.start, x.end))

    def neighbor(self, r: Row, side: str) -> Row | None:
        for o in self.m.rows:
            if o is r:
                continue
            if side == "next" and o.start == r.end:
                return o
            if side == "prev" and o.end == r.start:
                return o
        return None

    def mark(self, r: Row) -> None:
        if r not in self.changed:
            self.changed.append(r)

    def set_times(self, r: Row, start: datetime, end: datetime) -> None:
        self.editable(r)
        if end <= start:
            raise EditError(f"#{r.n} quedaría con duración {int((end - start).total_seconds() // 60)} min")
        if (start, end) == (r.start, r.end):
            return
        r.start, r.end = start, end
        r.data["start"], r.data["end"] = _hm(start), _hm(end)
        r.data["confirmed"] = False
        self.touched.add(r.data.get("id"))
        if r.kind == "block" and r.data.get("worklog_id"):
            orig = self.originals.get(str(r.data["worklog_id"]))
            r.data["action"] = "existing" if orig == (start, end) else "adjust"
        self.mark(r)

    def remove(self, r: Row) -> None:
        self.editable(r)
        if r.kind == "block" and r.data.get("worklog_id"):
            raise EditError(f"#{r.n} es un worklog existente: no se puede eliminar")
        self.touched.add(r.data.get("id"))
        lst = self.m.plan["blocks"] if r.kind == "block" else self.m.plan["gaps"]
        lst[:] = [x for x in lst if x is not r.data]
        self.m.rows.remove(r)
        if r in self.changed:
            self.changed.remove(r)

    def add(self, kind: str, data: dict, start: datetime, end: datetime) -> Row:
        data["start"], data["end"] = _hm(start), _hm(end)
        data.pop("id", None)
        (self.m.plan.setdefault("blocks" if kind == "block" else "gaps", [])).append(data)
        ensure_ids(self.m.plan)
        r = Row(kind, start, end, data)
        self.m.rows.append(r)
        self.mark(r)
        return r

    def minutes(self, value: str) -> int:
        try:
            mins = int(value)
        except ValueError:
            raise EditError(f"minutos inválidos: {value!r}")
        if mins % self.slot:
            raise EditError(f"{mins} min no es múltiplo de {self.slot}")
        return mins

    def at(self, value: str) -> datetime:
        try:
            return _parse_hm(value, self.m.day, self.tz)
        except ValueError as e:
            raise EditError(str(e))

    def reflow(self, segment: list[Row], start: datetime | None = None,
               durations: dict[int, timedelta] | None = None) -> None:
        """Reubica en orden y sin huecos las filas del segmento, conservando sus duraciones
        (salvo las indicadas en `durations`, por id de fila)."""
        if any(r.kind == "break" for r in segment):
            raise EditError("hay una salida del checkin en el medio: no se puede reordenar a través de ella")
        cursor = start or min(r.start for r in segment)
        for r in segment:
            dur = (durations or {}).get(id(r), r.end - r.start)
            self.set_times(r, cursor, cursor + dur)
            cursor += dur

    def segment(self, a: Row, b: Row) -> list[Row]:
        lo, hi = min(a.start, b.start), max(a.end, b.end)
        return [r for r in self.ordered() if r.start >= lo and r.end <= hi]

    # -- operaciones
    def op_confirm(self, *ns: str) -> None:
        for n in ns:
            r = self.row(n)
            if r.kind != "break":
                r.data["confirmed"] = True
                self.mark(r)

    def op_unconfirm(self, *ns: str) -> None:
        for n in ns:
            r = self.editable(self.row(n))
            r.data["confirmed"] = False
            self.mark(r)

    def op_set(self, n: str, *pairs: str) -> None:
        r = self.editable(self.row(n))
        if not pairs:
            raise EditError("set necesita campo=valor")
        for pair in pairs:
            if "=" not in pair:
                raise EditError(f"se espera campo=valor, no {pair!r}")
            k, v = pair.split("=", 1)
            if k in LIST_FIELDS:
                r.data[k] = [x.strip() for x in v.split(",") if x.strip()]
            elif k in EDITABLE:
                if k == "fixed":
                    if v not in ("true", "false"):
                        raise EditError("fixed=true o fixed=false")
                    r.data[k] = v == "true"
                    continue
                if k == "issue":
                    v = v.upper()
                    self.touched.add(r.data.get("id"))
                    if r.kind == "block" and r.data.get("worklog_id") and v != r.data.get("issue"):
                        raise EditError(f"#{r.n} es un worklog existente: no se cambia de incidencia")
                r.data[k] = v
            else:
                raise EditError(f"campo no editable: {k}")
        self.mark(r)

    def op_extend(self, n: str, delta: str, where: str = "end") -> None:
        r = self.editable(self.row(n))
        mins = self.minutes(delta.lstrip("+"))
        d = timedelta(minutes=mins)
        if where == "start":
            nb = self.neighbor(r, "prev")
            new_start = r.start - d
            if nb:
                self.set_times(nb, nb.start, new_start)
            elif self.m.range_start and new_start < self.m.range_start:
                raise EditError(f"#{r.n} empezaría antes de la entrada")
            self.set_times(r, new_start, r.end)
        elif where == "end":
            nb = self.neighbor(r, "next")
            new_end = r.end + d
            if nb:
                self.set_times(nb, new_end, nb.end)
            elif self.m.range_end and new_end > self.m.range_end:
                raise EditError(f"#{r.n} terminaría después del corte")
            self.set_times(r, r.start, new_end)
        else:
            raise EditError("extend: el tercer argumento solo puede ser 'start'")

    def op_time(self, n: str, span: str) -> None:
        r = self.editable(self.row(n))
        try:
            a, b = span.split("-")
        except ValueError:
            raise EditError("time espera HH:MM-HH:MM")
        start, end = self.at(a), self.at(b)
        prev, nxt = self.neighbor(r, "prev"), self.neighbor(r, "next")
        if prev and start != r.start:
            self.set_times(prev, prev.start, start)
        if nxt and end != r.end:
            self.set_times(nxt, end, nxt.end)
        self.set_times(r, start, end)

    def op_merge(self, a: str, b: str) -> None:
        ra, rb = self.editable(self.row(a)), self.editable(self.row(b))
        if ra is rb or ra.kind != "block" or rb.kind != "block":
            raise EditError("merge combina dos bloques distintos")
        seg = self.segment(ra, rb)
        if any(r.kind == "break" for r in seg):
            raise EditError("hay una salida del checkin entre ambos bloques: no se pueden combinar")
        start = seg[0].start
        new_dur = (ra.end - ra.start) + (rb.end - rb.start)
        for k in LIST_FIELDS:
            ra.data[k] = list(dict.fromkeys([*ra.data.get(k, []), *rb.data.get(k, [])]))
        self.remove(rb)
        seg = [r for r in seg if r is not rb]
        ra.data["confirmed"] = False
        self.mark(ra)
        self.reflow(seg, start, {id(ra): new_dur})

    def op_move(self, a: str, after: str, b: str) -> None:
        if after != "after":
            raise EditError("uso: move A after B")
        ra, rb = self.editable(self.row(a)), self.row(b)
        seg = self.segment(ra, rb)
        order = [r for r in seg if r is not ra]
        order.insert(order.index(rb) + 1, ra)
        self.reflow(order)

    def op_split(self, n: str, at: str, *rest: str) -> None:
        r = self.editable(self.row(n))
        if r.kind != "block":
            raise EditError("split solo aplica a bloques")
        t = self.at(at)
        if not r.start < t < r.end:
            raise EditError(f"{at} no está dentro de #{r.n}")
        new = copy.deepcopy(r.data)
        for k in ("worklog_id", "confirmed"):
            new.pop(k, None)
        new["action"] = "new"
        for pair in rest:
            k, _, v = pair.partition("=")
            if k != "issue":
                raise EditError("split solo acepta issue=KEY")
            new["issue"] = v.upper()
        end = r.end
        self.set_times(r, r.start, t)
        self.add("block", new, t, end)

    def op_absorb(self, n: str, where: str = "both") -> None:
        r = self.editable(self.row(n))
        prev, nxt = self.neighbor(r, "prev"), self.neighbor(r, "next")
        prev = prev if prev and prev.kind != "break" else None
        nxt = nxt if nxt and nxt.kind != "break" else None
        if where == "prev":
            nxt = None
        elif where == "next":
            prev = None
        elif where != "both":
            raise EditError("absorb: prev, next o both")
        if not prev and not nxt:
            raise EditError(f"#{r.n} no tiene vecinos que puedan absorberlo")
        total = r.minutes
        to_prev = total if not nxt else (0 if not prev else (total // 2) // self.slot * self.slot)
        start, end = r.start, r.end
        self.remove(r)
        split = start + timedelta(minutes=to_prev)
        if prev:
            self.set_times(prev, prev.start, split)
        if nxt:
            self.set_times(nxt, split, nxt.end)

    def op_unworked(self, n: str) -> None:
        r = self.editable(self.row(n))
        if r.kind == "gap":
            r.data["kind"], r.data["confirmed"] = "unworked", True
            self.mark(r)
            return
        start, end = r.start, r.end
        self.remove(r)
        self.add("gap", {"kind": "unworked", "confirmed": True}, start, end)

    def op_assign(self, n: str, key: str) -> None:
        r = self.editable(self.row(n))
        if r.kind != "gap":
            raise EditError("assign aplica a huecos; para bloques usar `set N issue=KEY`")
        start, end = r.start, r.end
        self.remove(r)
        self.add("block", {"issue": key.upper(), "action": "new", "confidence": "media",
                           "sources": [], "evidence": [], "confirmed": False}, start, end)

    def op_replace(self, ref: str, key: str) -> None:
        key = key.upper()
        ni = self.m.new_issue(ref)
        if ni is None:
            raise EditError(f"{ref} no está entre las incidencias nuevas")
        if ni.get("decision") == "create" and key not in self.m.plan.setdefault("created", []):
            # Recién creada: su cambio de estado se ofrece en una ronda aparte, después de cargar.
            self.m.plan["created"].append(key)
        for r in self.m.blocks:
            if r.data.get("issue") == ref:
                r.data["issue"] = key
                self.mark(r)
        self.m.plan["new_issues"] = [ni for ni in self.m.plan["new_issues"] if ni.get("ref") != ref]
        fu = self.m.plan.get("followup") or {}
        if ref in fu:
            fu[key] = fu.pop(ref)

    def apply(self, op: str) -> None:
        parts = shlex.split(op)
        if not parts:
            return
        fn = getattr(self, f"op_{parts[0]}", None)
        if fn is None:
            raise EditError(f"operación desconocida: {parts[0]}")
        try:
            fn(*parts[1:])
        except TypeError:
            raise EditError(f"argumentos inválidos para {parts[0]}: {op!r}")


def edit(plan: dict, digest: dict, cfg: dict, operations: list[str]) -> tuple[dict, list[int], Model]:
    """Aplica las operaciones sobre una copia del plan. Devuelve (plan nuevo, filas cambiadas, modelo validado).

    Si alguna operación falla, lanza EditError y no se modifica nada."""
    work = copy.deepcopy(plan)
    model = build_model(work, digest, cfg)
    ed = Editor(model)
    for op in operations:
        try:
            ed.apply(op)
        except EditError as e:
            raise EditError(f"{op!r}: {e}") from None
    if ed.touched and work.get("confirmed_rows"):
        # Una fila confirmada deja de estarlo si cambió alguno de sus bloques.
        work["confirmed_rows"] = [k for k in work["confirmed_rows"]
                                  if not any(i in ed.touched for i in variants.key_ids(k))]
    changed_data = [r.data for r in ed.changed]
    new_model = validate(build_model(work, digest, cfg))
    changed = [r.n for r in new_model.rows if any(r.data is d for d in changed_data)]
    return work, changed, new_model


NEW_ISSUE_KEYS = ("project", "type", "summary")


def add_new_issue(plan: dict, digest: dict, cfg: dict, spec: dict) -> tuple[dict, str, Model]:
    """Agrega un borrador de incidencia nueva (NEW-n) y le pasa los bloques indicados.

    `spec`: {project, type, summary, parent?, similar, fields, blocks: [ids]}. Lanza EditError
    si falta algo; los bloques que cambian de incidencia quedan sin confirmar."""
    missing = [k for k in NEW_ISSUE_KEYS if not str(spec.get(k) or "").strip()]
    if missing:
        raise EditError(f"faltan {', '.join(missing)}")
    blocks = [str(b) for b in spec.get("blocks") or []]
    if not blocks:
        raise EditError("hace falta `blocks` con los ids que pasan a la incidencia nueva")
    work = copy.deepcopy(plan)
    ensure_ids(work)
    by_id = {b.get("id"): b for b in work.get("blocks", [])}
    for b in blocks:
        if b not in by_id:
            raise EditError(f"no existe el bloque {b}")
        if by_id[b].get("action") != "new":
            raise EditError(f"{b} es un worklog existente: no se cambia de incidencia")
    used = [int(ni["ref"].split("-")[1]) for ni in work.get("new_issues", [])
            if str(ni.get("ref", "")).startswith("NEW-") and ni["ref"].split("-")[1].isdigit()]
    ref = f"NEW-{max(used, default=0) + 1}"
    ni = {"ref": ref, **{k: v for k, v in spec.items() if k not in ("blocks", "ref", "decision")}}
    ni.setdefault("similar", [])
    ni.setdefault("fields", [])
    work.setdefault("new_issues", []).append(ni)
    work, _, model = edit(work, digest, cfg, [f"set {b} issue={ref}" for b in blocks])
    return work, ref, model


def edit_summary(model: Model, changed: list[int]) -> str:
    out = []
    for r in model.rows:
        if r.n not in changed:
            continue
        mark = "✓" if is_confirmed(r) else "·"
        what = r.data.get("issue", "") if r.kind == "block" else ("no trabajado" if r.data.get("kind") == "unworked" else "hueco")
        out.append(f"{r.data.get('id')} {mark} {_hm(r.start)}–{_hm(r.end)} {what}".rstrip())
    reviewable = [r for r in model.rows if r.kind != "break"]
    pend = [r.data.get("id", f"#{r.n}") for r in pending(model)]
    out.append(f"Confirmados {sum(is_confirmed(r) for r in reviewable)}/{len(reviewable)}"
               + (f" · pendientes: {' '.join(pend)}" if pend else " · todo confirmado"))
    out += [f"✗ {e}" for e in model.errors] + [f"! {w}" for w in model.warnings]
    return "\n".join(out)


# --------------------------------------------------------------------------- revisión


def fetch_meta(cfg: dict, env: dict, keys: list[str], path: Path, refresh: bool = False,
               today: date | None = None) -> dict:
    """Estado y transiciones disponibles de cada incidencia.

    Se cachea en <state>/<fecha>/jira_meta.json solo para las rondas de la misma sesión: una caché
    que se trajo otro día se descarta."""
    today = (today or datetime.now(common.get_tz(cfg)).date()).isoformat()
    stored = {} if refresh else (common.read_json(path, {}) or {})
    cache = dict(stored.get("issues") or {}) if stored.get("fetched") == today else {}
    missing = [k for k in keys if k not in cache or cache[k].get("error")]
    if missing:
        token = env.get("JIRA_API_TOKEN")
        if token:
            client = jira.JiraClient(cfg["jira"]["site"], cfg["jira"]["email"], token)
            cache.update(jira.fetch_issue_meta(client, missing))
        else:
            cache.update({k: {"error": "falta JIRA_API_TOKEN"} for k in missing})
        common.write_json(path, {"fetched": today, "issues": cache})
    return {k: cache[k] for k in keys if k in cache}


def meta_keys(model: Model) -> list[str]:
    new_refs = {ni.get("ref") for ni in model.plan.get("new_issues", [])}
    keys = dict.fromkeys(r.data.get("issue") for r in model.blocks)
    return [k for k in keys if k and k not in new_refs and not page.misc_label(model.cfg, k)]


def describe_row(model: Model, r: dict) -> str:
    when = f"{common.fmt_hm(r['start'])}–{common.fmt_hm(r['end'])}"
    if r["kind"] == "block":
        cand = model.candidate(r["issue"]) or {}
        label = page.misc_label(model.cfg, r["issue"]) or cand.get("summary", "")
        return f"{r['key']} · {when} · {r['issue']} {label}".rstrip()
    if r["kind"] == "gap":
        return f"{r['key']} · {when} · hueco {r.get('gap_kind')}"
    return f"{r['key']} · {when} · {r['kind']}"


def missing_report(model: Model, vs: dict[str, dict]) -> list[str]:
    rows = missing_comments(model, vs)
    if not rows:
        return []
    out = [f"Faltan comentarios ({'/'.join(LEVELS)}) — cargarlos con `plan.py comments`:"]
    for r in rows:
        out.append(f"  {describe_row(model, r)} ({common.fmt_duration(int((r['end'] - r['start']).total_seconds() // 60))})")
        src = r.get("src") or {}
        partial = any(b and src.get(i, b.minutes) != b.minutes for i in r["ids"] for b in [find_row(model, i)])
        if len(r["ids"]) > 1 or partial:
            for i in r["ids"]:
                b = find_row(model, i)
                text = ((b.data.get("comments") or {}).get("normal") or "(sin comentario)") if b else "?"
                used = src.get(i, b.minutes if b else 0)
                amount = common.fmt_duration(used) if not b or used == b.minutes else \
                    f"{common.fmt_duration(used)} de {common.fmt_duration(b.minutes)}"
                out.append(f"      {i} ({amount}): {text}")
    return out


def set_comments(plan: dict, data: dict) -> list[str]:
    """Carga los tres niveles de comentario por key de fila (b3 o b2+b5). Devuelve errores."""
    errors = []
    ids = {b.get("id"): b for b in plan.get("blocks", [])}
    for key, levels in data.items():
        if not isinstance(levels, dict) or not all(isinstance(levels.get(lv), str) and levels[lv].strip() for lv in LEVELS):
            errors.append(f"{key}: hacen falta los tres niveles ({', '.join(LEVELS)}) con texto")
            continue
        clean = {lv: " ".join(levels[lv].split()) for lv in LEVELS}
        parts = key.split("+")
        if any(p not in ids for p in parts):
            errors.append(f"{key}: no existe el bloque {next(p for p in parts if p not in ids)}")
        elif len(parts) == 1:
            ids[key]["comments"] = clean
        else:
            plan.setdefault("group_comments", {})[variants.row_key(parts)] = clean
    return errors


def apply_review(plan: dict, digest: dict, cfg: dict, raw: Path, st: dict) -> tuple[dict, list[str]]:
    """Aplica el estado que guardó la página (db del artifact). Devuelve (plan nuevo, reporte)."""
    work = copy.deepcopy(plan)
    rnd = work.get("round", 1)
    report = []
    if st.get("round") != rnd:
        report.append(f"! el estado es de la ronda {st.get('round')} y el plan está en la {rnd}")
    old_model = validate(build_model(copy.deepcopy(work), digest, cfg))
    old_rows = {}
    for v in compute_variants(old_model, raw).values():
        for r in v["rows"]:
            old_rows.setdefault(r["key"], r)

    # 1. Cambios de estructura, de a uno para que un error no frene el resto.
    operations = [f"absorb {i}" for i, on in (st.get("absorb") or {}).items() if on]
    requested: dict[str, list[str]] = {}
    for bid, target in (st.get("reassign") or {}).items():
        target = str(target or "").strip()
        if target.startswith("new:"):
            requested.setdefault(target[4:], []).append(bid)
        elif target:
            operations.append(f"set {bid} issue={target}")
    for gid, g in (st.get("gaps") or {}).items():
        act = (g or {}).get("action")
        if act == "assign" and g.get("issue"):
            operations.append(f"assign {gid} {g['issue']}")
        elif act in ("absorb", "unworked"):
            operations.append(f"{act} {gid}")
    for ni in work.get("new_issues", []):
        d = (st.get("new_issues") or {}).get(ni.get("ref")) or {}
        if d.get("decision") == "existing" and d.get("existing_key"):
            operations.append(f"replace {ni['ref']} {d['existing_key']}")
    for op in operations:
        try:
            work, _, _ = edit(work, digest, cfg, [op])
            report.append(f"✓ {op}")
        except EditError as e:
            report.append(f"✗ {e}")

    # 2. Confirmaciones, niveles, modos, incidencias nuevas y seguimiento.
    by_id = {x.get("id"): x for x in [*work.get("blocks", []), *work.get("gaps", [])]}
    rows_ok = set(work.get("confirmed_rows") or [])
    for key, on in (st.get("confirmed") or {}).items():
        (rows_ok.add if on else rows_ok.discard)(key)
        if key in by_id and by_id[key].get("action") != "existing":
            by_id[key]["confirmed"] = bool(on)
    work["confirmed_rows"] = sorted(rows_ok)
    levels = {k: v for k, v in (st.get("levels") or {}).items() if v in common.COMMENT_LEVELS}
    work.setdefault("levels", {}).update(levels)
    if isinstance(st.get("modes"), dict):
        work["modes"] = {"group": bool(st["modes"].get("group")), "lunch": bool(st["modes"].get("lunch"))}
    for ni in work.get("new_issues", []):
        d = (st.get("new_issues") or {}).get(ni.get("ref")) or {}
        if d.get("decision"):
            ni["decision"] = d["decision"]
        for f in ni.get("fields", []):
            if f.get("key") in (d.get("fields") or {}):
                f["value"] = d["fields"][f["key"]]
    if isinstance(st.get("followup"), dict):
        work["followup"] = {k: v for k, v in st["followup"].items() if isinstance(v, dict)}
    work["round"] = rnd + 1

    if requested:
        report.append("Incidencias nuevas pedidas por el usuario (armá cada borrador como en la fase 2 "
                      "y cargalo con `plan.py new-issue`, con estos bloques):")
        hints = st.get("new_requests") or {}
        for n, bids in requested.items():
            parts = []
            for bid in sorted(bids, key=variants.block_id_order):
                r = find_row(old_model, bid)
                parts.append(f"{bid} {_hm(r.start)}–{_hm(r.end)} (hoy en {r.data.get('issue')})" if r else bid)
            hint = ((hints.get(n) or {}).get("hint") or "").strip()
            report.append(f"  nueva {n} → {', '.join(parts)}" + (f": «{hint}»" if hint else " (sin indicaciones: deducila de la evidencia)"))

    notes = {k: v.strip() for k, v in (st.get("notes") or {}).items() if isinstance(v, str) and v.strip()}
    for ref, d in (st.get("new_issues") or {}).items():
        if (d or {}).get("note", "").strip():
            notes[f"nueva {ref}"] = d["note"].strip()
    if notes or (st.get("global_note") or "").strip():
        report.append("Comentarios del usuario (interpretarlos y aplicarlos con edit/comments):")
        for k, v in notes.items():
            ctx = describe_row(old_model, old_rows[k]) if k in old_rows else k
            report.append(f"  [{ctx}] {v}")
        if (st.get("global_note") or "").strip():
            report.append(f"  [general] {st['global_note'].strip()}")
    report.append(f"ACCIÓN: {st.get('action') or 'review'}")
    return work, report


def unwrap_state(st) -> dict:
    """El documento puede venir solo o envuelto con su metadata ({"data": {...}, "version": N})."""
    if not isinstance(st, dict):
        return {}
    if "round" not in st and isinstance(st.get("data"), dict):
        return st["data"]
    return st


def load_checklist(model: Model, vs: dict[str, dict], followup_only: bool = False) -> list[str]:
    """Lo que falta hacer en Jira después de una acción `load` (o `apply` en la ronda de seguimiento), en orden."""
    out = []
    creates = [] if followup_only else [ni for ni in model.plan.get("new_issues", []) if ni.get("decision") == "create"]
    for ni in creates:
        fields = ", ".join(f"{f.get('name', f.get('key'))}={f.get('value')!r}" for f in ni.get("fields", [])
                           if f.get("value") not in (None, ""))
        out.append(f"  crear {ni['ref']}: [{ni.get('project')}/{ni.get('type')}] {ni.get('summary')}"
                   + (f" (padre {ni['parent']})" if ni.get("parent") else "") + (f" · {fields}" if fields else ""))
    skipped = [] if followup_only else [ni["ref"] for ni in model.plan.get("new_issues", [])
                                         if ni.get("decision") not in ("create",)]
    if skipped:
        out.append(f"  ! incidencias nuevas sin decisión de crear: {', '.join(skipped)}")
    for key, f in (model.plan.get("followup") or {}).items():
        if f.get("transition_id"):
            extra = f" · campos {f['fields']}" if f.get("fields") else ""
            out.append(f"  transición {key}: {f.get('transition') or f['transition_id']} "
                       f"(id {f['transition_id']}){extra}")
        if f.get("publish") and (f.get("comment") or "").strip():
            out.append(f"  comentario de resolución en {key}: {' '.join(f['comment'].split())}")
    return out


def match_transition(transitions: list[dict], wanted: str) -> dict | None:
    """Transición por id, por estado destino o por nombre (sin distinguir mayúsculas)."""
    w = wanted.strip().casefold()
    for t in transitions:
        if t["id"] == wanted.strip():
            return t
    for attr in ("to", "name"):
        for t in transitions:
            if str(t.get(attr) or "").casefold() == w:
                return t
    return None


def followup_round(plan: dict, meta: dict, suggest: list[str]) -> list[str]:
    """Prepara la ronda de seguimiento de las incidencias creadas: las transiciones sugeridas
    quedan preseleccionadas. Devuelve el reporte con el estado y las transiciones de cada una."""
    keys = plan.get("created") or []
    wanted = {}
    for item in suggest:
        k, _, v = item.partition("=")
        wanted[k.strip().upper()] = v
    plan["stage"] = "followup"
    plan["followup"] = {}
    out = []
    for k in keys:
        m = meta.get(k) or {}
        if m.get("error"):
            out.append(f"! {k}: sin estado/transiciones ({m['error'][:120]})")
            continue
        out.append(f"{k} · {m.get('status') or '?'} · transiciones: "
                   + ("; ".join(f"{t['id']}: {t['name']} → {t['to']}" for t in m.get("transitions", [])) or "ninguna"))
        if k in wanted:
            t = match_transition(m.get("transitions", []), wanted[k])
            if t:
                plan["followup"][k] = {"transition_id": t["id"], "transition": t["name"], "to": t["to"], "fields": {}}
                out.append(f"  sugerida: {t['name']} → {t['to']}")
            else:
                out.append(f"  ! la sugerencia {wanted[k]!r} no coincide con ninguna transición disponible")
    for k in wanted:
        if k not in keys:
            out.append(f"! {k} no es una incidencia creada en esta sesión")
    return out


# --------------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="día (AAAA-MM-DD); por defecto hoy")
    ap.add_argument("--plan", help="ruta a plan.json (default: <state>/<fecha>/plan.json)")
    ap.add_argument("--digest", help="ruta a digest.json (default: <state>/<fecha>/digest.json)")
    ap.add_argument("--config", help="ruta a config.json")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    p_build = sub.add_parser("build", help="variantes + chequeos + review.html")
    p_build.add_argument("--note", help="mensaje para el usuario que se muestra arriba de la página")
    p_build.add_argument("--refresh-jira", action="store_true", help="volver a traer estados y transiciones")
    p_build.add_argument("--no-jira", action="store_true", help=argparse.SUPPRESS)
    p_build.add_argument("--followup", action="store_true",
                         help="ronda de seguimiento: cambio de estado de las incidencias creadas")
    p_build.add_argument("--suggest", action="append", default=[], metavar="KEY=TRANSICIÓN",
                         help="con --followup: transición a preseleccionar (id, estado destino o nombre)")
    sub.add_parser("new-issue", help="agrega un borrador de incidencia nueva desde stdin (ver arriba)")
    sub.add_parser("comments", help="carga comentarios desde stdin: {\"b3\": {breve, normal, detallado}, ...}")
    p_rev = sub.add_parser("review", help="aplica el estado de la página leído de la db del artifact")
    p_rev.add_argument("file", nargs="?", help="JSON guardado con ArtifactData (out_dir); sin archivo, lee stdin")
    p_exp = sub.add_parser("expand")
    p_exp.add_argument("ref", help="id (b3, g1) o número de fila")
    sub.add_parser("ops")
    p_url = sub.add_parser("url", help="guarda la URL del artifact publicado")
    p_url.add_argument("url")
    p_edit = sub.add_parser("edit", description=EDIT_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    p_edit.add_argument("operations", nargs="+", help="una operación por argumento (ver --help)")
    args = ap.parse_args(argv)

    try:
        cfg = common.load_config(Path(args.config) if args.config else None)
    except (common.ConfigMissing, common.ConfigError) as e:
        print(e, file=sys.stderr)
        return 3
    day = common.parse_day(args.date, common.get_tz(cfg))
    sdir = common.state_dir(day, create=False)
    plan_path = Path(args.plan) if args.plan else sdir / "plan.json"
    digest_path = Path(args.digest) if args.digest else sdir / "digest.json"
    raw = plan_path.parent / "raw"
    plan = common.read_json(plan_path)
    if plan is None:
        print(f"No existe {plan_path}", file=sys.stderr)
        return 3
    digest = common.read_json(digest_path, {}) or {}
    digest.setdefault("date", day.isoformat())
    plan.setdefault("date", day.isoformat())
    if ensure_ids(plan):
        common.write_json(plan_path, plan)
    model = validate(build_model(plan, digest, cfg))

    if args.cmd == "validate":
        for e in model.errors:
            print(f"✗ {e}")
        for w in model.warnings:
            print(f"! {w}")
        if not model.errors:
            print(f"OK ({len(model.blocks)} bloques, {len(model.warnings)} advertencias)")
        return 1 if model.errors else 0
    if args.cmd == "expand":
        print(expand(model, args.ref, raw))
        return 0
    if args.cmd == "url":
        plan["artifact_url"] = args.url
        common.write_json(plan_path, plan)
        print(f"URL guardada: {args.url}")
        return 0
    if args.cmd == "edit":
        try:
            new_plan, changed, new_model = edit(plan, digest, cfg, args.operations)
        except EditError as e:
            print(f"✗ {e} (no se guardó nada)")
            return 1
        common.write_json(plan_path, new_plan)
        print(edit_summary(new_model, changed))
        return 1 if new_model.errors else 0
    if args.cmd == "comments":
        try:
            data = json.loads(sys.stdin.read())
        except json.JSONDecodeError as e:
            print(f"✗ JSON inválido: {e}")
            return 1
        errors = set_comments(plan, data if isinstance(data, dict) else {})
        if errors:
            print("\n".join(f"✗ {e}" for e in errors) + "\n(no se guardó nada)")
            return 1
        common.write_json(plan_path, plan)
        model = validate(build_model(plan, digest, cfg))
        rest = missing_report(model, compute_variants(model, raw))
        print("\n".join(rest) if rest else f"OK ({len(data)} filas con comentarios; no falta ninguno)")
        return 0
    if args.cmd == "new-issue":
        try:
            spec = json.loads(sys.stdin.read())
            new_plan, ref, new_model = add_new_issue(plan, digest, cfg, spec if isinstance(spec, dict) else {})
        except json.JSONDecodeError as e:
            print(f"✗ JSON inválido: {e}")
            return 1
        except EditError as e:
            print(f"✗ {e} (no se guardó nada)")
            return 1
        common.write_json(plan_path, new_plan)
        print(f"{ref}: {spec['summary']} · bloques {', '.join(spec['blocks'])}")
        for e in new_model.errors:
            print(f"✗ {e}")
        return 1 if new_model.errors else 0
    if args.cmd == "review":
        try:
            st = json.loads(Path(args.file).read_text() if args.file else sys.stdin.read())
        except (OSError, json.JSONDecodeError) as e:
            print(f"✗ no se pudo leer el estado: {e}")
            return 1
        st = unwrap_state(st)
        # El aviso a Claude sale en paralelo con el guardado: un estado de otra ronda o sin `sent`
        # todavía no es el que mandó el usuario.
        rnd = plan.get("round", 1)
        if st.get("round") != rnd or not st.get("sent"):
            what = (f"es de la ronda {st.get('round')} y el plan está en la {rnd}" if st.get("round") != rnd
                    else "todavía no dice que se envió")
            print(f"✗ el estado guardado {what}: volvé a leerlo en unos segundos (no se aplicó nada)")
            return 1
        followup_stage = plan.get("stage") == "followup"
        new_plan, report = apply_review(plan, digest, cfg, raw, st if isinstance(st, dict) else {})
        common.write_json(plan_path, new_plan)
        model = validate(build_model(new_plan, digest, cfg))
        vs = compute_variants(model, raw)
        out = list(report)
        if followup_stage:
            # Después de cargar, el digest ya trae los worklogs nuevos: el plan no se vuelve a validar.
            if st.get("action") in ("apply", "apply_more"):
                out.append("Pendiente en Jira, en orden:")
                out += load_checklist(model, vs, followup_only=True) or ["  (nada: no se eligió ninguna transición ni comentario)"]
            print("\n".join(out))
            return 0
        out += [f"✗ {e}" for e in model.errors]
        out += missing_report(model, vs)
        if st.get("action") == "load":
            try:
                n_ops = len(ops(model, vs))
                out.append(f"Listo para cargar: {n_ops} operaciones de worklog. Pendiente en Jira, en orden:")
                out += load_checklist(model, vs) or ["  (nada más que los worklogs)"]
            except ValueError as e:
                out.append(f"✗ no se puede cargar todavía: {e}")
        print("\n".join(out))
        return 0
    if args.cmd == "ops":
        vs = compute_variants(model, raw)
        try:
            print(json.dumps(ops(model, vs), ensure_ascii=False, indent=2))
        except ValueError as e:
            print(f"✗ {e}", file=sys.stderr)
            for err in model.errors:
                print(f"✗ {err}", file=sys.stderr)
            return 1
        return 0
    if args.cmd == "build" and args.followup:
        keys = plan.get("created") or []
        if not keys:
            print("No hay incidencias creadas en esta sesión: no hace falta la ronda de seguimiento.")
            return 1
        meta = {} if args.no_jira else fetch_meta(cfg, common.load_env(), keys,
                                                   plan_path.parent / "jira_meta.json", refresh=True)
        report = followup_round(plan, meta, args.suggest)
        plan["note"] = args.note or None
        common.write_json(plan_path, plan)
        model = validate(build_model(plan, digest, cfg))
        vs = compute_variants(model, raw)
        data = page.build_data(model, vs, meta, load_raw_events(raw), variant_name(modes(plan, cfg)), [],
                               confirmed_keys(model, vs), stage="followup", followup_keys=keys)
        out_path = plan_path.parent / "review.html"
        out_path.write_text(page.render_html(data))
        print(f"review.html: {out_path} (ronda {plan['round']}, seguimiento de {', '.join(keys)})")
        print("\n".join(report))
        return 0
    if args.cmd == "build":
        plan["note"] = args.note or None
        plan.setdefault("round", 1)
        plan["stage"] = "review"
        common.write_json(plan_path, plan)
        model = validate(build_model(plan, digest, cfg))
        if model.errors:
            print("\n".join(f"✗ {e}" for e in model.errors) + "\n(no se generó la página)")
            return 1
        vs = compute_variants(model, raw)
        v_err = [f"✗ {name}: {e}" for name, v in vs.items() for e in v["errors"]]
        missing = missing_report(model, vs)
        if v_err or missing:
            print("\n".join(v_err + missing) + "\n(no se generó la página)")
            return 1
        meta = {} if args.no_jira else fetch_meta(cfg, common.load_env(), meta_keys(model),
                                                   plan_path.parent / "jira_meta.json", args.refresh_jira)
        current = variant_name(modes(plan, cfg))
        data = page.build_data(model, vs, meta, load_raw_events(raw), current, model.warnings,
                               confirmed_keys(model, vs))
        out_path = plan_path.parent / "review.html"
        out_path.write_text(page.render_html(data))
        print(f"review.html: {out_path} (ronda {plan['round']}, variante inicial {current})")
        for name, v in vs.items():
            tot = " · ".join(f"{k} {common.fmt_duration(m)}" for k, m in sorted(v["totals"].items(), key=lambda kv: -kv[1]))
            extra = ""
            lu = v["lunch"]
            if lu and lu["mode"] == "discount":
                disc = ", ".join(f"{k} {common.fmt_duration(m)}" for k, m in lu["discounts"].items())
                extra = f" · almuerzo {common.fmt_hm(lu['start'])}–{common.fmt_hm(lu['end'])} (descontado: {disc})"
            elif lu and lu["mode"] == "gap":
                extra = f" · almuerzo {common.fmt_hm(lu['start'])}–{common.fmt_hm(lu['end'])} (en el hueco {lu['gap_id']})"
            n_blocks = sum(r["kind"] == "block" for r in v["rows"])
            print(f"  {name:<12} {n_blocks} bloques · {tot}{extra}{' · override' if v['override'] else ''}")
            for w in v["warnings"]:
                print(f"    ! {w}")
        for w in model.warnings:
            print(f"! {w}")
        for k, m in meta.items():
            if m.get("error"):
                print(f"! {k}: sin estado/transiciones ({m['error'][:120]})")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
