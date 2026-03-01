"""Re-import orphaned audio files into the database.

Run on the Pi after an accidental database overwrite:
    cd /home/murmur/murmur/api && python3 recover_audio.py
"""

import os
from datetime import datetime

from config import AUDIO_DIR, get_persisted_setting, OPENAI_API_KEY
from db import init_db, get_db
from transcribe import transcribe_entry

EXTENSIONS = (".wav", ".mp3", ".webm", ".m4a")


def recover():
    init_db()
    conn = get_db()

    # Find audio files already tracked so we don't duplicate
    tracked = set()
    for row in conn.execute("SELECT audio_filename FROM entries WHERE audio_filename IS NOT NULL"):
        tracked.add(row["audio_filename"])

    files = sorted(
        f for f in os.listdir(AUDIO_DIR)
        if os.path.splitext(f)[1].lower() in EXTENSIONS
    )

    added = 0
    for fname in files:
        if fname in tracked:
            continue

        # Parse timestamp from filename like 2025-03-01_143022.wav
        basename = os.path.splitext(fname)[0]
        try:
            created = datetime.strptime(basename, "%Y-%m-%d_%H%M%S")
        except ValueError:
            created = datetime.fromtimestamp(
                os.path.getmtime(os.path.join(AUDIO_DIR, fname))
            )

        filepath = os.path.join(AUDIO_DIR, fname)
        size = os.path.getsize(filepath)
        # Rough duration estimate: ~16KB/s for 16kHz mono WAV
        duration = round(size / 16000, 1) if size > 0 else None

        conn.execute(
            """INSERT INTO entries (audio_filename, duration_seconds, source,
               transcription_status, created_at, updated_at)
               VALUES (?, ?, 'button', 'pending', ?, ?)""",
            (fname, duration, created.isoformat(), created.isoformat()),
        )
        added += 1
        print(f"  + {fname}  ({created.strftime('%b %d %H:%M')})")

    conn.commit()

    if added == 0:
        print("No orphaned audio files found — database is up to date.")
        conn.close()
        return

    print(f"\nRecovered {added} entries.")

    # Kick off transcription for all pending entries
    api_key = get_persisted_setting("openai_api_key") or OPENAI_API_KEY
    if api_key:
        pending = conn.execute(
            """SELECT id, audio_filename FROM entries
               WHERE transcription_status = 'pending' AND audio_filename IS NOT NULL"""
        ).fetchall()
        conn.close()
        print(f"Transcribing {len(pending)} entries...\n")
        for row in pending:
            filepath = os.path.join(AUDIO_DIR, row["audio_filename"])
            if os.path.exists(filepath):
                transcribe_entry(row["id"], filepath, client_key=api_key)
    else:
        conn.close()
        print("No API key found — skipping transcription. Save a key in settings first.")


def transcribe_pending():
    """Transcribe all pending entries."""
    api_key = get_persisted_setting("openai_api_key") or OPENAI_API_KEY
    if not api_key:
        print("No API key found — save a key in settings first.")
        return

    conn = get_db()
    pending = conn.execute(
        """SELECT id, audio_filename FROM entries
           WHERE transcription_status = 'pending' AND audio_filename IS NOT NULL"""
    ).fetchall()
    conn.close()

    if not pending:
        print("No pending transcriptions.")
        return

    print(f"Transcribing {len(pending)} entries...\n")
    for row in pending:
        filepath = os.path.join(AUDIO_DIR, row["audio_filename"])
        if os.path.exists(filepath):
            transcribe_entry(row["id"], filepath, client_key=api_key)


if __name__ == "__main__":
    import sys
    if "--transcribe" in sys.argv:
        transcribe_pending()
    else:
        recover()
