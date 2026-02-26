import sqlite3
import os
from datetime import datetime, date
from config import DB_PATH


def get_db():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # better concurrent access
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            audio_filename TEXT,
            duration_seconds REAL,
            transcription TEXT,
            transcription_status TEXT DEFAULT 'pending',
            notes TEXT,
            source TEXT DEFAULT 'voice',
            is_favorite INTEGER DEFAULT 0,
            is_archived INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS entry_tags (
            entry_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (entry_id, tag_id),
            FOREIGN KEY (entry_id) REFERENCES entries(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS milestones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER,
            title TEXT NOT NULL,
            milestone_date DATE,
            FOREIGN KEY (entry_id) REFERENCES entries(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            last_shown DATE
        );

        CREATE INDEX IF NOT EXISTS idx_entries_created ON entries(created_at);
        CREATE INDEX IF NOT EXISTS idx_entries_status ON entries(transcription_status);
        CREATE INDEX IF NOT EXISTS idx_entries_favorite ON entries(is_favorite);
    """)

    # Seed some default prompts
    cursor = conn.execute("SELECT COUNT(*) FROM prompts")
    if cursor.fetchone()[0] == 0:
        prompts = [
            "What made you smile today?",
            "What new thing did your little one do today?",
            "What moment do you want to remember forever?",
            "What surprised you about being a parent today?",
            "What was the funniest thing that happened today?",
            "What are you grateful for today?",
            "How did your child make you feel today?",
            "What did you learn from your kid today?",
            "Describe the way your child looked at you today.",
            "What sound did your baby make that melted your heart?",
            "What was bedtime like tonight?",
            "What would you tell your future self about today?",
        ]
        conn.executemany("INSERT INTO prompts (text) VALUES (?)", [(p,) for p in prompts])

    conn.commit()
    conn.close()


# --- Entry helpers ---

def create_entry(audio_filename=None, duration_seconds=None, notes=None, source="voice"):
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO entries (audio_filename, duration_seconds, notes, source,
           transcription_status)
           VALUES (?, ?, ?, ?, ?)""",
        (audio_filename, duration_seconds, notes, source,
         "pending" if audio_filename else "none")
    )
    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return entry_id


def get_entry(entry_id):
    conn = get_db()
    entry = conn.execute(
        "SELECT * FROM entries WHERE id = ?", (entry_id,)
    ).fetchone()
    tags = conn.execute(
        """SELECT t.name FROM tags t
           JOIN entry_tags et ON t.id = et.tag_id
           WHERE et.entry_id = ?""", (entry_id,)
    ).fetchall()
    conn.close()
    return entry, [t["name"] for t in tags]


def get_entries(page=1, per_page=20, favorites_only=False, tag=None):
    conn = get_db()
    offset = (page - 1) * per_page

    if tag:
        entries = conn.execute(
            """SELECT e.* FROM entries e
               JOIN entry_tags et ON e.id = et.entry_id
               JOIN tags t ON t.id = et.tag_id
               WHERE t.name = ? AND e.is_archived = 0
               ORDER BY e.created_at DESC LIMIT ? OFFSET ?""",
            (tag, per_page, offset)
        ).fetchall()
    elif favorites_only:
        entries = conn.execute(
            """SELECT * FROM entries
               WHERE is_favorite = 1 AND is_archived = 0
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (per_page, offset)
        ).fetchall()
    else:
        entries = conn.execute(
            """SELECT * FROM entries WHERE is_archived = 0
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (per_page, offset)
        ).fetchall()

    total = conn.execute(
        "SELECT COUNT(*) FROM entries WHERE is_archived = 0"
    ).fetchone()[0]
    conn.close()
    return entries, total


def update_entry(entry_id, notes=None, transcription=None, transcription_status=None):
    conn = get_db()
    fields = []
    values = []
    if notes is not None:
        fields.append("notes = ?")
        values.append(notes)
    if transcription is not None:
        fields.append("transcription = ?")
        values.append(transcription)
    if transcription_status is not None:
        fields.append("transcription_status = ?")
        values.append(transcription_status)
    if fields:
        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(entry_id)
        conn.execute(f"UPDATE entries SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    conn.close()


def delete_entry(entry_id):
    conn = get_db()
    conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()


def toggle_favorite(entry_id):
    conn = get_db()
    conn.execute(
        "UPDATE entries SET is_favorite = NOT is_favorite WHERE id = ?",
        (entry_id,)
    )
    conn.commit()
    conn.close()


def search_entries(query):
    conn = get_db()
    like = f"%{query}%"
    entries = conn.execute(
        """SELECT * FROM entries
           WHERE (transcription LIKE ? OR notes LIKE ?) AND is_archived = 0
           ORDER BY created_at DESC""",
        (like, like)
    ).fetchall()
    conn.close()
    return entries


def get_on_this_day():
    """Get entries from this day in previous months/years."""
    conn = get_db()
    today = date.today()
    entries = conn.execute(
        """SELECT * FROM entries
           WHERE strftime('%m-%d', created_at) = ? AND is_archived = 0
           ORDER BY created_at ASC""",
        (today.strftime("%m-%d"),)
    ).fetchall()
    conn.close()
    return entries


# --- Tag helpers ---

def add_tag(entry_id, tag_name):
    tag_name = tag_name.strip().lower()
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
    tag = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
    conn.execute(
        "INSERT OR IGNORE INTO entry_tags (entry_id, tag_id) VALUES (?, ?)",
        (entry_id, tag["id"])
    )
    conn.commit()
    conn.close()


def remove_tag(entry_id, tag_name):
    conn = get_db()
    tag = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
    if tag:
        conn.execute(
            "DELETE FROM entry_tags WHERE entry_id = ? AND tag_id = ?",
            (entry_id, tag["id"])
        )
        conn.commit()
    conn.close()


def get_all_tags():
    conn = get_db()
    tags = conn.execute(
        """SELECT t.name, COUNT(et.entry_id) as entry_count
           FROM tags t LEFT JOIN entry_tags et ON t.id = et.tag_id
           GROUP BY t.id ORDER BY entry_count DESC"""
    ).fetchall()
    conn.close()
    return tags


# --- Milestone helpers ---

def create_milestone(title, milestone_date=None, entry_id=None):
    conn = get_db()
    conn.execute(
        "INSERT INTO milestones (title, milestone_date, entry_id) VALUES (?, ?, ?)",
        (title, milestone_date, entry_id)
    )
    conn.commit()
    conn.close()


def get_milestones():
    conn = get_db()
    milestones = conn.execute(
        "SELECT * FROM milestones ORDER BY milestone_date DESC"
    ).fetchall()
    conn.close()
    return milestones


# --- Stats ---

def get_stats():
    conn = get_db()
    stats = {}
    stats["total_entries"] = conn.execute(
        "SELECT COUNT(*) FROM entries WHERE is_archived = 0"
    ).fetchone()[0]
    stats["total_favorites"] = conn.execute(
        "SELECT COUNT(*) FROM entries WHERE is_favorite = 1"
    ).fetchone()[0]
    stats["total_duration_seconds"] = conn.execute(
        "SELECT COALESCE(SUM(duration_seconds), 0) FROM entries"
    ).fetchone()[0]
    stats["total_tags"] = conn.execute(
        "SELECT COUNT(*) FROM tags"
    ).fetchone()[0]
    stats["total_milestones"] = conn.execute(
        "SELECT COUNT(*) FROM milestones"
    ).fetchone()[0]

    # Streak: consecutive days with entries
    days = conn.execute(
        """SELECT DISTINCT date(created_at) as day FROM entries
           WHERE is_archived = 0 ORDER BY day DESC"""
    ).fetchall()
    streak = 0
    if days:
        from datetime import timedelta
        check = date.today()
        for row in days:
            day = date.fromisoformat(row["day"])
            if day == check:
                streak += 1
                check -= timedelta(days=1)
            elif day == check - timedelta(days=1):
                streak += 1
                check = day - timedelta(days=1)
            else:
                break
    stats["streak"] = streak
    conn.close()
    return stats


def get_untranscribed_entries():
    """Get entries waiting for remote transcription."""
    conn = get_db()
    entries = conn.execute(
        """SELECT id, audio_filename, duration_seconds, created_at
           FROM entries
           WHERE transcription_status = 'pending' AND audio_filename IS NOT NULL
           ORDER BY created_at ASC"""
    ).fetchall()
    conn.close()
    return entries


def get_random_prompt():
    conn = get_db()
    prompt = conn.execute(
        "SELECT * FROM prompts ORDER BY RANDOM() LIMIT 1"
    ).fetchone()
    conn.close()
    return prompt


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
