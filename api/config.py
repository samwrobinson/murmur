import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "journal.db")
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
FLASK_PORT = 5001
FLASK_HOST = "0.0.0.0"  # accessible from other devices on network

# Whisper settings
WHISPER_MODEL = "tiny"  # tiny | base | small (tiny is fastest on Pi Zero 2)
WHISPER_USE_CLOUD = False  # set True to use OpenAI API instead of local
TRANSCRIBE_LOCALLY = False  # False = wait for remote worker (Mac Mini) to transcribe

# Audio settings
SAMPLE_RATE = 44100
CHANNELS = 1
AUDIO_FORMAT = "wav"

# Ensure audio directory exists
os.makedirs(AUDIO_DIR, exist_ok=True)
