#!/usr/bin/env python3
"""
Murmur WhisPlay HAT Recorder

Press the WhisPlay button to record a voice journal entry directly on the Pi.
The recording gets uploaded to the local Murmur Flask API, transcribed, and
appears in the app/web UI.

Interaction flow:
  Idle        → LCD "Murmur" / "Press to record", LED blue breathing
  Press       → Start recording, LCD "Recording...", LED red blink
  Press again → Stop recording, LCD "Saving...", LED yellow
  Upload      → POST audio to API
  Success     → LCD "Saved!", LED green, beep, return to idle
  Error       → LCD error message, LED red solid, return to idle

Dependencies:
  sudo apt install python3-pil python3-requests alsa-utils

Usage:
  python3 murmur_recorder.py
  # Or specify sound card:
  python3 murmur_recorder.py --card 1
"""

import argparse
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time

import requests

sys.path.append("/home/murmur/Whisplay/Driver")
from WhisPlay import WhisPlayBoard  # noqa: E402

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_URL = os.environ.get("MURMUR_API_URL", "http://localhost:5001")
SAMPLE_RATE = 48000   # WM8960 native rate (clean MCLK on Pi)
CHANNELS = 2          # stereo — WM8960 dual mics
FORMAT = "S16_LE"
MAX_RECORD_SEC = 300  # 5 minute max


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class State:
    IDLE = 0
    RECORDING = 1
    UPLOADING = 2


# ---------------------------------------------------------------------------
# LCD screen generation (RGB565 via PIL — same as record_play_demo.py)
# ---------------------------------------------------------------------------

def make_screen(text, sub_text="", bg_color=(0, 0, 0), text_color=(255, 255, 255),
                width=240, height=280):
    """Generate RGB565 pixel data with centered text for the LCD."""
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    font_large = None
    font_small = None
    for fpath in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                  "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"]:
        if os.path.exists(fpath):
            try:
                font_large = ImageFont.truetype(fpath, 28)
                font_small = ImageFont.truetype(fpath, 18)
            except Exception:
                pass
            break
    if font_large is None:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Center main text
    bbox = draw.textbbox((0, 0), text, font=font_large)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (width - tw) // 2
    y = (height - th) // 2 - 15
    draw.text((x, y), text, fill=text_color, font=font_large)

    # Sub text below
    if sub_text:
        bbox2 = draw.textbbox((0, 0), sub_text, font=font_small)
        tw2 = bbox2[2] - bbox2[0]
        x2 = (width - tw2) // 2
        draw.text((x2, y + th + 15), sub_text, fill=text_color, font=font_small)

    # Convert to RGB565
    pixel_data = []
    for py in range(height):
        for px in range(width):
            r, g, b = img.getpixel((px, py))
            rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            pixel_data.extend([(rgb565 >> 8) & 0xFF, rgb565 & 0xFF])
    return pixel_data


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class MurmurRecorder:
    def __init__(self, card_index=None):
        self.board = WhisPlayBoard()
        self.board.set_backlight(60)

        self.card_index = card_index or self._find_wm8960_card()
        self._record_proc = None
        self._rec_file = None
        self._rec_start_time = None

        self.state = State.IDLE
        self._lock = threading.Lock()
        self._led_thread = None
        self._led_running = False

        # Pre-generate LCD screens
        w, h = self.board.LCD_WIDTH, self.board.LCD_HEIGHT
        self._screen_idle = make_screen(
            "Murmur", "Press to record",
            bg_color=(0, 0, 40), text_color=(100, 180, 255), width=w, height=h)
        self._screen_recording = make_screen(
            "Recording...", "Press to stop",
            bg_color=(60, 0, 0), text_color=(255, 80, 80), width=w, height=h)
        self._screen_saving = make_screen(
            "Saving...", "",
            bg_color=(40, 30, 0), text_color=(255, 200, 50), width=w, height=h)
        self._screen_saved = make_screen(
            "Saved!", "",
            bg_color=(0, 40, 0), text_color=(80, 255, 80), width=w, height=h)
        self._screen_error = make_screen(
            "Error", "See logs",
            bg_color=(60, 0, 0), text_color=(255, 80, 80), width=w, height=h)
        self._screen_too_short = make_screen(
            "Too short", "Try again",
            bg_color=(40, 30, 0), text_color=(255, 200, 50), width=w, height=h)

        # Register button callback — press to toggle recording
        self.board.on_button_press(self._on_button_press)

        # Configure ALSA mixer
        self._setup_mixer()

    def _find_wm8960_card(self):
        """Find WM8960 sound card number from /proc/asound/cards."""
        try:
            with open("/proc/asound/cards") as f:
                for line in f:
                    if "wm8960" in line.lower():
                        return int(line.strip().split()[0])
        except Exception:
            pass
        return 1  # Default

    def _setup_mixer(self):
        """Configure WM8960 mixer for recording + speaker playback."""
        card = str(self.card_index)
        cmds = [
            # Output routing (for beep playback)
            ["amixer", "-c", card, "sset", "Left Output Mixer PCM", "on"],
            ["amixer", "-c", card, "sset", "Right Output Mixer PCM", "on"],
            ["amixer", "-c", card, "sset", "Speaker", "121"],
            ["amixer", "-c", card, "sset", "Playback", "230"],
            # Recording input
            ["amixer", "-c", card, "sset", "Left Input Mixer Boost", "on"],
            ["amixer", "-c", card, "sset", "Right Input Mixer Boost", "on"],
            ["amixer", "-c", card, "sset", "Capture", "45"],
            ["amixer", "-c", card, "sset", "ADC PCM", "195"],
            # Microphone gain
            ["amixer", "-c", card, "sset", "Left Input Boost Mixer LINPUT1", "2"],
            ["amixer", "-c", card, "sset", "Right Input Boost Mixer RINPUT1", "2"],
        ]
        for cmd in cmds:
            try:
                subprocess.run(cmd, capture_output=True, timeout=5)
            except Exception:
                pass

    # ==================== Button ====================

    def _on_button_press(self):
        """Button pressed — toggle between idle and recording."""
        with self._lock:
            if self.state == State.IDLE:
                self._start_recording()
            elif self.state == State.RECORDING:
                self._stop_recording()

    # ==================== Recording ====================

    def _start_recording(self):
        self.state = State.RECORDING
        print("[recorder] recording...")

        self._show_screen(self._screen_recording)
        self._start_led_blink(255, 0, 0)

        # Start arecord in background thread
        self._rec_file = os.path.join(tempfile.gettempdir(), f"murmur_{int(time.time())}.wav")
        self._rec_start_time = time.time()

        hw_device = f"hw:{self.card_index},0"
        try:
            self._record_proc = subprocess.Popen(
                ["arecord", "-D", hw_device, "-f", FORMAT, "-r", str(SAMPLE_RATE),
                 "-c", str(CHANNELS), "-t", "wav", "-d", str(MAX_RECORD_SEC),
                 self._rec_file],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        except Exception as e:
            print(f"[recorder] ERROR starting arecord: {e}")
            self.state = State.IDLE
            self._show_error()
            return

    def _stop_recording(self):
        """Stop recording and kick off upload in background thread."""
        print("[recorder] stopping recording...")

        duration = time.time() - self._rec_start_time if self._rec_start_time else 0
        filepath = self._rec_file

        # Stop arecord
        try:
            if self._record_proc and self._record_proc.poll() is None:
                self._record_proc.send_signal(signal.SIGINT)
                self._record_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self._record_proc.kill()
            self._record_proc.wait()
        except Exception:
            pass
        self._record_proc = None
        self._rec_start_time = None

        self.state = State.UPLOADING
        print(f"[recorder] recorded {duration:.1f}s")

        # Upload in background so button callback returns quickly
        threading.Thread(
            target=self._upload_and_idle,
            args=(filepath, round(duration, 1)),
            daemon=True,
        ).start()

    # ==================== Upload ====================

    def _upload_and_idle(self, filepath, duration):
        """Upload the recording then return to idle state."""
        # Discard very short recordings
        if duration < 0.5:
            print("[recorder] too short, discarding")
            self._stop_led_blink()
            self._show_screen(self._screen_too_short)
            self.board.set_rgb(255, 200, 0)
            time.sleep(2)
            self._cleanup_file(filepath)
            self._go_idle()
            return

        # Show saving state
        self._stop_led_blink()
        self._show_screen(self._screen_saving)
        self.board.set_rgb(255, 200, 0)

        try:
            with open(filepath, "rb") as f:
                resp = requests.post(
                    f"{API_URL}/api/entries",
                    files={"audio": ("recording.wav", f, "audio/wav")},
                    data={"source": "whisplay", "duration": str(duration)},
                    timeout=30,
                )
            resp.raise_for_status()

            entry = resp.json()
            entry_id = entry.get("id", "?")
            print(f"[recorder] uploaded entry #{entry_id}")

            self._show_screen(self._screen_saved)
            self.board.set_rgb(0, 255, 0)
            self._play_beep()
            time.sleep(2)

        except requests.ConnectionError:
            print("[recorder] ERROR: cannot connect to API")
            self._show_error("API not running")

        except requests.HTTPError as e:
            print(f"[recorder] ERROR: HTTP {e.response.status_code}")
            self._show_error(f"HTTP {e.response.status_code}")

        except Exception as e:
            print(f"[recorder] ERROR: {e}")
            self._show_error()

        finally:
            self._cleanup_file(filepath)

        self._go_idle()

    def _show_error(self, detail=None):
        """Show error screen for 3 seconds."""
        if detail:
            w, h = self.board.LCD_WIDTH, self.board.LCD_HEIGHT
            screen = make_screen("Error", detail,
                                 bg_color=(60, 0, 0), text_color=(255, 80, 80),
                                 width=w, height=h)
            self._show_screen(screen)
        else:
            self._show_screen(self._screen_error)
        self._stop_led_blink()
        self.board.set_rgb(255, 0, 0)
        time.sleep(3)

    def _cleanup_file(self, filepath):
        try:
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
        except OSError:
            pass

    # ==================== Idle ====================

    def _go_idle(self):
        with self._lock:
            self.state = State.IDLE
        self._stop_led_blink()
        self.board.set_rgb(0, 0, 0)
        self._show_screen(self._screen_idle)
        self._start_led_breath(0, 0, 255)

    # ==================== Beep ====================

    def _play_beep(self):
        """Play a short confirmation beep through the WM8960 speaker."""
        try:
            hw_device = f"hw:{self.card_index},0"
            subprocess.run(
                ["play", "-n", "synth", "0.15", "sine", "880", "vol", "0.3"],
                capture_output=True, timeout=3,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # ==================== LED effects ====================

    def _start_led_blink(self, r, g, b):
        self._stop_led_blink()
        self._led_running = True
        self._led_thread = threading.Thread(
            target=self._led_blink_loop, args=(r, g, b), daemon=True)
        self._led_thread.start()

    def _led_blink_loop(self, r, g, b):
        while self._led_running:
            self.board.set_rgb(r, g, b)
            time.sleep(0.4)
            self.board.set_rgb(0, 0, 0)
            time.sleep(0.4)

    def _start_led_breath(self, r, g, b):
        self._stop_led_blink()
        self._led_running = True
        self._led_thread = threading.Thread(
            target=self._led_breath_loop, args=(r, g, b), daemon=True)
        self._led_thread.start()

    def _led_breath_loop(self, r, g, b):
        while self._led_running:
            for i in range(0, 101, 5):
                if not self._led_running:
                    return
                f = i / 100.0
                self.board.set_rgb(int(r * f), int(g * f), int(b * f))
                time.sleep(0.03)
            for i in range(100, -1, -5):
                if not self._led_running:
                    return
                f = i / 100.0
                self.board.set_rgb(int(r * f), int(g * f), int(b * f))
                time.sleep(0.03)

    def _stop_led_blink(self):
        self._led_running = False
        if self._led_thread and self._led_thread.is_alive():
            self._led_thread.join(timeout=1)
        self._led_thread = None

    # ==================== LCD ====================

    def _show_screen(self, pixel_data):
        try:
            self.board.draw_image(0, 0, self.board.LCD_WIDTH,
                                  self.board.LCD_HEIGHT, pixel_data)
        except Exception as e:
            print(f"[recorder] LCD error: {e}")

    # ==================== Run ====================

    def run(self):
        print("=" * 50)
        print("  Murmur WhisPlay Recorder")
        print("=" * 50)
        print(f"  Sound card: {self.card_index}")
        print(f"  API: {API_URL}")
        print(f"  Max recording: {MAX_RECORD_SEC}s")
        print()
        print("  Press button → record")
        print("  Press again  → stop & upload")
        print("  Ctrl+C       → exit")
        print("=" * 50)

        self._show_screen(self._screen_idle)
        self._start_led_breath(0, 0, 255)

        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n[recorder] shutting down...")
        finally:
            self._stop_led_blink()
            if self._record_proc and self._record_proc.poll() is None:
                self._record_proc.terminate()
                try:
                    self._record_proc.wait(timeout=2)
                except Exception:
                    self._record_proc.kill()
            self.board.set_rgb(0, 0, 0)
            self.board.set_backlight(0)
            self.board.cleanup()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Murmur WhisPlay Recorder")
    parser.add_argument("--card", type=int, default=None,
                        help="WM8960 sound card number (default: auto-detect)")
    args = parser.parse_args()

    recorder = MurmurRecorder(card_index=args.card)
    recorder.run()
