"""Gemini Desktop Native - GTK4/Libadwaita wrapper around gemini.google.com."""

import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

import gi

gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Notify", "0.7")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Notify

from hotkey import HotkeyManager
from mcp_dbus import MCPControlServer
from spotlight import SpotlightOverlay
from tray import build_tray
from webview import (
    GEMINI_URL,
    CHROME_UA,
    apply_theme,
    exec_js,
    focus_composer,
    inject_prompt,
    make_browser_view,
)

APP_ID = "org.native.GeminiDesktop"
APP_NAME = "Gemini Desktop Native"
VERSION = "2.1.0"
APP_BINARY = "gemini-desktop-native"

CSS_PATH = Path(__file__).with_name("styles.css")


class GeminiNativeApplication(Adw.Application):
    def __init__(self, start_hidden=False):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.start_hidden = start_hidden
        self.web_context = None
        self.main_window = None
        self.spotlight = None
        self.tray = None
        self.hotkeys = None
        self._quitting = False
        self.mcp = None

        self.connect("startup", self._on_startup)
        self.connect("activate", self._on_activate)
        self.connect("shutdown", self._on_shutdown)

    def _on_startup(self, app):
        GLib.set_application_name(APP_NAME)
        GLib.set_prgname(APP_ID)
        if not Notify.is_initted():
            Notify.init(APP_ID)

        self.data_dir = self._profile_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._load_styles()
        self._create_actions()

        from webview import build_web_context

        self.web_context = build_web_context(self.data_dir)
        self.main_window = self._build_window()
        self.tray = build_tray(self)
        self.mcp = MCPControlServer(self)
        self.mcp.start()
        self.hotkeys = HotkeyManager(
            on_spotlight=lambda: GLib.idle_add(self._toggle_spotlight),
            on_window=lambda: GLib.idle_add(self._toggle_window),
        )
        self.hotkeys.start()

        style_manager = Adw.StyleManager.get_default()
        style_manager.connect("notify::dark", lambda *_: self._mirror_theme())

    def _on_activate(self, app):
        if self.start_hidden and self.tray is not None:
            if self.hotkeys is not None and not self.hotkeys.active:
                print("running hidden in tray", flush=True)
            return
        win = self.get_active_window() or self.main_window
        if win is not None:
            win.present()

    def _on_shutdown(self, app):
        if self.hotkeys is not None:
            self.hotkeys.stop()
        if self.mcp is not None:
            self.mcp.stop()

    def _build_window(self):
        win = Adw.ApplicationWindow(application=self, title="Gemini")
        win.set_default_size(1180, 820)
        win.add_css_class("gemini-main-window")

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        self._view = make_browser_view(
            self.web_context, lambda view: apply_theme(view, self._theme_mode())
        )
        toolbar.set_content(self._view)
        win.set_content(toolbar)

        back = self._nav_button("go-previous-symbolic", "Back", self._go_back)
        forward = self._nav_button("go-next-symbolic", "Forward", self._go_forward)
        reload_btn = self._nav_button("view-refresh-symbolic", "Reload", self._reload)
        home = self._nav_button("go-home-symbolic", "Home", self._home)

        header.pack_start(back)
        header.pack_start(forward)
        header.pack_start(reload_btn)
        header.pack_start(home)

        menu_model = Gio.Menu()
        menu_model.append("Open Gemini", "app.main-window")
        menu_model.append("Spotlight", "app.spotlight")
        menu_model.append("Quit", "app.quit")

        menu_button = Gtk.MenuButton(
            icon_name="open-menu-symbolic",
            menu_model=menu_model,
            tooltip_text="Menu",
        )
        header.pack_end(menu_button)

        win.connect("close-request", self._on_close_request)
        return win

    def _nav_button(self, icon_name, tooltip, callback):
        button = Gtk.Button(icon_name=icon_name)
        button.set_tooltip_text(tooltip)
        button.connect("clicked", lambda *_: callback())
        return button

    def _create_actions(self):
        self.add_action(self._simple_action("main-window", self._toggle_window))
        self.add_action(self._simple_action("spotlight", self._toggle_spotlight))
        self.add_action(self._simple_action("quit", self._quit))
        self.add_action(self._simple_action("back", self._go_back))
        self.add_action(self._simple_action("forward", self._go_forward))
        self.add_action(self._simple_action("reload", self._reload))
        self.add_action(self._simple_action("home", self._home))
        self.set_accels_for_action("app.spotlight", ["<Control><Alt>s"])
        self.set_accels_for_action("app.main-window", ["<Control><Alt>f"])

    def _simple_action(self, name, callback):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", lambda *_: callback())
        return action

    def _toggle_window(self, *_args):
        win = self.get_active_window() or self.main_window
        if win is None:
            return
        if win.get_visible():
            win.set_visible(False)
        else:
            win.present()

    def _toggle_spotlight(self, *_args):
        if self.spotlight is None:
            self.spotlight = SpotlightOverlay(self)
        if self.spotlight.is_visible():
            self.spotlight.hide_overlay()
        else:
            self.spotlight.show_overlay()

    def dispatch_mcp(self, tool_name, args):
        """Execute an MCP tool triggered over D-Bus (callbacks run on main loop)."""
        try:
            return self._mcp_dispatch(tool_name, args)
        except Exception as exc:
            return {
                "ok": False,
                "error": f"internal-error: {exc.__class__.__name__}: {exc}",
            }

    def _mcp_dispatch(self, tool_name, args):
        if tool_name == "go_back":
            view = self._mcp_get_view()
            if view is None:
                return {"ok": False, "error": "no-webview"}
            if hasattr(view, "go_back"):
                view.go_back()
            return {"ok": True, "status": "success", "action": "go_back"}
        if tool_name == "go_forward":
            view = self._mcp_get_view()
            if view is None:
                return {"ok": False, "error": "no-webview"}
            if hasattr(view, "go_forward"):
                view.go_forward()
            return {"ok": True, "status": "success", "action": "go_forward"}
        if tool_name == "navigate":
            url = args.get("url")
            if url is None:
                url = GEMINI_URL
            if not isinstance(url, str) or not url.strip():
                return {"ok": False, "error": "url must be a non-empty string"}
            view = self._mcp_get_view()
            if view is None:
                return {"ok": False, "error": "no-webview"}
            view.load_uri(url)
            return {"ok": True, "status": "success", "navigated_to": url}
        if tool_name == "reload_session":
            view = self._mcp_get_view()
            if view is None:
                return {"ok": False, "error": "no-webview"}
            view.reload()
            return {"ok": True, "status": "success", "action": "reload_session"}
        if tool_name == "exec_js":
            script = args.get("script", "")
            if not isinstance(script, str) or not script.strip():
                return {"ok": False, "error": "script must be a non-empty string"}
            view = self._mcp_get_view()
            if view is None:
                return {"ok": False, "error": "no-webview"}
            outcome = self._exec_js_blocking(view, script)
            if "error" in outcome:
                return {"ok": False, "error": outcome["error"]}
            return {
                "ok": True,
                "status": "success",
                "executed_script": script,
                "result": outcome["value"],
            }
        if tool_name == "send_prompt":
            prompt = args.get("prompt", "")
            if not isinstance(prompt, str) or not prompt.strip():
                return {"ok": False, "error": "prompt must be a non-empty string"}
            view = self._mcp_get_view()
            if view is None:
                return {"ok": False, "error": "no-webview"}
            target = self.get_active_window() or self.main_window
            if target is not None and not target.get_visible():
                target.present()
            inject_prompt(view, prompt)
            return {"ok": True, "status": "success", "prompt": prompt}
        if tool_name == "focus_composer":
            view = self._mcp_get_view()
            if view is None:
                return {"ok": False, "error": "no-webview"}
            focus_composer(view)
            return {"ok": True, "status": "success", "action": "focus_composer"}
        if tool_name == "toggle_window":
            visible = bool(args.get("visible"))
            win = self.get_active_window() or self.main_window
            if win is None:
                return {"ok": False, "error": "no-window"}
            if visible:
                win.present()
            else:
                win.set_visible(False)
            return {
                "ok": True,
                "status": "success",
                "action": "toggle_window",
                "visible": visible,
            }
        if tool_name == "toggle_spotlight":
            self._toggle_spotlight()
            active = bool(
                self.spotlight is not None and self.spotlight.is_visible()
            )
            return {
                "ok": True,
                "status": "success",
                "action": "toggle_spotlight",
                "spotlight_active": active,
            }
        if tool_name == "set_window_geometry":
            width = args.get("width")
            height = args.get("height")
            if (
                not isinstance(width, int)
                or isinstance(width, bool)
                or width <= 0
            ):
                return {"ok": False, "error": "width must be a positive integer"}
            if (
                not isinstance(height, int)
                or isinstance(height, bool)
                or height <= 0
            ):
                return {"ok": False, "error": "height must be a positive integer"}
            win = self.main_window
            if win is None:
                return {"ok": False, "error": "no-window"}
            try:
                win.set_default_size(width, height)
                if hasattr(win, "resize"):
                    win.resize(width, height)
            except Exception as exc:
                return {"ok": False, "error": f"resize-failed: {exc}"}
            return {
                "ok": True,
                "status": "success",
                "action": "set_window_geometry",
                "width": width,
                "height": height,
            }
        if tool_name == "get_state":
            win = self.main_window
            view = getattr(self, "_view", None)
            state = {
                "visible": bool(win.get_visible()) if win is not None else False,
                "current_url": self._view_uri(view),
                "url": self._view_uri(view),
                "can_go_back": self._view_bool(view, "can_go_back"),
                "can_go_forward": self._view_bool(view, "can_go_forward"),
                "spotlight_active": bool(
                    self.spotlight is not None and self.spotlight.is_visible()
                ),
            }
            return {"ok": True, "status": "success", "state": state}
        return {"ok": False, "error": f"unknown-tool: {tool_name}"}

    def _mcp_get_view(self):
        if (
            self.spotlight is not None
            and self.spotlight.is_visible()
            and getattr(self, "_view", None) is not None
            and not (self._view.is_visible() if hasattr(self._view, "is_visible") else False)
        ):
            return self.spotlight.webview
        if getattr(self, "_view", None) is not None:
            return self._view
        if self.spotlight is not None:
            return self.spotlight.webview
        return None

    @staticmethod
    def _view_uri(view):
        if view is None:
            return None
        getter = getattr(view, "get_uri", None)
        if callable(getter):
            try:
                return getter()
            except Exception:
                pass
        props = getattr(view, "props", None)
        if props is not None:
            try:
                return getattr(props, "uri")
            except Exception:
                pass
        return None

    @staticmethod
    def _view_bool(view, name):
        if view is None:
            return False
        method = getattr(view, name, None)
        if callable(method):
            try:
                return bool(method())
            except Exception:
                pass
        props = getattr(view, "props", None)
        if props is not None:
            try:
                return bool(getattr(props, name))
            except Exception:
                pass
        return False

    @staticmethod
    def _js_result_to_str(view, result):
        for name in ("evaluate_javascript_finish", "run_javascript_finish"):
            finish = getattr(view, name, None)
            if finish is None:
                continue
            try:
                value = finish(result)
            except Exception:
                continue
            if value is None:
                continue
            for attr in ("to_string", "to_json"):
                stringify = getattr(value, attr, None)
                if callable(stringify):
                    try:
                        return str(stringify())
                    except Exception:
                        pass
            return str(value)
        return None

    def _exec_js_blocking(self, view, script):
        holder = {}
        loop = GLib.MainLoop()
        state = {"timed_out": False, "done": False, "scheduled": False}

        def on_timeout(*_args):
            state["timed_out"] = True
            if loop.is_running():
                loop.quit()
            return False

        def on_result(source_view, result, *_user_data):
            if state["timed_out"]:
                return
            try:
                value = self._js_result_to_str(source_view, result)
                holder["value"] = value if value is not None else ""
            except Exception:
                holder["value"] = ""
            state["done"] = True
            if loop.is_running():
                loop.quit()

        try:
            state["scheduled"] = exec_js(view, script, on_result)
        except Exception:
            state["scheduled"] = False
        if not state["scheduled"]:
            return {"error": "js-not-scheduled"}
        if state["done"]:
            return {"value": holder.get("value", "")}
        GLib.timeout_add(3000, on_timeout)
        try:
            loop.run()
        except Exception as exc:
            return {"error": f"js-loop-failed: {exc}"}
        if state["timed_out"]:
            return {"error": "js-timeout"}
        return {"value": holder.get("value", "")}

    def _quit(self, *_args):
        self._quitting = True
        self.quit()

    def _go_back(self):
        if self._view is not None and hasattr(self._view, "go_back"):
            self._view.go_back()

    def _go_forward(self):
        if self._view is not None and hasattr(self._view, "go_forward"):
            self._view.go_forward()

    def _reload(self):
        if self._view is not None and hasattr(self._view, "reload"):
            self._view.reload()

    def _home(self):
        if self._view is not None:
            self._view.load_uri(GEMINI_URL)

    def _on_close_request(self, win):
        if self._quitting or self.tray is None:
            return False
        win.set_visible(False)
        return True

    def _theme_mode(self):
        try:
            style = Adw.StyleManager.get_default()
            return "dark" if style.get_dark() else "light"
        except Exception:
            return "light"

    def _mirror_theme(self):
        mode = self._theme_mode()
        if self._view is not None:
            apply_theme(self._view, mode)
        if self.spotlight is not None:
            apply_theme(self.spotlight.webview, mode)

    def _load_styles(self):
        if not CSS_PATH.exists():
            return
        provider = Gtk.CssProvider()
        try:
            provider.load_from_path(str(CSS_PATH))
        except Exception:
            return
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def _profile_dir(self):
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local/share"))
        return base / "gemini-desktop-native"


def _print_ua():
    print(CHROME_UA)
    print("Note: USER_AGENT is injected via WebKit.Settings.set_user_agent().")
    print("Sign-in flow should load accounts.google.com without disallowed_useragent.")


def _autostart_desktop():
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        "Comment=Native desktop client for Google Gemini\n"
        f"Exec={APP_BINARY} --hidden\n"
        f"Icon={APP_ID}\n"
        "Terminal=false\n"
        "Categories=Network;Utility;\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def _autostart(action):
    target = Path.home() / ".config" / "autostart" / f"{APP_BINARY}.desktop"
    if action == "enable":
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_autostart_desktop())
        print(f"Autostart enabled: {target}")
    elif action == "disable":
        if target.exists():
            target.unlink()
            print(f"Autostart disabled: {target}")
        else:
            print(f"No autostart entry present: {target}")
    else:
        print("Usage: --autostart enable|disable")
        return 1
    return 0


def main():
    args = list(sys.argv[1:])
    if "--print-ua" in args:
        _print_ua()
        return 0
    if "--autostart" in args:
        idx = args.index("--autostart")
        value = args[idx + 1] if idx + 1 < len(args) else ""
        return _autostart(value)
    if "--help" in args or "-h" in args:
        print("Usage: gemini-desktop-native [--hidden] [--print-ua] [--autostart enable|disable]")
        return 0
    start_hidden = "--hidden" in args
    filtered = [a for a in args if a != "--hidden"]
    app = GeminiNativeApplication(start_hidden=start_hidden)
    return app.run(filter_args(filtered))


def filter_args(argv):
    return ["gemini-desktop-native"] + argv


if __name__ == "__main__":
    raise SystemExit(main())