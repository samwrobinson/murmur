# Murmur — Architecture

## Overview

The project is split into three layers:

1. **Frontend (11ty + LESS)** — CodeStitch Intermediate LESS kit structure. Handles all page rendering, styling, and user interaction.
2. **API (Flask)** — Lightweight JSON API that manages journal data, serves audio files, and handles transcription.
3. **Network (Samba + Avahi + nginx)** — Makes the device discoverable at `murmur.local`, serves the web app, and exposes a shared folder in Finder/Explorer.

All three run on the Pi. No cloud. No accounts. Your memories never leave your home network.

```
┌─────────────────────────────────────┐
│          Your Home Network          │
│                                     │
│   Phone/Laptop                      │
│   ├── http://murmur.local    ──────────┐
│   └── smb://murmur.local/Murmur ───────┤
│                                     │  │
│   ┌─────────────────────────────────┼──┤
│   │  Murmur Device (Raspberry Pi)   │  │
│   │                                 │  │
│   │  nginx (:80) ◄──────────────────┘  │
│   │  ├── /         → static 11ty site  │
│   │  └── /api/*    → Flask (:5000)     │
│   │                                    │
│   │  Samba (:445) ◄────────────────────┘
│   │  └── /home/murmur/share/
│   │      ├── entries/   (.txt files)
│   │      ├── audio/     (.wav files)
│   │      └── favorites/ (symlinks)
│   │                                    │
│   │  Services:                         │
│   │  ├── murmur-api        Flask       │
│   │  ├── murmur-sync       File sync   │
│   │  ├── murmur-recorder   Hardware    │
│   │  └── murmur-transcribe Whisper     │
│   └────────────────────────────────────┘
└─────────────────────────────────────┘
```

## Directory Structure

```
dad-journal/
├── src/                            # 11ty source (CodeStitch structure)
│   ├── _data/
│   │   └── client.js               # Site metadata (name, description, API URL)
│   ├── _includes/
│   │   ├── components/
│   │   │   ├── header.html          # Site navigation
│   │   │   ├── footer.html          # Site footer
│   │   │   ├── entry-card.html      # Reusable entry card component
│   │   │   ├── audio-player.html    # Audio player component
│   │   │   ├── stats-grid.html      # Stats display component
│   │   │   ├── tag-list.html        # Tag pills component
│   │   │   └── prompt-card.html     # Daily prompt component
│   │   └── layouts/
│   │       └── base.html            # Base layout with <head>, nav, footer
│   ├── assets/
│   │   ├── css/                     # Compiled CSS (don't edit directly)
│   │   ├── less/
│   │   │   ├── root.less            # :root variables, CS globals
│   │   │   ├── header.less          # Header styles
│   │   │   ├── footer.less          # Footer styles
│   │   │   ├── journal.less         # Journal-specific styles
│   │   │   ├── entry.less           # Entry card / detail styles
│   │   │   └── local.less           # Imports all section LESS files
│   │   ├── images/
│   │   ├── js/
│   │   │   ├── app.js               # Main JS — fetch() calls, rendering
│   │   │   └── nav.js               # Navigation toggle (from CS kit)
│   │   └── svgs/
│   ├── content/
│   │   └── pages/
│   │       ├── timeline.html        # Main timeline page
│   │       ├── entry.html           # Single entry detail
│   │       ├── search.html          # Search page
│   │       ├── milestones.html      # Milestones page
│   │       ├── tags.html            # Tags page
│   │       └── stats.html           # Stats page
│   ├── index.html                   # Home page (redirects to timeline)
│   ├── robots.html
│   └── sitemap.html
├── api/                             # Flask API (runs on Pi)
│   ├── app.py                       # Flask server — JSON endpoints only
│   ├── db.py                        # Database helpers
│   ├── config.py                    # API config
│   ├── transcribe.py                # Whisper worker
│   ├── journal.db                   # SQLite database
│   └── audio/                       # Voice memo files
├── recorder/                        # Device-side code (runs on Pi)
│   ├── recorder.py                  # Whisplay button/mic/LCD controller
│   └── lcd/
│       └── screens.py               # LCD screen rendering
├── .eleventy.js                     # 11ty config
├── netlify.toml                     # Deploy config (if using Netlify)
├── package.json
└── package-lock.json
```

## How It Works

### Development (on your laptop)
1. `npm start` — runs 11ty dev server on port 8080
2. `python api/app.py` — runs Flask API on port 5000
3. Edit LESS files, Nunjucks templates, JS as usual
4. JS fetch() calls hit Flask API for data

### Production (on the Pi)
1. `npm run build` — builds static site to /public
2. Serve /public with nginx or similar
3. Flask API runs as systemd service on port 5000
4. Recorder runs as systemd service (hardware interaction)
5. Transcription worker runs as systemd service

### For the product/marketing site
The same 11ty project can host both:
- Marketing pages (static, built with CodeStitch stitches)
- Journal app pages (dynamic, pulling from Flask API)
- Blog via Decap CMS (for product updates, parenting tips, etc.)

## Device Setup (One-Time)

Run `sudo bash setup/setup.sh` on a fresh Raspberry Pi OS install. It:

1. Sets hostname to `murmur` (device becomes `murmur.local`)
2. Installs Samba, nginx, Avahi, Python packages
3. Configures Samba share (read-only guest access)
4. Configures nginx (serves static site + proxies /api to Flask)
5. Configures Avahi/mDNS (Finder/network discovery)
6. Creates systemd services for all 4 workers
7. Starts core services

After setup + reboot:
- Web app: `http://murmur.local`
- Shared folder: `smb://murmur.local/Murmur` (or just check Finder sidebar)

## WiFi Setup (AP Mode — Future)

On first boot (or after 10-second button reset):
1. Device creates hotspot: "Murmur-XXXX"
2. User connects phone to hotspot
3. Captive portal opens → pick home WiFi, enter password
4. Device reboots onto home network
5. LCD shows "Connected ✓"

## Shared Folder (Samba)

The `share_sync.py` worker mirrors the SQLite database to human-readable files every 30 seconds:

```
smb://murmur.local/Murmur/
├── README.txt
├── entries/
│   ├── 2026-02-15_first-laugh.txt
│   ├── 2026-02-20_bath-time-chaos.txt
│   └── 2026-02-23_she-said-dada.txt
├── audio/
│   ├── 2026-02-15_entry_1.wav
│   ├── 2026-02-20_entry_2.wav
│   └── 2026-02-23_entry_3.wav
└── favorites/
    └── 2026-02-15_first-laugh.txt → ../entries/...
```

**Each .txt file is a nicely formatted document:**
```
============================================================
  MURMUR — Memory #12
============================================================

  Date:     Saturday, February 15, 2026
  Time:     07:23 AM
  Source:   voice
  Duration: 0:34
  Favorite: ★

------------------------------------------------------------

  TRANSCRIPTION

  She grabbed my finger today for the first time...

  NOTES

  Added later: this was the morning after her first night
  sleeping through.

------------------------------------------------------------
  Audio: audio/2026-02-15_entry_1.wav
```

The share is read-only. All editing happens through the web app.

## Backup Strategy

Since everything is local, backup matters. Three layers, easiest to hardest:

1. **Samba share** — drag the Murmur folder to an external drive. Done.
2. **Time Machine** — macOS can include network shares in Time Machine backups.
3. **USB export** — (future) hold button 5 seconds, plug in USB drive, auto-copies.

If the SD card dies, someone can pop it into any computer and find:
- `api/audio/` — all .wav files
- `api/journal.db` — SQLite database (openable with any SQLite viewer)
- No proprietary format. Just files.
