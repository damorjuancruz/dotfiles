---
name: implement-issue
description: Handle GitHub issues end-to-end. Analyze, implement fix, and commit. Use when user provides a GitHub issue URL, asks to fix an issue, or wants to tackle a bug/feature request.
---

# Implement Issue

## Workflow

### 1. Analyze the Issue

- [ ] Fetch issue with `gh issue view <number> --json title,body,labels`
- [ ] Read linked files and understand the problem
- [ ] Explore codebase using parallel @explore subagents for relevant context (search, read files)
- [ ] Ask the user for clarification if needed (using question tool)
- [ ] Summarize the issue and proposed approach to the user

### 2. Plan the Implementation

- [ ] Identify all files that need changes
- [ ] Determine the scope (small fix or larger refactor?)
- [ ] If tests are relevant, **ask the user** if they want tests — never create tests unless explicitly requested
- [ ] Use the /plan-task skill if available and it hasn't been called for this issue
- [ ] Present the plan and get user approval
- [ ] If in plan mode, ask the user to switch to build mode before continuing

### 3. Implement

- [ ] Create todos (using tool) for each step in the implementation process
- [ ] Create a feature branch: `gh issue checkout <number>` or `git checkout -b fix/<number>-<slug>`
- [ ] Make changes in focused commits (not thousands of lines, but not strictly atomic either)
- [ ] Use conventional commit messages: `fix:`, `feat:`, `refactor:`, `chore:`, `docs:`, `test:`
- [ ] Keep commit messages short and descriptive
- [ ] Reference the issue number in commits when relevant
- [ ] Update todos regularly

### 4. Verify

- [ ] Run relevant tests/build commands if the project has them
- [ ] Confirm the fix addresses the issue requirements

## Commit Message Conventions

```
fix: resolve null pointer in user auth
feat: add export to CSV for transactions
refactor: simplify balance calculation logic
chore: update dependencies
docs: clarify setup instructions
```

Keep messages under 72 characters. Use imperative mood ("fix" not "fixed").

## Important Rules

- **NEVER create tests unless the user EXPLICITLY ASKS FOR THEM.** Always offer testing as an option, but respect the user's decision.
- **NEVER work on a different issue or topic**: work ONLY on the issue the user provided.
- **ALWAYS use the question tool when asking questions to the user.**
- **Keep commits reasonably sized.** Not strictly atomic, but avoid massive single commits.
- **Use `gh` CLI** for all GitHub operations when available.
- **ONLY if the /issue-to-pr skill has already been called for THE SAME ISSUE you should analyze which steps of the workflow remain pending and skip to them.**
- **ALWAYS use parallel @explore subagents when exploring the codebase**
