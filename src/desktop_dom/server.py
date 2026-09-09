from __future__ import annotations
import json
import time
import logging
import sys
from typing import Optional, Dict, Any
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

from desktop_dom import __version__
from desktop_dom.app import DesktopApp
from desktop_dom.diff import compute_dom_diff
from desktop_dom.adapters import get_platform_adapter
from desktop_dom.assistant.brain import AssistantBrain
from desktop_dom.assistant.memory import AuraMemory
from desktop_dom.agent import AutonomousDesktopAgent

logger = logging.getLogger("desktop_dom.server")

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Multi-threaded minimal HTTP server with daemon threads."""
    daemon_threads = True
    allow_reuse_address = True


class DesktopDomRequestHandler(BaseHTTPRequestHandler):
    """Minimalist, high-performance JSON-RPC / REST API handler for Crcle integration."""

    app_cache: Dict[str, DesktopApp] = {}
    brain: Optional[AssistantBrain] = None
    memory: Optional[AuraMemory] = None

    @classmethod
    def get_brain(cls) -> AssistantBrain:
        if cls.brain is None:
            cls.memory = AuraMemory()
            cls.brain = AssistantBrain(memory=cls.memory)
        return cls.brain

    @classmethod
    def get_app(cls, target: str = "Finder") -> DesktopApp:
        if target not in cls.app_cache:
            cls.app_cache[target] = DesktopApp.attach(target)
        return cls.app_cache[target]

    def _send_json(self, status_code: int, data: Dict[str, Any]):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json(200, {"status": "ok"})

    def do_GET(self):
        start = time.perf_counter()
        if self.path in ("/", "/health", "/status"):
            adapter = get_platform_adapter()
            perms = adapter.check_permissions()
            brain = self.get_brain()
            mem_summary = brain.memory.get_summary() if brain.memory else {}
            elapsed = (time.perf_counter() - start) * 1000.0

            self._send_json(200, {
                "status": "healthy",
                "service": "desktop-dom-daemon",
                "version": __version__,
                "platform": perms.get("platform", sys.platform),
                "accessibility_trusted": perms.get("accessibility_trusted", False),
                "memory_vips": mem_summary.get("contacts_count", 0),
                "cached_apps": list(self.app_cache.keys()),
                "latency_ms": round(elapsed, 2),
            })
        else:
            self._send_json(404, {"error": f"Endpoint not found: {self.path}"})

    def do_POST(self):
        start = time.perf_counter()
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        
        try:
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except Exception as e:
            self._send_json(400, {"error": f"Malformed JSON: {e}"})
            return

        endpoint = self.path.rstrip("/")

        try:
            if endpoint == "/tree":
                # Pruned accessibility DOM
                target = payload.get("target", "Finder")
                depth = payload.get("depth", 10)
                prune = payload.get("prune", True)
                app = self.get_app(target)
                tree_dict = app.get_tree(max_depth=depth, prune=prune, as_dict=True)
                elapsed = (time.perf_counter() - start) * 1000.0
                self._send_json(200, {
                    "status": "success",
                    "target": target,
                    "elapsed_ms": round(elapsed, 2),
                    "tree": tree_dict,
                })

            elif endpoint == "/action":
                # Deterministic action with state verification
                target = payload.get("target", "Finder")
                action_name = payload.get("action", "click")
                elem_id = payload.get("element_id")
                text = payload.get("text", "")
                key = payload.get("key", "return")
                verify = payload.get("verify", True)
                expected = payload.get("expected", {"type": "any_change"}) if verify else None

                app = self.get_app(target)

                if action_name == "click":
                    act_fn = lambda: app.click(elem_id)
                elif action_name == "type":
                    act_fn = lambda: app.type(elem_id, text)
                elif action_name == "press":
                    act_fn = lambda: app.press(key)
                else:
                    self._send_json(400, {"error": f"Unknown action '{action_name}'"})
                    return

                if verify:
                    result = app.execute_and_verify(act_fn, expected_effect=expected)
                    self._send_json(200, {
                        "status": result.status,
                        "action": result.action,
                        "verified": result.verified,
                        "verification_message": result.verification_message,
                        "diff": result.diff.to_dict(),
                        "elapsed_ms": round(result.elapsed_ms, 2),
                    })
                else:
                    res = act_fn()
                    elapsed = (time.perf_counter() - start) * 1000.0
                    self._send_json(200, {
                        "status": "success",
                        "action": action_name,
                        "result": res,
                        "elapsed_ms": round(elapsed, 2),
                    })

            elif endpoint == "/diff":
                # State verification / diff
                target = payload.get("target", "Finder")
                app = self.get_app(target)
                diff = app.diff()
                elapsed = (time.perf_counter() - start) * 1000.0
                self._send_json(200, {
                    "status": "success",
                    "target": target,
                    "diff": diff.to_dict(),
                    "elapsed_ms": round(elapsed, 2),
                })

            elif endpoint == "/intent":
                # Level 2 Personal Intent & Memory resolution
                query = payload.get("query", "")
                brain = self.get_brain()
                exec_result = brain.execute_intent(query)
                elapsed = (time.perf_counter() - start) * 1000.0
                self._send_json(200, {
                    "status": "success",
                    "query": query,
                    "result": exec_result,
                    "elapsed_ms": round(elapsed, 2),
                })

            elif endpoint == "/agent/run":
                # Level 3 Autonomous Loop
                target = payload.get("target", "Finder")
                goal = payload.get("goal", "")
                max_steps = payload.get("max_steps", 10)
                settle_delay = payload.get("settle_delay", 0.01)
                app = self.get_app(target)
                agent = AutonomousDesktopAgent(app=app, max_steps=max_steps, settle_delay=settle_delay)
                agent_res = agent.run(goal)
                self._send_json(200, {
                    "status": "success",
                    "result": agent_res.to_dict(),
                })

            else:
                self._send_json(404, {"error": f"Endpoint not found: {endpoint}"})

        except Exception as e:
            logger.error(f"Server error handling {endpoint}: {e}", exc_info=True)
            self._send_json(500, {"error": str(e), "endpoint": endpoint})

    def log_message(self, format: str, *args: Any):
        # Quiet standard output during server operations
        logger.debug(f"%s - - [%s] {format % args}", self.client_address[0], self.log_date_time_string())


def start_server(host: str = "127.0.0.1", port: int = 8484) -> ThreadedHTTPServer:
    """Initializes and starts the minimal desktop-dom HTTP daemon."""
    server = ThreadedHTTPServer((host, port), DesktopDomRequestHandler)
    logger.info(f"desktop-dom daemon listening on http://{host}:{port}")
    return server
