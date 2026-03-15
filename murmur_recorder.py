#!/usr/bin/env python3
"""
Murmur INMP441 I2S Mic Recorder

Press the button (GPIO5) to record a voice journal entry directly on the Pi.
The recording gets uploaded to the local Murmur Flask API, transcribed, and
appears in the app/web UI.

Interaction flow:
  Idle        → LED off, waiting for button press
  Press       → Start recording, LED on solid
  Press again → Stop recording, LED blink while uploading
  Upload      → POST audio to API
  Success     → LED off, return to idle
  Error       → LED rapid blink, return to idle

Hardware:
  Mic:    INMP441 I2S on card 1 (plughw:1,0), S32_LE mono 48kHz
  Button: GPIO5 (Pin 29) to GND (Pin 30), active low with internal pull-up
  LED:    GPIO13 (Pin 33), active high (optional, fails gracefully)

Dependencies:
  sudo apt install python3-requests python3-gpiozero python3-lgpio alsa-utils sox

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

try:
    from gpiozero import Button as GPIOButton, LED as GPIOLED
except ImportError:
    print("[recorder] WARNING: gpiozero not available — button/LED disabled")
    GPIOButton = None
    GPIOLED = None

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_URL = os.environ.get("MURMUR_API_URL", "http://localhost:5001")
SAMPLE_RATE = 48000   # INMP441 native rate
CHANNELS = 1          # mono — single INMP441 mic
FORMAT = "S32_LE"     # INMP441 outputs 24-bit data in 32-bit frames
MAX_RECORD_SEC = 300  # 5 minute max

BUTTON_GPIO = 5       # GPIO5 (Pin 29)
LED_GPIO = 13         # GPIO13 (Pin 33)

# Software gain boost (dB) applied via sox to compensate for quiet INMP441
GAIN_DB = 20


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class State:
    IDLE = 0
    RECORDING = 1
    UPLOADING = 2


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class MurmurRecorder:
    def __init__(self, card_index=None):
        self.card_index = card_index if card_index is not None else 1
        self._record_proc = None
        self._rec_file = None
        self._rec_start_time = None

        self.state = State.IDLE
        self._lock = threading.Lock()
        self._led_thread = None
        self._led_running = False

        # Setup GPIO button
        self._button = None
        if GPIOButton is not None:
            try:
                self._button = GPIOButton(BUTTON_GPIO, pull_up=True, bounce_time=0.3)
                self._button.when_pressed = self._on_button_press
            except Exception as e:
                print(f"[recorder] WARNING: GPIO button init failed: {e}")

        # Setup GPIO LED (optional — may not be wired yet)
        self._led = None
        if GPIOLED is not None:
            try:
                self._led = GPIOLED(LED_GPIO)
            except Exception as e:
                print(f"[recorder] NOTE: GPIO LED init failed (not wired?): {e}")

    # ==================== LED helpers ====================

    def _led_on(self):
        if self._led:
            try:
                self._led.on()
            except Exception:
                pass

    def _led_off(self):
        if self._led:
            try:
                self._led.off()
            except Exception:
                pass

    def _start_led_blink(self, on_time=0.3, off_time=0.3):
        self._stop_led_blink()
        self._led_running = True
        self._led_thread = threading.Thread(
            target=self._led_blink_loop, args=(on_time, off_time), daemon=True)
        self._led_thread.start()

    def _led_blink_loop(self, on_time, off_time):
        while self._led_running:
            self._led_on()
            time.sleep(on_time)
            self._led_off()
            time.sleep(off_time)

    def _stop_led_blink(self):
        self._led_running = False
        if self._led_thread and self._led_thread.is_alive():
            self._led_thread.join(timeout=1)
        self._led_thread = None

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

        self._stop_led_blink()
        self._led_on()

        # Start arecord in background
        self._rec_file = os.path.join(tempfile.gettempdir(), f"murmur_{int(time.time())}.wav")
        self._rec_start_time = time.time()

        hw_device = f"plughw:{self.card_index},0"
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
            self._led_off()
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

    def _filter_audio(self, filepath):
        """Normalize audio: convert to 16kHz mono 16-bit, apply gain boost."""
        filtered = filepath + ".filtered.wav"
        noise_prof = os.path.join(os.path.dirname(os.path.abspath(__file__)), "noise.prof")
        try:
            cmd = [
                "sox", filepath, filtered,
                "rate", "16000",
                "channels", "1",
                "gain", str(GAIN_DB),
            ]
            if os.path.exists(noise_prof):
                cmd += ["noisered", noise_prof, "0.05"]
            subprocess.run(cmd, check=True, capture_output=True, timeout=60)
            os.replace(filtered, filepath)
            print(f"[recorder] audio filtered (gain +{GAIN_DB}dB, 16kHz mono)")
        except Exception as e:
            print(f"[recorder] audio filter failed, using original: {e}")
            if os.path.exists(filtered):
                os.remove(filtered)

    def _upload_and_idle(self, filepath, duration):
        """Upload the recording then return to idle state."""
        # Show uploading state
        self._stop_led_blink()
        self._start_led_blink(0.15, 0.15)  # fast blink while uploading

        # Discard very short recordings
        if duration < 0.5:
            print("[recorder] too short, discarding")
            self._cleanup_file(filepath)
            self._go_idle()
            return

        # Filter/boost audio
        self._filter_audio(filepath)

        try:
            with open(filepath, "rb") as f:
                resp = requests.post(
                    f"{API_URL}/api/entries",
                    files={"audio": ("recording.wav", f, "audio/wav")},
                    data={"source": "recorder", "duration": str(duration)},
                    timeout=30,
                )
            resp.raise_for_status()

            entry = resp.json()
            entry_id = entry.get("id", "?")
            print(f"[recorder] uploaded entry #{entry_id}")

        except requests.ConnectionError:
            print("[recorder] ERROR: cannot connect to API")

        except requests.HTTPError as e:
            print(f"[recorder] ERROR: HTTP {e.response.status_code}")

        except Exception as e:
            print(f"[recorder] ERROR: {e}")

        finally:
            self._cleanup_file(filepath)

        self._go_idle()

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
        self._led_off()

    # ==================== Run ====================

    def run(self):
        print("=" * 50)
        print("  Murmur Recorder (INMP441 I2S)")
        print("=" * 50)
        print(f"  Sound card: plughw:{self.card_index},0")
        print(f"  Format:     {FORMAT} {SAMPLE_RATE}Hz mono")
        print(f"  Gain:       +{GAIN_DB}dB")
        print(f"  Button:     GPIO{BUTTON_GPIO}")
        print(f"  LED:        GPIO{LED_GPIO}" + (" (not wired)" if not self._led else ""))
        print(f"  API:        {API_URL}")
        print(f"  Max rec:    {MAX_RECORD_SEC}s")
        print()
        print("  Press button → record")
        print("  Press again  → stop & upload")
        print("  Ctrl+C       → exit")
        print("=" * 50)

        self._led_off()

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
            self._led_off()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Murmur INMP441 Recorder")
    parser.add_argument("--card", type=int, default=None,
                        help="ALSA sound card number (default: 1)")
    parser.add_argument("--gain", type=int, default=None,
                        help=f"Software gain in dB (default: {GAIN_DB})")
    args = parser.parse_args()

    if args.gain is not None:
        GAIN_DB = args.gain

    recorder = MurmurRecorder(card_index=args.card)
    recorder.run()
