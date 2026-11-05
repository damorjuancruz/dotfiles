#!/usr/bin/env python3
"""Lado remoto del colector `remote`: corre en la máquina remota (lo invoca collectors/remote.py
por SSH, no se usa a mano).

Lee por stdin {"day": "AAAA-MM-DD", "cfg": {...}}, corre los colectores habilitados en esa config (las rutas con ~ se expanden en el remoto) y escribe por stdout {fuente: resultado}.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collectors import claude_code, git_local, t3_code  # noqa: E402

COLLECTORS = {"git_local": git_local.collect, "claude_code": claude_code.collect, "t3_code": t3_code.collect}


def main() -> int:
    req = json.load(sys.stdin)
    cfg, day = req["cfg"], date.fromisoformat(req["day"])
    out = {}
    for name, collect in COLLECTORS.items():
        if not cfg["sources"].get(name, {}).get("enabled"):
            continue
        try:
            out[name] = collect(cfg, {}, day)
        except Exception as e:  # un colector roto no debe cortar el resto
            out[name] = {"source": name, "status": "error", "message": f"{type(e).__name__}: {e}"[:300], "events": []}
    json.dump(out, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
