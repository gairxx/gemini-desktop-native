"""Frameless Spotlight overlay with glassmorphism and smooth auto-expand."""

import gi

gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gdk, GLib, Gtk

from webview import (
    GEMINI_URL,
    apply_theme,
    exec_js,
    get_measured_value,
    make_browser_view,
    run_measure,
)

COMPACT_HEIGHT = 132
MAX_HEIGHT = 640
DEFAULT_WIDTH = 780
ANIM_MS = 170

MEASURE_JS = (
    "(function(){var d=document.documentElement;return Math.max("
    "d.scrollHeight,d.body?d.body.scrollHeight:0);})();"
)
FOCUS_JS = (
    "(function(){var el=document.querySelector('textarea,[contenteditable=\"true\"]');"
    "if(el){try{el.focus();}catch(e){}}})();"
)
NEW_CHAT_JS = "(function(){location.href='https://gemini.google.com/app';})();"


class SpotlightOverlay(Gtk.Window):
    def __init__(self, app):
        super().__init__(application=app)
        self._app = app
        self._target_height = COMPACT_HEIGHT
        self._anim_source = None
        self._pulse_source = None
        self._avoid_hide = False

        self.set_decorated(False)
        self.set_resizable(True)
        self.set_default_size(DEFAULT_WIDTH, COMPACT_HEIGHT)
        self.set_title("Gemini Spotlight")
        self.add_css_class("gemini-spotlight")

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.add_css_class("spotlight-card")

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.add_css_class("spotlight-header")

        title = Gtk.Label(label="Gemini")
        title.add_css_class("spotlight-title")

        spacer = Gtk.Label()

        close = Gtk.Button()
        close.add_css_class("flat")
        close.set_icon_name("window-close-symbolic")
        close.set_tooltip_text("Dismiss (Esc)")
        close.connect("clicked", lambda *_: self.hide_overlay())

        new_chat = Gtk.Button.new_with_label("New chat")
        new_chat.add_css_class("suggested-action")
        new_chat.add_css_class("circular")
        new_chat.set_tooltip_text("Start a new conversation")
        new_chat.connect("clicked", self._on_new_chat)

        header.append(title)
        header.append(spacer)
        header.append(new_chat)
        header.append(close)
        header.set_hexpand(True)

        self.webview = make_browser_view(
            app.web_context,
            lambda view: apply_theme(view, self._current_theme()),
        )
        self.webview.set_vexpand(True)
        self.webview.set_margin_bottom(10)

        root.append(header)
        root.append(self.webview)
        self.set_child(root)

        esc = Gtk.EventControllerKey()
        esc.connect("key-pressed", self._on_key_pressed)
        self.add_controller(esc)

        focus = Gtk.EventControllerFocus()
        focus.connect("leave", self._on_focus_left)
        self.add_controller(focus)

        self.connect("realize", self._on_realize)
        self.connect("unrealize", self._on_unrealize)

    def _current_theme(self):
        try:
            style = Adw.StyleManager.get_default()
            return "dark" if style.get_dark() else "light"
        except Exception:
            return "light"

    def show_overlay(self):
        self.present()
        if not self.is_visible():
            self.set_visible(True)
        self._recenter()
        GLib.timeout_add(200, self._run_focus_js)
        if self._pulse_source is None:
            self._pulse_source = GLib.timeout_add(700, self._pulse)
        self.present()

    def hide_overlay(self):
        self.set_visible(False)
        if self._pulse_source is not None:
            GLib.source_remove(self._pulse_source)
            self._pulse_source = None

    def _run_focus_js(self):
        exec_js(self.webview, FOCUS_JS)
        return False

    def _pulse(self):
        if not self.is_visible():
            self._pulse_source = None
            return False
        GLib.timeout_add(60, self._measure)
        return True

    def _measure(self):
        if self.is_visible():
            run_measure(self.webview, MEASURE_JS, self._measure_done)
        return False

    def _measure_done(self, view, result, user_data):
        height = get_measured_value(view, result)
        if height is None:
            return
        height = max(COMPACT_HEIGHT, min(MAX_HEIGHT, int(height) + 48))
        if abs(height - self._target_height) > 12:
            self._animate_height(height)

    def _animate_height(self, target):
        self._target_height = target
        start = self.get_height() or COMPACT_HEIGHT
        if start == target:
            return
        width, _current = self.get_default_size()
        t0 = GLib.get_monotonic_time()
        if self._anim_source is not None:
            GLib.source_remove(self._anim_source)

        def tick(*_args):
            frac = (GLib.get_monotonic_time() - t0) / (ANIM_MS * 1000.0)
            if frac >= 1.0:
                self.set_default_size(width, target)
                self._anim_source = None
                self._recenter()
                return False
            eased = 1 - (1 - frac) ** 3
            self.set_default_size(width, int(start + (target - start) * eased))
            self._recenter()
            return True

        self._anim_source = GLib.timeout_add(16, tick)

    def _on_new_chat(self, *_args):
        if not exec_js(self.webview, NEW_CHAT_JS):
            try:
                self.webview.load_uri(GEMINI_URL)
            except Exception:
                pass
        self._animate_height(COMPACT_HEIGHT)
        return False

    def _on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.hide_overlay()
            return True
        return False

    def _on_focus_left(self, focus):
        if self._avoid_hide:
            return
        if self.is_visible() and not self.has_focus():
            GLib.timeout_add(80, self._maybe_hide_delayed)

    def _maybe_hide_delayed(self):
        if self.is_visible() and not self.has_focus() and not self._avoid_hide:
            self.hide_overlay()
        return False

    def _on_realize(self, widget):
        self._recenter()

    def _on_unrealize(self, widget):
        if self._pulse_source is not None:
            GLib.source_remove(self._pulse_source)
            self._pulse_source = None
        if self._anim_source is not None:
            GLib.source_remove(self._anim_source)
            self._anim_source = None

    def _recenter(self):
        if not self.get_realized():
            return
        monitor = self._current_monitor()
        if monitor is None:
            return
        geometry = monitor.get_geometry()
        width, height = self.get_default_size()
        x = geometry.x + (geometry.width - width) // 2
        y = geometry.y + int((geometry.height - height) * 0.22)
        if hasattr(self, "move"):
            self.move(max(geometry.x, x), max(geometry.y, y))

    def _current_monitor(self):
        try:
            surface = self.get_surface()
            if surface is None:
                return None
            return self.get_display().get_monitor_at_surface(surface)
        except Exception:
            return None