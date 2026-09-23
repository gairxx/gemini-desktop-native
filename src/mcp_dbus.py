"""MCP-over-D-Bus control server for the Gemini desktop app.

Owns org.freedesktop.AI.Control on the session bus and exposes an MCP-style
tool surface (capabilities + tool execution) to external agents.
"""

import json

BUS_NAME = "org.freedesktop.AI.Control"
OBJECT_PATH = "/org/freedesktop/AI/Control"
INTERFACE_NAME = "org.freedesktop.AI.Control"

TOOLS = [
    {
        "name": "go_back",
        "description": "Navigate back in WebKit history.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "go_forward",
        "description": "Navigate forward in WebKit history.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "navigate",
        "description": (
            "Navigate the web view to a URL or Gemini sub-route "
            "(defaults to the Gemini home page)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
        },
    },
    {
        "name": "reload_session",
        "description": "Reload the Gemini page to refresh the Google session.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "exec_js",
        "description": (
            "Execute arbitrary JavaScript in the web view and return the "
            "execution result as a string."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"script": {"type": "string"}},
            "required": ["script"],
        },
    },
    {
        "name": "send_prompt",
        "description": (
            "Focus the Gemini composer and inject a prompt for the user to send."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"prompt": {"type": "string"}},
            "required": ["prompt"],
        },
    },
    {
        "name": "focus_composer",
        "description": (
            "Focus the composer input element in the web view without "
            "submitting text."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "toggle_window",
        "description": "Show or hide the main application window.",
        "inputSchema": {
            "type": "object",
            "properties": {"visible": {"type": "boolean"}},
            "required": ["visible"],
        },
    },
    {
        "name": "toggle_spotlight",
        "description": "Toggle or present the Spotlight card overlay.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "set_window_geometry",
        "description": "Resize the main application window.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "width": {"type": "integer"},
                "height": {"type": "integer"},
            },
            "required": ["width", "height"],
        },
    },
    {
        "name": "get_state",
        "description": (
            "Return the current application runtime state (visibility, URL, "
            "history, spotlight)."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def capabilities_json():
    return json.dumps({"tools": TOOLS})


class MCPControlServer:
    """Publish the control interface on the session bus (dasbus)."""

    def __init__(self, app):
        self._app = app
        self._bus = None
        self._interface = None

    def start(self):
        try:
            from dasbus.connection import SessionMessageBus
            from dasbus.server.interface import dbus_interface
        except Exception as exc:
            print(
                f"gemini-desktop-native: MCP over D-Bus disabled "
                f"({exc.__class__.__name__}: {exc}).",
                flush=True,
            )
            return False

        @dbus_interface(INTERFACE_NAME)
        class ControlInterface:
            def GetCapabilities(self) -> str:
                return capabilities_json()

            def ExecuteTool(
                self, tool_name: str, arguments_json: str
            ) -> str:
                try:
                    args = json.loads(arguments_json or "{}")
                    if not isinstance(args, dict):
                        raise ValueError("arguments must be a JSON object")
                except Exception as exc:
                    return json.dumps(
                        {"ok": False, "error": f"bad-arguments: {exc}"}
                    )
                return json.dumps(
                    self._app.dispatch_mcp(str(tool_name), args)
                )

        try:
            self._bus = SessionMessageBus()
            self._interface = ControlInterface()
            self._interface._app = self._app
            self._bus.publish_object(OBJECT_PATH, self._interface)
            self._bus.register_service(BUS_NAME)
            print(
                f"gemini-desktop-native: MCP D-Bus service ready "
                f"({BUS_NAME}{OBJECT_PATH}).",
                flush=True,
            )
            return True
        except Exception as exc:
            print(
                f"gemini-desktop-native: failed to start MCP D-Bus service "
                f"({exc.__class__.__name__}: {exc}).",
                flush=True,
            )
            try:
                self._bus.disconnect()
            except Exception:
                pass
            self._bus = None
            return False

    def stop(self):
        if self._bus is not None:
            try:
                self._bus.disconnect()
            except Exception:
                pass
            self._bus = None
        self._interface = None