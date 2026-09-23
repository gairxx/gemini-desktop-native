#!/usr/bin/env bash
set -euo pipefail

APP_ID="org.native.GeminiDesktop"
BUNDLE_URL="https://github.com/gairxx/gemini-desktop-native/releases/latest/download/${APP_ID}.flatpak"

if ! command -v flatpak >/dev/null 2>&1; then
  echo "flatpak is not installed. Install it first, then re-run this script:"
  echo "  Debian/Ubuntu:  sudo apt install flatpak"
  echo "  Fedora:         sudo dnf install flatpak"
  echo "  Arch:           sudo pacman -S flatpak"
  echo "  openSUSE:       sudo zypper install flatpak"
  exit 1
fi

if ! flatpak remotes | awk '{print $1}' | grep -qx flathub; then
  echo "==> Adding the Flathub remote (needed for the GNOME runtime)"
  flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "==> Downloading ${APP_ID} bundle"
curl -fL --progress-bar -o "$TMP/${APP_ID}.flatpak" "$BUNDLE_URL"

echo "==> Installing (first run also pulls the GNOME runtime; this can take a few minutes)"
flatpak install --user -y "$TMP/${APP_ID}.flatpak"

echo
echo "==> Done. Launch with:"
echo "    flatpak run ${APP_ID}"
