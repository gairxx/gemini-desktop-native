# Gemini Desktop Native

A native GTK4 / Libadwaita / WebKitGTK 6.0 Linux desktop client for [Google Gemini](https://gemini.google.com), distributed as a Flatpak.

## Install

```
flatpak install flathub org.native.GeminiDesktop
```

Run with:

```
flatpak run org.native.GeminiDesktop
```

## Systems

- Linux (Flatpak sandbox, Bubblewrap isolation)
- GTK4 + Libadwaita, WebKitGTK 6.0 rendering
- GNOME, KDE Plasma, XFCE, Sway/Hyprland (Wayland & X11)

## Features

- Native freedesktop notifications + system tray
- Frameless spotlight overlay with glass effect
- Global hotkeys and dark/light theme mirroring
- Chrome-compatible user agent for sign-in

## Local automation

The app exposes a local D-Bus control interface (`org.freedesktop.AI.Control`) for automation. It is usable only from the machine the app runs on, not from the Gemini web page:

```
gdbus call --session \
    --dest org.freedesktop.AI.Control \
    --object-path /org/freedesktop/AI/Control \
    --method org.freedesktop.AI.Control.GetCapabilities
```

## License

GPL-3.0
