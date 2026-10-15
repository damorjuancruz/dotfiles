---
name: domain-modeling
description: Build and sharpen a project's domain model. Use when discussing codebase terminology, writing or editing a CONTEXT.md, or recording or editing an ADR.
---

# Domain modeling

Build and sharpen the project's domain model while you design. That means challenging terms, inventing edge-case scenarios, and writing down glossary terms and decisions as soon as they settle. Reading `CONTEXT.md` for vocabulary doesn't need this skill. Use it when you change the model.

## File structure

Most repos have a single context:

```
/
├── CONTEXT.md
├── docs/
│   └── adr/
│       ├── 0001-event-sourced-orders.md
│       └── 0002-postgres-for-write-model.md
└── src/
```

If a `CONTEXT-MAP.md` exists at the root, the repo has multiple contexts. The map points to where each one lives:

```
/
├── CONTEXT-MAP.md
├── docs/
│   └── adr/                          ← system-wide decisions
├── src/
│   ├── ordering/
│   │   ├── CONTEXT.md
│   │   └── docs/adr/                 ← context-specific decisions
│   └── billing/
│       ├── CONTEXT.md
│       └── docs/adr/
```

Create files only when you have something to write. If no `CONTEXT.md` exists, create one when you resolve the first term. If no `docs/adr/` exists, create it for the first ADR.

## During the session

### Challenge against the glossary

When the user uses a term that conflicts with the existing language in `CONTEXT.md`, say so immediately. "Your glossary defines 'cancellation' as X, but you seem to mean Y. Which is it?"

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term. "You're saying 'account'. Do you mean the Customer or the User? Those are different things."

### Discuss concrete scenarios

When the discussion turns to how domain concepts relate, test those relationships with specific scenarios. Invent edge cases that force the user to say exactly where one concept ends and the next begins.

### Cross-reference with code

When the user states how something works, check whether the code agrees. If it doesn't, point out the contradiction. "Your code cancels entire Orders, but you just said partial cancellation is possible. Which is right?"

### Update CONTEXT.md inline

When you resolve a term, update `CONTEXT.md` right away instead of batching updates. Use the format in [CONTEXT-FORMAT.md](./CONTEXT-FORMAT.md).

`CONTEXT.md` holds no implementation details. It is a glossary, not a spec, a scratch pad, or a record of implementation decisions.

### Offer ADRs sparingly

Only offer to create an ADR when all three are true:

1. Changing your mind later would be costly.
2. A future reader would wonder why it was done this way.
3. It came from a real trade-off, where you chose between real alternatives for specific reasons.

If any of the three is missing, skip the ADR. Use the format in [ADR-FORMAT.md](./ADR-FORMAT.md).
