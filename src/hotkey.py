"""Global hotkey manager. Uses pynput on X11; degrades gracefully on Wayland."""

import threading

try:
    from pynput import keyboard
except Exception:
    keyboard = None

TRIGGERS = {
    "<alt>+<space>": "spotlight",
    "<alt>+<shift>+<space>": "window",
}


class HotkeyManager:
    def __init__(self, on_spotlight, on_window):
        self.on_spotlight = on_spotlight
        self.on_window = on_window
        self._listener = None
        self._thread = None

    @property
    def active(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if keyboard is None:
            print(
                "gemini-desktop-native: pynput not available; "
                "global hotkeys disabled (use Ctrl+Alt+S / Ctrl+Alt+F in-app).",
                flush=True,
            )
            return False
        try:
            handlers = {
                key: self._dispatch(action) for key, action in TRIGGERS.items()
            }
            listener = keyboard.GlobalHotKeys(handlers)
            thread = threading.Thread(target=listener.run, daemon=True, name="hotkeys")
            thread.start()
        except Exception as exc:
            print(
                f"gemini-desktop-native: global hotkeys unavailable "
                f"({exc.__class__.__name__}: {exc}); "
                "use in-app accelerators instead.",
                flush=True,
            )
            return False
        self._listener = listener
        self._thread = thread
        return True

    def stop(self):
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
        self._thread = None

    def _dispatch(self, action):
        def invoke():
            callback = self.on_spotlight if action == "spotlight" else self.on_window
            if callback is not None:
                callback()

        return invoke