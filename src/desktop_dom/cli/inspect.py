from __future__ import annotations
import json
from rich.tree import Tree
from rich.console import Console
from rich.text import Text
from desktop_dom.schema import DesktopNode

ROLE_COLORS = {
    "button": "bold cyan",
    "input": "bold green",
    "checkbox": "bold yellow",
    "radio": "bold yellow",
    "combobox": "bold magenta",
    "menuitem": "blue",
    "tab": "bright_blue",
    "table": "bright_magenta",
    "text": "white",
    "window": "bold red",
    "dialog": "bold red",
    "group": "dim white",
    "pane": "dim cyan",
}

def render_rich_tree(node: DesktopNode) -> Tree:
    color = ROLE_COLORS.get(node.role, "white")
    role_badge = f"[{node.role.upper()}]"
    
    label = Text()
    label.append(f"{role_badge} ", style=color)
    if node.name:
        label.append(f'"{node.name}" ', style="bold")
    if node.value:
        label.append(f'(val: "{node.value}") ', style="italic yellow")
    
    cx, cy = node.bbox.centroid
    label.append(f"({node.bbox.x}, {node.bbox.y}, {node.bbox.width}x{node.bbox.height}) ", style="dim")
    label.append(f"--> ID: {node.id}", style="bold magenta")

    tree = Tree(label)
    _add_children(tree, node)
    return tree

def _add_children(tree: Tree, parent: DesktopNode):
    for child in parent.children:
        color = ROLE_COLORS.get(child.role, "white")
        role_badge = f"[{child.role.upper()}]"
        
        label = Text()
        label.append(f"{role_badge} ", style=color)
        if child.name:
            label.append(f'"{child.name}" ', style="bold")
        if child.value:
            label.append(f'(val: "{child.value}") ', style="italic yellow")
        
        cx, cy = child.bbox.centroid
        label.append(f"({child.bbox.x}, {child.bbox.y}, {child.bbox.width}x{child.bbox.height}) ", style="dim")
        label.append(f"--> ID: {child.id}", style="bold magenta")

        branch = tree.add(label)
        _add_children(branch, child)
