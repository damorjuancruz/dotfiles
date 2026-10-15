# ADR format

ADRs live in `docs/adr/` and use sequential numbering: `0001-slug.md`, `0002-slug.md`, etc.

Create `docs/adr/` only when you need the first ADR.

## Template

```md
# {Short title of the decision}

{1-3 sentences: what's the context, what did we decide, and why.}
```

An ADR can be a single paragraph. It records that a decision was made and why. It doesn't need to fill out sections.

## Optional sections

Most ADRs don't need these.

- A `status` frontmatter field (`proposed | accepted | deprecated | superseded by ADR-NNNN`), when decisions get revisited.
- A "Considered options" section, when the rejected alternatives are worth remembering.
- A "Consequences" section, when downstream effects aren't obvious.

## Numbering

Find the highest number in `docs/adr/` and add one.

## When to offer an ADR

All three of these must be true:

1. Changing your mind later would be costly.
2. A future reader would look at the code and wonder why it was done this way.
3. It came from a real trade-off, where you chose between real alternatives for specific reasons.

Skip decisions that are easy to reverse, since you can just reverse them. Skip unsurprising ones, since nobody will ask why. If there was no real alternative, there is nothing to record beyond "we did the obvious thing."

### What qualifies

- **Architectural shape.** "We're using a monorepo." "The write model is event-sourced, the read model is projected into Postgres."
- **Integration patterns between contexts.** "Ordering and Billing communicate via domain events, not synchronous HTTP."
- **Technology choices that carry lock-in.** Database, message bus, auth provider, deployment target. Not every library, only the ones that would take a quarter to swap out.
- **Boundary and scope decisions.** "Customer data is owned by the Customer context; other contexts reference it by ID only." Recording what a context doesn't own matters as much as recording what it owns.
- **Deliberate deviations from the obvious path.** "We're using manual SQL instead of an ORM because X." Anything where a reasonable reader would assume the opposite. These ADRs stop the next engineer from "fixing" something that was deliberate.
- **Constraints not visible in the code.** "We can't use AWS because of compliance requirements." "Response times must be under 200ms because of the partner API contract."
- **Rejected alternatives when the reason isn't obvious.** If you considered GraphQL and picked REST for subtle reasons, record it. Otherwise someone will suggest GraphQL again in six months.
