"""WebKitGTK browser view factory with Google-compatible UA emulation."""

import json
from pathlib import Path

import gi

gi.require_version("Gio", "2.0")
gi.require_version("Gtk", "4.0")

from gi.repository import GLib

GEMINI_URL = "https://gemini.google.com"

CHROME_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

THEME_JS = """(() => {
    const root = document.documentElement;
    const theme = 'THEME';
    root.setAttribute('data-gemini-native-theme', theme);
    root.setAttribute('data-theme', theme);
    let style = document.getElementById('gemini-native-theme');
    if (!style) {
        style = document.createElement('style');
        style.id = 'gemini-native-theme';
        (document.head || root).appendChild(style);
    }
    style.textContent = theme === 'dark'
        ? ':root{color-scheme:dark !important}'
          'html,body{background:#14161a !important;color:#e7e9ee !important}'
          'input,textarea{color-scheme:dark !important}'
        : ':root{color-scheme:light !important}'
          'html,body{background:#ffffff !important;color:#1f1f1f !important}';
})();"""

FOCUS_COMPOSER_JS = (
    "(function(){var el=document.querySelector('textarea,[contenteditable=\"true\"]');"
    "if(el){try{el.focus();}catch(e){}}})();"
)

PROMPT_INJECT_JS = """(() => {
    const prompt = %s;
    const candidates = document.querySelectorAll(
        'div[contenteditable="true"], [contenteditable="plaintext-only"], textarea'
    );
    let el = null;
    for (const node of candidates) {
        if (node.offsetParent !== null || node.getBoundingClientRect().width > 0) {
            el = node;
            break;
        }
    }
    if (!el) return false;
    el.focus();
    if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
        el.value = prompt;
        el.dispatchEvent(new Event('input', {bubbles: true}));
        el.dispatchEvent(new Event('change', {bubbles: true}));
    } else {
        el.textContent = prompt;
        const range = document.createRange();
        range.selectNodeContents(el);
        range.collapse(false);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        el.dispatchEvent(new InputEvent('input', {
            bubbles: true, data: prompt, inputType: 'insertText'
        }));
    }
    return true;
})();"""


def require_webkit():
    """Load the GTK4 WebKit binding (WebKit 6.0)."""
    gi.require_version("WebKit", "6.0")
    from gi.repository import WebKit

    return WebKit


def build_web_context(base_dir):
    """Return the process-wide WebKit context (WebKit 6.0 single-context model)."""
    WebKit = require_webkit()
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)

    try:
        context = WebKit.WebContext.get_default()
    except (AttributeError, TypeError):
        try:
            context = WebKit.WebContext.new()
        except (AttributeError, TypeError):
            context = WebKit.WebContext()

    try:
        manager = WebKit.WebsiteDataManager.new_with_base_data_directory(str(base))
    except (AttributeError, TypeError):
        try:
            manager = WebKit.WebsiteDataManager(base_data_directory=str(base))
        except (AttributeError, TypeError):
            manager = None
    if manager is not None and hasattr(context, "set_website_data_manager"):
        try:
            context.set_website_data_manager(manager)
        except Exception:
            pass

    if hasattr(context, "set_cache_model"):
        cache_model = getattr(
            WebKit.CacheModel, "WEB_BROWSER", getattr(
                WebKit.CacheModel, "PRIMARY_WEBBROWSER", None
            )
        )
        if cache_model is not None:
            try:
                context.set_cache_model(cache_model)
            except Exception:
                pass
    _optional(context, "set_favicon_database_directory", str(base / "favicons"))
    return context


def make_browser_view(_context, theme_cb):
    """Build a configured WebKit.WebView (uses the shared default context)."""
    WebKit = require_webkit()
    view = WebKit.WebView()

    settings = view.get_settings()
    _optional(settings, "set_enable_javascript", True)
    _optional(settings, "set_enable_media_stream", True)
    _optional(settings, "set_enable_mediasource", True)
    _optional(settings, "set_media_playback_requires_user_gesture", False)
    _optional(settings, "set_media_playback_allows_inline", True)
    _optional(settings, "set_javascript_can_access_clipboard", True)
    _optional(
        settings, "set_javascript_can_open_windows_automatically", False
    )
    _optional(settings, "set_enable_back_forward_navigation_gestures", True)
    if hasattr(settings, "set_hardware_acceleration_policy") and hasattr(
        WebKit, "HardwareAccelerationPolicy"
    ):
        try:
            settings.set_hardware_acceleration_policy(
                WebKit.HardwareAccelerationPolicy.ALWAYS
            )
        except Exception:
            pass
    if hasattr(settings, "set_user_agent"):
        settings.set_user_agent(CHROME_UA)
    elif hasattr(settings, "set_user_agent_with_application_details"):
        settings.set_user_agent_with_application_details("Chrome", "124.0.0.0")

    view.connect("load-changed", lambda v, ev: _on_load_changed(v, ev, theme_cb))
    _safe_connect(view, "permission-request", _on_permission_request)
    _safe_connect(view, "create", _on_create_window)
    _safe_connect(view, "enter-fullscreen", _on_enter_fullscreen)
    _safe_connect(view, "leave-fullscreen", _on_leave_fullscreen)
    _safe_connect(view, "show-notification", _on_show_notification)
    _safe_connect(view, "notify::title", _on_title_changed)

    view.load_uri(GEMINI_URL)
    return view


def exec_js(view, script, callback=None):
    """Run a JS snippet. Works with both WebKit async API generations."""
    if view is None:
        return False
    if callback is None:
        try:
            view.evaluate_javascript(script, -1, None, None, None, None, None)
            return True
        except Exception:
            pass
        try:
            view.run_javascript(script)
            return True
        except Exception:
            return False
    try:
        view.evaluate_javascript(script, -1, None, None, None, callback, None)
        return True
    except TypeError:
        pass
    except Exception:
        return False
    try:
        view.run_javascript(script, None, callback)
        return True
    except Exception:
        return False


def run_measure(view, script, callback):
    """Evaluate JS and deliver the result to an async callback."""
    return exec_js(view, script, callback)


def get_measured_value(view, result):
    """Extract a numeric result from a finished JS evaluation."""
    value = None
    for name in ("evaluate_javascript_finish", "run_javascript_finish"):
        finish = getattr(view, name, None)
        if finish is None:
            continue
        try:
            value = finish(result)
            break
        except Exception:
            continue
    if value is None:
        return None
    try:
        return float(value.to_double())
    except Exception:
        pass
    try:
        return float(str(value.to_string()))
    except Exception:
        return None


def apply_theme(view, mode):
    """Micro-inject desktop CSS so the page mirrors the system GTK theme."""
    if view is None:
        return
    js = THEME_JS.replace("THEME", mode if mode in ("dark", "light") else "light")
    exec_js(view, js)


def focus_composer(view):
    """Place the caret into the Gemini prompt field if it exists."""
    exec_js(view, FOCUS_COMPOSER_JS)
    return False


def inject_prompt(view, text):
    """Inject a prompt into the focused composer (fire-and-forget)."""
    if view is None:
        return False
    script = PROMPT_INJECT_JS % json.dumps(text or "")
    return exec_js(view, script)


def _optional(obj, method_name, value):
    setter = getattr(obj, method_name, None)
    if setter is None:
        return
    try:
        setter(value)
    except Exception:
        pass


def _safe_connect(widget, signal, handler):
    try:
        widget.connect(signal, handler)
    except Exception:
        pass


def _on_load_changed(view, event, theme_cb):
    WebKit = require_webkit()
    if event != WebKit.LoadEvent.FINISHED:
        return
    if theme_cb is not None:
        theme_cb(view)
    try:
        GLib.timeout_add(250, focus_composer, view)
    except Exception:
        focus_composer(view)


def _on_title_changed(view, param):
    root = view.get_root()
    if root is None or not hasattr(root, "set_title"):
        return
    title = view.get_title() or "Gemini"
    if hasattr(view, "is_playing_audio") and view.is_playing_audio():
        title = f"{title}  •"
    root.set_title(title)


def _on_permission_request(view, request):
    try:
        request.allow()
    except Exception:
        pass
    return True


def _on_create_window(view, action):
    uri = None
    try:
        request = action.get_request()
        if request is not None:
            uri = request.get_uri()
    except Exception:
        uri = None
    if uri and uri != "about:blank":
        try:
            view.load_uri(uri)
        except Exception:
            pass
    return None


def _on_enter_fullscreen(view):
    root = view.get_root()
    if root is not None and hasattr(root, "fullscreen"):
        root.fullscreen()


def _on_leave_fullscreen(view):
    root = view.get_root()
    if root is not None and hasattr(root, "unfullscreen"):
        root.unfullscreen()


def _on_show_notification(view, notification):
    title, body = _notification_text(notification)
    try:
        gi.require_version("Notify", "0.7")
        from gi.repository import Notify

        if not Notify.is_initted():
            Notify.init("org.native.GeminiDesktop")
        native = Notify.Notification.new(title, body, None)
        native.set_app_name("Gemini Desktop Native")
        native.show()
        return True
    except Exception:
        return False


def _notification_text(notification):
    title = body = None
    for name in ("get_title", "title"):
        getter = getattr(notification, name, None)
        if getter is None:
            continue
        try:
            title = getter() if callable(getter) else getter
            break
        except Exception:
            continue
    for name in ("get_body", "body"):
        getter = getattr(notification, name, None)
        if getter is None:
            continue
        try:
            body = getter() if callable(getter) else getter
            break
        except Exception:
            continue
    return title or "Gemini", body or ""