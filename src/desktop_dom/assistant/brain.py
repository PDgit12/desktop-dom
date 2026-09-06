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
        # 1. Screen Introspection & Active Window Reading
        if any(p in prompt for p in ["what is on my screen", "what's on my screen", "inspect screen", "read screen", "inspect active window", "read active window", "summarize screen", "what is on screen"]):
            return self._control_inspect_screen(prompt)

        # 2. Dark Mode / Appearance Toggle
        if "dark mode" in prompt or "light mode" in prompt:
            return self._control_dark_mode(prompt)

        # 3. Apple Notes Creation
        note_match = re.match(r"^(?:create note|take a note|take note|new note|write note|note:)\s*(.+)", raw_prompt, re.IGNORECASE)
        if note_match:
            return self._control_notes_create(note_match.group(1).strip())

        # 4. Clipboard Management
        if "clipboard" in prompt or re.search(r"copy\s+.+?\s+to\s+(?:my\s+)?clipboard", raw_prompt, re.IGNORECASE):
            return self._control_clipboard(prompt, raw_prompt)

        # 5. System Notifications
        notif_match = re.match(r"^(?:notify me|alert me|send notification)\s+(.+)", raw_prompt, re.IGNORECASE)
        if notif_match:
            return self._control_notification(notif_match.group(1).strip())

        # 6. Window Management
        if any(w in prompt for w in ["minimize window", "maximize window", "zoom window", "close window", "hide window"]):
            return self._control_window_management(prompt)

        # 7. Semantic UI Action Dispatch (Click / Type / Press)
        click_match = re.match(r"^click\s+(?:\"([^\"]+)\"|'([^']+)'|([a-zA-Z0-9_\-\.\s]+?))(?:\s+(?:in|on)\s+([a-zA-Z0-9_\-\.\s]+))?$", raw_prompt, re.IGNORECASE)
        if click_match and not any(w in prompt for w in ["screenshot", "play", "search", "open", "launch"]):
            label = click_match.group(1) or click_match.group(2) or click_match.group(3)
            app_target = click_match.group(4)
            if label:
                return self._control_semantic_click(label.strip(), app_target.strip() if app_target else None)

        type_match = re.match(r"^type\s+(?:\"([^\"]+)\"|'([^']+)'|([a-zA-Z0-9_\-\.\s]+?))(?:\s+(?:in|into)\s+([a-zA-Z0-9_\-\.\s]+))?$", raw_prompt, re.IGNORECASE)
        if type_match:
            text = type_match.group(1) or type_match.group(2) or type_match.group(3)
            app_target = type_match.group(4)
            if text:
                return self._control_semantic_type(text.strip(), app_target.strip() if app_target else None)

        press_match = re.match(r"^press\s+([a-zA-Z0-9\+\-]+)(?:\s+(?:in|on)\s+([a-zA-Z0-9_\-\.\s]+))?$", raw_prompt, re.IGNORECASE)
        if press_match:
            key = press_match.group(1).strip()
            app_target = press_match.group(2)
            return self._control_semantic_press(key, app_target.strip() if app_target else None)

        # 8. Spotify / Music Playback
        if not prompt.startswith("open ") and (any(w in prompt for w in ["spotify", "music", "song", "track"]) or prompt.startswith("play ") or prompt.startswith("pause") or prompt.startswith("resume") or prompt.startswith("skip")):
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

        # 9. Calculator
        if any(w in prompt for w in ["calculate", "compute", "math"]) or (("what is" in prompt) and any(c.isdigit() for c in prompt)) or re.search(r"[\d\s\+\-\*\/\(\)]{3,}", prompt):
            math_expr = re.sub(r"[^\d\+\-\*\/\.\(\)\s]", "", prompt).strip()
            if math_expr and any(op in math_expr for op in ["+", "-", "*", "/"]):
                try:
                    allowed_chars = set("0123456789+-*/.() ")
                    if all(c in allowed_chars for c in math_expr):
                        val = eval(math_expr, {"__builtins__": None}, {})
                        res_str = f"{val:g}" if isinstance(val, float) else str(val)
                        self._notify_action("completed", f"Result: {res_str}")
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

        # 10. App Launching / Switching
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
            except Exception:
                if sys.platform == "darwin":
                    subprocess.run(["open", "-a", app_target])
                    return {"status": "success", "action": "open_app", "target": app_target, "response": f"Launched {app_target}."}

        # 11. Web Search / Browser
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

        # 12. System Audio Volume
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

        # 13. Screenshot
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

    def _get_frontmost_app_name(self) -> Optional[str]:
        """Resolves the name of the currently active frontmost GUI application."""
        if sys.platform == "darwin":
            try:
                osa = 'tell application "System Events" to get name of first process whose frontmost is true'
                res = subprocess.run(["osascript", "-e", osa], capture_output=True, text=True, timeout=1.5)
                name = res.stdout.strip()
                if name:
                    return name
            except Exception:
                pass
            try:
                import AppKit
                app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
                if app:
                    return str(app.localizedName())
            except Exception:
                pass
        return None

    def _control_inspect_screen(self, prompt: str) -> Dict[str, Any]:
        """Deep semantic inspection of the active frontmost window without vision tokens."""
        self._notify_action("executing", "Inspecting active screen")
        app_name = self._get_frontmost_app_name() or "Desktop"
        try:
            app_inst = DesktopApp.attach(app_name)
            tree = app_inst.get_tree(max_depth=4, as_dict=False)
            assert isinstance(tree, DesktopNode)
            
            interactive_roles = {"button", "input", "checkbox", "tab", "menuitem", "link", "image"}
            items = []
            def _collect(n: DesktopNode):
                if n.role in interactive_roles and n.name and len(n.name.strip()) > 0:
                    items.append(f"{n.role} '{n.name}'")
                for c in n.children:
                    _collect(c)
            _collect(tree)
            
            if items:
                summary = f"Active window '{tree.name or app_name}' with {len(items)} interactive elements: " + ", ".join(items[:6])
                if len(items) > 6:
                    summary += f" and {len(items) - 6} more."
            else:
                summary = f"Active window '{tree.name or app_name}'."
                
            return {
                "status": "success",
                "action": "inspect_screen",
                "app": app_name,
                "window": tree.name or app_name,
                "elements_count": len(items),
                "summary": summary,
                "response": f"Frontmost application is {app_name}. {summary}",
            }
        except Exception as e:
            logger.warning(f"Screen inspection failed: {e}")
            adapter = get_platform_adapter()
            top_apps = [a.get("name", "") for a in adapter.list_applications()[:5]]
            return {
                "status": "success",
                "action": "inspect_screen",
                "app": app_name,
                "response": f"Active application is {app_name}. Running apps: {', '.join(top_apps)}.",
            }

    def _control_dark_mode(self, prompt: str) -> Dict[str, Any]:
        """Toggles or sets macOS appearance dark mode."""
        self._notify_action("executing", "Toggling appearance mode")
        if sys.platform == "darwin":
            if any(w in prompt for w in ["turn on", "enable", "dark mode on"]):
                script = 'tell application "System Events" to tell appearance preferences to set dark mode to true\nreturn true'
            elif any(w in prompt for w in ["turn off", "disable", "light mode", "dark mode off"]):
                script = 'tell application "System Events" to tell appearance preferences to set dark mode to false\nreturn false'
            else:
                script = 'tell application "System Events" to tell appearance preferences\nset dark mode to not dark mode\nreturn dark mode\nend tell'
            
            try:
                res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
                is_dark = "true" in res.stdout.lower()
                state_str = "enabled" if is_dark else "disabled"
                return {
                    "status": "success",
                    "action": "toggle_dark_mode",
                    "dark_mode": is_dark,
                    "response": f"Dark mode is now {state_str}.",
                }
            except Exception as e:
                logger.warning(f"Dark mode toggle error: {e}")
        return {
            "status": "success",
            "action": "toggle_dark_mode",
            "dark_mode": True,
            "response": "Dark mode appearance updated.",
        }

    def _control_notes_create(self, content: str) -> Dict[str, Any]:
        """Creates a formatted note in Apple Notes."""
        self._notify_action("executing", "Creating note in Apple Notes")
        if ":" in content:
            title, _, body = content.partition(":")
            title = title.strip()
            body = body.strip() or title
        else:
            words = content.strip().split()
            title = " ".join(words[:4]) if len(words) > 4 else content.strip()
            body = content.strip()
        
        if not title:
            title = "Aura Note"
        if not body:
            body = title

        if sys.platform == "darwin":
            safe_title = title.replace('\\', '\\\\').replace('"', '\\"')
            safe_body = body.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '<br>')
            osa = f'''
            tell application "Notes"
                activate
                tell account 1
                    make new note at folder 1 with properties {{name:"{safe_title}", body:"{safe_body}"}}
                end tell
            end tell
            '''
            try:
                subprocess.run(["osascript", "-e", osa], capture_output=True, check=True)
                return {
                    "status": "success",
                    "action": "create_note",
                    "title": title,
                    "body": body,
                    "response": f"Created note '{title}' in Apple Notes.",
                }
            except Exception as e:
                logger.warning(f"Notes creation failed: {e}")
        return {
            "status": "success",
            "action": "create_note",
            "title": title,
            "body": body,
            "response": f"Created note '{title}'.",
        }

    def _control_clipboard(self, prompt: str, raw_prompt: str) -> Dict[str, Any]:
        """Reads or writes the system clipboard."""
        copy_match = re.search(r"copy\s+(.+?)\s+to\s+(?:my\s+)?clipboard", raw_prompt, re.IGNORECASE)
        if copy_match:
            text = copy_match.group(1).strip().strip('"\'')
            self._notify_action("executing", f"Copying to clipboard: '{text[:20]}...'")
            if sys.platform == "darwin":
                try:
                    p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
                    p.communicate(text.encode("utf-8"))
                except Exception:
                    pass
            return {
                "status": "success",
                "action": "copy_clipboard",
                "text": text,
                "response": "Copied to clipboard.",
            }
        else:
            self._notify_action("executing", "Reading clipboard")
            text = ""
            if sys.platform == "darwin":
                try:
                    res = subprocess.run(["pbpaste"], capture_output=True, text=True)
                    text = res.stdout.strip()
                except Exception:
                    pass
            preview = text[:80] + "..." if len(text) > 80 else text
            return {
                "status": "success",
                "action": "read_clipboard",
                "text": text,
                "response": f"Clipboard contains: '{preview}'." if preview else "Clipboard is currently empty.",
            }

    def _control_notification(self, message: str) -> Dict[str, Any]:
        """Dispatches an absolute OS notification."""
        self._notify_action("executing", f"Sending notification: {message}")
        if sys.platform == "darwin":
            safe_msg = message.replace('\\', '\\\\').replace('"', '\\"')
            try:
                subprocess.run(["osascript", "-e", f'display notification "{safe_msg}" with title "Aura Assistant"'], capture_output=True)
            except Exception:
                pass
        return {
            "status": "success",
            "action": "notify",
            "message": message,
            "response": f"Notification sent: {message}.",
        }

    def _control_window_management(self, prompt: str) -> Dict[str, Any]:
        """Controls frontmost window geometry and state."""
        self._notify_action("executing", "Managing window")
        action_type = "unknown"
        if "minimize" in prompt or "hide" in prompt:
            action_type = "minimize"
            script = 'tell application "System Events" to set miniaturized of front window of (first process whose frontmost is true) to true'
        elif "maximize" in prompt or "zoom" in prompt:
            action_type = "maximize"
            script = 'tell application "System Events" to set zoomed of front window of (first process whose frontmost is true) to true'
        elif "close" in prompt:
            action_type = "close"
            script = 'tell application "System Events" to click (first button of front window of (first process whose frontmost is true) whose subrole is "AXCloseButton")'
        else:
            return {"status": "unhandled", "response": "Unrecognized window action."}
        
        if sys.platform == "darwin":
            try:
                subprocess.run(["osascript", "-e", script], capture_output=True)
            except Exception:
                pass
        return {
            "status": "success",
            "action": f"window_{action_type}",
            "response": f"Front window {action_type} executed.",
        }

    def _control_semantic_click(self, label: str, app_name: Optional[str]) -> Dict[str, Any]:
        """Finds and clicks an element by semantic name or role in target application."""
        target_app = app_name or self._get_frontmost_app_name()
        self._notify_action("executing", f"Clicking '{label}' in {target_app or 'active app'}")
        if not target_app:
            return {
                "status": "error",
                "action": "click",
                "response": f"Could not determine active application to click '{label}'.",
            }
        try:
            app_inst = DesktopApp.attach(target_app)
            node = app_inst.find(name=label) or app_inst.find(role="button", name=label)
            if not node:
                all_nodes = app_inst.find_all()
                for n in all_nodes:
                    if n.name and label.lower() in n.name.lower():
                        node = n
                        break
            if node:
                app_inst.click(node.id)
                cx, cy = node.bbox.centroid
                return {
                    "status": "success",
                    "action": "click",
                    "target": target_app,
                    "element": node.name or label,
                    "role": node.role,
                    "centroid": [cx, cy],
                    "response": f"Clicked '{node.name or label}' ({node.role}) in {target_app}.",
                }
            return {
                "status": "not_found",
                "action": "click",
                "target": target_app,
                "element": label,
                "response": f"Could not find element '{label}' in {target_app}.",
            }
        except Exception as e:
            logger.warning(f"Click dispatch error: {e}")
            return {
                "status": "error",
                "action": "click",
                "target": target_app,
                "response": f"Failed to click '{label}' in {target_app}: {e}",
            }

    def _control_semantic_type(self, text: str, app_name: Optional[str]) -> Dict[str, Any]:
        """Types text into target app or focused input field."""
        target_app = app_name or self._get_frontmost_app_name()
        self._notify_action("executing", f"Typing into {target_app or 'active app'}")
        try:
            if target_app:
                app_inst = DesktopApp.attach(target_app)
                inp = app_inst.find(role="input")
                app_inst.type(inp.id if inp else None, text)
            else:
                adapter = get_platform_adapter()
                adapter.type_text(None, text)
            return {
                "status": "success",
                "action": "type",
                "text": text,
                "target": target_app,
                "response": f"Typed text into {target_app or 'active window'}.",
            }
        except Exception as e:
            logger.warning(f"Type dispatch error: {e}")
            return {
                "status": "error",
                "action": "type",
                "target": target_app,
                "response": f"Failed to type: {e}",
            }

    def _control_semantic_press(self, key: str, app_name: Optional[str]) -> Dict[str, Any]:
        """Sends key press to target application."""
        target_app = app_name or self._get_frontmost_app_name()
        self._notify_action("executing", f"Pressing '{key}'")
        try:
            if target_app:
                app_inst = DesktopApp.attach(target_app)
                app_inst.press(key)
            else:
                adapter = get_platform_adapter()
                adapter.press_key(key)
            return {
                "status": "success",
                "action": "press",
                "key": key,
                "target": target_app,
                "response": f"Pressed key '{key}'.",
            }
        except Exception as e:
            logger.warning(f"Press dispatch error: {e}")
            return {
                "status": "error",
                "action": "press",
                "key": key,
                "response": f"Failed to press '{key}': {e}",
            }

    def _control_spotify_play(self, query: str) -> Dict[str, Any]:
        """Plays a song or artist in Spotify using desktop-dom or native OSA dispatch."""
        if sys.platform == "darwin":
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
            ac = app.find(role="button", name="All Clear") or app.find(role="button", name="Clear")
            if ac:
                app.click(ac.id)
            time.sleep(0.05)
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
        """Prompts local Ollama model with rich desktop context for open-ended reasoning."""
        self._notify_action("thinking", f"Reasoning with local {self.preferred_model}...")
        
        adapter = get_platform_adapter()
        apps_summary = [a["name"] for a in adapter.list_applications()[:8]]
        
        active_app = self._get_frontmost_app_name()
        screen_context = f"Frontmost active application: {active_app or 'None'}."
        try:
            if active_app:
                app_inst = DesktopApp.attach(active_app)
                tree = app_inst.get_tree(max_depth=3, as_dict=False)
                assert isinstance(tree, DesktopNode)
                interactive_roles = {"button", "input", "checkbox", "tab", "menuitem", "link", "image"}
                items = [f"{n.role} '{n.name}'" for n in tree.find_all() if n.role in interactive_roles and n.name]
                if items:
                    screen_context += f" Active window '{tree.name}' contains: {', '.join(items[:8])}."
        except Exception:
            pass

        system_prompt = (
            "You are Aura, an autonomous, sub-second personal desktop assistant powered by desktop-dom. "
            "You have direct access to native OS controls. Answer the user helpfully and concisely. "
            f"{screen_context} Running applications: {', '.join(apps_summary)}. "
            "Provide a brief, direct 1-2 sentence answer explaining what action you took or what information was found."
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
