# Murmur Pi Setup Guide

Complete setup instructions for a fresh Raspberry Pi. Follow these steps in order.

## What You Need

- Raspberry Pi Zero 2W (or any Pi)
- PiSugar WhisPlay HAT installed
- SD card with fresh Raspberry Pi OS (flashed via Raspberry Pi Imager)
- WiFi configured in Imager before flashing
- Mac on the same network

## Step 1: Flash SD Card

Use Raspberry Pi Imager:
- OS: Raspberry Pi OS (64-bit, Lite recommended)
- Set hostname: `murmur`
- Set username: `murmur` with your password
- Configure WiFi (your home network)
- Enable SSH

Boot the Pi and wait 2-3 minutes.

## Step 2: SSH In

From your Mac:
```bash
ssh murmur@murmur.local
```

If it says "host key has changed":
```bash
ssh-keygen -R murmur.local
ssh murmur@murmur.local
```

## Step 3: Install WhisPlay Driver

```bash
git clone --depth 1 https://github.com/PiSugar/Whisplay.git ~/Whisplay
cd ~/Whisplay/Driver && sudo bash install_wm8960_drive.sh
```

Say `y` when prompted. **Don't reboot yet.**

## Step 4: Clone Murmur

```bash
git clone https://github.com/samwrobinson/murmur.git ~/murmur
```

## Step 5: Deploy Frontend from Mac

**On your Mac** (not the Pi — the Pi can't handle npm):
```bash
cd ~/Desktop/Murmur/murmur
bash setup/deploy.sh
```

This builds the frontend on your Mac and SCPs it to the Pi.

## Step 6: Run Setup Script on Pi

Back **on the Pi**:
```bash
cd ~/murmur && sudo bash setup/setup.sh
```

This installs all packages, configures nginx, samba, and starts all services.

## Step 7: Reboot

```bash
sudo reboot
```

Wait 2-3 minutes, then verify:
```bash
ssh murmur@murmur.local
```

## Step 8: Verify Everything Works

On the Pi:
```bash
sudo systemctl status murmur-api
sudo systemctl status murmur-recorder
sudo systemctl status nginx
```

All should show `active (running)`.

From your Mac browser:
- Open `http://murmur.local` — should show the Murmur app
- The WhisPlay LCD should show "Murmur / Press to record" with blue breathing LED
- Press the button, speak, press again — entry should appear in the app

## Updating

When you make changes to the code on your Mac:

**Frontend changes:**
```bash
cd ~/Desktop/Murmur/murmur
bash setup/deploy.sh
```

**API/backend changes:**
Push to GitHub, then on the Pi:
```bash
cd ~/murmur && git pull
sudo systemctl restart murmur-api
```

**Recorder changes:**
```bash
cd ~/Desktop/Murmur/murmur
bash setup/deploy.sh
ssh murmur@murmur.local "sudo systemctl restart murmur-recorder"
```

## Troubleshooting

**Can't SSH in:**
- Wait 3-5 minutes after boot (Zero 2W is slow)
- Try IP directly: `ssh murmur@192.168.1.214`
- Move Pi closer to router (Zero 2W has weak WiFi)

**API not starting:**
```bash
sudo journalctl -u murmur-api --no-pager -n 30
```

**Recorder not working:**
```bash
sudo journalctl -u murmur-recorder --no-pager -n 30
```

**No sound card:**
```bash
cat /proc/asound/cards
```
Should show `wm8960`. If not, the driver needs reinstalling (Step 3).

**NEVER run `npm install` on the Pi** — it will OOM the Zero 2W and crash.
