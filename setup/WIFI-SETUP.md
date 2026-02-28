# Murmur WiFi Setup

## First-Time Setup (or New WiFi Network)

When Murmur can't connect to a known WiFi network, it automatically creates its own hotspot after 30 seconds.

### Steps

1. **Power on your Murmur Pi** and wait about 30 seconds
2. On your phone or laptop, look for a WiFi network called **"Murmur-Setup"** and connect to it
3. Open a browser and go to **http://10.42.0.1/settings**
4. Scroll down to the **WiFi** section
5. Tap **"Scan for Networks"** — your home WiFi should appear in the list
6. Tap **Connect** on your network
   - If the network has a password, you'll be asked to enter it
7. Murmur will connect to your WiFi. **Your browser will lose connection** — this is normal since you were connected to the Murmur hotspot
8. Switch your phone/laptop back to your regular WiFi network
9. Visit **http://murmur.local** to confirm everything is working

## Switching WiFi Networks (e.g. Moving to a New Home)

If you move Murmur to a location with a different WiFi network:

1. Just plug it in and wait 30 seconds
2. The "Murmur-Setup" hotspot will appear automatically since Murmur doesn't know the new network
3. Follow the same steps above to connect it to the new WiFi

## Managing Saved Networks

Visit **http://murmur.local/settings** (while connected to the same WiFi as Murmur) to:

- **See your current connection** — network name, IP address, signal strength
- **Scan for networks** — find and connect to nearby WiFi
- **Forget a saved network** — remove a network Murmur remembers

## Troubleshooting

- **"Murmur-Setup" hotspot doesn't appear** — Make sure the Pi is powered on and wait at least 60 seconds. If it still doesn't show, the Pi may have connected to a previously saved network.
- **Can't reach http://10.42.0.1** — Make sure your phone/laptop is connected to the "Murmur-Setup" network, not your regular WiFi.
- **Can't reach http://murmur.local** — Try using the IP address instead (shown on the settings page). Some networks don't support `.local` addresses.
- **WiFi section doesn't appear on settings page** — This section only shows when you're accessing Murmur directly on the Pi's network. It won't appear in the mobile app when you're on a different network.
