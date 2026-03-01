import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "journal.db")
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")
FLASK_PORT = 5001
FLASK_HOST = "0.0.0.0"  # accessible from other devices on network

# Whisper settings
WHISPER_MODEL = "tiny"  # tiny | base | small (tiny is fastest on Pi Zero 2)
WHISPER_USE_CLOUD = True  # set True to use OpenAI API instead of local
TRANSCRIBE_LOCALLY = True  # False = wait for remote worker (Mac Mini) to transcribe
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Audio settings
SAMPLE_RATE = 44100
CHANNELS = 1
AUDIO_FORMAT = "wav"

# Ensure audio directory exists
os.makedirs(AUDIO_DIR, exist_ok=True)


def get_persisted_setting(key):
    """Read a single value from settings.json (returns None if missing)."""
    try:
        with open(SETTINGS_PATH, "r") as f:
            return json.load(f).get(key)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def set_persisted_setting(key, value):
    """Write a single key/value into settings.json (merges with existing)."""
    data = {}
    try:
        with open(SETTINGS_PATH, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    data[key] = value
    with open(SETTINGS_PATH, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
