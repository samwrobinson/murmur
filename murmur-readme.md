# Murmur

A pocket-sized voice journal. Press button, speak memory, done. No phone, no cloud, no distractions.

Your memories live on your home network — searchable through a web app, exportable to your desktop, and always backed up as plain text and audio files.

---

## What's in this folder

```
murmur/
├── src/                        ← 11ty frontend (CodeStitch Intermediate LESS)
│   ├── _data/client.js         ← Site metadata + API URL config
│   ├── _includes/
│   │   ├── components/         ← Header, footer (add CodeStitch stitches here)
│   │   └── layouts/base.html   ← Base page layout
│   ├── assets/
│   │   ├── less/               ← EDIT STYLES HERE (root, header, footer, journal)
│   │   ├── css/local.css       ← Compiled CSS (don't edit)
│   │   └── js/
│   │       ├── app.js          ← All API calls + page rendering
│   │       └── nav.js          ← Mobile nav toggle
│   ├── content/pages/          ← Entry detail, search, milestones, tags, stats, new
│   └── index.html              ← Timeline / home page
│
├── api/                        ← Flask JSON API
│   ├── app.py                  ← All endpoints (/api/entries, /api/search, etc.)
│   ├── db.py                   ← SQLite database helpers + schema
│   ├── config.py               ← Paths, ports, audio settings
│   ├── seed.py                 ← Sample data for testing
│   ├── share_sync.py           ← Mirrors entries to Samba shared folder
│   └── requirements.txt        ← Python dependencies
│
├── setup/                      ← Pi setup scripts (run once)
│   ├── setup.sh                ← Installs everything, configures services
│   └── smb-murmur.conf         ← Samba config reference
│
├── recorder/                   ← Hardware code (build when HAT arrives)
│   └── (recorder.py, lcd/)     ← Whisplay button/mic/LCD controller
│
├── .eleventy.js                ← 11ty config
├── package.json                ← Node dependencies
├── ARCHITECTURE.md             ← Full system design doc
└── README.md                   ← You are here
```

---

## Step 1: Test the web app NOW (on your laptop)

You can run the full web app without any Pi hardware.

### Terminal 1 — Flask API
```bash
cd murmur/api
pip3 install flask flask-cors
python3 seed.py          # creates sample data
python3 app.py           # starts API on http://localhost:5000
```

### Terminal 2 — 11ty dev server
```bash
cd murmur
npm install
npm start                # starts site on http://localhost:8080
```

Open **http://localhost:8080** — you should see the timeline with 10 sample entries. Click around, search, add tags, star favorites.

### If you want to use the real CodeStitch kit:
1. Go to https://github.com/CodeStitchOfficial/Intermediate-Website-Kit-LESS
2. Click "Use This Template" → create your repo
3. Clone it, `npm install`
4. Delete their example content in `content/pages/` and `_includes/components/`
5. Copy in the files from this project's `src/` folder
6. Copy the `api/` folder alongside the 11ty project

---

## Step 2: Flash the Pi (when hardware arrives)

### What you ordered:
- Raspberry Pi Zero 2 WH (pre-soldered headers)
- PiSugar Whisplay HAT (mics, LCD, speaker, button)
- PiSugar S Battery (1200mAh, USB-C charging)

### Flash Raspberry Pi OS:
1. Download **Raspberry Pi Imager** → https://www.raspberrypi.com/software/
2. Choose **Raspberry Pi OS Lite (64-bit)** — no desktop needed
3. Before flashing, click the gear icon and set:
   - Hostname: `murmur`
   - Enable SSH
   - Set username: `murmur` / password: (your choice)
   - Configure WiFi (your home network)
4. Flash to microSD card
5. Insert card, assemble the hardware stack, power on

### SSH in:
```bash
ssh murmur@murmur.local
# enter your password
```

---

## Step 3: Set up the device

### Copy project files to the Pi:
```bash
# From your laptop:
scp -r murmur/ murmur@murmur.local:~/murmur/
```

### Run the setup script:
```bash
ssh murmur@murmur.local
cd ~/murmur
sudo bash setup/setup.sh
sudo reboot
```

This installs and configures everything:
- **Samba** — shared folder visible in Finder
- **nginx** — serves web app on port 80
- **Avahi** — makes `murmur.local` work
- **systemd services** — API + file sync start on boot

### After reboot, everything works:
- **Web app:** http://murmur.local
- **Shared folder:** Look in Finder sidebar under Network → Murmur
  - Or: Finder → Go → Connect to Server → `smb://murmur.local/Murmur`

---

## Step 4: Build the recorder (when Whisplay HAT arrives)

This is the part we haven't written yet — the Python script that:
- Listens for button press on the Whisplay HAT
- Records audio from the dual INMP441 mics via WM8960 codec
- Saves .wav file and creates a database entry
- Updates the 1.69" LCD with status (idle, recording, saved)
- Triggers transcription

We'll build `recorder/recorder.py` together when your hardware is in hand and you can test it live.

### What we know about the Whisplay HAT:
- WM8960 audio codec (I2C) — needs driver install
- 1.69" LCD (ST7789, SPI) — 240×280 pixels
- Dual INMP441 MEMS mics
- One programmable button
- RGB LED
- Speaker output (onboard + PH2.0 external)
- GPIO: Button likely on a GPIO pin, check PiSugar docs

### Driver install (will need to verify):
```bash
# WM8960 audio codec
git clone https://github.com/waveshare/WM8960-Audio-HAT
cd WM8960-Audio-HAT
sudo bash install.sh
sudo reboot

# Test recording:
arecord -D hw:0,0 -f S16_LE -r 44100 -c 1 -d 5 test.wav
aplay test.wav
```

---

## Step 5: 3D print the case

You've got matte black and white PLA arriving. The hardware stack is:
- 65mm × 30mm × ~20mm (Pi + HAT + battery)
- Add ~4mm per side for case walls
- Final size: ~72mm × 38mm × 28mm

PiSugar has STL files on their GitHub you can start from:
https://github.com/PiSugar

Start with **The Sleeve** (open frame, fastest to print, test hardware fit).
Then iterate toward **The Keeper** (clean enclosed case).

---

## How it all connects

```
┌─────────────────────────────────────┐
│          Your Home WiFi             │
│                                     │
│  Phone/Laptop                       │
│  ├── http://murmur.local     ──────────▶ Web App
│  └── Finder sidebar: "Murmur" ─────────▶ Shared Folder
│                                     │
│  ┌──────────────────────────────────┐│
│  │  Murmur Device (in your pocket)  ││
│  │                                  ││
│  │  [Button] → recorder.py         ││
│  │     → saves .wav + DB entry      ││
│  │     → LCD shows "Saved ✓"        ││
│  │                                  ││
│  │  transcribe.py (background)      ││
│  │     → Whisper speech-to-text     ││
│  │                                  ││
│  │  Flask API (port 5000)           ││
│  │     → JSON endpoints             ││
│  │                                  ││
│  │  nginx (port 80)                 ││
│  │     → serves web app             ││
│  │     → proxies /api to Flask      ││
│  │                                  ││
│  │  Samba (port 445)                ││
│  │     → read-only shared folder    ││
│  │                                  ││
│  │  share_sync.py (every 30s)       ││
│  │     → mirrors DB → .txt + .wav   ││
│  └──────────────────────────────────┘│
└─────────────────────────────────────┘
```

---

## Shared folder structure

The Samba share mirrors your journal as plain files:

```
Murmur/
├── README.txt
├── entries/
│   ├── 2026-02-15_she-grabbed-my-finger-today.txt
│   ├── 2026-02-20_bath-time-was-hilarious.txt
│   └── ...
├── audio/
│   ├── 2026-02-15_entry_1.wav
│   ├── 2026-02-20_entry_2.wav
│   └── ...
└── favorites/
    └── (symlinks to starred entries)
```

Each `.txt` file is nicely formatted with date, transcription, notes, and audio reference. If the device ever dies, your memories are just files.

---

## Backup

Everything is local, so backup matters.

1. **Samba share** — drag the Murmur folder to an external drive
2. **Time Machine** — can include network shares
3. **SD card** — pop it in any computer, files are in `api/audio/` and `api/journal.db`

No proprietary formats. Plain `.wav` audio and `.txt` text. Readable in 50 years.

---

## Development workflow (CodeStitch)

Same flow you're used to:

| What                | Where                              |
|---------------------|------------------------------------|
| Styles              | `src/assets/less/*.less`           |
| Components          | `src/_includes/components/`        |
| Layouts             | `src/_includes/layouts/`           |
| Pages               | `src/content/pages/`               |
| Site data           | `src/_data/client.js`              |
| API endpoints       | `api/app.py`                       |
| Database schema     | `api/db.py`                        |
| Device setup        | `setup/setup.sh`                   |

Drop in CodeStitch stitches as usual — copy HTML to components, LESS to `assets/less/`, import in `local.less`.

---

## Services (systemd)

| Service              | What it does                    | Auto-start |
|----------------------|---------------------------------|------------|
| `murmur-api`         | Flask API on port 5000          | Yes        |
| `murmur-sync`        | Mirrors DB to shared folder     | Yes        |
| `murmur-recorder`    | Button/mic/LCD (enable later)   | No         |
| `murmur-transcribe`  | Whisper speech-to-text          | No         |
| `nginx`              | Web server on port 80           | Yes        |
| `smbd`               | Samba file sharing              | Yes        |

```bash
# Check status:
sudo systemctl status murmur-api

# View logs:
sudo journalctl -u murmur-api -f

# Enable recorder (when hardware is ready):
sudo systemctl enable --now murmur-recorder
sudo systemctl enable --now murmur-transcribe
```

---

## What's left to build

- [ ] `recorder/recorder.py` — Whisplay HAT button/mic/LCD integration
- [ ] `api/transcribe.py` — Whisper transcription worker
- [ ] `recorder/lcd/screens.py` — LCD screen states (idle, recording, saved)
- [ ] WiFi captive portal (AP mode for first-time setup)
- [ ] 3D case design (The Keeper)
- [ ] Export features in web app (download zip, PDF keepsake)
- [ ] USB export (hold button → copy to USB drive)
