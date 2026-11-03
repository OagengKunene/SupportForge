# API errors and rate limits

## Rate limits
An HTTP 429 response means the API rate limit was exceeded. Honour the Retry-After response
header and retry with exponential backoff and jitter. Do not retry every request immediately.
Repeated failures should be escalated with a timestamp, request ID and endpoint, excluding tokens.

## Authentication and timeouts
For HTTP 401 errors, verify that the API key is active and belongs to the correct workspace.
Never paste an API key into a support ticket. For a timeout, record the request ID and time,
check the service status page, and retry only idempotent operations. A timeout does not prove
that a write operation failed; check its status before resubmitting.
