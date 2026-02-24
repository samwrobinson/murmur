"""Seed the database with sample entries for testing the web UI."""
from db import init_db, create_entry, update_entry, add_tag, create_milestone, get_db
from datetime import datetime, timedelta
import random

init_db()

# Sample entries simulating real dad journal usage
samples = [
    {
        "notes": None,
        "transcription": "She grabbed my finger today for the first time. Like really grabbed it, not just a reflex. She looked right at me and held on. I almost cried in the middle of Target.",
        "source": "voice",
        "duration": 12.4,
        "days_ago": 45,
        "tags": ["milestone", "tender"],
        "favorite": True,
    },
    {
        "notes": None,
        "transcription": "Bath time was hilarious tonight. She discovered splashing and just went for it. Water everywhere. We're both soaked and she's laughing that deep belly laugh.",
        "source": "voice",
        "duration": 8.2,
        "days_ago": 30,
        "tags": ["funny", "bath-time"],
        "favorite": False,
    },
    {
        "notes": "First time she slept through the whole night. 7pm to 6am. I woke up in a panic at 3am thinking something was wrong. She was just peacefully sleeping. I stood there watching her breathe for like ten minutes.",
        "transcription": None,
        "source": "web",
        "duration": None,
        "days_ago": 22,
        "tags": ["milestone", "sleep"],
        "favorite": True,
    },
    {
        "notes": None,
        "transcription": "Walking through the park with her in the carrier. She keeps reaching for leaves on the trees. Everything is new to her and it's making me see everything differently too.",
        "source": "voice",
        "duration": 15.1,
        "days_ago": 18,
        "tags": ["outside", "tender"],
        "favorite": False,
    },
    {
        "notes": None,
        "transcription": "She said something that sounded like dada today. Probably just babbling but I'm counting it. My heart is so full right now.",
        "source": "voice",
        "duration": 6.8,
        "days_ago": 10,
        "tags": ["milestone", "first-words"],
        "favorite": True,
    },
    {
        "notes": "Rough night. She's teething and nothing seems to help. Held her for three hours just rocking. My back is killing me but she finally fell asleep on my chest. These hard nights matter too.",
        "transcription": None,
        "source": "web",
        "duration": None,
        "days_ago": 7,
        "tags": ["tough-days"],
        "favorite": False,
    },
    {
        "notes": None,
        "transcription": "Feeding time. She's trying solid food for the first time. Sweet potatoes. The face she made... pure confusion and then she went back for more. Got it all over her face and in her hair somehow.",
        "source": "voice",
        "duration": 18.3,
        "days_ago": 5,
        "tags": ["funny", "milestone", "food"],
        "favorite": True,
    },
    {
        "notes": None,
        "transcription": "She rolled over today. Back to belly. Then got stuck and got really mad about it. I helped her back and she immediately rolled over again. Determined little human.",
        "source": "voice",
        "duration": 11.0,
        "days_ago": 3,
        "tags": ["milestone"],
        "favorite": False,
    },
    {
        "notes": "Sitting on the porch watching the rain together. She's fascinated by the sound. Just the two of us. These quiet moments are my favorite.",
        "transcription": None,
        "source": "web",
        "duration": None,
        "days_ago": 1,
        "tags": ["tender", "quiet-moments"],
        "favorite": True,
    },
    {
        "notes": None,
        "transcription": "Morning routine. Changed her diaper, made faces at her while she was on the changing table. She thinks peek-a-boo is the funniest thing ever invented. I kind of agree.",
        "source": "voice",
        "duration": 9.5,
        "days_ago": 0,
        "tags": ["funny", "morning"],
        "favorite": False,
    },
]

conn = get_db()
for s in samples:
    created = datetime.now() - timedelta(days=s["days_ago"], hours=random.randint(0, 12))
    audio_fn = f"{created.strftime('%Y-%m-%d_%H%M%S')}.wav" if s["source"] == "voice" else None
    status = "done" if s["transcription"] else "none"

    cursor = conn.execute(
        """INSERT INTO entries (created_at, updated_at, audio_filename, duration_seconds,
           transcription, transcription_status, notes, source, is_favorite)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (created, created, audio_fn, s["duration"], s["transcription"], status,
         s["notes"], s["source"], 1 if s["favorite"] else 0)
    )
    entry_id = cursor.lastrowid
    for tag in s["tags"]:
        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
        tag_row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag,)).fetchone()
        conn.execute("INSERT OR IGNORE INTO entry_tags (entry_id, tag_id) VALUES (?, ?)",
                     (entry_id, tag_row["id"]))

conn.commit()
conn.close()

# Add some milestones
create_milestone("First real grip", (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d"))
create_milestone("Slept through the night", (datetime.now() - timedelta(days=22)).strftime("%Y-%m-%d"))
create_milestone("First 'dada'", (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"))
create_milestone("First solid food", (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"))
create_milestone("First roll over", (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"))

print("Seeded database with 10 sample entries and 5 milestones!")
