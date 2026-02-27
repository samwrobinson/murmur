"""Remote Whisper transcription worker for Murmur.

Runs on a capable machine (e.g. Mac Mini) and polls the Pi's API
for untranscribed voice entries, transcribes them locally with Whisper,
and pushes the results back.

Usage:
    pip3 install openai-whisper requests
    python3 transcribe_worker.py
"""

import os
import sys
import time
import tempfile
import traceback

import requests
import urllib3
import whisper

# Suppress SSL warnings for self-signed cert
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Configuration ---
PI_BASE_URL = os.environ.get("MURMUR_API_URL", "http://murmur.local:5001")
POLL_INTERVAL = int(os.environ.get("MURMUR_POLL_INTERVAL", "10"))
WHISPER_MODEL = os.environ.get("MURMUR_WHISPER_MODEL", "base")

# --- Whisper model (loaded once) ---
_model = None


def get_model():
    global _model
    if _model is None:
        print(f"[worker] Loading Whisper model '{WHISPER_MODEL}'...")
        _model = whisper.load_model(WHISPER_MODEL)
        print("[worker] Model loaded.")
    return _model


def fetch_untranscribed():
    """Get the list of entries waiting for transcription."""
    resp = requests.get(f"{PI_BASE_URL}/api/entries/untranscribed", timeout=10, verify=False)
    resp.raise_for_status()
    return resp.json()["entries"]


def download_audio(filename):
    """Download an audio file from the Pi to a temp file. Returns the path."""
    resp = requests.get(f"{PI_BASE_URL}/api/audio/{filename}", timeout=30, verify=False)
    resp.raise_for_status()
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.write(resp.content)
    tmp.close()
    return tmp.name


def push_transcription(entry_id, text):
    """Send the transcription result back to the Pi."""
    resp = requests.put(
        f"{PI_BASE_URL}/api/entries/{entry_id}",
        json={"transcription": text, "transcription_status": "done"},
        timeout=10,
        verify=False,
    )
    resp.raise_for_status()


def mark_failed(entry_id):
    """Mark an entry as failed on the Pi."""
    try:
        requests.put(
            f"{PI_BASE_URL}/api/entries/{entry_id}",
            json={"transcription_status": "failed"},
            timeout=10,
            verify=False,
        )
    except Exception:
        pass


def process_entry(entry):
    """Download, transcribe, and push back a single entry."""
    entry_id = entry["id"]
    filename = entry["audio_filename"]
    print(f"[worker] Processing entry {entry_id}: {filename}")

    tmp_path = download_audio(filename)
    try:
        model = get_model()
        result = model.transcribe(tmp_path)
        text = result.get("text", "").strip()
        push_transcription(entry_id, text)
        print(f"[worker] Entry {entry_id} done ({len(text)} chars)")
    except Exception:
        traceback.print_exc()
        mark_failed(entry_id)
        print(f"[worker] Entry {entry_id} FAILED")
    finally:
        os.unlink(tmp_path)


def main():
    print(f"[worker] Murmur transcription worker")
    print(f"[worker] API: {PI_BASE_URL}")
    print(f"[worker] Model: {WHISPER_MODEL}")
    print(f"[worker] Poll interval: {POLL_INTERVAL}s")
    print()

    # Eagerly load the model so it's ready when work arrives
    get_model()

    while True:
        try:
            entries = fetch_untranscribed()
            if entries:
                print(f"[worker] Found {len(entries)} untranscribed entries")
                for entry in entries:
                    process_entry(entry)
        except requests.ConnectionError:
            print("[worker] Pi unreachable — will retry")
        except Exception:
            traceback.print_exc()

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
