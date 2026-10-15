# CONTEXT.md format

## Structure

```md
# {Context Name}

{One or two sentence description of what this context is and why it exists.}

## Language

**Order**:
{A one or two sentence description of the term}
_Avoid_: Purchase, transaction

**Invoice**:
A request for payment sent to a customer after delivery.
_Avoid_: Bill, payment request

**Customer**:
A person or organization that places orders.
_Avoid_: Client, buyer, account
```

## Rules

- **Be opinionated.** When several words exist for the same concept, pick the best one and list the others under `_Avoid_`.
- **Keep definitions short.** One or two sentences at most. Define what the term is, not what it does.
- **Only include terms specific to this context.** Leave out general programming concepts (timeouts, error types, utility patterns), even if the project uses them a lot.
- **Group terms under subheadings** when natural clusters emerge. If all terms belong to one area, a flat list is fine.

## Single and multi-context repos

Most repos have a single context, with one `CONTEXT.md` at the repo root.

Repos with multiple contexts have a `CONTEXT-MAP.md` at the root. It lists the contexts, where they live, and how they relate:

```md
# Context Map

## Contexts

- [Ordering](./src/ordering/CONTEXT.md): receives and tracks customer orders
- [Billing](./src/billing/CONTEXT.md): generates invoices and processes payments
- [Fulfillment](./src/fulfillment/CONTEXT.md): manages warehouse picking and shipping

## Relationships

- **Ordering → Fulfillment**: Ordering emits `OrderPlaced` events; Fulfillment consumes them to start picking
- **Fulfillment → Billing**: Fulfillment emits `ShipmentDispatched` events; Billing consumes them to generate invoices
- **Ordering ↔ Billing**: Shared types for `CustomerId` and `Money`
```

To find out which structure applies:

- If `CONTEXT-MAP.md` exists, read it to find the contexts.
- If only a root `CONTEXT.md` exists, there is a single context.
- If neither exists, create a root `CONTEXT.md` when you resolve the first term.

When there are multiple contexts, infer which one the current topic belongs to. If it's unclear, ask.
