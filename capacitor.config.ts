import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.murmur.app",
  appName: "Murmur",
  webDir: "public",
  server: {
    // Use https scheme so WKWebView treats it as a secure context (needed for mediaDevices)
    iosScheme: "https",
    // Allow cleartext HTTP to local network (Pi)
    cleartext: true,
    allowNavigation: ["murmur.local", "*.local", "192.168.*"],
  },
};

export default config;
