from __future__ import annotations
import sys
from typing import Optional, Literal
from rich.console import Console
from desktop_dom.app import DesktopApp

console = Console()
err_console = Console(stderr=True)

def run_click(app_target: str, element_id: str, button: str = "left"):
    try:
        app = DesktopApp.attach(app_target)
        res = app.click(element_id, button=button)
        console.print(f"[bold green]✓ Clicked element:[/bold green] [magenta]{res['element_id']}[/magenta] ({res['role']} '{res['name']}') at centroid {res['centroid']}")
    except Exception as e:
        err_console.print(f"[bold red]✗ Click failed:[/bold red] {e}")
        sys.exit(1)

def run_type(app_target: str, text: str, element_id: Optional[str] = None, clear_first: bool = False):
    try:
        app = DesktopApp.attach(app_target)
        res = app.type(element_id, text=text, clear_first=clear_first)
        target_str = f"element [magenta]{element_id}[/magenta]" if element_id else "active focus"
        console.print(f"[bold green]✓ Typed into {target_str}:[/bold green] '{text}'")
    except Exception as e:
        err_console.print(f"[bold red]✗ Type failed:[/bold red] {e}")
        sys.exit(1)

def run_press(key_combination: str):
    try:
        from desktop_dom.adapters import get_platform_adapter
        adapter = get_platform_adapter()
        adapter.press_key(key_combination)
        console.print(f"[bold green]✓ Pressed hotkey:[/bold green] [yellow]{key_combination}[/yellow]")
    except Exception as e:
        err_console.print(f"[bold red]✗ Press failed:[/bold red] {e}")
        sys.exit(1)
