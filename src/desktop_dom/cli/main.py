from __future__ import annotations
import sys
import json
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from desktop_dom.app import DesktopApp
from desktop_dom.adapters import get_platform_adapter
from desktop_dom.cli.inspect import render_rich_tree
from desktop_dom.cli.actions import run_click, run_type, run_press
from desktop_dom.cli.recorder import InteractionRecorder

app = typer.Typer(
    name="desktop-dom",
    help="Playwright for Desktop: Semantic Accessibility DOM and Deterministic Action Engine for AI Agents",
    add_completion=False,
)
console = Console()

@app.command()
def doctor():
    """Validates OS accessibility permissions, display scale factors, and dependencies."""
    adapter = get_platform_adapter()
    perms = adapter.check_permissions()
    scale = adapter.get_display_scale_factor()

    table = Table(title="desktop-dom Doctor Check")
    table.add_column("Component", style="cyan", no_wrap=True)
    table.add_column("Status", style="bold")
    table.add_column("Details")

    status_style = "[green]PASSED[/green]" if perms["accessibility_trusted"] else "[red]FAILED[/red]"
    table.add_row("OS Accessibility API", status_style, perms["message"])
    table.add_row("Display Scaling", "[green]OK[/green]", f"Backing scale factor: {scale}x")
    table.add_row("Platform Adapter", "[green]OK[/green]", f"{adapter.__class__.__name__} ({perms['platform']})")

    console.print(table)
    if not perms["accessibility_trusted"]:
        sys.exit(1)

@app.command()
def apps():
    """Lists running GUI desktop applications available for attachment."""
    adapter = get_platform_adapter()
    app_list = adapter.list_applications()

    table = Table(title="Running Desktop Applications")
    table.add_column("PID", style="cyan", no_wrap=True)
    table.add_column("Application Name", style="bold green")
    table.add_column("Bundle / Identifier", style="dim")
    table.add_column("Active", style="yellow")

    for a in app_list:
        table.add_row(
            str(a["pid"]),
            a["name"],
            a.get("bundle_id", ""),
            "✓" if a.get("is_active") else "",
        )

    console.print(table)

@app.command()
def inspect(
    target: str = typer.Option("Finder", "--app", "-a", help="Application name or PID to inspect"),
    format_type: str = typer.Option("tree", "--format", "-f", help="'tree' or 'json'"),
    depth: int = typer.Option(10, "--depth", "-d", help="Max hierarchy depth"),
    prune: bool = typer.Option(True, "--prune/--raw", help="Prune non-interactive containers and assign clean IDs"),
):
    """Inspects the desktop accessibility DOM and renders a token-pruned tree."""
    try:
        app_instance = DesktopApp.attach(target)
        if format_type == "json":
            dom_dict = app_instance.get_tree(max_depth=depth, prune=prune, as_dict=True)
            console.print_json(json.dumps(dom_dict))
        else:
            root_node = app_instance.get_tree(max_depth=depth, prune=prune, as_dict=False)
            rich_tree = render_rich_tree(root_node)
            console.print(rich_tree)
            
            # Print token & node summary
            total_nodes = root_node.total_count()
            raw_bytes = len(json.dumps(root_node.to_token_dict(include_children=True, max_child_depth=depth)))
            est_tokens = raw_bytes // 4
            console.print(
                f"\n[dim]Summary: {total_nodes} elements | ~{est_tokens} tokens JSON payload (<300ms query)[/dim]"
            )
    except Exception as e:
        console.print(f"[bold red]Error inspecting '{target}':[/bold red] {e}", file=sys.stderr)
        sys.exit(1)

@app.command()
def click(
    element_id: str = typer.Option(..., "--id", "-i", help="Deterministic element ID (e.g. 'btn_clear_02')"),
    target: str = typer.Option("Finder", "--app", "-a", help="Application name or PID"),
    button: str = typer.Option("left", "--button", "-b", help="'left', 'right', or 'double'"),
):
    """Dispatches a deterministic hardware click to an element's centroid."""
    run_click(target, element_id, button=button)

@app.command()
def type_text(
    text: str = typer.Option(..., "--text", "-t", help="Text to type"),
    target: str = typer.Option("Finder", "--app", "-a", help="Application name or PID"),
    element_id: Optional[str] = typer.Option(None, "--id", "-i", help="Element ID to focus first"),
    clear_first: bool = typer.Option(False, "--clear", "-c", help="Clear existing text first"),
):
    """Types text into an element or the currently focused control."""
    run_type(target, text, element_id=element_id, clear_first=clear_first)

@app.command()
def press(
    key: str = typer.Option(..., "--key", "-k", help="Key combination (e.g. 'cmd+s', 'return', 'tab')"),
):
    """Dispatches a keyboard shortcut or modifier chord."""
    run_press(key)

@app.command()
def record(
    target: str = typer.Option(..., "--app", "-a", help="Application name or PID to record interactions on"),
    output: Optional[str] = typer.Option(None, "--out", "-o", help="Path to write the generated Python script"),
):
    """Launches an interactive session to record actions and generate Python agent code."""
    recorder = InteractionRecorder(target)
    recorder.start_passive_listener()
    console.print(f"[bold green]Recording interactions on '{target}'. Click directly on the window or type commands. Type 'exit' to stop.[/bold green]")
    
    try:
        while True:
            try:
                line = input("recorder> ").strip()
                if not line or line == "exit":
                    break
                parts = line.split()
                cmd = parts[0].lower()
                if cmd == "click" and len(parts) >= 2:
                    recorder.record_click(parts[1])
                elif cmd == "type" and len(parts) >= 2:
                    text_content = " ".join(parts[1:])
                    recorder.record_type(text_content)
                elif cmd == "press" and len(parts) >= 2:
                    recorder.record_press(parts[1])
                elif cmd == "tree":
                    tree = recorder.app.get_tree(as_dict=False)
                    console.print(render_rich_tree(tree))
                elif cmd == "help":
                    console.print("Commands:\n  (Physical click on app window is recorded automatically)\n  click <id>\n  type <text>\n  press <chord>\n  tree\n  exit")
                else:
                    console.print("[yellow]Unknown command. Type 'help' for commands.[/yellow]")
            except (KeyboardInterrupt, EOFError):
                break
    finally:
        recorder.stop_passive_listener()

    script = recorder.generate_python_script()
    if output:
        with open(output, "w") as f:
            f.write(script)
        console.print(f"[bold green]✓ Wrote automation script to {output}[/bold green]")
    else:
        console.print("\n[bold cyan]Generated Agent Code:[/bold cyan]\n")
        console.print(script)

@app.command()
def serve(
    target: Optional[str] = typer.Option(None, "--app", "-a", help="Target application name or PID"),
):
    """Starts the Model Context Protocol (MCP) server on stdio."""
    from desktop_dom.integrations.mcp import DesktopDomMCPServer
    server = DesktopDomMCPServer(target_app=target)
    server.run_stdio()

if __name__ == "__main__":
    app()
