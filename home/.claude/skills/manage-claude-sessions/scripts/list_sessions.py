#!/usr/bin/env python3
"""List Claude Code session metadata for a project directory.

Usage:
    list_sessions.py [project_dir] [--n N]

If project_dir is omitted, defaults to the current working directory.
Resolves to ~/.claude/projects/<slugified-cwd>/ and prints, for each .jsonl session:
    - session id (current session marked [CURRENT SESSION] if $CLAUDE_SESSION_ID set)
    - size and mtime
    - ai-title (last seen)
    - custom-title (last seen)
    - first N real user messages
    - last N real user messages

N defaults to 3. Output is plain text intended to be read by an agent that will
synthesize a short summary of each session from the message snippets.
"""
from __future__ import annotations

import datetime
import glob
import json
import os
import sys
from pathlib import Path


def slugify_cwd(path: str) -> str:
    return "-" + path.strip("/").replace("/", "-")


def collect_user_msgs(path: str) -> list[str]:
    """Return all real user messages (in order), filtering system wrappers."""
    out: list[str] = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if o.get("type") != "user":
                continue
            msg = o.get("message", {}) or {}
            content = msg.get("content", "")
            text = ""
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        text = c.get("text", "")
                        break
            elif isinstance(content, str):
                text = content
            if not text:
                continue
            stripped = text.lstrip()
            # Skip system-injected / tool-result wrappers and local-command caveats.
            if stripped.startswith("<"):
                continue
            head = stripped[:120].lower()
            if "caveat" in head or stripped.startswith("Caveat"):
                continue
            out.append(text.strip())
    return out


def get_last_field(path: str, type_name: str, field_name: str) -> str | None:
    val = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if o.get("type") == type_name:
                v = o.get(field_name)
                if v:
                    val = v
    return val


def trunc(s: str | None, n: int = 400) -> str:
    if not s:
        return "(none)"
    s = s.replace("\n", " ⏎ ")
    return s if len(s) <= n else s[:n] + "…"


def parse_args(argv: list[str]) -> tuple[str, int]:
    n = 3
    positional: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--n" and i + 1 < len(argv):
            try:
                n = max(1, int(argv[i + 1]))
            except ValueError:
                pass
            i += 2
            continue
        if a.startswith("--n="):
            try:
                n = max(1, int(a.split("=", 1)[1]))
            except ValueError:
                pass
            i += 1
            continue
        positional.append(a)
        i += 1
    target = os.path.abspath(positional[0]) if positional else os.getcwd()
    return target, n


def main() -> int:
    target, n = parse_args(sys.argv[1:])

    projects_root = Path.home() / ".claude" / "projects"
    slug = slugify_cwd(target)
    session_dir = projects_root / slug

    if not session_dir.is_dir():
        print(f"No sessions directory: {session_dir}", file=sys.stderr)
        return 1

    files = sorted(glob.glob(str(session_dir / "*.jsonl")))
    if not files:
        print(f"No sessions found in {session_dir}", file=sys.stderr)
        return 0

    current_sid = os.environ.get("CLAUDE_SESSION_ID", "")

    for f in files:
        sid = Path(f).stem
        size = os.path.getsize(f)
        mt = datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M")
        ai = get_last_field(f, "ai-title", "aiTitle")
        custom = get_last_field(f, "custom-title", "customTitle")
        msgs = collect_user_msgs(f)
        firsts = msgs[:n]
        # Last N, but if the session is short and overlaps, dedupe by index.
        if len(msgs) <= n:
            lasts: list[str] = []
        else:
            lasts = msgs[-n:]
        is_current = sid == current_sid

        size_h = f"{size/1024:.0f}K" if size < 1024 * 1024 else f"{size/1024/1024:.1f}M"
        marker = "  [CURRENT SESSION]" if is_current else ""
        print(f"╔══ {sid}{marker}")
        print(f"║ Size: {size_h}  |  Modified: {mt}  |  User msgs: {len(msgs)}")
        print(f"║ ai-title:     {ai or '(none)'}")
        print(f"║ custom-title: {custom or '(none)'}")
        print(f"║ First {len(firsts)} user msg(s):")
        for i, m in enumerate(firsts, 1):
            print(f"║   [{i}] {trunc(m)}")
        if lasts:
            print(f"║ Last {len(lasts)} user msg(s):")
            for i, m in enumerate(lasts, 1):
                print(f"║   [{i}] {trunc(m)}")
        else:
            print("║ Last user msg(s): (already shown above — short session)")
        print("╚══")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
