import sqlite3
import time
import json
from contextlib import contextmanager
from pathlib import Path

from .models import ProcessResult


class Conflict(Exception):
    pass


class Store:
    """Single-worker request journal; reservation precedes the potentially billed call."""

    def __init__(self, path: Path, ttl_hours: int):
        self.path = path
        self.ttl_seconds = ttl_hours * 3600
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY, digest TEXT NOT NULL, result TEXT, created REAL NOT NULL
            )""")
        self.prune()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            with connection:
                yield connection
        finally:
            # sqlite3's own context manager commits/rolls back but does not close.
            connection.close()

    def prune(self):
        with self.connect() as db:
            db.execute("DELETE FROM requests WHERE created < ?", (time.time() - self.ttl_seconds,))

    def find(self, request_id: str, digest: str) -> tuple[bool, ProcessResult | None]:
        with self.connect() as db:
            row = db.execute("SELECT digest, result FROM requests WHERE id = ?", (request_id,)).fetchone()
        if row is None:
            return False, None
        if row[0] != digest:
            raise Conflict("Request ID was already used for different input.")
        if not row[1]:
            return True, None
        result = json.loads(row[1])
        # Earlier journal rows predate Anthropic support; preserve their original replay.
        result.setdefault("provider", "demo" if result["mode"] == "demo" else "openai")
        return True, ProcessResult.model_validate(result)

    def reserve(self, request_id: str, digest: str):
        with self.connect() as db:
            db.execute("INSERT INTO requests VALUES (?, ?, NULL, ?)", (request_id, digest, time.time()))

    def finish(self, result: ProcessResult):
        with self.connect() as db:
            db.execute("UPDATE requests SET result = ? WHERE id = ?", (result.model_dump_json(), str(result.request_id)))
