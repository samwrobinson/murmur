#!/usr/bin/env python3
"""
Murmur Share Sync
Mirrors journal entries to human-readable files in the Samba share folder.
Runs as a background service, syncing every 30 seconds.

Share structure:
    /home/murmur/share/
    ├── audio/
    │   ├── 2026-02-15_first-laugh.wav
    │   └── 2026-02-20_bath-time.wav
    ├── entries/
    │   ├── 2026-02-15_first-laugh.txt
    │   └── 2026-02-20_bath-time.txt
    ├── favorites/
    │   └── (symlinks to favorite entries)
    └── README.txt
"""

import os
import re
import shutil
import sqlite3
import time
from datetime import datetime

# Paths
DB_PATH = os.path.expanduser("~/murmur/api/journal.db")
AUDIO_SRC = os.path.expanduser("~/murmur/api/audio")
SHARE_DIR = os.path.expanduser("~/share")
SHARE_AUDIO = os.path.join(SHARE_DIR, "audio")
SHARE_ENTRIES = os.path.join(SHARE_DIR, "entries")
SHARE_FAVORITES = os.path.join(SHARE_DIR, "favorites")
SYNC_INTERVAL = 30  # seconds


def slugify(text, max_len=40):
    """Turn transcription/notes into a filename-safe slug."""
    if not text:
        return "untitled"
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = text.strip('-')
    return text[:max_len].rstrip('-') or "untitled"


def format_entry(entry):
    """Format an entry as a nice readable text file."""
    lines = []
    lines.append("=" * 60)
    lines.append(f"  MURMUR — Memory #{entry['id']}")
    lines.append("=" * 60)
    lines.append("")

    created = entry.get("created_at", "")
    if created:
        try:
            dt = datetime.fromisoformat(created)
            lines.append(f"  Date:     {dt.strftime('%A, %B %d, %Y')}")
            lines.append(f"  Time:     {dt.strftime('%I:%M %p')}")
        except (ValueError, TypeError):
            lines.append(f"  Date:     {created}")

    source = entry.get("source", "voice")
    lines.append(f"  Source:   {source}")

    duration = entry.get("duration_seconds")
    if duration:
        m, s = divmod(int(duration), 60)
        lines.append(f"  Duration: {m}:{s:02d}")

    if entry.get("is_favorite"):
        lines.append(f"  Favorite: ★")

    lines.append("")
    lines.append("-" * 60)
    lines.append("")

    # Transcription
    transcription = entry.get("transcription", "")
    if transcription:
        lines.append("  TRANSCRIPTION")
        lines.append("")
        for para in transcription.split("\n"):
            lines.append(f"  {para}")
        lines.append("")

    # Notes
    notes = entry.get("notes", "")
    if notes:
        lines.append("  NOTES")
        lines.append("")
        for para in notes.split("\n"):
            lines.append(f"  {para}")
        lines.append("")

    # Audio reference
    audio = entry.get("audio_filename", "")
    if audio:
        lines.append("-" * 60)
        lines.append(f"  Audio: audio/{audio}")

    lines.append("")
    return "\n".join(lines)


def get_entry_filename(entry):
    """Generate a human-readable filename from an entry."""
    created = entry.get("created_at", "")
    date_prefix = "undated"
    if created:
        try:
            dt = datetime.fromisoformat(created)
            date_prefix = dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass

    text = entry.get("transcription") or entry.get("notes") or ""
    slug = slugify(text)
    return f"{date_prefix}_{slug}"


def sync():
    """One sync pass — mirror DB entries to share folder."""
    if not os.path.exists(DB_PATH):
        return

    # Ensure directories exist
    os.makedirs(SHARE_AUDIO, exist_ok=True)
    os.makedirs(SHARE_ENTRIES, exist_ok=True)
    os.makedirs(SHARE_FAVORITES, exist_ok=True)

    # Write README
    readme_path = os.path.join(SHARE_DIR, "README.txt")
    if not os.path.exists(readme_path):
        with open(readme_path, "w") as f:
            f.write("MURMUR — Your Voice Journal\n")
            f.write("=" * 40 + "\n\n")
            f.write("This folder contains all your journal entries\n")
            f.write("as plain text and audio files.\n\n")
            f.write("Folders:\n")
            f.write("  entries/    — Text files of each memory\n")
            f.write("  audio/      — Original voice recordings\n")
            f.write("  favorites/  — Shortcuts to starred entries\n\n")
            f.write("These files are read-only. Use the web app\n")
            f.write("at http://murmur.local to record, edit, and\n")
            f.write("search your memories.\n\n")
            f.write("Your data never leaves your home network.\n")

    # Connect to DB
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get all entries
    cur.execute("SELECT * FROM entries ORDER BY created_at DESC")
    entries = cur.fetchall()

    # Track what we write so we can clean up stale files
    current_entry_files = set()
    current_audio_files = set()
    current_fav_files = set()

    for entry in entries:
        entry = dict(entry)
        basename = get_entry_filename(entry)

        # Write text file
        txt_name = f"{basename}.txt"
        txt_path = os.path.join(SHARE_ENTRIES, txt_name)
        current_entry_files.add(txt_name)

        content = format_entry(entry)
        # Only write if changed (avoid unnecessary writes that confuse backup tools)
        should_write = True
        if os.path.exists(txt_path):
            with open(txt_path, "r") as f:
                if f.read() == content:
                    should_write = False
        if should_write:
            with open(txt_path, "w") as f:
                f.write(content)

        # Copy audio file
        audio = entry.get("audio_filename", "")
        if audio:
            src = os.path.join(AUDIO_SRC, audio)
            dst = os.path.join(SHARE_AUDIO, audio)
            current_audio_files.add(audio)
            if os.path.exists(src) and not os.path.exists(dst):
                shutil.copy2(src, dst)

        # Favorites — symlink into favorites folder
        if entry.get("is_favorite"):
            fav_link = os.path.join(SHARE_FAVORITES, txt_name)
            current_fav_files.add(txt_name)
            target = os.path.join("../entries", txt_name)
            if not os.path.exists(fav_link):
                try:
                    os.symlink(target, fav_link)
                except OSError:
                    pass

    # Clean up removed favorites
    if os.path.exists(SHARE_FAVORITES):
        for f in os.listdir(SHARE_FAVORITES):
            if f not in current_fav_files:
                try:
                    os.remove(os.path.join(SHARE_FAVORITES, f))
                except OSError:
                    pass

    conn.close()


def main():
    print("Murmur share sync started")
    print(f"  DB:    {DB_PATH}")
    print(f"  Share: {SHARE_DIR}")
    print(f"  Interval: {SYNC_INTERVAL}s")
    print()

    while True:
        try:
            sync()
        except Exception as e:
            print(f"Sync error: {e}")
        time.sleep(SYNC_INTERVAL)


if __name__ == "__main__":
    main()
