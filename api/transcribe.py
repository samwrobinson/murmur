"""Local Whisper transcription for Murmur voice entries."""

import threading
import traceback

from config import WHISPER_MODEL
from db import update_entry

_model = None
_model_lock = threading.Lock()


def _get_model():
    """Lazy-load the Whisper model on first use (avoids slow startup)."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                import whisper
                print(f"[transcribe] Loading Whisper model '{WHISPER_MODEL}'...")
                _model = whisper.load_model(WHISPER_MODEL)
                print("[transcribe] Model loaded.")
    return _model


def transcribe_entry(entry_id, filepath):
    """Run Whisper on *filepath* and write the result back to the database.

    Intended to be called in a background thread.  Sets
    transcription_status to "done" on success, "failed" on error.
    """
    try:
        print(f"[transcribe] Starting transcription for entry {entry_id}: {filepath}")
        model = _get_model()
        result = model.transcribe(filepath)
        text = result.get("text", "").strip()
        update_entry(entry_id, transcription=text, transcription_status="done")
        print(f"[transcribe] Entry {entry_id} done ({len(text)} chars)")
    except Exception:
        traceback.print_exc()
        update_entry(entry_id, transcription_status="failed")
        print(f"[transcribe] Entry {entry_id} FAILED")
