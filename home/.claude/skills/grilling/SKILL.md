---
name: grilling
description: Grill the user relentlessly about a plan, decision, or idea. Use when the user wants to stress-test their thinking, or uses any 'grill' trigger phrases.
---

Interview the user relentlessly until you reach a shared understanding. Map the discussion as a **design tree**, where every decision branches into the decisions that depend on it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled, meaning the questions you can ask _now_ without guessing at answers you haven't heard yet. Ask the whole frontier in one round. Number each question and give your recommended answer. Then wait for the user's answers before the next round.

Format a round like this:

```
**Q1. <question title>** <question body, might be multiple paragraphs, including multiple choices>

**->** <your recommended answer>

---

**Q2. <question title>** <question body, might be multiple paragraphs, including multiple choices>

**->** <your recommended answer>
```

The user's answers in each round reshape the tree. Settled decisions push the frontier outward and unblock the questions that depended on them. Recompute the frontier and ask the next round. If a question depends on another question still open in this round, it belongs to a _later_ round.

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, tools, etc.), dispatch a sub-agent to find it. Don't ask the user for anything you could look up yourself. Don't block on it either. A running exploration counts as an unsettled prerequisite, so only the questions that depend on it wait for the sub-agent's report. Ask the rest of the frontier now. The _decisions_ belong to the user. Put each one to them and wait.

The session is done when the frontier is empty, with every branch of the design tree visited and no unstated assumptions left. Do not act on it until the user confirms you have reached a shared understanding.
