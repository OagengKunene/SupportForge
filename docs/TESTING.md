# Testing and evidence

## Tests you can reproduce

`uv sync --frozen` installs the same dependency set as the lockfile. Then:

| Command | Evidence |
| --- | --- |
| `uv run pytest` | Plugin workflow, API, source validation, failure handling, reviews, persistence, authentication |
| `uv run python scripts/evaluate.py` | Retrieval/abstention and triage checks across all labelled sample cases |
| `uv run ruff check .` | Python lint and selected security checks |
| `uv run ruff format --check .` | Consistent formatting |
| `npm ci --ignore-scripts && npm test` | Console rendering, source tabs, review control, token handling, and failure UI |
| `uv build` | Source archive and installable wheel |
| `uv run python scripts/check_server.py` | Launch a disposable real HTTP server, run the smoke check, and stop it |
| `uv run python scripts/smoke.py http://localhost:8000` | Health, drafting, source return, review, duplicate protection, and audit via a running HTTP server |

Coverage must be at least 85% for the Python application package. Coverage does not measure model
quality or establish correctness. The tests use temporary SQLite databases and fictional data.

## What is actually exercised

The demo workflow invokes real Semantic Kernel functions, not a fake kernel. Live-model unit tests
replace the chat-completion method with controlled responses to check valid structure, unavailable
providers, timeouts, and invented/missing citations. They never send a real model request.
An additional test uses the real Semantic Kernel/OpenAI adapter with an in-memory mock HTTP
transport, returning a tool call, executing the real knowledge plugin, and then producing the
structured final draft. This validates SDK/tool-loop integration without provider access.

Concurrent review tests use two threads against the same SQLite database and assert a single
ticket and a single approval audit event. Persistence tests close and recreate the application,
then retrieve the saved request. HTTP tests exercise the optional bearer token on data routes.

The small evaluation set contains straightforward examples from the included fictional policies,
plus unmatched queries. Its scores are regression checks on that fixture, not general-world
accuracy, prompt-injection resistance, or a calibrated retrieval confidence estimate.

## Container checks

CI builds the Dockerfile and runs the container with a read-only filesystem, dropped Linux
capabilities, a writable database volume, and a temporary `/tmp`. It waits for the health endpoint
and executes the black-box HTTP smoke script. The release workflow requires this CI to pass.

Configured CI is not proof of a completed GitHub Actions run. Check the repository's Actions tab
for actual results once the project is uploaded. See `docs/VALIDATION.md` for the checks performed
in the creation environment, including any checks that were unavailable there.

## Manual browser check

1. Open the console on a desktop and a narrow viewport.
2. Choose the duplicate-payment sample and generate a draft.
3. Inspect the source excerpts and execution trace.
4. Confirm the reviewer field is required before approval.
5. Approve and verify a local ticket appears; retry the API review to confirm the same ticket ID.
6. Reopen the request from history, then reload and confirm its state persists.
7. Check an unrelated question produces an escalation instead of invented policy.

Real provider calls require an operator's API key and can incur costs. No live-model performance
or production-readiness claim is made without those additional checks.
