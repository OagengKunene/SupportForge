"""SQLite persistence with atomic review transitions and duplicate protection."""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from supportforge.models import ReviewRequest, Run, SupportRequest


class ConflictError(Exception):
    """An idempotency key or review decision conflicts with existing state."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def fingerprint(request: SupportRequest) -> str:
    return hashlib.sha256(request.model_dump_json().encode()).hexdigest()


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self):
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                    idempotency_key TEXT UNIQUE, fingerprint TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tickets (
                    id TEXT PRIMARY KEY, run_id TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL, occurred_at TEXT NOT NULL,
                    event TEXT NOT NULL, actor TEXT NOT NULL, note TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL,
                    document TEXT NOT NULL, body TEXT NOT NULL
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
                    USING fts5(id UNINDEXED, title, body, tokenize='porter unicode61');
            """)

    def find_existing(self, key: str | None, request: SupportRequest) -> Run | None:
        if not key:
            return None
        with self.connect() as db:
            row = db.execute(
                "SELECT payload, fingerprint FROM runs WHERE idempotency_key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        if row["fingerprint"] != fingerprint(request):
            raise ConflictError("Idempotency-Key was already used for a different request")
        return Run.model_validate_json(row["payload"])

    def save_run(self, run: Run, key: str | None) -> Run:
        try:
            with self.connect() as db:
                db.execute(
                    "INSERT INTO runs VALUES (?, ?, ?, ?, ?)",
                    (run.id, run.created_at, key, fingerprint(run.request), run.model_dump_json()),
                )
                db.execute(
                    "INSERT INTO audit(run_id, occurred_at, event, actor, note) VALUES(?,?,?,?,?)",
                    (run.id, utc_now(), "draft_created", "agent", "Awaiting human review"),
                )
            return run
        except sqlite3.IntegrityError:
            existing = self.find_existing(key, run.request)
            if existing:
                return existing
            raise

    def get_run(self, run_id: str) -> Run | None:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM runs WHERE id = ?", (run_id,)).fetchone()
        return Run.model_validate_json(row["payload"]) if row else None

    def list_runs(self, limit: int = 50) -> list[Run]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT payload FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [Run.model_validate_json(row["payload"]) for row in rows]

    def review(self, run_id: str, review: ReviewRequest) -> Run:
        with self.connect() as db:
            # Acquire the write lock before checking state: two reviewers cannot create two tickets.
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            run = Run.model_validate_json(row["payload"])
            target = "approved" if review.decision == "approve" else "rejected"
            if run.status == target:
                return run
            if run.status != "pending":
                raise ConflictError("This request has already received a different decision")
            run.status = target
            if target == "approved":
                run.ticket_id = f"SF-{uuid4().hex[:12].upper()}"
                db.execute(
                    "INSERT INTO tickets VALUES (?, ?, ?, ?)",
                    (
                        run.ticket_id,
                        run.id,
                        utc_now(),
                        json.dumps(
                            {
                                "customer": run.request.customer_name,
                                "message": run.request.message,
                                "draft": run.answer,
                                "category": run.triage.category,
                                "priority": run.triage.priority,
                                "reviewer": review.reviewer,
                            }
                        ),
                    ),
                )
            db.execute("UPDATE runs SET payload = ? WHERE id = ?", (run.model_dump_json(), run.id))
            db.execute(
                "INSERT INTO audit(run_id, occurred_at, event, actor, note) VALUES(?,?,?,?,?)",
                (run.id, utc_now(), target, review.reviewer, review.note),
            )
        return run

    def audit(self, run_id: str) -> list[dict]:
        with self.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT sequence, occurred_at, event, actor, note FROM audit "
                    "WHERE run_id = ? ORDER BY sequence",
                    (run_id,),
                )
            ]

    def stats(self) -> dict:
        with self.connect() as db:
            return {
                "runs": db.execute("SELECT count(*) FROM runs").fetchone()[0],
                "tickets": db.execute("SELECT count(*) FROM tickets").fetchone()[0],
                "knowledge_chunks": db.execute("SELECT count(*) FROM chunks").fetchone()[0],
            }
