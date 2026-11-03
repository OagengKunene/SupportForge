# Creation-environment validation

Checked on 3 November 2026. These are local results, not a GitHub Actions badge or a production
deployment claim.

| Check | Observed result |
| --- | --- |
| Python workflow/API tests | 35 passed on Python 3.12.14 |
| Python statement coverage | 99.49% across the application package; minimum required is 85% |
| Console DOM tests | 6 passed using Node.js 24.22.1 and development-only LinkeDOM |
| Retrieval/abstention regression | 12 of 12 labelled cases passed |
| Rule-based triage regression | 12 of 12 labelled cases passed |
| Ruff lint and formatting | Passed |
| JavaScript syntax check | Passed |
| Real HTTP server smoke check | Passed: health, draft, evidence, review, idempotency, audit |
| Semantic Kernel live tool loop | Real SDK/adapter + mock HTTP: tool request, real knowledge plugin, structured final answer |
| Python package build | Wheel and source distribution built successfully; wheel includes all 4 static assets and 5 policy documents |

## Limits of these results

- Docker is not installed in the creation environment. The Dockerfile and Compose configuration
  are included; actual container build/run is an explicit CI job and has not run here.
- GitHub Actions runs, GHCR publishing, and Python 3.13 validation require a repository upload.
  Their workflows are configured, not claimed to have executed.
- No real paid model request was made. Provider access and live model output quality still need
  an operator's API key and an explicit live test.
- Console checks use an in-memory DOM and mocked API responses. They cover frontend behaviour,
  not a real browser screenshot, visual accessibility audit, or full cross-browser testing.
- The sample evaluation is small and based on the shipped fictional policies. It is not evidence
  of general support accuracy, prompt-injection immunity, or production readiness.
- The installed Semantic Kernel/Pydantic combination emits one upstream Pydantic deprecation
  warning during the Python tests. It does not fail the tests. Recheck it when updating either
  dependency.
