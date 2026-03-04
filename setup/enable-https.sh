#!/usr/bin/env bash
# Generate self-signed cert and enable HTTPS on nginx
set -euo pipefail

echo "Generating self-signed TLS certificate..."
sudo mkdir -p /etc/ssl/murmur
sudo openssl req -x509 -nodes -days 3650 \
    -newkey rsa:2048 \
    -keyout /etc/ssl/murmur/murmur.key \
    -out /etc/ssl/murmur/murmur.crt \
    -subj "/CN=murmur.local" \
    -addext "subjectAltName=DNS:murmur.local,DNS:localhost,IP:127.0.0.1"
sudo chmod 600 /etc/ssl/murmur/murmur.key

echo "Applying nginx config..."
sudo cp ~/murmur/setup/nginx-murmur.conf /etc/nginx/sites-available/murmur
sudo nginx -t && sudo systemctl restart nginx

echo "Done! Visit https://murmur.local"
