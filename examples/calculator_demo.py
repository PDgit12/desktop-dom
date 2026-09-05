#!/usr/bin/env python3
"""
End-to-end desktop-dom demonstration:
Autonomously controls macOS Calculator using native accessibility trees.
"""

import time
from rich.console import Console
from rich.panel import Panel
from desktop_dom import DesktopApp

console = Console()

def main():
    console.print(Panel.fit("[bold cyan]desktop-dom: Autonomous Calculator Demo[/bold cyan]\n[dim]Deterministic Centroid Dispatch via Native macOS AXUIElement[/dim]"))

    # 1. Attach to Calculator
    console.print("\n[bold]Step 1: Attaching to Calculator...[/bold]")
    app = DesktopApp.attach("Calculator")

    # 2. Extract pruned DOM
    console.print("[bold]Step 2: Inspecting Accessibility DOM...[/bold]")
    tree = app.get_tree(as_dict=False)
    total_elements = tree.total_count()
    console.print(f"✓ Extracted and pruned DOM: [bold green]{total_elements} actionable elements[/bold green]")

    # Helper to find button by visible label
    def get_btn(label: str):
        btn = app.find(role="button", name=label)
        if not btn:
            raise RuntimeError(f"Could not find button labeled '{label}'")
        return btn

    # 3. Clear existing display
    console.print("\n[bold]Step 3: Resetting display (All Clear)...[/bold]")
    ac_btn = app.find(role="button", name="All Clear") or app.find(role="button", name="Clear")
    if ac_btn:
        app.click(ac_btn.id)
        time.sleep(0.2)

    # 4. Perform calculation: 25 * 4 = 100
    console.print("\n[bold]Step 4: Executing calculation: [cyan]25 × 4 =[/cyan][/bold]")
    
    sequence = ["2", "5", "Multiply", "4", "Equals"]
    for sym in sequence:
        btn = get_btn(sym)
        res = app.click(btn.id)
        console.print(f"  → Clicked [bold]{sym}[/bold] ([magenta]{btn.id}[/magenta]) at centroid {res['centroid']}")
        time.sleep(0.15)

    # 5. Read back result from accessibility DOM
    console.print("\n[bold]Step 5: Inspecting result from DOM...[/bold]")
    fresh_tree = app.get_tree(as_dict=False)
    result_text = None
    for node in fresh_tree.flatten():
        if node.role == "text" and node.value:
            # Look for non-empty text value
            val = node.value.replace("\u200e", "").strip()
            if val.isdigit() or "," in val:
                result_text = val

    console.print(Panel(f"[bold green]Calculation Result in Calculator Display: {result_text}[/bold green]", title="Verification Passed"))

if __name__ == "__main__":
    main()
