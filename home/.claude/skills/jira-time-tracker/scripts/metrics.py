#!/usr/bin/env python3
"""Reporte de las métricas de uso del skill (<STATE_ROOT>/metrics.jsonl).

Cada línea es una tanda cerrada con `plan.py close` (ver lib/metrics.py). El reporte muestra
una fila por tanda y los promedios: precisión de la atribución (por confianza), ediciones de
texto, rondas, tiempos, costo del agente, cobertura de las fuentes MCP y errores frecuentes.

Uso:
  metrics.py report [--since AAAA-MM-DD] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import common  # noqa: E402
from lib import metrics as M  # noqa: E402


def read(since: str | None = None, path: Path | None = None) -> list[dict]:
    path = path or common.STATE_ROOT / M.GLOBAL
    out = []
    if not path.exists():
        return out
    for line in path.read_text(errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if since and str(rec.get("date", "")) < since:
            continue
        out.append(rec)
    return out


def _avg(values: list[float | int | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def _tokens(usage: dict | None) -> tuple[int, int, int]:
    """(turnos del principal, tokens de entrada del principal, tokens de entrada de subagentes)."""
    if not usage:
        return 0, 0, 0
    def total(models: dict) -> tuple[int, int]:
        turns = sum(m.get("turns", 0) for m in models.values())
        tok = sum(m.get("input", 0) + m.get("cache_read", 0) + m.get("cache_write", 0) for m in models.values())
        return turns, tok
    turns, main = total(usage.get("main") or {})
    subs = sum(total(s)[1] for s in usage.get("subagents") or [])
    return turns, main, subs


def report(recs: list[dict]) -> str:
    if not recs:
        return "Sin métricas todavía: se registran al cerrar cada tanda (`plan.py close`)."
    out = ["fecha       tanda resultado  min  rondas precisión  movido  editados  turnos  tokens(M) sub(M)  revisión"]
    for r in recs:
        a = r.get("attribution") or {}
        rv = r.get("review") or {}
        turns, main, subs = _tokens(r.get("usage"))
        acc = f"{a['accuracy'] * 100:.0f}%" if a.get("accuracy") is not None else "—"
        out.append(f"{r.get('date', '?'):<11} {r.get('run', '?'):>5} {str(r.get('outcome')):<10} "
                   f"{r.get('minutes') or '—':>4} {r.get('rounds', 0):>6} {acc:>9} "
                   f"{a.get('moved_minutes', 0) + a.get('removed_minutes', 0):>6}m {rv.get('texts_edited') or 0:>9} "
                   f"{turns:>7} {main / 1e6:>9.1f} {subs / 1e6:>6.1f}  {rv.get('page_minutes') or 0:>5}m")

    out.append("")
    out.append("Promedios:")
    out.append(f"  minutos por tanda: {_avg([r.get('minutes') for r in recs])} · rondas: {_avg([r.get('rounds') for r in recs])}")
    out.append(f"  precisión de la atribución: {_avg([(r.get('attribution') or {}).get('accuracy') for r in recs])}")
    conf: dict[str, list[int]] = {}
    for r in recs:
        for c, v in ((r.get("attribution") or {}).get("by_confidence") or {}).items():
            agg = conf.setdefault(c, [0, 0])
            agg[0] += v.get("minutes", 0)
            agg[1] += v.get("moved", 0) + v.get("removed", 0)
    if conf:
        out.append("  corregido según la confianza propuesta: " + ", ".join(
            f"{c} {bad / tot * 100:.0f}% de {tot} min" for c, (tot, bad) in sorted(conf.items()) if tot))
    levels = Counter()
    for r in recs:
        levels.update((r.get("review") or {}).get("levels") or {})
    if levels:
        out.append("  niveles de comentario elegidos: " + ", ".join(f"{k} {v}" for k, v in levels.most_common()))
    out.append(f"  similitud de los textos editados con el sugerido: "
               f"{_avg([(r.get('review') or {}).get('text_similarity_avg') for r in recs])}")
    out.append(f"  incidencias nuevas: propuestas {sum((r.get('attribution') or {}).get('new_issues_proposed', 0) for r in recs)}"
               f", creadas {sum((r.get('attribution') or {}).get('new_issues_created', 0) for r in recs)}")

    cov: dict[str, Counter] = {}
    for r in recs:
        for src, c in (r.get("mcp") or {}).items():
            cov.setdefault(src, Counter())[c.get("status")] += 1
    if cov:
        out.append("  cobertura MCP: " + " · ".join(f"{s} {dict(c)}" for s, c in sorted(cov.items())))
    slow = Counter()
    for r in recs:
        for src, s in (((r.get("collect") or {}).get("sources")) or {}).items():
            slow[src] += s.get("seconds") or 0
    if slow:
        out.append("  segundos por colector (total): " + ", ".join(f"{k} {v:.0f}" for k, v in slow.most_common(6)))

    errs = Counter()
    for r in recs:
        for e in r.get("errors") or []:
            errs[f"{e.get('where')}: {e.get('message', '')[:80]}"] += 1
        for e in ((r.get("load") or {}).get("errors")) or []:
            errs[f"load {e.get('step')}: {e.get('error', '')[:80]}"] += 1
    if errs:
        out.append("")
        out.append("Errores más frecuentes:")
        out += [f"  {n}× {k}" for k, n in errs.most_common(10)]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("report")
    p.add_argument("--since", help="desde esta fecha de carga (AAAA-MM-DD)")
    p.add_argument("--json", action="store_true", help="las líneas crudas, para analizarlas aparte")
    args = ap.parse_args(argv)
    recs = read(args.since)
    if args.json:
        print(json.dumps(recs, ensure_ascii=False, indent=1))
    else:
        print(report(recs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
