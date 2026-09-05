"""
Visual Overlay HUD and HTML Snapshot Generator for desktop-dom.
Renders real-time bounding box badges and interactive SVG inspections.
"""
from __future__ import annotations
import sys
import time
import json
from typing import Optional
from desktop_dom.schema import DesktopNode
from desktop_dom.app import DesktopApp

def generate_html_snapshot(root_node: DesktopNode, app_name: str) -> str:
    """
    Generates a standalone, beautiful HTML/SVG interactive visualization of the DOM tree.
    """
    elements = root_node.flatten()
    win_bbox = root_node.bbox
    svg_w = max(800, win_bbox.width)
    svg_h = max(600, win_bbox.height)
    offset_x = win_bbox.x
    offset_y = win_bbox.y

    boxes_svg = []
    role_colors = {
        "button": "#06b6d4",
        "input": "#10b981",
        "checkbox": "#eab308",
        "radio": "#eab308",
        "combobox": "#a855f7",
        "text": "#94a3b8",
        "window": "#ef4444",
        "menuitem": "#3b82f6",
        "tab": "#38bdf8",
    }

    for el in elements:
        rel_x = el.bbox.x - offset_x
        rel_y = el.bbox.y - offset_y
        color = role_colors.get(el.role, "#64748b")
        name_esc = (el.name or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        
        boxes_svg.append(f"""
        <g class="element-box" data-id="{el.id}" data-role="{el.role}" data-name="{name_esc}" data-centroid="{el.bbox.centroid[0]},{el.bbox.centroid[1]}">
            <rect x="{rel_x}" y="{rel_y}" width="{el.bbox.width}" height="{el.bbox.height}" 
                  fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-width="1.5" rx="3"/>
            <text x="{rel_x + 4}" y="{rel_y + 12}" fill="{color}" font-size="10" font-family="monospace" font-weight="bold">{el.id}</text>
        </g>
        """)

    svg_content = "\n".join(boxes_svg)
    json_tree = json.dumps(root_node.model_dump(), indent=2)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>desktop-dom HUD Snapshot: {app_name}</title>
    <style>
        body {{
            margin: 0;
            background: #0f172a;
            color: #f8fafc;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            height: 100vh;
            overflow: hidden;
        }}
        #viewport {{
            flex: 1;
            padding: 24px;
            overflow: auto;
            display: flex;
            flex-direction: column;
        }}
        #sidebar {{
            width: 420px;
            background: #1e293b;
            border-left: 1px solid #334155;
            display: flex;
            flex-direction: column;
        }}
        header {{
            padding: 16px 20px;
            background: #090d16;
            border-bottom: 1px solid #334155;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        h1 {{ margin: 0; font-size: 16px; color: #38bdf8; }}
        .badge {{ background: #0284c7; padding: 3px 8px; border-radius: 4px; font-size: 12px; }}
        #canvas-container {{
            background: #182234;
            border: 1px solid #334155;
            border-radius: 8px;
            overflow: auto;
            position: relative;
        }}
        svg {{ display: block; }}
        .element-box:hover rect {{
            fill-opacity: 0.35;
            stroke-width: 2.5;
            cursor: pointer;
        }}
        #info-panel {{
            padding: 16px;
            background: #0f172a;
            border-bottom: 1px solid #334155;
            font-size: 13px;
        }}
        #tree-view {{
            flex: 1;
            padding: 16px;
            overflow: auto;
            font-family: monospace;
            font-size: 12px;
            white-space: pre;
            color: #cbd5e1;
        }}
    </style>
</head>
<body>
    <div id="viewport">
        <header>
            <h1>desktop-dom Visual HUD &bull; {app_name}</h1>
            <span class="badge">{len(elements)} Elements &bull; {svg_w}x{svg_h}px</span>
        </header>
        <div id="canvas-container" style="margin-top: 16px;">
            <svg width="{svg_w}" height="{svg_h}" viewBox="0 0 {svg_w} {svg_h}">
                {svg_content}
            </svg>
        </div>
    </div>
    <div id="sidebar">
        <div id="info-panel">
            <h3 style="margin-top:0; color:#38bdf8;">Element Inspector</h3>
            <div id="hover-info">Hover or click an element box to inspect details.</div>
        </div>
        <div id="tree-view">{json_tree}</div>
    </div>
    <script>
        document.querySelectorAll('.element-box').forEach(el => {{
            el.addEventListener('mouseenter', () => {{
                const id = el.getAttribute('data-id');
                const role = el.getAttribute('data-role');
                const name = el.getAttribute('data-name');
                const centroid = el.getAttribute('data-centroid');
                document.getElementById('hover-info').innerHTML = `
                    <div style="margin-bottom:4px;"><b>ID:</b> <code style="color:#f43f5e;">${{id}}</code></div>
                    <div style="margin-bottom:4px;"><b>Role:</b> <span style="color:#38bdf8;">${{role}}</span></div>
                    <div style="margin-bottom:4px;"><b>Name:</b> "${{name}}"</div>
                    <div><b>Centroid:</b> (${{centroid}})</div>
                `;
            }});
        }});
    </script>
</body>
</html>
"""
    return html

def show_macos_overlay(app_name: str, duration: float = 6.0) -> None:
    """
    Renders a native transparent click-through Cocoa overlay window over the target application.
    """
    if sys.platform != "darwin":
        print(f"Native overlay window requires macOS. Use 'desktop-dom snapshot --app {app_name}' on other platforms.")
        return

    from AppKit import (
        NSApplication,
        NSWindow,
        NSView,
        NSColor,
        NSBezierPath,
        NSAttributedString,
        NSFont,
        NSScreen,
        NSBackingStoreBuffered,
        NSWindowStyleMaskBorderless,
    )
    from PyObjCTools import AppHelper

    app = DesktopApp.attach(app_name)
    tree = app.get_tree(as_dict=False)
    assert isinstance(tree, DesktopNode)
    elements = tree.flatten()
    win_bbox = tree.bbox

    # Screen height inversion for Cocoa coordinates
    screen = NSScreen.mainScreen()
    screen_h = screen.frame().size.height if screen else 1080

    class HUDOverlayView(NSView):
        def drawRect_(self, rect):
            NSColor.clearColor().set()
            NSBezierPath.fillRect_(rect)

            for el in elements:
                # Invert Y for Cocoa bottom-left origin
                cocoa_y = screen_h - (el.bbox.y + el.bbox.height)
                box_rect = ((el.bbox.x, cocoa_y), (el.bbox.width, el.bbox.height))

                # Outline box
                path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(box_rect, 3.0, 3.0)
                NSColor.colorWithCalibratedRed_green_blue_alpha_(0.0, 0.9, 1.0, 0.25).set()
                path.fill()
                NSColor.colorWithCalibratedRed_green_blue_alpha_(0.0, 0.9, 1.0, 0.85).set()
                path.setLineWidth_(1.5)
                path.stroke()

    # Create borderless transparent window
    cocoa_y = screen_h - (win_bbox.y + win_bbox.height)
    win_rect = ((0, 0), (screen.frame().size.width, screen.frame().size.height))
    overlay_win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        win_rect,
        NSWindowStyleMaskBorderless,
        NSBackingStoreBuffered,
        False,
    )
    overlay_win.setOpaque_(False)
    overlay_win.setBackgroundColor_(NSColor.clearColor())
    overlay_win.setLevel_(1000)  # Floating above all normal windows
    overlay_win.setIgnoresMouseEvents_(True)  # Click-through!

    view = HUDOverlayView.alloc().initWithFrame_(win_rect)
    overlay_win.setContentView_(view)
    overlay_win.orderFrontRegardless()

    time.sleep(duration)
    overlay_win.close()
