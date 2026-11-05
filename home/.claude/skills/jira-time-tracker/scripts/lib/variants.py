"""Variantes del plan del día: agrupar y descontar almuerzo.

A partir del plan base (el que escribe el agente) se derivan cuatro variantes, todas con el
mismo total por incidencia salvo el descuento del almuerzo:

  base         el plan tal cual
  lunch        base con el almuerzo descontado
  group        base con los bloques de cada incidencia agrupados
  group+lunch  agrupar sobre la variante con almuerzo

Partes fijas (no se mueven nunca): salidas del checkin, huecos, worklogs existentes
(`existing`/`adjust`) y bloques marcados `fixed` (reuniones). El resto del día son tramos
libres: secuencias de bloques nuevos que se pueden reordenar dentro de su tramo y, al
agrupar, intercambiar tiempo entre tramos.

Almuerzo (`review.lunch_minutes` dentro de `review.lunch_window`):
  1. Si un hueco cubre el almuerzo completo dentro de la ventana, se usa ese hueco y no se
     descuenta nada.
  2. Si no, se elige la ventana de menor actividad (minutos de eventos de raw/) que caiga
     entera en un tramo libre. Esos minutos se descuentan de los bloques que la cubren,
     repartidos según cuánto cubre cada uno.
  3. El hueco del almuerzo se ubica en la ventana configurada, preferentemente en un borde
     entre bloques, y pasa a ser una parte fija.

Agrupar con almuerzo: la mañana y la tarde se agrupan por separado. Se intenta no repetir
incidencias dentro de cada mitad, pero nunca se mueve trabajo de un lado al otro del almuerzo.

Las variantes se pueden reemplazar a mano con `variant_overrides` en plan.json; se usan solo
si pasan los mismos chequeos que las automáticas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from lib import common

VARIANTS = ("base", "lunch", "group", "group+lunch")


@dataclass
class Piece:
    """Tiempo de trabajo movible de una incidencia.

    `src` dice cuántos minutos aporta cada bloque base (en orden cronológico). Al mover tiempo
    entre tramos se mueven minutos de bloques concretos, así cada fila sabe de dónde sale."""

    issue: str
    src: dict[str, int]

    @property
    def minutes(self) -> int:
        return sum(self.src.values())

    @property
    def ids(self) -> list[str]:
        return [i for i, m in self.src.items() if m > 0]


def add_src(target: dict[str, int], extra: dict[str, int]) -> None:
    """Suma minutos por bloque y deja `target` en orden cronológico (por id)."""
    merged = dict(target)
    for i, m in extra.items():
        merged[i] = merged.get(i, 0) + m
    target.clear()
    target.update({i: merged[i] for i in sorted(merged, key=block_id_order)})


def take_src(src: dict[str, int], amount: int, from_end: bool) -> tuple[dict[str, int], dict[str, int]]:
    """Separa `amount` minutos de `src`, tomando bloques enteros desde un extremo (como mucho
    parte uno). Devuelve (lo tomado, lo que queda), ambos en orden cronológico."""
    order = list(src)[::-1] if from_end else list(src)
    taken, left = {}, dict(src)
    need = amount
    for i in order:
        if need <= 0:
            break
        t = min(need, left[i])
        taken[i] = t
        left[i] -= t
        need -= t
    taken = {i: taken[i] for i in src if taken.get(i)}
    left = {i: m for i, m in left.items() if m > 0}
    return taken, left


@dataclass
class Fixed:
    kind: str  # block | gap | break | lunch
    start: datetime
    end: datetime
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Segment:
    start: datetime
    end: datetime
    pieces: list[Piece]


def block_id_order(i: str) -> tuple[int, str]:
    digits = "".join(c for c in i if c.isdigit())
    return (int(digits) if digits else 0, i)


def row_key(ids: list[str]) -> str:
    return "+".join(sorted(dict.fromkeys(ids), key=block_id_order))


def is_fixed_block(data: dict) -> bool:
    return data.get("action") in ("existing", "adjust") or bool(data.get("fixed"))


# --------------------------------------------------------------------------- layout


def base_layout(model) -> list:
    items: list = []
    seg: Segment | None = None
    for r in sorted(model.rows, key=lambda x: (x.start, x.end)):
        if r.kind == "block" and not is_fixed_block(r.data):
            if seg is None or seg.end != r.start:
                seg = Segment(r.start, r.end, [])
                items.append(seg)
            seg.pieces.append(Piece(r.data.get("issue", "?"), {r.data["id"]: r.minutes}))
            seg.end = r.end
        else:
            seg = None
            items.append(Fixed(r.kind, r.start, r.end, r.data))
    return items


def piece_spans(seg: Segment) -> list[tuple[datetime, datetime]]:
    out, cur = [], seg.start
    for p in seg.pieces:
        out.append((cur, cur + timedelta(minutes=p.minutes)))
        cur += timedelta(minutes=p.minutes)
    return out


def to_rows(items: list) -> list[dict]:
    rows = []
    for it in items:
        if isinstance(it, Segment):
            for p, (s, e) in zip(it.pieces, piece_spans(it)):
                rows.append({"kind": "block", "start": s, "end": e, "issue": p.issue, "ids": p.ids,
                             "src": {i: m for i, m in p.src.items() if m > 0},
                             "key": row_key(p.ids), "fixed": False, "action": "new"})
        elif it.kind == "block":
            mins = int((it.end - it.start).total_seconds() // 60)
            rows.append({"kind": "block", "start": it.start, "end": it.end, "issue": it.data.get("issue"),
                         "ids": [it.data["id"]], "src": {it.data["id"]: mins}, "key": it.data["id"], "fixed": True,
                         "action": it.data.get("action")})
        elif it.kind == "gap":
            rows.append({"kind": "gap", "start": it.start, "end": it.end, "id": it.data.get("id"),
                         "key": it.data.get("id"), "gap_kind": it.data.get("kind", "open")})
        elif it.kind == "lunch":
            rows.append({"kind": "lunch", "start": it.start, "end": it.end, "key": "lunch"})
        else:
            rows.append({"kind": "break", "start": it.start, "end": it.end, "key": f"break@{common.fmt_hm(it.start)}"})
    return rows


def unique_keys(rows: list[dict]) -> list[dict]:
    """Cada fila de una variante tiene una key única (la confirmación y el nivel de comentario
    son por fila). `comment_key` es la key sin sufijo: dos partes del mismo bloque (por ejemplo,
    partido por el almuerzo) comparten el texto del comentario."""
    seen: dict[str, int] = {}
    for r in rows:
        if r["kind"] != "block":
            continue
        base = r["key"]
        r["comment_key"] = base
        seen[base] = seen.get(base, 0) + 1
        if seen[base] > 1:
            r["key"] = f"{base}#{seen[base]}"
    return rows


def key_ids(key: str) -> list[str]:
    return key.split("#")[0].split("+")


# --------------------------------------------------------------------------- almuerzo


def _hm_on(day, value: str, tz) -> datetime:
    h, m = (int(x) for x in value.split(":"))
    return datetime(day.year, day.month, day.day, h, m, tzinfo=tz)


def activity_score(start: datetime, end: datetime, events: list[tuple[datetime, datetime]]) -> int:
    """Minutos de actividad dentro de [start, end); un evento puntual cuenta como 1 minuto."""
    total = 0
    for s, e in events:
        if s == e:
            total += 1 if start <= s < end else 0
        else:
            ov = (min(e, end) - max(s, start)).total_seconds() / 60
            total += max(0, int(round(ov)))
    return total


def apply_lunch(items: list, events: list[tuple[datetime, datetime]], cfg: dict, day, tz) -> tuple[list, dict]:
    rv, slot, min_block = cfg["review"], cfg["rules"]["slot_minutes"], cfg["rules"]["min_block_minutes"]
    L = timedelta(minutes=rv["lunch_minutes"])
    ws, we = (_hm_on(day, v, tz) for v in rv["lunch_window"])
    step = timedelta(minutes=slot)

    # 1. Un hueco que ya cubre el almuerzo dentro de la ventana.
    for idx, it in enumerate(items):
        if isinstance(it, Fixed) and it.kind == "gap":
            s, e = max(it.start, ws), min(it.end, we)
            if e - s >= L:
                parts = []
                if it.start < s:
                    parts.append(Fixed("gap", it.start, s, it.data))
                parts.append(Fixed("lunch", s, s + L))
                if s + L < it.end:
                    parts.append(Fixed("gap", s + L, it.end, it.data))
                info = {"mode": "gap", "gap_id": it.data.get("id"), "start": s, "end": s + L, "discounts": {}}
                return items[:idx] + parts + items[idx + 1:], info

    # 2. Ventana de menor actividad, entera dentro de un tramo libre.
    best = None
    p = ws
    while p + L <= we:
        for si, seg in enumerate(items):
            if not (isinstance(seg, Segment) and seg.start <= p and p + L <= seg.end):
                continue
            cuts, ok = {}, True
            for pi, (s, e) in enumerate(piece_spans(seg)):
                ov = int((min(e, p + L) - max(s, p)).total_seconds() // 60)
                if ov > 0:
                    rest = seg.pieces[pi].minutes - ov
                    if 0 < rest < min_block:
                        ok = False
                    cuts[pi] = (int((max(s, p) - s).total_seconds() // 60), ov)
            if ok:
                cand = (activity_score(p, p + L, events), p, si, cuts)
                if best is None or cand[:2] < best[:2]:
                    best = cand
        p += step
    if best is None:
        return items, {"mode": "none", "reason": "no hay una ventana libre de reuniones, worklogs, huecos o "
                                                  "salidas para ubicar el almuerzo", "discounts": {}}
    _, p, si, cuts = best
    seg = items[si]
    discounts: dict[str, int] = {}
    cut_ids: dict[str, int] = {}
    pieces = []
    for pi, pc in enumerate(seg.pieces):
        src = dict(pc.src)
        if pi in cuts:
            offset, cut = cuts[pi]
            discounts[pc.issue] = discounts.get(pc.issue, 0) + cut
            head, rest = take_src(src, offset, from_end=False)
            removed, tail = take_src(rest, cut, from_end=False)
            add_src(cut_ids, removed)
            src = dict(head)
            add_src(src, tail)
            src = {i: src[i] for i in pc.src if src.get(i)}
        if src:
            pieces.append(Piece(pc.issue, src))

    # 3. Ubicar el hueco: en un borde entre bloques o, si no hay, partiendo un bloque.
    lo, hi = max(ws, seg.start), min(we, seg.end)
    bounds, cur = [], seg.start
    for i in range(len(pieces) + 1):
        bounds.append((i, cur))
        if i < len(pieces):
            cur += timedelta(minutes=pieces[i].minutes)
    valid = [(abs((b - p).total_seconds()), i, b) for i, b in bounds if lo <= b and b + L <= hi]
    if valid:
        _, i, at = min(valid)
        before, after = pieces[:i], pieces[i:]
    else:
        options = []
        cur = seg.start
        for j, pc in enumerate(pieces):
            q = common.round_up(max(cur, lo), slot)
            while q + L <= hi and q < cur + timedelta(minutes=pc.minutes):
                a = int((q - cur).total_seconds() // 60)
                if a >= min_block and pc.minutes - a >= min_block:
                    options.append((abs((q - p).total_seconds()), j, q, a))
                q += step
            cur += timedelta(minutes=pc.minutes)
        if not options:
            return items, {"mode": "none", "reason": "no se pudo ubicar el almuerzo sin dejar bloques de menos del mínimo",
                           "discounts": {}}
        _, j, at, a = min(options)
        pc = pieces[j]
        first, second = take_src(pc.src, a, from_end=False)
        before = pieces[:j] + [Piece(pc.issue, first)]
        after = [Piece(pc.issue, second)] + pieces[j + 1:]
    new = []
    if before:
        new.append(Segment(seg.start, at, before))
    new.append(Fixed("lunch", at, at + L))
    if after:
        new.append(Segment(at + L, seg.end, after))
    info = {"mode": "discount", "window": (p, p + L), "start": at, "end": at + L,
            "discounts": discounts, "cut_ids": cut_ids}
    return items[:si] + new + items[si + 1:], info


# --------------------------------------------------------------------------- agrupar


def apply_group(items: list, cfg: dict) -> list:
    """Agrupa por incidencia. Si hay almuerzo, la mañana y la tarde se agrupan por separado:
    no se mueve tiempo de un lado al otro del almuerzo."""
    min_block = cfg["rules"]["min_block_minutes"]
    # 1. Dentro de cada tramo, un solo bloque por incidencia (en orden de primera aparición).
    allocs: list[dict[str, Piece]] = []
    halves: list[list[int]] = [[]]
    for it in items:
        if isinstance(it, Fixed) and it.kind == "lunch":
            halves.append([])
        if not isinstance(it, Segment):
            continue
        alloc: dict[str, Piece] = {}
        for pc in it.pieces:
            if pc.issue in alloc:
                add_src(alloc[pc.issue].src, pc.src)
            else:
                alloc[pc.issue] = Piece(pc.issue, dict(pc.src))
        halves[-1].append(len(allocs))
        allocs.append(alloc)

    # 2. Entre tramos del mismo lado del almuerzo: intercambiar tiempo entre incidencias
    #    mientras baje la cantidad de bloques.
    for half in halves:
        sub = [allocs[k] for k in half]
        order = list(dict.fromkeys(issue for a in sub for issue in a))
        for _ in range(200):
            if not _swap_once(sub, order, min_block):
                break
        for k, a in zip(half, sub):
            allocs[k] = a

    out, k = [], 0
    for it in items:
        if isinstance(it, Segment):
            out.append(Segment(it.start, it.end, list(allocs[k].values())))
            k += 1
        else:
            out.append(it)
    return out


def _swap_once(allocs: list[dict[str, Piece]], order: list[str], min_block: int) -> bool:
    for A in order:
        where = [i for i, a in enumerate(allocs) if A in a]
        for i in where:
            for j in where:
                if i == j:
                    continue
                amount = allocs[j][A].minutes
                for B, pb in list(allocs[i].items()):
                    if B == A or pb.minutes < amount:
                        continue
                    rest = pb.minutes - amount
                    if 0 < rest < min_block:
                        continue
                    delta = -1 - (rest == 0) + (B not in allocs[j])
                    if delta >= 0:
                        continue
                    _move(allocs, A, B, i, j, amount, rest)
                    return True
    return False


def _move(allocs, A, B, i, j, amount, rest) -> None:
    """A deja el tramo j (se suma a su bloque del tramo i); B cede `amount` del tramo i al j.

    De B se mueven minutos de bloques concretos: los más cercanos al tramo j (los últimos si
    j va después, los primeros si va antes), así cada fila describe el trabajo que contiene."""
    add_src(allocs[i][A].src, allocs[j][A].src)
    pb = allocs[i][B]
    taken, left = take_src(pb.src, amount, from_end=j > i)
    if B in allocs[j]:
        add_src(allocs[j][B].src, taken)
        del allocs[j][A]
    else:
        # B ocupa el lugar que deja A en el tramo j.
        allocs[j] = {(B if k == A else k): (Piece(B, taken) if k == A else v) for k, v in allocs[j].items()}
    if rest == 0:
        del allocs[i][B]
    else:
        pb.src = left


# --------------------------------------------------------------------------- chequeos


def totals(rows: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        if r["kind"] == "block":
            out[r["issue"]] = out.get(r["issue"], 0) + minutes(r)
    return out


def minutes(r: dict) -> int:
    return int((r["end"] - r["start"]).total_seconds() // 60)


def check(rows: list[dict], model, expected_totals: dict[str, int], lunch: bool,
          cut_ids: dict[str, int] | None = None) -> list[str]:
    cfg = model.cfg
    slot, min_block = cfg["rules"]["slot_minutes"], cfg["rules"]["min_block_minutes"]
    tz = common.get_tz(cfg)
    errors = []
    rows = sorted(rows, key=lambda r: (r["start"], r["end"]))
    for a, b in zip(rows, rows[1:]):
        if b["start"] < a["end"]:
            errors.append(f"{common.fmt_hm(a['start'])} y {common.fmt_hm(b['start'])} se superponen")
        elif b["start"] > a["end"]:
            errors.append(f"tiempo sin cubrir {common.fmt_hm(a['end'])}–{common.fmt_hm(b['start'])}")
    if rows and model.range_start and rows[0]["start"] != model.range_start:
        errors.append("no empieza en la hora de entrada")
    if rows and model.range_end and rows[-1]["end"] != model.range_end:
        errors.append("no termina en la hora de corte")

    base_fixed = {(r.kind, r.start, r.end) for r in model.rows
                  if r.kind == "break" or (r.kind == "block" and is_fixed_block(r.data))}
    got_fixed = {(r["kind"], r["start"], r["end"]) for r in rows
                 if r["kind"] == "break" or (r["kind"] == "block" and r.get("fixed"))}
    if base_fixed != got_fixed:
        errors.append("cambió el horario de una parte fija (salida, worklog existente o reunión)")

    issue_of = {r.data.get("id"): r.data.get("issue") for r in model.rows if r.kind == "block"}
    for r in rows:
        if r["kind"] != "block":
            continue
        tag = f"{common.fmt_hm(r['start'])}–{common.fmt_hm(r['end'])} {r['issue']}"
        if any(issue_of.get(i) != r["issue"] for i in r["ids"]):
            errors.append(f"{tag}: los bloques base {', '.join(r['ids'])} no son todos de esa incidencia")
        if not r.get("fixed"):
            if r["start"].minute % slot or r["end"].minute % slot:
                errors.append(f"{tag}: no está alineado a {slot} min")
            if minutes(r) < min_block:
                errors.append(f"{tag}: dura menos de {min_block} min")
    if all(r.get("src") is not None for r in rows if r["kind"] == "block"):
        used: dict[str, int] = {}
        for r in rows:
            if r["kind"] != "block":
                continue
            if sum(r["src"].values()) != minutes(r):
                errors.append(f"{common.fmt_hm(r['start'])} {r['issue']}: el origen suma "
                              f"{sum(r['src'].values())} min y la fila dura {minutes(r)}")
            add_src(used, r["src"])
        for row in model.rows:
            if row.kind == "block":
                i = row.data["id"]
                want = row.minutes - (cut_ids or {}).get(i, 0)
                if used.get(i, 0) != want:
                    errors.append(f"el bloque {i} aparece con {used.get(i, 0)} min y tiene {want}")
    got = totals(rows)
    for issue in sorted(set(got) | set(expected_totals)):
        if got.get(issue, 0) != expected_totals.get(issue, 0):
            errors.append(f"total de {issue}: {common.fmt_duration(got.get(issue, 0))}, "
                          f"debería ser {common.fmt_duration(expected_totals.get(issue, 0))}")

    lunches = [r for r in rows if r["kind"] == "lunch"]
    if lunch:
        rv = cfg["review"]
        ws, we = (_hm_on(model.day, v, tz) for v in rv["lunch_window"])
        if len(lunches) != 1:
            errors.append(f"debe haber un almuerzo y hay {len(lunches)}")
        else:
            lu = lunches[0]
            if minutes(lu) != rv["lunch_minutes"] or lu["start"] < ws or lu["end"] > we:
                errors.append(f"el almuerzo {common.fmt_hm(lu['start'])}–{common.fmt_hm(lu['end'])} no dura "
                              f"{rv['lunch_minutes']} min dentro de {rv['lunch_window'][0]}–{rv['lunch_window'][1]}")
            span = {r.data.get("id"): (r.start, r.end) for r in model.rows if r.kind == "block"}
            for r in rows:
                if r["kind"] != "block":
                    continue
                if r["end"] <= lu["start"]:
                    moved = [i for i in r["ids"] if span[i][0] >= lu["end"]]
                elif r["start"] >= lu["end"]:
                    moved = [i for i in r["ids"] if span[i][1] <= lu["start"]]
                else:
                    moved = []
                if moved:
                    errors.append(f"{common.fmt_hm(r['start'])}–{common.fmt_hm(r['end'])} {r['issue']}: "
                                  f"mueve {', '.join(moved)} al otro lado del almuerzo")
    elif lunches:
        errors.append("una variante sin almuerzo no puede tener almuerzo")
    return errors


def rows_from_override(spec: list[dict], model) -> list[dict]:
    """Filas de `variant_overrides[<variante>]`: [{start, end, ids} | {start, end, gap} | {start, end, lunch: true}].

    Las salidas del checkin se agregan solas."""
    tz = common.get_tz(model.cfg)
    by_id = {r.data.get("id"): r for r in model.rows if r.kind in ("block", "gap")}
    rows = []
    for item in spec:
        s, e = (_hm_on(model.day, item[k], tz) for k in ("start", "end"))
        if item.get("lunch"):
            rows.append({"kind": "lunch", "start": s, "end": e, "key": "lunch"})
        elif item.get("gap"):
            g = by_id.get(item["gap"])
            if g is None:
                raise ValueError(f"no existe el hueco {item['gap']}")
            rows.append({"kind": "gap", "start": s, "end": e, "id": item["gap"], "key": item["gap"],
                         "gap_kind": g.data.get("kind", "open")})
        else:
            ids = item.get("ids") or []
            src = [by_id.get(i) for i in ids]
            if not ids or any(x is None or x.kind != "block" for x in src):
                raise ValueError(f"ids inválidos: {ids}")
            first = src[0].data
            fixed = len(ids) == 1 and is_fixed_block(first)
            rows.append({"kind": "block", "start": s, "end": e, "issue": first.get("issue"), "ids": list(ids),
                         "src": None, "key": row_key(ids), "fixed": fixed,
                         "action": first.get("action") if fixed else "new"})
    for r in model.rows:
        if r.kind == "break":
            rows.append({"kind": "break", "start": r.start, "end": r.end, "key": f"break@{common.fmt_hm(r.start)}"})
    return sorted(rows, key=lambda r: (r["start"], r["end"]))


# --------------------------------------------------------------------------- entrada


def compute(model, events: list[tuple[datetime, datetime]]) -> dict[str, dict]:
    """Calcula las cuatro variantes. Cada una: rows, totals, lunch, errors, warnings, override."""
    cfg, tz = model.cfg, common.get_tz(model.cfg)
    base = base_layout(model)
    lunch_items, lunch_info = apply_lunch(base, events, cfg, model.day, tz)
    has_lunch = lunch_info["mode"] != "none"
    layouts = {
        "base": base,
        "lunch": lunch_items,
        "group": apply_group(base, cfg),
        "group+lunch": apply_group(lunch_items, cfg),
    }
    base_totals = totals(to_rows(base))
    lunch_totals = {k: v - lunch_info["discounts"].get(k, 0) for k, v in base_totals.items()}
    lunch_totals = {k: v for k, v in lunch_totals.items() if v > 0}
    overrides = model.plan.get("variant_overrides") or {}
    out = {}
    for name, items in layouts.items():
        with_lunch = name.endswith("lunch") and has_lunch
        expected = lunch_totals if with_lunch else base_totals
        rows = unique_keys(to_rows(items))
        res = {"rows": rows, "totals": totals(rows), "lunch": lunch_info if name.endswith("lunch") else None,
               "errors": check(rows, model, expected, with_lunch, lunch_info.get("cut_ids") if with_lunch else None),
               "warnings": [], "override": False}
        if name.endswith("lunch") and not has_lunch:
            res["warnings"].append(f"sin almuerzo: {lunch_info['reason']}")
        if name in overrides:
            try:
                o_rows = unique_keys(rows_from_override(overrides[name], model))
                o_err = check(o_rows, model, expected, with_lunch)
            except (KeyError, ValueError) as e:
                o_err = [str(e)]
            if o_err:
                res["warnings"].append("variant_overrides ignorado: " + "; ".join(o_err))
            else:
                res.update(rows=o_rows, totals=totals(o_rows), override=True)
        out[name] = res
    return out
