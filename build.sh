#!/usr/bin/env bash
set -euo pipefail

APP_ID="org.native.GeminiDesktop"
MANIFEST="${1:-org.native.GeminiDesktop.yml}"
REPO="${REPO:-$PWD/../gemini-flatpak-repo}"
BUILDDIR="${BUILDDIR:-$PWD/build}"
BUNDLE="${BUNDLE:-$PWD/${APP_ID}.flatpak}"

echo "==> Building $APP_ID (manifest: $MANIFEST)"
flatpak-builder \
    --user \
    --install \
    --force-clean \
    --disable-rofiles-fuse \
    --repo="$REPO" \
    "$BUILDDIR" \
    "$MANIFEST"

echo "==> Exporting bundle"
flatpak build-bundle "$REPO" "$BUNDLE" "$APP_ID"

echo "==> Done: $BUNDLE"
echo "    Install with:  flatpak install --user ${BUNDLE}"