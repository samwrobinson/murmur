"""Whisper transcription for Murmur voice entries (cloud or local)."""

import threading
import traceback

import requests

from config import WHISPER_MODEL, WHISPER_USE_CLOUD, OPENAI_API_KEY
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


def transcribe_entry_cloud(entry_id, filepath, client_key=None):
    """Send audio to OpenAI Whisper API and write the result back to the database."""
    api_key = client_key or OPENAI_API_KEY
    if not api_key:
        print(f"[transcribe] Entry {entry_id} — no OpenAI API key available, skipping cloud transcription")
        update_entry(entry_id, transcription_status="failed")
        return
    try:
        print(f"[transcribe] Starting cloud transcription for entry {entry_id}: {filepath}")
        with open(filepath, "rb") as audio_file:
            resp = requests.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": audio_file},
                data={"model": "whisper-1"},
                timeout=300,
            )
        resp.raise_for_status()
        text = resp.json().get("text", "").strip()
        update_entry(entry_id, transcription=text, transcription_status="done")
        print(f"[transcribe] Entry {entry_id} done via cloud ({len(text)} chars)")
    except Exception:
        traceback.print_exc()
        update_entry(entry_id, transcription_status="failed")
        print(f"[transcribe] Entry {entry_id} cloud transcription FAILED")


def transcribe_entry(entry_id, filepath, client_key=None):
    """Transcribe an audio entry (cloud or local depending on config).

    Intended to be called in a background thread.  Sets
    transcription_status to "done" on success, "failed" on error.
    """
    if WHISPER_USE_CLOUD:
        return transcribe_entry_cloud(entry_id, filepath, client_key=client_key)

    try:
        print(f"[transcribe] Starting local transcription for entry {entry_id}: {filepath}")
        model = _get_model()
        result = model.transcribe(filepath)
        text = result.get("text", "").strip()
        update_entry(entry_id, transcription=text, transcription_status="done")
        print(f"[transcribe] Entry {entry_id} done ({len(text)} chars)")
    except Exception:
        traceback.print_exc()
        update_entry(entry_id, transcription_status="failed")
        print(f"[transcribe] Entry {entry_id} FAILED")
