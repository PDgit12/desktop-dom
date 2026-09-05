from __future__ import annotations
import sys
import time
import threading
from typing import List, Dict, Any, Optional
from rich.console import Console
from desktop_dom.app import DesktopApp
from desktop_dom.schema import DesktopNode

console = Console()

class InteractionRecorder:
    """
    Monitors user interactions or manual command traces on a desktop application
    and compiles them into executable Python SDK agent scripts.
    Supports live OS-level mouse interception via pynput.
    """

    def __init__(self, target_app: str):
        self.target_app = target_app
        self.app = DesktopApp.attach(target_app)
        self.recorded_steps: List[Dict[str, Any]] = []
        self._current_tree: Optional[DesktopNode] = None
        self._listener = None
        self._active = False
        self._refresh_tree()

    def _refresh_tree(self):
        try:
            self._current_tree = self.app.get_tree(as_dict=False)
        except Exception as e:
            console.print(f"[dim yellow]Warning refreshing tree: {e}[/dim yellow]")

    def record_click(self, element_id: str, button: str = "left"):
        node = self.app._resolve_node(element_id)
        self.recorded_steps.append({
            "action": "click",
            "element_id": node.id,
            "role": node.role,
            "name": node.name,
            "button": button,
        })
        console.print(f"[bold green]✓ Recorded click:[/bold green] [magenta]{node.id}[/magenta] ({node.role} '{node.name}')")
        self._refresh_tree()

    def record_type(self, text: str, element_id: Optional[str] = None):
        self.recorded_steps.append({
            "action": "type",
            "element_id": element_id,
            "text": text,
        })
        console.print(f"[bold green]✓ Recorded type:[/bold green] '{text}' into {element_id or 'active focus'}")

    def record_press(self, key_combination: str):
        self.recorded_steps.append({
            "action": "press",
            "key": key_combination,
        })
        console.print(f"[bold green]✓ Recorded hotkey:[/bold green] '{key_combination}'")

    def _on_physical_click(self, x: int, y: int, button: Any, pressed: bool):
        if not pressed or not self._active:
            return

        btn_name = "left"
        button_str = str(button).lower()
        if "right" in button_str:
            btn_name = "right"

        if self._current_tree is None:
            self._refresh_tree()

        if self._current_tree is None:
            return

        # Check if click is inside application window bounds
        if not self._current_tree.bbox.contains(x, y):
            return

        hit = self._current_tree.find_element_at(x, y)
        if hit and hit.id != "app_root":
            self.recorded_steps.append({
                "action": "click",
                "element_id": hit.id,
                "role": hit.role,
                "name": hit.name,
                "button": btn_name,
            })
            console.print(
                f"[bold green]✓ Intercepted click:[/bold green] [magenta]{hit.id}[/magenta] "
                f"({hit.role} '{hit.name}') at ({x}, {y})"
            )
            # Brief pause then refresh tree for dynamic updates
            time.sleep(0.1)
            self._refresh_tree()

    def start_passive_listener(self):
        """Starts OS-level background mouse listener using pynput."""
        try:
            from pynput import mouse
            self._active = True
            self._listener = mouse.Listener(on_click=self._on_physical_click)
            self._listener.daemon = True
            self._listener.start()
            console.print("[dim cyan]Passive OS mouse hook enabled. Clicks on the application window are recorded automatically.[/dim cyan]")
        except Exception as e:
            console.print(f"[dim yellow]Could not initialize pynput mouse hook ({e}). Manual input fallback active.[/dim yellow]")

    def stop_passive_listener(self):
        self._active = False
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass

    def generate_python_script(self) -> str:
        lines = [
            "# Auto-generated desktop-dom automation script",
            "from desktop_dom import DesktopApp",
            "import time",
            "",
            f"app = DesktopApp.attach('{self.target_app}')",
            "tree = app.get_tree()",
            "",
        ]
        for step in self.recorded_steps:
            if step["action"] == "click":
                lines.append(f"app.click('{step['element_id']}', button='{step['button']}')  # {step['role']}: '{step['name']}'")
            elif step["action"] == "type":
                elem_arg = f"'{step['element_id']}', " if step["element_id"] else "None, "
                lines.append(f"app.type({elem_arg}text='{step['text']}')")
            elif step["action"] == "press":
                lines.append(f"app.press('{step['key']}')")
            lines.append("time.sleep(0.5)")

        return "\n".join(lines)
