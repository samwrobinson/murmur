#!/usr/bin/env python3
"""One-time script to apply noise reduction to all existing audio files on the Pi.

Run from the api/ directory:
    python3 filter_existing.py

Creates backups in audio/originals/ before filtering.
"""

import os
import shutil
import subprocess

AUDIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio")
BACKUP_DIR = os.path.join(AUDIO_DIR, "originals")
NOISE_PROF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "noise.prof")


def filter_file(filepath):
    """Apply noisered + notch filters to a single audio file."""
    tmp = filepath + ".filtered.wav"
    cmd = ["sox", filepath, tmp, "rate", "16000", "channels", "1"]
    if os.path.exists(NOISE_PROF):
        cmd += ["noisered", NOISE_PROF, "0.05"]
    cmd += ["bandreject", "550", "20q", "bandreject", "450", "20q",
            "bandreject", "750", "20q", "bandreject", "7000", "50q"]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        os.replace(tmp, filepath)
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        if os.path.exists(tmp):
            os.remove(tmp)
        return False


def main():
    if not os.path.isdir(AUDIO_DIR):
        print(f"Audio directory not found: {AUDIO_DIR}")
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)

    files = sorted(f for f in os.listdir(AUDIO_DIR)
                   if f.endswith((".wav", ".webm", ".m4a")) and os.path.isfile(os.path.join(AUDIO_DIR, f)))

    print(f"Found {len(files)} audio files to filter.")
    if not files:
        return

    success = 0
    for i, fname in enumerate(files, 1):
        src = os.path.join(AUDIO_DIR, fname)
        backup = os.path.join(BACKUP_DIR, fname)

        # Skip if already backed up (already filtered)
        if os.path.exists(backup):
            print(f"  [{i}/{len(files)}] {fname} — already filtered, skipping")
            continue

        # Backup original
        shutil.copy2(src, backup)
        print(f"  [{i}/{len(files)}] {fname} — filtering...", end=" ")

        if filter_file(src):
            orig_size = os.path.getsize(backup)
            new_size = os.path.getsize(src)
            print(f"OK ({orig_size // 1024}KB -> {new_size // 1024}KB)")
            success += 1
        else:
            # Restore from backup on failure
            shutil.copy2(backup, src)
            print("restored original")

    print(f"\nDone. {success}/{len(files)} files filtered.")
    print(f"Originals backed up to: {BACKUP_DIR}")


if __name__ == "__main__":
    main()
