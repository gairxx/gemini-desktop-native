# ✨ Gemini Desktop Native — The Native Google Gemini App for Linux

Welcome to **Gemini Desktop Native**, the sleek, fast, and privacy-conscious way to run **Google Gemini on Linux**. Say goodbye to juggling browser tabs for your AI chats — this is a true **native desktop app for Gemini**, purpose-built for modern Linux desktops and engineered around speed, sandboxing, and deep desktop integration.

Whether you're a developer automating flows via **D-Bus**, a GNOME user who wants **native notifications**, or a KDE/Plasma fan looking for a **Gemini client with a system tray**, Gemini Desktop Native turns your Linux machine into a first-class **AI chat desktop experience** — no browser chrome, no clutter, just Gemini.

---

## 🚀 Why You'll Love It

- **It's a real desktop app.** No browser needed. Rendered with **WebKitGTK 6.0** hardware acceleration inside a lightweight **GTK4 / Libadwaita** shell.
- **Sandboxed by default.** Ships as a **Flatpak** with Bubblewrap isolation — your system stays clean and secure.
- **Feels native on any Linux desktop.** Works beautifully on **GNOME, KDE Plasma, XFCE, Sway, and Hyprland**, on **Wayland or X11**.
- **Automation-ready.** Expose real app controls over **D-Bus** for scripting and keyboard-wizard workflows.
- **One-command install.** Get the fully packaged **Gemini Linux desktop client** in seconds.

---

## 📦 Quick Install (One Command)

Get the latest **Google Gemini desktop app for Linux** with a single command:

```bash
curl -fsSL https://raw.githubusercontent.com/gairxx/gemini-desktop-native/main/install.sh | bash
```

The installer grabs the **prebuilt Flatpak bundle** from the [latest release](https://github.com/gairxx/gemini-desktop-native/releases/latest) and handles everything — including pulling the GNOME runtime on first run.

### Manual install

Prefer to do it by hand with the released bundle?

```bash
flatpak install --user ./org.native.GeminiDesktop.flatpak
```

### Launch Gemini

Once installed, fire it up with:

```bash
flatpak run org.native.GeminiDesktop
```

> 💡 Tip: Add `flatpak run org.native.GeminiDesktop` to your launcher or keybindings for instant access to **Gemini on your Linux desktop**.

---

## 🖥️ Built for Every Linux Desktop

| Capability | Details |
| --- | --- |
| **Platform** | Linux, distributed as a sandboxed **Flatpak** |
| **UI toolkit** | **GTK4** with **Libadwaita** adaptive styling |
| **Rendering** | **WebKitGTK 6.0** — hardware-accelerated, GPU-composited |
| **Window systems** | **Wayland & X11** |
| **Desktop environments** | **GNOME**, **KDE Plasma 6**, **XFCE**, **Sway**, **Hyprland**, and any Freedesktop-compliant WM |
| **Security** | **Bubblewrap** sandbox isolation + XDG desktop portals |

---

## ✨ Feature Highlights

- **Native freedesktop notifications** — get chat responses delivered to your notification center while you work.
- **System tray integration** — minimize to tray, toggle visibility, reset prompts, tweak settings without hunting for a window.
- **Frameless spotlight overlay** — an instant-summon, glass-effect search bar for quick Gemini queries without leaving your workspace.
- **Global hotkeys** — configurable system-wide shortcuts for one-key access and clipboard dispatch.
- **Dark & light theme mirroring** — automatically follows your desktop color scheme preference.
- **Chrome-compatible user agent** — smooth sign-in and the full Gemini web experience with zero legacy-browser restrictions.
- **D-Bus control interface** — script and automate the app from the terminal or your own tools.

---

## 🤖 Local Automation & D-Bus Control

Love automation? Gemini Desktop Native exposes a **local D-Bus control interface** (`org.freedesktop.AI.Control`) with methods for navigation, prompt sending, JavaScript execution, window management, and more — perfect for **AI desktop automation** and building your own workflows.

> ℹ️ It's a **local-only** interface: usable from the machine the app runs on, never exposed to the Gemini web page.

List available capabilities:

```bash
gdbus call --session \
    --dest org.freedesktop.AI.Control \
    --object-path /org/freedesktop/AI/Control \
    --method org.freedesktop.AI.Control.GetCapabilities
```

---

## 🛠️ Development

Want to build the **Gemini native Linux app** from source? You'll need [flatpak-builder](https://flatpak.org/):

```bash
./build.sh
```

---

## 📄 License

Released under the **GPL-3.0** license.

---

*Gemini Desktop Native — the fast, native, sandboxed way to run Google Gemini on your Linux desktop. Install it once and keep Gemini one keystroke away.*