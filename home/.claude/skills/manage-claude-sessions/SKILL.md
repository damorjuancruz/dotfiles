---
name: manage-claude-sessions
description: Review and optionally delete Claude Code session transcripts (.jsonl files in ~/.claude/projects/<slug>/) for the current project. Use when the user asks to list, review, prune, clean up, or delete past Claude sessions / conversations / transcripts for this project — e.g. "leé mis sesiones de claude", "borrá conversaciones viejas", "limpiá las sesiones de este proyecto", "show me my past sessions and let me delete some".
disable-model-invocation: true
---

# Manage Claude Sessions

Review and optionally delete past Claude Code session transcripts for the current project, in batches.

## Where sessions live

Claude Code stores per-project session transcripts at:

```
~/.claude/projects/<slug>/<session-id>.jsonl
```

The `<slug>` is the project's absolute path with `/` replaced by `-`, prefixed with `-`. For `/home/jcdamor/code/gvw` the slug is `-home-jcdamor-code-gvw`. Each session may also have a sibling directory `<session-id>/` with cached artifacts. The `memory/` subdirectory holds engram memory — never delete it as part of this skill.

## Workflow

1. **List sessions.** Run `scripts/list_sessions.py <project-dir>` (optionally `--n 5` to get more messages per side). The script prints, per session: id, size, mtime, total user-msg count, `ai-title`, `custom-title`, the first N real user messages, and the last N real user messages. The current session (if `CLAUDE_SESSION_ID` is set in env) is marked `[CURRENT SESSION]`.

2. **Identify the current session and skip it.** Never offer to delete the live transcript. If `CLAUDE_SESSION_ID` is unset, fall back to "the `.jsonl` with the most recent mtime is almost certainly current" — confirm before deleting.

3. **Synthesize a 1–2 sentence summary per session.** Read the first and last user-message snippets together. The first messages reveal the **goal / starting intent**; the last messages reveal what was **actually accomplished or where it ended** (feature shipped, abandoned, pivoted, ran out of context, etc.). Write a brief Spanish or English summary (match the user's language) that captures both: e.g. _"Planificó e implementó el escudo de confiabilidad en termografías; terminó agregando la referencia al pie de cada gráfica."_ Ignore obvious noise like `[Request interrupted by user for tool use]`, `## Context Usage` token-breakdown dumps, and command stdout wrappers.

4. **Batch the prompts.** Ask **up to 4 sessions per `AskUserQuestion` call** (the tool's hard limit — even if the user requests more, 4 is the cap). Order oldest-first by mtime. For each question include:
   - session id (short form ok, e.g. first 8 chars)
   - `ai-title` and `custom-title`
   - mtime, size, total user-msg count
   - **the synthesized summary** (the main signal — surface it prominently)
   - optionally the literal first/last message if it adds info

   Each question offers two options: **Conservar** / **Eliminar** (match user language).

5. **Process answers, then move on.** After each batch, delete the sessions the user marked **Eliminar**, then issue the next batch of up to 4. Repeat until all non-current sessions are decided.

6. **Delete safely.** For each session to delete, remove both:
   - `~/.claude/projects/<slug>/<session-id>.jsonl`
   - `~/.claude/projects/<slug>/<session-id>/` directory if it exists

   Use `rm` / `rm -rf` via Bash, targeting the specific `<session-id>` path only. **Never** delete the project slug directory itself or the `memory/` subdirectory.

7. **Final summary.** Report one line: how many kept, how many deleted, and the freed disk space if easy to compute.

## Writing good summaries (step 3 in detail)

- **First messages = intent.** The first non-noise user message is almost always the kickoff prompt — a feature ask, a bug report, a planning request. Use it to name the topic.
- **Last messages = outcome.** The last non-noise user message often shows: a final tweak ("agregá X al pie"), confirmation ("tests pasan"), a context-exhaustion dump, or a hard pivot. Use it to describe how the session ended.
- **Combine into one or two clauses.** Format: _"<what they set out to do>; <how it ended>."_ If the session looks abandoned or trivial, say so plainly — that's exactly the signal the user needs to decide whether to keep it.
- **Skip the noise.** Filter `[Request interrupted by user for tool use]`, `## Context Usage` blocks, `<command-name>` wrappers. Look one or two messages deeper if the immediate first/last is noise.

## Extracting metadata directly (if the script is unavailable)

Each line of the `.jsonl` is a JSON object with a `type` field. Relevant types:

- `ai-title` → `aiTitle` (auto-generated title; may appear multiple times — use the **last**)
- `custom-title` → `customTitle` (user-set title)
- `user` → `message.content` is either a string or a list of `{type: "text", text: "..."}` blocks. Skip messages whose text starts with `<` (system / tool wrappers) or contains "Caveat" near the start (local-command stdout).

## Gotchas

- The first few `user` entries are often system-injected wrappers, not real prompts. Always filter by leading `<` and the "Caveat" marker.
- `ai-title` / `custom-title` entries can appear many times. Always take the **last** occurrence.
- `AskUserQuestion` is capped at **4 questions per call** by the tool schema. Don't try to send 5+ — split into batches.
- Don't `rm -rf` the project slug directory itself or `memory/`. Only individual `<session-id>` paths.
- Don't read full `.jsonl` files into the conversation; they can be multi-MB. Let the script do the summarization.
