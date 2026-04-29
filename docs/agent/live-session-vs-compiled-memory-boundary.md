# Live session vs compiled memory boundary

## Why this boundary exists

The Agent Memory Graph is the stable, graph-readable layer for archived project knowledge.
The current live session is the active reasoning layer for work that is still changing.
These two layers must not be collapsed into one another.

If live reasoning is treated as already-compiled memory, the graph becomes noisy, unstable, and privacy-risky.
If compiled memory is treated as the only source of truth during active work, the agent loses the latest user intent and in-flight corrections.

## Authority order

Use this default read order:

1. current live session context
2. exported graph-governed context packets
3. pending updates
4. mapped lineage artifacts and logs
5. raw sessions only for explicit forensic recovery

Protocol rule:

> Current live session context is authoritative for in-progress reasoning, while the Agent Memory Graph is authoritative for stable archived project knowledge. New information discovered during a live session must enter pending updates first, and only becomes graph-readable archived memory after explicit compilation or validated auto-compilation.

## What counts as live session context

Live session context includes:

- active user instructions
- corrections that have not stabilized yet
- partial implementation notes
- exploratory debugging findings
- unresolved trade-offs
- temporary command output needed only for the current reasoning loop

Live session context has priority for the current task, but it is not automatically durable knowledge.

## What counts as compiled memory

Compiled memory is suitable for `compiled-session` only when the knowledge is:

- stable enough to survive outside the original conversation
- compressible into `summary`, `decisions`, `requirements`, `constraints`, and `graph_links`
- useful across future sessions
- safe to store as local structured knowledge
- specific enough to improve routing and graph traversal

Typical compiled memory examples:

- architecture direction
- long-lived protocol rules
- settled safety boundaries
- approved profile/project/lineage conventions
- stable context routing requirements
- durable frontend QA workflow rules

## What should not be compiled yet

Keep information out of compiled memory when it is still:

- speculative
- contradicted by newer messages
- dependent on the exact transcript wording
- a temporary debugging branch
- a noisy command transcript
- a local screenshot-only observation
- a private path or secret-bearing artifact

These belong in the live session or, if potentially durable, in pending updates.

## Pending updates as the boundary buffer

`pending_update` is the review buffer between live reasoning and compiled memory.

Use it for knowledge that may become durable, but is not yet archive-safe.
Examples:

- "we probably need stale summary review for this project"
- "lineage mapping seems incomplete for a new node family"
- "context router may need a new gap repair rule"

Rules:

- pending updates are graph-visible as maintenance signals
- pending updates do not become compiled memory automatically
- pending updates require explicit review before archive
- pending updates can be resolved, promoted, or discarded later

## Resuming an old session

If a past session is reopened and the same work continues:

- that reopened thread becomes live context again
- new findings stay live or enter pending updates first
- previous compiled memory remains stable until a new reviewed compilation supersedes it

If a past session is reopened but the topic has changed:

- keep prior compiled memory intact
- treat the new material as a new live delta
- compile a new curated session later if the new topic stabilizes

## Raw sessions policy

Raw sessions are source material, not default working context.

They are only for:

- forensic recovery
- ambiguity resolution when compiled memory is insufficient
- audit backtracking to original evidence

Raw sessions must remain:

- local only
- explicit access only
- last-resort by default
- excluded from committed examples

## Operational consequence for v2.0

In v2.0-dev:

- the dashboard reads exported graph artifacts, not live transcripts
- archive lifecycle governance is review/proposal-based
- `compiled_candidate` requires an explicit reviewed archive command path
- `forensic_only` keeps raw sessions outside normal context loading
- automatic archival is deferred until these boundaries are validated against gold fixtures
