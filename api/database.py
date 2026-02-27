import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "novels.db"


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    with _conn() as conn:
        conn.executescript("""
            PRAGMA journal_mode=WAL;
        """)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS novels (
                id          TEXT PRIMARY KEY,
                user_prompt TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'created',
                blueprint_json TEXT,
                current_chapter INTEGER NOT NULL DEFAULT 0,
                output_path TEXT NOT NULL DEFAULT '',
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS chapters (
                id          TEXT PRIMARY KEY,
                novel_id    TEXT NOT NULL REFERENCES novels(id),
                number      INTEGER NOT NULL,
                title       TEXT NOT NULL DEFAULT '',
                content     TEXT NOT NULL DEFAULT '',
                audit_passed INTEGER NOT NULL DEFAULT 0,
                audit_notes TEXT NOT NULL DEFAULT '',
                UNIQUE(novel_id, number)
            );

            CREATE TABLE IF NOT EXISTS chapter_summaries (
                novel_id    TEXT NOT NULL REFERENCES novels(id),
                chapter_number INTEGER NOT NULL,
                summary     TEXT NOT NULL,
                PRIMARY KEY (novel_id, chapter_number)
            );
        """)
        # Indexes for JOIN performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chapters_novel_id ON chapters(novel_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_summaries_novel_id ON chapter_summaries(novel_id)")

        # Migration: add style_config column if missing (safe for existing DBs)
        try:
            conn.execute("ALTER TABLE novels ADD COLUMN style_config TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise

        # Migration: add word_count column if missing
        try:
            conn.execute("ALTER TABLE chapters ADD COLUMN word_count INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise

        # Migration: add notes column if missing
        try:
            conn.execute("ALTER TABLE chapters ADD COLUMN notes TEXT NOT NULL DEFAULT ''")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise

        # Migration: add is_continuation column if missing
        try:
            conn.execute("ALTER TABLE novels ADD COLUMN is_continuation INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise

        # Backfill word_count for existing chapters (approximation via SQL — one-time)
        conn.execute("""
            UPDATE chapters
            SET word_count = LENGTH(TRIM(content)) - LENGTH(REPLACE(TRIM(content), ' ', '')) + 1
            WHERE word_count = 0 AND content != ''
        """)


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Novel CRUD ─────────────────────────────────────────────────────────────

def create_novel(novel_id: str, user_prompt: str, style_config: str | None = None) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO novels (id, user_prompt, style_config) VALUES (?, ?, ?)",
            (novel_id, user_prompt, style_config),
        )


def update_novel_status(novel_id: str, status: str, current_chapter: int = None) -> None:
    if current_chapter is not None:
        with _conn() as conn:
            conn.execute(
                "UPDATE novels SET status=?, current_chapter=? WHERE id=?",
                (status, current_chapter, novel_id),
            )
    else:
        with _conn() as conn:
            conn.execute(
                "UPDATE novels SET status=? WHERE id=?",
                (status, novel_id),
            )


def update_novel_blueprint(novel_id: str, blueprint_json: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE novels SET blueprint_json=? WHERE id=?",
            (blueprint_json, novel_id),
        )


def update_novel_output_path(novel_id: str, output_path: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE novels SET output_path=? WHERE id=?",
            (output_path, novel_id),
        )


def list_novels() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("""
            SELECT
                n.id, n.status, n.blueprint_json, n.created_at,
                COUNT(c.id) as chapter_count,
                COALESCE(SUM(c.word_count), 0) as total_words
            FROM novels n
            LEFT JOIN chapters c ON c.novel_id = n.id
            GROUP BY n.id
            ORDER BY n.created_at DESC
        """).fetchall()
        return [dict(r) for r in rows]


def delete_novel(novel_id: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM chapter_summaries WHERE novel_id=?", (novel_id,))
        conn.execute("DELETE FROM chapters WHERE novel_id=?", (novel_id,))
        conn.execute("DELETE FROM novels WHERE id=?", (novel_id,))


def get_novel(novel_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM novels WHERE id=?", (novel_id,)).fetchone()
        return dict(row) if row else None


# ── Chapter CRUD ───────────────────────────────────────────────────────────

def upsert_chapter(novel_id: str, chapter_id: str, number: int, title: str,
                   content: str, audit_passed: bool, audit_notes: str) -> None:
    wc = len(content.split())
    with _conn() as conn:
        conn.execute("""
            INSERT INTO chapters (id, novel_id, number, title, content, audit_passed, audit_notes, word_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(novel_id, number) DO UPDATE SET
                content=excluded.content,
                audit_passed=excluded.audit_passed,
                audit_notes=excluded.audit_notes,
                word_count=excluded.word_count
        """, (chapter_id, novel_id, number, title, content, int(audit_passed), audit_notes, wc))


def get_chapters(novel_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM chapters WHERE novel_id=? ORDER BY number",
            (novel_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_chapter_content(novel_id: str, number: int, content: str) -> None:
    wc = len(content.split())
    with _conn() as conn:
        conn.execute(
            "UPDATE chapters SET content=?, word_count=? WHERE novel_id=? AND number=?",
            (content, wc, novel_id, number),
        )


def update_chapter_notes(novel_id: str, number: int, notes: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE chapters SET notes=? WHERE novel_id=? AND number=?",
            (notes, novel_id, number),
        )


def get_chapter(novel_id: str, number: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM chapters WHERE novel_id=? AND number=?",
            (novel_id, number),
        ).fetchone()
        return dict(row) if row else None


# ── Summary CRUD ───────────────────────────────────────────────────────────

def save_chapter_with_summary(
    novel_id: str, chapter_id: str, number: int, title: str,
    content: str, audit_passed: bool, audit_notes: str,
    summary: str,
) -> None:
    """Atomically save chapter + summary in one transaction."""
    wc = len(content.split())
    with _conn() as conn:
        conn.execute("""
            INSERT INTO chapters (id, novel_id, number, title, content, audit_passed, audit_notes, word_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(novel_id, number) DO UPDATE SET
                content=excluded.content,
                audit_passed=excluded.audit_passed,
                audit_notes=excluded.audit_notes,
                word_count=excluded.word_count
        """, (chapter_id, novel_id, number, title, content, int(audit_passed), audit_notes, wc))
        if summary:
            conn.execute("""
                INSERT INTO chapter_summaries (novel_id, chapter_number, summary)
                VALUES (?, ?, ?)
                ON CONFLICT(novel_id, chapter_number) DO UPDATE SET summary=excluded.summary
            """, (novel_id, number, summary))


def save_summary(novel_id: str, chapter_number: int, summary: str) -> None:
    with _conn() as conn:
        conn.execute("""
            INSERT INTO chapter_summaries (novel_id, chapter_number, summary)
            VALUES (?, ?, ?)
            ON CONFLICT(novel_id, chapter_number) DO UPDATE SET summary=excluded.summary
        """, (novel_id, chapter_number, summary))


def delete_chapters_from(novel_id: str, from_number: int) -> None:
    """Delete chapters with number >= from_number and their summaries (one transaction)."""
    with _conn() as conn:
        conn.execute(
            "DELETE FROM chapter_summaries WHERE novel_id=? AND chapter_number>=?",
            (novel_id, from_number),
        )
        conn.execute(
            "DELETE FROM chapters WHERE novel_id=? AND number>=?",
            (novel_id, from_number),
        )


def get_summaries(novel_id: str) -> dict[int, str]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT chapter_number, summary FROM chapter_summaries WHERE novel_id=? ORDER BY chapter_number",
            (novel_id,),
        ).fetchall()
        return {r["chapter_number"]: r["summary"] for r in rows}
