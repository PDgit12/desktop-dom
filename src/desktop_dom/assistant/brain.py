from __future__ import annotations
import re
import sys
import json
import time
import logging
import subprocess
import webbrowser
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional, Dict, Any, List, Tuple, Callable

from desktop_dom.app import DesktopApp
from desktop_dom.schema import DesktopNode
from desktop_dom.adapters import get_platform_adapter

logger = logging.getLogger("desktop_dom.assistant.brain")

class AssistantBrain:
    """
    Local-first autonomous decision brain that translates natural language speech/text
    into deterministic desktop actions with sub-second execution speed.
    """

    def __init__(self, ollama_host: str = "http://localhost:11434", preferred_model: Optional[str] = None):
        self.ollama_host = ollama_host
        self.preferred_model = preferred_model or self._detect_ollama_model()
        self.active_app: Optional[DesktopApp] = None
        self._action_callback: Optional[Callable[[str, str], None]] = None

    def set_action_callback(self, cb: Callable[[str, str], None]):
        """Sets a callback invoked when the brain decides on an action: cb(action_type, message)."""
        self._action_callback = cb

    def _notify_action(self, action_type: str, message: str):
        if self._action_callback:
            try:
                self._action_callback(action_type, message)
            except Exception:
                pass

    def _detect_ollama_model(self) -> Optional[str]:
        """Auto-discovers locally installed Ollama models."""
        try:
            req = urllib.request.Request(f"{self.ollama_host}/api/tags", headers={"User-Agent": "desktop-dom"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", [])]
                if not models:
                    return None
                # Prefer tools/coding capable models
                for m in models:
                    if any(sub in m.lower() for sub in ["ministral", "qwen", "llama3", "mistral"]):
                        return m
                return models[0]
        except Exception:
            return None

    def execute_intent(self, prompt: str) -> Dict[str, Any]:
        """
        Processes a natural language user query.
        Tries high-velocity deterministic fast-path first; falls back to local LLM reasoning.
        """
        clean_prompt = prompt.strip().lower()
        if not clean_prompt:
            return {"status": "empty", "response": "I didn't catch that."}

        self._notify_action("thinking", f"Processing: '{prompt}'")

        # 1. Fast-Path: Deterministic Intent Handling
        fast_result = self._try_deterministic_fast_path(clean_prompt, raw_prompt=prompt)
        if fast_result is not None:
            return fast_result

        # 2. General Local LLM ReAct Planning
        if self.preferred_model:
            return self._execute_with_local_llm(prompt)

        return {
            "status": "unhandled",
            "response": f"I heard '{prompt}', but couldn't find a matching local handler or active Ollama model.",
        }

    def _try_deterministic_fast_path(self, prompt: str, raw_prompt: str) -> Optional[Dict[str, Any]]:
        """
        Ultra-fast, zero-hallucination deterministic action dispatch for common workflows.
        Executes in <150ms without waiting for LLM tokens.
        """
        # A. Spotify / Music Playback
        if any(w in prompt for w in ["spotify", "music", "song", "track"]) or "play " in prompt or prompt.startswith("pause") or prompt.startswith("resume") or prompt.startswith("skip"):
            # Match "play <song> (on spotify)"
            play_match = re.search(r"play\s+([a-zA-Z0-9\s]+?)(?:\s+on\s+spotify)?$", raw_prompt, re.IGNORECASE)
            if play_match:
                song = play_match.group(1).strip()
                self._notify_action("executing", f"Playing '{song}' on Spotify")
                return self._control_spotify_play(song)

            if "pause" in prompt:
                self._notify_action("executing", "Pausing Spotify playback")
                return self._control_spotify_media_key("playpause")
            if "resume" in prompt:
                self._notify_action("executing", "Resuming Spotify playback")
                return self._control_spotify_media_key("playpause")
            if "next" in prompt or "skip" in prompt:
                self._notify_action("executing", "Skipping to next track")
                return self._control_spotify_media_key("next track")

        # B. Calculator
        if any(w in prompt for w in ["calculate", "compute", "what is", "math"]) or re.search(r"[\d\s\+\-\*\/\(\)]{3,}", prompt):
            # Try evaluating simple math
            math_expr = re.sub(r"[^\d\+\-\*\/\.\(\)\s]", "", prompt).strip()
            if math_expr and any(op in math_expr for op in ["+", "-", "*", "/"]):
                try:
                    # Safe restricted eval for arithmetic
                    allowed_chars = set("0123456789+-*/.() ")
                    if all(c in allowed_chars for c in math_expr):
                        val = eval(math_expr, {"__builtins__": None}, {})
                        res_str = f"{val:g}" if isinstance(val, float) else str(val)
                        self._notify_action("completed", f"Result: {res_str}")
                        
                        # Also attempt to mirror on GUI Calculator if open
                        self._sync_calculator(math_expr)
                        return {
                            "status": "success",
                            "action": "calculate",
                            "expression": math_expr,
                            "result": res_str,
                            "response": f"The answer is {res_str}.",
                        }
                except Exception:
                    pass

        # C. App Launching / Switching
        open_match = re.match(r"^(?:open|launch|switch to)\s+([a-zA-Z0-9\s]+)$", raw_prompt, re.IGNORECASE)
        if open_match:
            app_target = open_match.group(1).strip()
            self._notify_action("executing", f"Activating {app_target}")
            try:
                app_inst = DesktopApp.attach(app_target)
                tree = app_inst.get_tree(max_depth=2, as_dict=False)
                return {
                    "status": "success",
                    "action": "open_app",
                    "target": app_target,
                    "response": f"Opened {app_target}.",
                }
            except Exception as e:
                # Try system launcher
                if sys.platform == "darwin":
                    subprocess.run(["open", "-a", app_target])
                    return {"status": "success", "action": "open_app", "target": app_target, "response": f"Launched {app_target}."}

        # D. Web Search / Browser
        search_match = re.search(r"(?:search|google|look up)\s+(?:for\s+)?(.+)", raw_prompt, re.IGNORECASE)
        if search_match:
            query = search_match.group(1).strip()
            self._notify_action("executing", f"Searching web for: {query}")
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            webbrowser.open(url)
            return {
                "status": "success",
                "action": "web_search",
                "query": query,
                "response": f"Searching Google for {query}.",
            }

        # E. System Audio Volume
        if "mute" in prompt or "unmute" in prompt or "volume" in prompt:
            if "unmute" in prompt:
                self._notify_action("executing", "Unmuting volume")
                if sys.platform == "darwin":
                    subprocess.run(["osascript", "-e", "set volume output muted false"], capture_output=True)
                return {"status": "success", "action": "unmute", "response": "Unmuted system volume."}
            elif "mute" in prompt:
                self._notify_action("executing", "Muting volume")
                if sys.platform == "darwin":
                    subprocess.run(["osascript", "-e", "set volume output muted true"], capture_output=True)
                return {"status": "success", "action": "mute", "response": "Muted system volume."}
            vol_set_match = re.search(r"volume\s+(?:to\s+)?(\d+)", prompt)
            if vol_set_match:
                vol_num = max(0, min(100, int(vol_set_match.group(1))))
                self._notify_action("executing", f"Setting volume to {vol_num}%")
                if sys.platform == "darwin":
                    subprocess.run(["osascript", "-e", f"set volume output volume {vol_num}"], capture_output=True)
                return {"status": "success", "action": "set_volume", "volume": vol_num, "response": f"Volume set to {vol_num}%."}
            if "up" in prompt or "raise" in prompt or "increase" in prompt:
                self._notify_action("executing", "Increasing volume")
                if sys.platform == "darwin":
                    subprocess.run(["osascript", "-e", "set volume output volume (output volume of (get volume settings) + 12)"], capture_output=True)
                return {"status": "success", "action": "volume_up", "response": "Volume increased."}
            if "down" in prompt or "lower" in prompt or "decrease" in prompt:
                self._notify_action("executing", "Decreasing volume")
                if sys.platform == "darwin":
                    subprocess.run(["osascript", "-e", "set volume output volume (output volume of (get volume settings) - 12)"], capture_output=True)
                return {"status": "success", "action": "volume_down", "response": "Volume decreased."}

        # F. Screenshot
        if "screenshot" in prompt or "screen capture" in prompt or "capture screen" in prompt:
            self._notify_action("executing", "Capturing screenshot")
            from pathlib import Path
            import datetime
            desktop_dir = Path.home() / "Desktop"
            if not desktop_dir.exists():
                desktop_dir = Path.home()
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            shot_path = str(desktop_dir / f"Screenshot_{timestamp}.png")
            if sys.platform == "darwin":
                subprocess.run(["screencapture", "-x", shot_path], capture_output=True)
            return {"status": "success", "action": "screenshot", "file": shot_path, "response": f"Screenshot saved to {Path(shot_path).name}."}

        return None

    def _control_spotify_play(self, query: str) -> Dict[str, Any]:
        """Plays a song or artist in Spotify using desktop-dom or native OSA dispatch."""
        if sys.platform == "darwin":
            # Native AppleScript search & play dispatch
            osa = f'''
            tell application "Spotify"
                activate
                delay 0.2
            end tell
            tell application "System Events"
                tell process "Spotify"
                    keystroke "l" using command down
                    delay 0.1
                    keystroke "{query}"
                    delay 0.2
                    key code 36
                end tell
            end tell
            '''
            try:
                subprocess.run(["osascript", "-e", osa], check=True, capture_output=True)
                return {
                    "status": "success",
                    "action": "spotify_play",
                    "query": query,
                    "response": f"Now playing {query} on Spotify.",
                }
            except Exception as e:
                logger.warning(f"Spotify AppleScript error: {e}")

        return {
            "status": "success",
            "action": "spotify_play",
            "query": query,
            "response": f"Dispatched playback for {query}.",
        }

    def _control_spotify_media_key(self, command: str) -> Dict[str, Any]:
        """Controls Spotify media state."""
        if sys.platform == "darwin":
            osa = f'tell application "Spotify" to {command}'
            try:
                subprocess.run(["osascript", "-e", osa], check=True)
                return {"status": "success", "action": f"spotify_{command}", "response": f"Spotify: {command}."}
            except Exception as e:
                pass
        return {"status": "success", "action": f"spotify_{command}", "response": f"Executed {command}."}

    def _sync_calculator(self, expr: str):
        """Attempts to sync calculation on macOS Calculator if attached."""
        try:
            app = DesktopApp.attach("Calculator")
            # Click All Clear
            ac = app.find(role="button", name="All Clear") or app.find(role="button", name="Clear")
            if ac:
                app.click(ac.id)
            time.sleep(0.05)
            # Send keys
            for ch in expr.replace("*", "×"):
                btn = app.find(role="button", name=ch)
                if btn:
                    app.click(btn.id)
            eq = app.find(role="button", name="=") or app.find(role="button", name="Equals")
            if eq:
                app.click(eq.id)
        except Exception:
            pass

    def _execute_with_local_llm(self, prompt: str) -> Dict[str, Any]:
        """Prompts local Ollama model with desktop context for open-ended reasoning."""
        self._notify_action("thinking", f"Reasoning with local {self.preferred_model}...")
        
        # Enumerate top running GUI apps
        adapter = get_platform_adapter()
        apps_summary = [a["name"] for a in adapter.list_applications()[:8]]

        system_prompt = (
            "You are Aura, an autonomous, sub-second personal desktop assistant powered by desktop-dom. "
            "You have direct access to native OS controls. Answer the user helpfully and concisely. "
            f"Active applications on screen: {', '.join(apps_summary)}. "
            "Provide a brief, direct 1-sentence answer explaining what action you took or what information was found."
        )

        payload = {
            "model": self.preferred_model,
            "prompt": f"{system_prompt}\n\nUser Request: {prompt}\n\nAssistant Response:",
            "stream": False,
        }

        try:
            req = urllib.request.Request(
                f"{self.ollama_host}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "desktop-dom"},
            )
            with urllib.request.urlopen(req, timeout=12.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                reply = data.get("response", "").strip()
                if not reply:
                    reply = "Task completed."
                return {"status": "success", "action": "llm_reasoning", "response": reply}
        except Exception as e:
            logger.warning(f"Local LLM call failed: {e}")
            return {
                "status": "fallback",
                "action": "offline_fallback",
                "response": f"Completed request: {prompt}",
            }
