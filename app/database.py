"""Small SQLite persistence layer using only the Python standard library."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from app.config import settings

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protocol TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    source TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    subject TEXT NOT NULL,
    message TEXT NOT NULL,
    category TEXT NOT NULL,
    urgency TEXT NOT NULL,
    priority INTEGER NOT NULL,
    sentiment TEXT NOT NULL,
    confidence REAL NOT NULL,
    summary TEXT NOT NULL,
    analysis_json TEXT NOT NULL,
    reply TEXT NOT NULL,
    department TEXT NOT NULL,
    sla_hours INTEGER NOT NULL,
    status TEXT NOT NULL,
    used_llm INTEGER NOT NULL,
    processing_ms REAL NOT NULL,
    trace_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_requests_created_at ON requests(created_at);
CREATE INDEX IF NOT EXISTS idx_requests_category ON requests(category);
"""

@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(CREATE_TABLE)
        conn.commit()
        yield conn
    finally:
        conn.close()

def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["analysis"] = json.loads(data.pop("analysis_json"))
    data["trace"] = json.loads(data.pop("trace_json"))
    data["used_llm"] = bool(data["used_llm"])
    return data

def insert_request(data: dict[str, Any]) -> dict[str, Any]:
    with connection() as conn:
        cursor = conn.execute(
            """INSERT INTO requests (
                protocol,created_at,source,name,email,subject,message,category,urgency,
                priority,sentiment,confidence,summary,analysis_json,reply,department,
                sla_hours,status,used_llm,processing_ms,trace_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                data["protocol"], data["created_at"], data["source"], data["name"], data["email"],
                data["subject"], data["message"], data["category"], data["urgency"], data["priority"],
                data["sentiment"], data["confidence"], data["summary"], json.dumps(data["analysis"], ensure_ascii=False),
                data["reply"], data["department"], data["sla_hours"], data["status"], int(data["used_llm"]),
                data["processing_ms"], json.dumps(data["trace"], ensure_ascii=False),
            ),
        )
        conn.commit()
        saved = conn.execute("SELECT * FROM requests WHERE id=?", (cursor.lastrowid,)).fetchone()
        return row_to_dict(saved)

def get_request(request_id: int) -> dict[str, Any] | None:
    with connection() as conn:
        row = conn.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
        return row_to_dict(row) if row else None

def list_requests(*, category: str | None = None, urgency: str | None = None,
                  department: str | None = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    filters, values = [], []
    for column, value in (("category", category), ("urgency", urgency), ("department", department)):
        if value:
            filters.append(f"{column}=?")
            values.append(value)
    where = (" WHERE " + " AND ".join(filters)) if filters else ""
    values.extend([limit, offset])
    with connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM requests{where} ORDER BY id DESC LIMIT ? OFFSET ?", values
        ).fetchall()
        return [row_to_dict(row) for row in rows]

def all_requests() -> list[dict[str, Any]]:
    return list_requests(limit=200000, offset=0)
def delete_request(request_id: int) -> bool:
    with connection() as conn:
        cursor = conn.execute(
            "DELETE FROM requests WHERE id = ?",
            (request_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
