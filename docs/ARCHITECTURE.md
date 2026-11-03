# Architecture and design decisions

## Runtime

One Python process serves the operator console and FastAPI endpoints. SQLite persists requests,
review decisions, local tickets, and audit entries. The knowledge index is rebuilt atomically from
local Markdown documents during startup. A single-process deployment suits demonstrations and
small local operator workflows; this is not a distributed helpdesk platform.

## Semantic Kernel boundary

`SupportAgent` registers two native plugins with `Kernel.add_plugin`. Classification and first
retrieval are deterministic kernel invocations so they can be tested without a model.

| Plugin | Function | Side effect |
| --- | --- | --- |
| `Triage` | `classify(message)` | None; returns rule-based category, priority, and queue |
| `Knowledge` | `search(query)` | None; returns approved local document excerpts |

In live mode, `OpenAIChatCompletion` and `OpenAIChatPromptExecutionSettings` request a typed JSON
draft and allow automatic calls only to `Knowledge`. The live stage has three auto-invocation
attempts and an overall timeout. There is no email, payment, approval, shell, or ticket-writing
plugin registered with the model. Review writes run through explicit HTTP handlers instead.
The execution trace records application stages, not hidden model reasoning or raw provider traffic.

This is a bounded agent workflow, not an autonomous multi-agent conversation or reinforcement
learning system. The default demo extracts text verbatim and labels that behaviour in the trace.

## Retrieval

Markdown level-two headings define sections, with long sections split into at most 1,500-character
chunks. Chunk IDs hash the filename and text, giving stable IDs until a source changes. FTS5's
Porter tokenizer supports stemming. A small stop-word list and safe term construction produce an
OR query, ranked by BM25, returning up to four sources in the application.

This keeps the example local and inspectable without an embedding API or vector database.
It also has clear limits: lexical matching can miss synonyms, section boundaries can lose context,
and a term match is not a confidence score. The project makes no calibrated-confidence claim.
The labelled evaluation is a small regression fixture, not an external benchmark.

## Persistence and review

- `runs`: complete typed request/draft snapshots, an optional unique idempotency key, and a
  fingerprint that prevents reuse of that key for a different request.
- `tickets`: one local support ticket per approved run, enforced with a unique `run_id`.
- `audit`: timestamped creation/review events with actor and review note.
- `chunks`, `chunks_fts`: current policy texts and a search index.

Review starts `BEGIN IMMEDIATE` before checking status. That serialises conflicting reviewers
and commits the ticket, state transition, and audit event together. Repeating the same decision
returns the existing result; attempting the opposite decision returns HTTP 409. This provides
exactly one local ticket per run, not exactly-once delivery to any external service.

Request retries with an idempotency key share a saved run. Concurrent first-time requests can
still generate more than one model response before the unique insert resolves to one persisted
run. They may therefore incur duplicate model cost; no cost-level exactly-once guarantee is made.

Audit rows are stored normally in SQLite. They are not cryptographically signed, append-only
against a database administrator, or a regulatory compliance record.

## Grounding and failure handling

The model sees customer input and provided policy excerpts as labelled data. The system prompt
instructs it to ignore embedded instructions. Tool access is constrained in code and write actions
are unavailable. Missing evidence causes an escalation draft without calling a model.

Unknown citation IDs, missing citations on an evidenced answer, malformed output, provider errors,
and timeouts stop the live draft before persistence. Citation checking verifies identifiers and
does not prove that a claim follows from the cited source. Prompt injection and hallucination
cannot be eliminated by prompts or citation checks; reviewers verify the actual answer.

## Delivery

The Python package bundles the console and fictional policy documents, so the wheel works without
a source checkout. A multi-stage Docker build installs the frozen production dependency set and
runs as UID/GID 10001. Compose binds only to localhost, drops capabilities, uses a read-only root
filesystem, and persists only the database directory.

CI checks Python 3.12 and 3.13, then builds and exercises the actual container over HTTP.
The release workflow reuses CI and publishes versioned images only after success. Action references
are pinned to verified commit SHAs; Dependabot proposes action/base-image updates. Python updates
require editing the pinned dependencies, running `uv lock`, and re-running validation.
