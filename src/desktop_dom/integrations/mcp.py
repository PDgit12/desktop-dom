from __future__ import annotations
import sys
import json
import logging
from typing import Dict, Any, Optional

from desktop_dom.app import DesktopApp

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("desktop_dom.mcp")

class DesktopDomMCPServer:
    """
    Lightweight, dependency-free Model Context Protocol (MCP) server
    communicating over standard input/output (stdio JSON-RPC).
    """

    def __init__(self, target_app: Optional[str] = None):
        self.target_app = target_app or "active"
        self.app: Optional[DesktopApp] = None
        self._init_app()

    def _init_app(self):
        try:
            if self.target_app == "active":
                # Will query active window dynamically
                self.app = DesktopApp.attach("Finder") # default fallback anchor
            else:
                self.app = DesktopApp.attach(self.target_app)
        except Exception as e:
            logger.warning(f"Initial app attach warning: {e}")

    def run_stdio(self):
        logger.info("Desktop-DOM MCP Server running on stdio...")
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = self.handle_request(request)
                if response is not None:
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()
            except Exception as e:
                logger.error(f"Error handling MCP line: {e}")

    def handle_request(self, req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "desktop-dom-mcp", "version": "0.1.0"},
                },
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": "desktop_get_screen_dom",
                            "description": "Extracts the semantic accessibility DOM of the targeted desktop window, pruned to actionable elements.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "app_name": {"type": "string", "description": "Optional application name or PID (e.g. 'Spotify', 'Calculator')"},
                                    "max_depth": {"type": "integer", "default": 8},
                                },
                            },
                        },
                        {
                            "name": "desktop_click_element",
                            "description": "Dispatches a deterministic hardware click to an element's centroid using its ephemeral ID.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "element_id": {"type": "string", "description": "Deterministic ID (e.g. 'btn_save_4f2b')"},
                                    "button": {"type": "string", "enum": ["left", "right", "double"], "default": "left"},
                                },
                                "required": ["element_id"],
                            },
                        },
                        {
                            "name": "desktop_type_text",
                            "description": "Types text using native OS keyboard events into a focused or specified element.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "text": {"type": "string"},
                                    "element_id": {"type": "string", "description": "Optional element ID to focus first"},
                                    "clear_first": {"type": "boolean", "default": False},
                                },
                                "required": ["text"],
                            },
                        },
                        {
                            "name": "desktop_press_key",
                            "description": "Dispatches hotkeys or special keyboard chords (e.g. 'cmd+s', 'return', 'tab').",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "key_combination": {"type": "string"},
                                },
                                "required": ["key_combination"],
                            },
                        },
                    ]
                },
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})
            try:
                result_content = self.call_tool(tool_name, args)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(result_content, indent=2)}]
                    },
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": str(e)},
                }

        elif method == "notifications/initialized":
            return None

        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}

    def call_tool(self, name: str, args: Dict[str, Any]) -> Any:
        app_name = args.get("app_name")
        if app_name:
            self.app = DesktopApp.attach(app_name)
        elif self.app is None:
            self.app = DesktopApp.attach("Finder")

        if name == "desktop_get_screen_dom":
            depth = args.get("max_depth", 8)
            return self.app.get_tree(max_depth=depth, as_dict=True)

        elif name == "desktop_click_element":
            elem_id = args["element_id"]
            btn = args.get("button", "left")
            return self.app.click(elem_id, button=btn)

        elif name == "desktop_type_text":
            text = args["text"]
            elem_id = args.get("element_id")
            clear = args.get("clear_first", False)
            return self.app.type(elem_id, text=text, clear_first=clear)

        elif name == "desktop_press_key":
            chord = args["key_combination"]
            return self.app.press(chord)

        raise ValueError(f"Unknown tool: {name}")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    server = DesktopDomMCPServer(target_app=target)
    server.run_stdio()
