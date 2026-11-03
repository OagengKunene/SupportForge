# Running and operating SupportForge

## Local deployment

`docker compose up --build -d` starts the default demo. `/healthz` checks database connectivity.
The named volume is writable by UID 10001; the application root filesystem is read-only.
Initial startup can take longer while Semantic Kernel imports its dependencies.

For an already-published image, create a separate Compose override pointing `image` to an actual
GHCR release and omit `build`. Pull the desired version and recreate the container. Keep the
previous version or image digest so you can roll back. A published image URL is not a live app URL.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `SUPPORTFORGE_MODE` | `demo` | `demo` or `openai` |
| `SUPPORTFORGE_DATABASE` | `data/supportforge.sqlite3` | SQLite database path; Compose sets `/app/data/supportforge.sqlite3` |
| `SUPPORTFORGE_KNOWLEDGE_DIR` | Packaged sample policies | Directory containing approved local `.md` documents |
| `SUPPORTFORGE_API_TOKEN` | Empty | Optional bearer token protecting every `/api/*` route |
| `OPENAI_API_KEY` | Empty | Provider key; required for `openai` mode |
| `OPENAI_MODEL` | `gpt-4o-mini` | Compatible chat-completions model supporting structured output + tools |
| `SUPPORTFORGE_MODEL_TIMEOUT` | `45` | Overall live model stage timeout in seconds |
| `SUPPORTFORGE_PORT` | `8000` | Compose host port, bound to `127.0.0.1` |

The runtime never requires a model key in demo mode. A shared API token is a basic operator gate;
the reviewer name is operator-supplied, not an authenticated identity claim. OpenAPI and health
endpoints are public and expose no ticket data. The static console contains no embedded secrets.

## Before a shared or public deployment

This project defaults to a local demonstration. A real multi-user deployment needs identity-based
authentication, reviewer roles, TLS, rate limiting, provider spending limits, data-retention and
deletion controls, secure document administration, and application monitoring. Add them for the
specific deployment rather than treating the demo's shared token as production RBAC.

Customer messages, draft answers, and review notes are stored unencrypted in the database volume.
Do not collect passwords, API keys, full payment-card details, or sensitive personal information.
An operator can access all runs in this workspace; there is no tenant isolation. In live mode,
request text and retrieved policies go to the configured model provider.

## Knowledge updates

For custom policies, mount a read-only directory and set `SUPPORTFORGE_KNOWLEDGE_DIR` to its
container path. Restart after changes. The startup process rejects an absent or empty knowledge
directory. The loader reads top-level `.md` files only; documents are data, never executable code.

## Backups

Back up the database using SQLite's backup API or stop the application before copying the entire
volume. SQLite uses WAL mode, so copying only the main database file while writes are active may
miss committed data. Store backups with permissions appropriate to the support data. Test a
restore in a separate environment before relying on it.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Console requests a token | Configure the same `SUPPORTFORGE_API_TOKEN` through the gear button |
| Live startup fails | Confirm mode, provider key, model access, and outgoing HTTPS connectivity |
| HTTP 502 on drafting | Provider availability, compatible structured-output model, timeout, server configuration |
| No policy evidence | Inspect the knowledge directory; reword the question or add an approved policy |
| HTTP 409 on retry | An idempotency key was reused with different text, or the run already has the opposite review decision |
| Permission error on data | Confirm the mounted directory allows UID/GID 10001 to write |

The app suppresses provider error details in HTTP responses. Avoid logging or posting raw
requests, tokens, or customer content when diagnosing a problem.
