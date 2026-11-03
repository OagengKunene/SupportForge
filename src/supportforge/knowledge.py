"""Local Markdown ingestion and parameterised FTS5/BM25 retrieval."""

import hashlib
import re
from pathlib import Path

from supportforge.models import Source
from supportforge.store import Store

STOP_WORDS = set(
    """the and for are was were have has had with that this from you your can could
would should please help need how what when where why does not want about into been will them
they our their but just get got some also now then use using each all who which may like tell
me my must make thanks thank hello hi any its it's
i a an to of in is it on at as do be or by""".split()
)


class KnowledgeBase:
    def __init__(self, store: Store):
        self.store = store

    def ingest(self, directory: Path) -> int:
        if not directory.is_dir():
            raise ValueError(f"Knowledge directory does not exist: {directory}")
        chunks = []
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            title = path.stem.replace("-", " ").title()
            for section in re.split(r"(?m)^## +", text):
                section = section.strip()
                if not section:
                    continue
                if section.startswith("# "):
                    first, _, section = section.partition("\n")
                    title = first.removeprefix("# ").strip()
                if not section.strip():
                    continue
                for offset in range(0, len(section), 1500):
                    body = section[offset : offset + 1500].strip()
                    digest = hashlib.sha256(f"{path.name}:{body}".encode()).hexdigest()[:16]
                    chunks.append((f"kb-{digest}", title, path.name, body))
        if not chunks:
            raise ValueError("Knowledge directory must contain non-empty Markdown documents")
        with self.store.connect() as db:
            db.execute("DELETE FROM chunks")
            db.execute("DELETE FROM chunks_fts")
            db.executemany("INSERT INTO chunks VALUES (?, ?, ?, ?)", chunks)
            db.executemany(
                "INSERT INTO chunks_fts(id, title, body) VALUES (?, ?, ?)",
                [(chunk[0], chunk[1], chunk[3]) for chunk in chunks],
            )
        return len(chunks)

    def search(self, query: str, limit: int = 4) -> list[Source]:
        terms = [
            word
            for word in re.findall(r"[a-z0-9]+", query.lower())
            if len(word) > 2 and word not in STOP_WORDS
        ]
        terms = list(dict.fromkeys(terms))[:20]
        if not terms:
            return []
        match = " OR ".join(f'"{term}"' for term in terms)
        with self.store.connect() as db:
            rows = db.execute(
                "SELECT c.id, c.title, c.document, c.body FROM chunks_fts f "
                "JOIN chunks c ON c.id = f.id WHERE chunks_fts MATCH ? "
                "ORDER BY bm25(chunks_fts), c.id LIMIT ?",
                (match, max(1, min(limit, 6))),
            ).fetchall()
        return [
            Source(id=row["id"], title=row["title"], document=row["document"], excerpt=row["body"])
            for row in rows
        ]

    def documents(self) -> list[dict]:
        with self.store.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT document, title, count(*) AS chunks FROM chunks "
                    "GROUP BY document, title "
                    "ORDER BY title"
                )
            ]
