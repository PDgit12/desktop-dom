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
def doctor(
    fix: bool = typer.Option(False, "--fix", help="Automatically launch OS accessibility settings to grant permissions")
):
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
        if fix:
            import subprocess
            if sys.platform == "darwin":
                console.print("\n[bold cyan]Attempting auto-fix: Opening macOS Accessibility Settings...[/bold cyan]")
                subprocess.run(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])
            elif sys.platform.startswith("linux"):
                console.print("\n[bold cyan]Attempting auto-fix: Enabling GNOME accessibility...[/bold cyan]")
                subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "toolkit-accessibility", "true"])
        else:
            console.print("\n[yellow]Tip: Run 'desktop-dom doctor --fix' to automatically open your OS accessibility settings.[/yellow]")
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

@app.command(name="wait-for")
def wait_for_element(
    target: str = typer.Option(..., "--app", "-a", help="Application name or PID"),
    role: Optional[str] = typer.Option(None, "--role", "-r", help="Element role (button, input, text, etc.)"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Element name/label substring"),
    element_id: Optional[str] = typer.Option(None, "--id", "-i", help="Exact or prefix element ID"),
    timeout: float = typer.Option(5.0, "--timeout", "-t", help="Timeout in seconds"),
):
    """Waits for an element matching role, name, or ID to appear and become actionable."""
    try:
        app_instance = DesktopApp.attach(target)
        console.print(f"[dim]Waiting up to {timeout}s for element in '{target}'...[/dim]")
        node = app_instance.wait_for(role=role, name=name, element_id=element_id, timeout=timeout)
        console.print(f"[bold green]✓ Found element:[/bold green] [{node.role.upper()}] \"{node.name}\" (ID: {node.id}, Centroid: {node.bbox.centroid})")
    except TimeoutError as e:
        console.print(f"[bold red]Timeout:[/bold red] {e}", file=sys.stderr)
        sys.exit(1)

@app.command()
def snapshot(
    target: str = typer.Option("Finder", "--app", "-a", help="Application name or PID to snapshot"),
    output: str = typer.Option("dom_snapshot.html", "--out", "-o", help="Output HTML snapshot file path"),
):
    """Generates an interactive standalone HTML/SVG visual HUD snapshot of the application DOM."""
    from desktop_dom.cli.overlay import generate_html_snapshot
    from desktop_dom.schema import DesktopNode
    try:
        app_instance = DesktopApp.attach(target)
        root_node = app_instance.get_tree(as_dict=False)
        assert isinstance(root_node, DesktopNode)
        html = generate_html_snapshot(root_node, target)
        with open(output, "w") as f:
            f.write(html)
        console.print(f"[bold green]✓ Generated visual HUD snapshot:[/bold green] {output}")
    except Exception as e:
        console.print(f"[bold red]Error generating snapshot for '{target}':[/bold red] {e}", file=sys.stderr)
        sys.exit(1)

@app.command()
def overlay(
    target: str = typer.Option(..., "--app", "-a", help="Application name or PID to overlay"),
    duration: float = typer.Option(5.0, "--duration", "-d", help="Duration to display overlay in seconds"),
):
    """Renders a transparent floating click-through HUD directly over the application window."""
    from desktop_dom.cli.overlay import show_macos_overlay
    try:
        console.print(f"[dim]Rendering HUD overlay over '{target}' for {duration}s...[/dim]")
        show_macos_overlay(target, duration=duration)
    except Exception as e:
        console.print(f"[bold red]Error launching overlay for '{target}':[/bold red] {e}", file=sys.stderr)
        sys.exit(1)

@app.command()
def serve(
    target: Optional[str] = typer.Option(None, "--app", "-a", help="Target application name or PID"),
):
    """Starts the Model Context Protocol (MCP) server on stdio."""
    from desktop_dom.integrations.mcp import DesktopDomMCPServer
    server = DesktopDomMCPServer(target_app=target)
    server.run_stdio()

@app.command(name="install-mcp")
def install_mcp(
    client: str = typer.Option("claude", "--client", "-c", help="Target AI client ('claude' or 'cursor')"),
):
    """Auto-configures desktop-dom MCP server in Claude Desktop or Cursor configuration."""
    from pathlib import Path
    import os

    config_path: Optional[Path] = None
    if client.lower() == "claude":
        if sys.platform == "darwin":
            config_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        elif sys.platform.startswith("win"):
            appdata = os.environ.get("APPDATA", "")
            if appdata:
                config_path = Path(appdata) / "Claude" / "claude_desktop_config.json"
        else:
            config_path = Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
    elif client.lower() == "cursor":
        config_path = Path.home() / ".cursor" / "mcp.json"

    if not config_path:
        console.print(f"[bold red]Unsupported client or platform:[/bold red] {client} on {sys.platform}", file=sys.stderr)
        sys.exit(1)

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        if "mcpServers" not in data:
            data["mcpServers"] = {}

        data["mcpServers"]["desktop-dom"] = {
            "command": "desktop-dom",
            "args": ["serve"]
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        console.print(f"[bold green]✓ Successfully configured desktop-dom MCP in:[/bold green]\n  {config_path}")
        console.print("[dim]Restart your AI assistant to start using desktop-dom tools natively.[/dim]")
    except Exception as e:
        console.print(f"[bold red]Failed to write configuration:[/bold red] {e}", file=sys.stderr)
        sys.exit(1)

@app.command()
def displays():
    """Enumerates all connected physical and virtual displays, bounds, and scale factors."""
    adapter = get_platform_adapter()
    disp_list = adapter.get_displays()

    table = Table(title="Connected Displays & Coordinates")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Display Name", style="bold green")
    table.add_column("Origin (X, Y)", style="yellow")
    table.add_column("Dimensions (WxH)", style="magenta")
    table.add_column("Scale", style="blue")
    table.add_column("Primary", style="green")

    for d in disp_list:
        table.add_row(
            str(d.id),
            d.name,
            f"({d.bounds.x}, {d.bounds.y})",
            f"{d.bounds.width}x{d.bounds.height}",
            f"{d.scale_factor}x",
            "✓" if d.is_primary else "",
        )

    console.print(table)

@app.command()
def spaces(
    target: str = typer.Option(..., "--app", "-a", help="Application name or PID"),
):
    """Checks whether the application window is present on the currently active virtual space."""
    adapter = get_platform_adapter()
    is_active = adapter.is_window_on_active_space(target)
    if is_active:
        console.print(f"[bold green]✓ '{target}' is visible on the current active virtual space.[/bold green]")
    else:
        console.print(f"[bold yellow]! '{target}' is currently NOT visible on the active virtual space (minimized, hidden, or on another Space).[/bold yellow]")

@app.command()
def crop(
    target: str = typer.Option(..., "--app", "-a", help="Application name or PID"),
    element_id: Optional[str] = typer.Option(None, "--id", "-i", help="Element ID to crop"),
    bbox_str: Optional[str] = typer.Option(None, "--bbox", "-b", help="Bounding box as 'x,y,width,height'"),
    output: str = typer.Option("crop.png", "--out", "-o", help="Output image file path"),
):
    """Crops an exact subregion bounding box for multimodal vision fallback with token estimation."""
    from desktop_dom.schema import BoundingBox
    try:
        adapter = get_platform_adapter()
        app_instance = DesktopApp.attach(target, adapter=adapter)
        if element_id:
            capture = app_instance.crop_element(element_id)
        elif bbox_str:
            parts = [int(p.strip()) for p in bbox_str.split(",")]
            if len(parts) != 4:
                raise ValueError("Bounding box must be 'x,y,width,height'")
            box = BoundingBox(x=parts[0], y=parts[1], width=parts[2], height=parts[3])
            capture = app_instance.crop_region(box)
        else:
            tree = app_instance.get_tree(as_dict=False)
            capture = app_instance.crop_region(tree.bbox)

        capture.save(output)
        console.print(
            f"[bold green]✓ Saved subregion image to:[/bold green] {output}\n"
            f"[dim]Dimensions: {capture.width}x{capture.height}px | "
            f"Estimated Vision LLM Tokens: ~{capture.estimated_tokens} tokens (>90% savings vs 4K)[/dim]"
        )
    except Exception as e:
        console.print(f"[bold red]Error cropping subregion for '{target}':[/bold red] {e}")
        sys.exit(1)

@app.command()
def assistant(
    mode: str = typer.Option("omnibar", "--mode", "-m", help="'omnibar' (floating Spotlight HUD) or 'cli' (conversational terminal)"),
    cli: bool = typer.Option(False, "--cli", help="Shorthand for conversational terminal HUD mode"),
    ollama_host: str = typer.Option("http://localhost:11434", "--ollama-host", help="Local Ollama endpoint"),
    model: Optional[str] = typer.Option(None, "--model", help="Preferred Ollama model name (e.g. 'ministral-3:8b', 'qwen3:8b')"),
    mute: bool = typer.Option(False, "--mute", help="Disable voice speech feedback (TTS)"),
):
    """Launches the Personal Desktop Assistant (Aura): Floating Spotlight Omnibar or Terminal HUD."""
    from desktop_dom.assistant import DesktopAssistant
    assistant_inst = DesktopAssistant(ollama_host=ollama_host, preferred_model=model)
    if mute:
        assistant_inst.audio.speak = lambda text, wait=False, rate=210: None

    if cli or mode.lower() == "cli":
        assistant_inst.run_cli_session()
    else:
        try:
            assistant_inst.launch_omnibar()
        except Exception as e:
            console.print(f"[bold yellow]Omnibar note:[/bold yellow] {e}. Falling back to CLI mode.")
            assistant_inst.run_cli_session()

if __name__ == "__main__":
    app()
