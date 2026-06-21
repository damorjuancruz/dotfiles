---
name: plan-task
description: Explore the codebase and interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user is planning a task.
---

Explore the codebase using multiple @explore subagents in parallel to understand the context of the task.

Then, interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one at a time. For each question, provide your recommended answer.

Ask the questions one by one using the question tool. Asking many questions is encouraged. If an answer generates more questions, keep exploring the codebase and asking questions, until every branch of the decision tree is resolved.

Do not ask questions that have already been answered.
