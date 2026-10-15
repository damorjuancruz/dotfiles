---
name: manage-claude-sessions
description: Review and optionally delete Claude Code session transcripts (.jsonl files in ~/.claude/projects/<slug>/) for the current project. Use when the user asks to list, review, prune, clean up, or delete past Claude sessions, conversations, or transcripts for this project. Examples are "leé mis sesiones de claude", "borrá conversaciones viejas", "limpiá las sesiones de este proyecto", "show me my past sessions and let me delete some".
disable-model-invocation: true
---

# Manage Claude sessions

Review the current project's past Claude Code session transcripts in batches, and delete the ones the user picks.

## Where sessions live

Claude Code stores each project's session transcripts at:

```
~/.claude/projects/<slug>/<session-id>.jsonl
```

The `<slug>` is the project's absolute path with every `/` replaced by `-`. For `/home/jcdamor/code/gvw` the slug is `-home-jcdamor-code-gvw`. A session may also have a sibling directory `<session-id>/` with cached artifacts. The `memory/` subdirectory holds engram memory. Never delete it.

## Workflow

1. **List sessions.** Run `scripts/list_sessions.py <project-dir>`. Add `--n 5` to get more messages from each end. For each session the script prints the id, size, mtime, user message count, `ai-title`, `custom-title`, and the first and last N real user messages. If `CLAUDE_SESSION_ID` is set, the script marks the current session with `[CURRENT SESSION]`.

2. **Skip the current session.** Never offer to delete the live transcript. If `CLAUDE_SESSION_ID` is unset, the `.jsonl` with the most recent mtime is almost certainly the current one. Confirm with the user before deleting it.

3. **Summarize each session in one or two sentences.** Read the first and last user messages together. The first ones show the goal. The last ones show how the session ended, for example a shipped feature, an abandoned attempt, a pivot, or running out of context. Write the summary in the user's language and cover both, for example _"Planificó e implementó el escudo de confiabilidad en termografías; terminó agregando la referencia al pie de cada gráfica."_ Ignore noise such as `[Request interrupted by user for tool use]`, `## Context Usage` token dumps, and command stdout wrappers.

4. **Ask in batches.** Ask about at most 4 sessions per `AskUserQuestion` call. The tool schema caps it at 4, even if the user asks for more. Go oldest first by mtime. Each question includes:
   - the session id (the first 8 characters are enough)
   - `ai-title` and `custom-title`
   - mtime, size, and user message count
   - the summary, placed where the user sees it first, since it is what they decide on
   - the literal first or last message, if it adds information

   Each question has two options, "Conservar" and "Eliminar" (in the user's language).

5. **Process answers, then move on.** After each batch, delete the sessions the user marked "Eliminar" and send the next batch. Repeat until the user has decided on every session except the current one.

6. **Delete safely.** For each session to delete, remove both:
   - `~/.claude/projects/<slug>/<session-id>.jsonl`
   - `~/.claude/projects/<slug>/<session-id>/`, if it exists

   Use `rm` and `rm -rf` on that `<session-id>` path only. Never delete the project slug directory or `memory/`.

7. **Report.** Say in one line how many sessions the user kept and deleted, and the freed disk space if it's easy to compute.

## Writing the summaries

- **First messages show intent.** The first real user message is almost always the kickoff prompt, such as a feature request, a bug report, or a planning request. Use it to name the topic.
- **Last messages show the outcome.** The last real user message is often a final tweak ("agregá X al pie"), a confirmation ("tests pasan"), a context usage dump, or a hard pivot. Use it to say how the session ended.
- **Combine both in one or two clauses.** Use the form _"<what they set out to do>; <how it ended>."_ If the session looks abandoned or trivial, say so. The user needs exactly that to decide whether to keep it.
- **Skip the noise listed in step 3.** If the first or last message is noise, look one or two messages further in.

## Reading metadata without the script

Each line of the `.jsonl` is a JSON object with a `type` field. The relevant types are:

- `ai-title`, with the auto-generated title in `aiTitle`. It can appear several times. Use the last one.
- `custom-title`, with the user-set title in `customTitle`.
- `user`, where `message.content` is either a string or a list of `{type: "text", text: "..."}` blocks. Skip messages whose text starts with `<` (system and tool wrappers) or has "Caveat" near the start (local command stdout).

## Gotchas

- The first few `user` entries are often system wrappers, not real prompts. Always filter by the leading `<` and the "Caveat" marker.
- `ai-title` and `custom-title` entries can appear many times. Always take the last one.
- `AskUserQuestion` accepts at most 4 questions per call. Split larger sets into batches.
- Only `rm -rf` individual `<session-id>` paths, never the project slug directory or `memory/`.
- Don't read whole `.jsonl` files into the conversation, since they can be several MB. Let the script extract what you need.
