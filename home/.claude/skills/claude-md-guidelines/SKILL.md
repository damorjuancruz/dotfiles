---
name: claude-md-guidelines
description: Guidelines for writing, reviewing or pruning a CLAUDE.md / AGENTS.md (repository instruction files for coding agents). Use when creating one, after running /init, when editing or auditing an existing one, or when deciding whether something belongs in it.
---

# Writing a good CLAUDE.md

Context files add cost to every request, and the agent follows what they say, needed or not. Controlled studies found no general gain in task success from them, and repository overviews in particular don't help. So the bar for each line is high.

## Content

1. Don't commit `/init` output as is. Use it at most as a draft and keep only lines that prevent a concrete mistake.
2. Only include what an agent can't discover by reading the repo: non-obvious commands, environment quirks, gotchas, and the rationale behind non-evident decisions. No directory trees, dependency lists, architecture overviews or file-by-file descriptions.
3. Every line must prevent a concrete mistake. If you can't say what goes wrong without it, or the agent already gets it right unprompted, delete it.
4. Grow it from observed mistakes. When the agent repeats an error, add the minimal rule that prevents it. Don't fill it from templates or copy other projects' files.
5. Keep the root file short (well under 200 lines). If it grows past that, prune or move content to on-demand files instead of adding more.
6. Task-specific procedures go in skills, and detailed domain docs stay in `docs/` linked from the root file. Don't use path-scoped rules or nested CLAUDE.md files. They only load when a file is accessed through Read/Write/Edit, so reads and edits done through the shell silently skip them. `@imports` don't save context.
7. When linking a doc, state what it covers and when to read it (e.g. "read X before changing Y"). A bare link doesn't help.
8. Don't use it as a linter. Formatting and style rules belong in a formatter, linter or CI check. If a style rule matters and no tool enforces it, add the tool rather than a line.
9. Rules with no exceptions are enforced with hooks, permissions, settings or CI, not prose. Rules where the user may grant exceptions stay in prose, since a hard block would get in the way.
10. Be concrete: exact commands, paths and values, not vague advice. Only mention tools and commands the agent should actually use, since it tends to use whatever the file mentions.
11. The most valuable rules are those that go against what the model would naturally do, and they're also the most likely to be ignored. State them plainly and include the reason, so the model can apply it to cases the rule doesn't name.
12. Prefer stating intent and judgment over absolute rules, and use emphasis ("IMPORTANT", "MUST", caps) on very few lines, if any. If everything is emphasized, nothing stands out.
13. Avoid contradictions across all instruction sources: global and project files, skills, plugins and harness settings. When two conflict, the agent may pick either one.
14. Treat it like code: change it through PRs, update it in the same PR as any refactor that touches what it mentions, and re-audit it after model upgrades or big tooling changes.
15. Leave out anything that changes often (versions, in-progress refactors, current plans). Plans and work-in-progress state belong in plan docs or the issue tracker.
16. Keep one source of truth: don't repeat what's in the README, docs or skills.
17. Optionally, a few lines of intent (what the project is for, non-negotiable constraints, where the domain glossary lives), only if they prevent real misunderstandings.

## Where a rule goes

- A rule that only matters when editing one file goes in a comment in that file. The agent reads it right before touching the code, whatever tool it uses.
- A rule whose mistake happens somewhere the agent has no reason to open (a new job writing to a table, a new route assuming an auth guard) goes in CLAUDE.md.

## Sources (2026, for re-auditing)

- Gloaguen et al., "Evaluating AGENTS.md" (ETH Zürich), arXiv 2602.11988 (v3, Sep 2026).
- Anthropic docs: https://code.claude.com/docs/en/best-practices and https://code.claude.com/docs/en/memory
- Anthropic, "The new rules of context engineering for Claude 5 generation models" (Jul 2026).
- dos Santos et al., "Configuration Smells in AGENTS.md Files", arXiv 2606.15828.
