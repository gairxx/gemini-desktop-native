"""System tray indicator built on AppIndicator / Ayatana bindings."""

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")

from gi.repository import GLib

APP_ID = "org.native.GeminiDesktop"
INDICATOR_ICON = "org.native.GeminiDesktop"


def _load_indicator():
    for namespace, version in (
        ("AyatanaAppIndicator3", "0.1"),
        ("AppIndicator3", "0.1"),
    ):
        try:
            import gi

            gi.require_version(namespace, version)
            module = __import__("gi.repository", fromlist=[namespace])
            return getattr(module, namespace)
        except Exception:
            continue
    return None


def build_tray(app):
    """Create the tray indicator, or return None when unsupported."""
    iface = _load_indicator()
    if iface is None:
        return None

    indicator = iface.Indicator.new(
        APP_ID,
        INDICATOR_ICON,
        iface.IndicatorCategory.APPLICATION_STATUS,
    )
    indicator.set_status(iface.IndicatorStatus.ACTIVE)
    try:
        indicator.set_label("", "")
    except Exception:
        pass

    menu = _build_menu_model(app)
    attached = False
    if menu is not None:
        if hasattr(indicator, "set_menu_model"):
            try:
                indicator.set_menu_model(menu)
                attached = True
            except Exception:
                attached = False
        if not attached and hasattr(indicator, "set_menu"):
            try:
                indicator.set_menu(menu)
                attached = True
            except Exception:
                attached = False

    if hasattr(indicator, "connect"):
        try:
            indicator.connect("activate", lambda *_: GLib.idle_add(app.activate))
        except Exception:
            pass
    return indicator


def _build_menu_model(app):
    try:
        import gi

        gi.require_version("Gio", "2.0")
        from gi.repository import Gio
    except Exception:
        return None

    menu = Gio.Menu()
    menu.append("Open Gemini", "app.main-window")
    menu.append("Spotlight", "app.spotlight")
    menu.append("Quit", "app.quit")
    return menu