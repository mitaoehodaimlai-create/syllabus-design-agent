"""
STEP 1 — Database Layer
-----------------------
Uses Python's built-in sqlite3.  No ORM needed for this scope.

Tables:
  users   — stores registered users + their role (admin | user)
  uploads — stores every file upload with who did it and the status
"""

import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "syllabus_agent.db"


# ── connection helper ─────────────────────────────────────────────
@contextmanager
def get_db():
    """
    Context-manager that opens a connection, yields a cursor,
    commits on success, rolls back on exception, always closes.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row       # rows behave like dicts
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── schema creation (run once on startup) ────────────────────────
def init_db() -> None:
    """Create tables if they don't already exist."""
    with get_db() as conn:
        conn.executescript("""
        -- USERS TABLE
        -- role is either 'admin' or 'user'
        CREATE TABLE IF NOT EXISTS users (
            id            TEXT PRIMARY KEY,
            username      TEXT UNIQUE NOT NULL,
            email         TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'user',
            is_active     INTEGER NOT NULL DEFAULT 1,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- UPLOADS TABLE
        -- tracks every JSON file uploaded by an admin
        CREATE TABLE IF NOT EXISTS uploads (
            id            TEXT PRIMARY KEY,
            filename      TEXT NOT NULL,
            uploaded_by   TEXT NOT NULL REFERENCES users(id),
            status        TEXT NOT NULL DEFAULT 'pending',
            output_md     TEXT,
            output_pdf    TEXT,
            error_message TEXT,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)


# ── user queries ─────────────────────────────────────────────────
def create_user(username: str, email: str, hashed_password: str, role: str = "user") -> dict:
    uid = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO users (id, username, email, hashed_password, role) VALUES (?,?,?,?,?)",
            (uid, username, email, hashed_password, role),
        )
    return {"id": uid, "username": username, "email": email, "role": role}


def get_user_by_username(username: str) -> sqlite3.Row | None:
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()


def get_user_by_id(user_id: str) -> sqlite3.Row | None:
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()


# ── upload queries ────────────────────────────────────────────────
def create_upload_record(filename: str, uploaded_by: str) -> str:
    uid = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO uploads (id, filename, uploaded_by) VALUES (?,?,?)",
            (uid, filename, uploaded_by),
        )
    return uid


def update_upload_status(
    upload_id: str,
    status: str,
    output_md: str = None,
    output_pdf: str = None,
    error_message: str = None,
) -> None:
    with get_db() as conn:
        conn.execute(
            """UPDATE uploads
               SET status=?, output_md=?, output_pdf=?, error_message=?
               WHERE id=?""",
            (status, output_md, output_pdf, error_message, upload_id),
        )


def list_uploads(limit: int = 50) -> list[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(
            "SELECT u.*, us.username FROM uploads u JOIN users us ON u.uploaded_by=us.id "
            "ORDER BY u.created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
