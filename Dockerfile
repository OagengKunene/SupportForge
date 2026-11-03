# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.4
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable --python /usr/local/bin/python

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    SUPPORTFORGE_DATABASE=/app/data/supportforge.sqlite3 \
    SUPPORTFORGE_MODE=demo \
    HOME=/tmp
WORKDIR /app
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app \
    && mkdir /app/data && chown app:app /app/data
COPY --from=builder /app/.venv /app/.venv
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"
CMD ["uvicorn", "supportforge.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
