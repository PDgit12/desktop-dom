from __future__ import annotations
import time
import logging
from typing import List, Optional, Literal, Dict, Any, Set, Tuple

logger = logging.getLogger("desktop_dom.adapters.macos")

# macOS Native imports (guarded)
try:
    import objc
    import Quartz
    import ApplicationServices
    from AppKit import NSWorkspace, NSScreen
    HAS_MACOS_DEPS = True
except ImportError:
    HAS_MACOS_DEPS = False

from desktop_dom.adapters.base import BasePlatformAdapter
from desktop_dom.schema import DesktopNode, BoundingBox, ElementStates

# Canonical role mapping from macOS AX roles
MACOS_ROLE_MAP: Dict[str, str] = {
    "AXApplication": "window",
    "AXWindow": "window",
    "AXSheet": "dialog",
    "AXDrawer": "dialog",
    "AXButton": "button",
    "AXPopUpButton": "combobox",
    "AXMenuButton": "button",
    "AXTextField": "input",
    "AXTextArea": "input",
    "AXSearchField": "input",
    "AXCheckBox": "checkbox",
    "AXRadioButton": "radio",
    "AXComboBox": "combobox",
    "AXMenuItem": "menuitem",
    "AXMenu": "menu",
    "AXMenuBar": "menubar",
    "AXMenuBarItem": "menuitem",
    "AXTabGroup": "tab_group",
    "AXTable": "table",
    "AXOutline": "table",
    "AXRow": "table_row",
    "AXCell": "table_cell",
    "AXColumn": "group",
    "AXStaticText": "text",
    "AXHeading": "text",
    "AXLink": "link",
    "AXImage": "image",
    "AXSlider": "slider",
    "AXScrollBar": "scrollbar",
    "AXProgressIndicator": "slider",
    "AXGroup": "group",
    "AXScrollArea": "pane",
    "AXSplitGroup": "pane",
    "AXList": "group",
    "AXBrowser": "pane",
    "AXWebArea": "pane",
}

# Virtual Keycodes for macOS Quartz keyboard events
MACOS_KEYCODES: Dict[str, int] = {
    "return": 36,
    "enter": 76,
    "tab": 48,
    "space": 49,
    "backspace": 51,
    "delete": 51,
    "forward_delete": 117,
    "escape": 53,
    "esc": 53,
    "command": 55,
    "cmd": 55,
    "shift": 56,
    "capslock": 57,
    "option": 58,
    "alt": 58,
    "control": 59,
    "ctrl": 59,
    "right_shift": 60,
    "right_option": 61,
    "right_control": 62,
    "left": 123,
    "right": 124,
    "down": 125,
    "up": 126,
    "home": 115,
    "end": 119,
    "pageup": 116,
    "pagedown": 121,
    "f1": 122,
    "f2": 120,
    "f3": 99,
    "f4": 118,
    "f5": 96,
    "f6": 97,
    "f7": 98,
    "f8": 100,
    "f9": 101,
    "f10": 109,
    "f11": 103,
    "f12": 111,
    # Letter keys (QWERTY layout virtual codes)
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9,
    "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "1": 18, "2": 19,
    "3": 20, "4": 21, "6": 22, "5": 23, "=": 24, "9": 25, "7": 26, "-": 27, "8": 28,
    "0": 29, "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35, "l": 37, "j": 38,
    "'": 39, "k": 40, ";": 41, "\\": 42, ",": 43, "/": 44, "n": 45, "m": 46, ".": 47,
}

class MacOSAdapter(BasePlatformAdapter):
    """
    Production-grade macOS Platform Adapter using ApplicationServices AXUIElement
    and Quartz CoreGraphics Event Taps.
    """

    def __init__(self):
        if not HAS_MACOS_DEPS:
            raise RuntimeError(
                "macOS dependencies are missing. Please run:\n"
                "pip install pyobjc-framework-ApplicationServices pyobjc-framework-Quartz pyobjc-framework-Cocoa"
            )

    def check_permissions(self) -> Dict[str, Any]:
        trusted = ApplicationServices.AXIsProcessTrusted()
        return {
            "platform": "darwin",
            "accessibility_trusted": bool(trusted),
            "message": (
                "Accessibility permissions granted."
                if trusted
                else "Accessibility permissions missing! Enable Terminal or your Python process under:\n"
                "System Settings -> Privacy & Security -> Accessibility"
            ),
        }

    def list_applications(self) -> List[Dict[str, Any]]:
        ws = NSWorkspace.sharedWorkspace()
        apps = ws.runningApplications()
        result: List[Dict[str, Any]] = []

        for app in apps:
            # Activation policy 0 == NSApplicationActivationPolicyRegular (standard GUI apps)
            if app.activationPolicy() == 0:
                result.append({
                    "pid": int(app.processIdentifier()),
                    "name": str(app.localizedName() or ""),
                    "bundle_id": str(app.bundleIdentifier() or ""),
                    "is_active": bool(app.isActive()),
                    "is_hidden": bool(app.isHidden()),
                })
        result.sort(key=lambda x: (not x["is_active"], x["name"].lower()))
        return result

    def get_display_scale_factor(self) -> float:
        try:
            screen = NSScreen.mainScreen()
            if screen:
                return float(screen.backingScaleFactor())
        except Exception:
            pass
        return 1.0

    def _resolve_pid(self, app_identifier: str | int) -> int:
        if isinstance(app_identifier, int):
            return app_identifier
        if app_identifier.isdigit():
            return int(app_identifier)

        # Search running GUI apps by localized name or bundle id
        apps = self.list_applications()
        target_clean = app_identifier.strip().lower()

        # 1. Exact match on name
        for app in apps:
            if app["name"].lower() == target_clean:
                return app["pid"]

        # 2. Exact match on bundle id
        for app in apps:
            if app["bundle_id"].lower() == target_clean:
                return app["pid"]

        # 3. Substring match
        for app in apps:
            if target_clean in app["name"].lower() or target_clean in app["bundle_id"].lower():
                return app["pid"]

        raise ProcessLookupError(
            f"Could not find running desktop application matching '{app_identifier}'. "
            f"Available apps: {[a['name'] for a in apps[:8]]}..."
        )

    def _hydrate_electron_accessibility(self, app_ref: Any):
        """
        Forces Chromium/Electron apps (VS Code, Slack, Spotify, Chrome) to hydrate
        their accessibility tree by toggling AXEnhancedUserInterface.
        """
        try:
            ApplicationServices.AXUIElementSetAttributeValue(
                app_ref, "AXEnhancedUserInterface", True
            )
            ApplicationServices.AXUIElementSetAttributeValue(
                app_ref, "AXManualAccessibility", True
            )
        except Exception:
            pass

    def get_root_window(self, app_identifier: str | int) -> DesktopNode:
        pid = self._resolve_pid(app_identifier)
        
        # Ensure target application is active so macOS Accessibility populates the windows list
        try:
            ws = NSWorkspace.sharedWorkspace()
            for app in ws.runningApplications():
                if app.processIdentifier() == pid:
                    if not app.isActive():
                        app.activateWithOptions_(2)  # NSApplicationActivateIgnoringOtherApps
                        for _ in range(10):
                            time.sleep(0.04)
                            if app.isActive():
                                break
                        time.sleep(0.05)
                    break

        except Exception:
            pass

        app_ref = ApplicationServices.AXUIElementCreateApplication(pid)
        self._hydrate_electron_accessibility(app_ref)

        visited_ptrs: Set[int] = set()

        # Query Windows
        err, windows = ApplicationServices.AXUIElementCopyAttributeValue(
            app_ref, ApplicationServices.kAXWindowsAttribute, None
        )

        root_children: List[DesktopNode] = []
        app_title = str(app_identifier)

        # Retrieve app title
        err_t, title_val = ApplicationServices.AXUIElementCopyAttributeValue(
            app_ref, ApplicationServices.kAXTitleAttribute, None
        )
        if err_t == 0 and title_val:
            app_title = str(title_val)

        if err == 0 and windows:
            for win_ref in windows:
                win_node = self._traverse_element(win_ref, visited_ptrs, depth=1, max_depth=12)
                if win_node:
                    root_children.append(win_node)

        # Fallback: if no windows exposed, traverse the application ref itself
        if not root_children:
            app_node = self._traverse_element(app_ref, visited_ptrs, depth=0, max_depth=12)
            if app_node:
                return app_node

        # Compute bounding box covering all child windows
        if root_children:
            min_x = min(c.bbox.x for c in root_children)
            min_y = min(c.bbox.y for c in root_children)
            max_x = max(c.bbox.x + c.bbox.width for c in root_children)
            max_y = max(c.bbox.y + c.bbox.height for c in root_children)
            bbox = BoundingBox(x=min_x, y=min_y, width=max(1, max_x - min_x), height=max(1, max_y - min_y))
        else:
            bbox = BoundingBox(x=0, y=0, width=1920, height=1080)

        return DesktopNode(
            id="app_root",
            role="window",
            name=app_title,
            bbox=bbox,
            states=ElementStates(focusable=True),
            children=root_children,
            raw_role="AXApplication",
            depth=0,
        )

    def get_active_window(self) -> Optional[DesktopNode]:
        system_ref = ApplicationServices.AXUIElementCreateSystemWide()
        err, focused_app = ApplicationServices.AXUIElementCopyAttributeValue(
            system_ref, ApplicationServices.kAXFocusedApplicationAttribute, None
        )
        if err != 0 or not focused_app:
            return None

        err, focused_win = ApplicationServices.AXUIElementCopyAttributeValue(
            focused_app, ApplicationServices.kAXFocusedWindowAttribute, None
        )
        if err != 0 or not focused_win:
            return None

        visited_ptrs: Set[int] = set()
        return self._traverse_element(focused_win, visited_ptrs, depth=0, max_depth=12)

    def _traverse_element(
        self,
        element_ref: Any,
        visited_ptrs: Set[int],
        depth: int,
        max_depth: int = 12,
    ) -> Optional[DesktopNode]:
        if depth > max_depth:
            return None

        # Pointer identity hash for cycle guard
        ptr_hash = hash(element_ref)
        if ptr_hash in visited_ptrs:
            return None
        visited_ptrs.add(ptr_hash)

        # 1. Role
        err, raw_role = ApplicationServices.AXUIElementCopyAttributeValue(
            element_ref, ApplicationServices.kAXRoleAttribute, None
        )
        if err != 0 or not raw_role:
            raw_role = "unknown"
        else:
            raw_role = str(raw_role)

        canonical_role = MACOS_ROLE_MAP.get(raw_role, "group")

        # 2. Name / Label / Description
        name = ""
        for attr in [
            ApplicationServices.kAXTitleAttribute,
            ApplicationServices.kAXDescriptionAttribute,
            ApplicationServices.kAXHelpAttribute,
        ]:
            err_name, val_name = ApplicationServices.AXUIElementCopyAttributeValue(
                element_ref, attr, None
            )
            if err_name == 0 and val_name:
                name = str(val_name).strip()
                if name:
                    break

        # 3. Value
        value = None
        err_val, val_obj = ApplicationServices.AXUIElementCopyAttributeValue(
            element_ref, ApplicationServices.kAXValueAttribute, None
        )
        if err_val == 0 and val_obj is not None:
            # Don't dump complex structural objects as value
            val_str = str(val_obj)
            if "<AXValue" not in val_str and "<AXUIElement" not in val_str:
                value = val_str[:256]

        # 4. Geometry (Position & Size)
        bbox = self._extract_bounds(element_ref)

        # 5. Interactive States
        states = self._extract_states(element_ref, canonical_role)

        # 6. Children
        children: List[DesktopNode] = []
        err_c, child_refs = ApplicationServices.AXUIElementCopyAttributeValue(
            element_ref, ApplicationServices.kAXChildrenAttribute, None
        )
        if err_c == 0 and child_refs:
            for child_ref in child_refs:
                child_node = self._traverse_element(
                    child_ref, visited_ptrs, depth=depth + 1, max_depth=max_depth
                )
                if child_node is not None:
                    children.append(child_node)

        return DesktopNode(
            id="temp",
            role=canonical_role,
            name=name,
            value=value,
            bbox=bbox,
            states=states,
            children=children,
            raw_role=raw_role,
            depth=depth,
        )

    def _extract_bounds(self, element_ref: Any) -> BoundingBox:
        x, y, w, h = 0, 0, 0, 0
        err_pos, pos_val = ApplicationServices.AXUIElementCopyAttributeValue(
            element_ref, ApplicationServices.kAXPositionAttribute, None
        )
        if err_pos == 0 and pos_val:
            ok, pt = ApplicationServices.AXValueGetValue(
                pos_val, ApplicationServices.kAXValueCGPointType, None
            )
            if ok and pt:
                x, y = int(round(pt.x)), int(round(pt.y))

        err_sz, sz_val = ApplicationServices.AXUIElementCopyAttributeValue(
            element_ref, ApplicationServices.kAXSizeAttribute, None
        )
        if err_sz == 0 and sz_val:
            ok, sz = ApplicationServices.AXValueGetValue(
                sz_val, ApplicationServices.kAXValueCGSizeType, None
            )
            if ok and sz:
                w, h = int(round(sz.width)), int(round(sz.height))

        return BoundingBox(x=x, y=y, width=max(0, w), height=max(0, h))

    def _extract_states(self, element_ref: Any, role: str) -> ElementStates:
        focused = False
        focusable = False
        disabled = False
        checked = None

        # Check focus
        err, val = ApplicationServices.AXUIElementCopyAttributeValue(
            element_ref, ApplicationServices.kAXFocusedAttribute, None
        )
        if err == 0 and val is not None:
            focused = bool(val)
            focusable = True

        # Check enabled
        err, val = ApplicationServices.AXUIElementCopyAttributeValue(
            element_ref, ApplicationServices.kAXEnabledAttribute, None
        )
        if err == 0 and val is not None:
            disabled = not bool(val)

        # Check checked state for buttons/radios/checkboxes
        if role in {"checkbox", "radio"}:
            err, val = ApplicationServices.AXUIElementCopyAttributeValue(
                element_ref, ApplicationServices.kAXValueAttribute, None
            )
            if err == 0 and val is not None:
                checked = bool(val == 1 or val is True)

        clickable = role in {"button", "checkbox", "radio", "combobox", "menuitem", "tab", "link"}
        editable = role in {"input"}

        return ElementStates(
            focused=focused,
            focusable=focusable or editable or clickable,
            editable=editable,
            clickable=clickable,
            checked=checked,
            disabled=disabled,
        )

    def click(self, node: DesktopNode, button: Literal["left", "right", "double"] = "left") -> None:
        cx, cy = node.bbox.centroid
        self.click_coords(cx, cy, button=button)

    def click_coords(self, x: int, y: int, button: Literal["left", "right", "double"] = "left") -> None:
        pt = Quartz.CGPoint(x, y)
        btn_type = Quartz.kCGMouseButtonLeft if button in {"left", "double"} else Quartz.kCGMouseButtonRight
        down_type = Quartz.kCGEventLeftMouseDown if button in {"left", "double"} else Quartz.kCGEventRightMouseDown
        up_type = Quartz.kCGEventLeftMouseUp if button in {"left", "double"} else Quartz.kCGEventRightMouseUp

        # 1. Smooth synthetic mouse move
        move = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, pt, btn_type)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, move)
        time.sleep(0.02)

        # 2. Click 1: Mouse down + up
        down = Quartz.CGEventCreateMouseEvent(None, down_type, pt, btn_type)
        up = Quartz.CGEventCreateMouseEvent(None, up_type, pt, btn_type)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
        time.sleep(0.01)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)

        # 3. Double click dispatch
        if button == "double":
            time.sleep(0.05)
            down2 = Quartz.CGEventCreateMouseEvent(None, down_type, pt, btn_type)
            Quartz.CGEventSetIntegerValueField(down2, Quartz.kCGMouseEventClickState, 2)
            up2 = Quartz.CGEventCreateMouseEvent(None, up_type, pt, btn_type)
            Quartz.CGEventSetIntegerValueField(up2, Quartz.kCGMouseEventClickState, 2)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, down2)
            time.sleep(0.01)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, up2)

        time.sleep(0.05)

    def type_text(self, node: Optional[DesktopNode], text: str, clear_first: bool = False) -> None:
        if node is not None:
            self.click(node, button="left")
            time.sleep(0.05)

        if clear_first:
            # Select all (cmd+a) then backspace
            self.press_key("cmd+a")
            time.sleep(0.02)
            self.press_key("backspace")
            time.sleep(0.02)

        # Dispatch string as Quartz unicode keyboard events
        for char in text:
            down = Quartz.CGEventCreateKeyboardEvent(None, 0, True)
            Quartz.CGEventKeyboardSetUnicodeString(down, 1, char)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)

            up = Quartz.CGEventCreateKeyboardEvent(None, 0, False)
            Quartz.CGEventKeyboardSetUnicodeString(up, 1, char)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)
            time.sleep(0.005)

    def press_key(self, key_combination: str) -> None:
        parts = [p.strip().lower() for p in key_combination.split("+")]
        modifiers = 0
        key_name = parts[-1]

        for mod in parts[:-1]:
            if mod in {"cmd", "command"}:
                modifiers |= Quartz.kCGEventFlagMaskCommand
            elif mod in {"shift"}:
                modifiers |= Quartz.kCGEventFlagMaskShift
            elif mod in {"ctrl", "control"}:
                modifiers |= Quartz.kCGEventFlagMaskControl
            elif mod in {"alt", "option"}:
                modifiers |= Quartz.kCGEventFlagMaskAlternate

        keycode = MACOS_KEYCODES.get(key_name)
        if keycode is None:
            # If not in keycode map, fallback to unicode single char
            if len(key_name) == 1:
                down = Quartz.CGEventCreateKeyboardEvent(None, 0, True)
                if modifiers:
                    Quartz.CGEventSetFlags(down, modifiers)
                Quartz.CGEventKeyboardSetUnicodeString(down, 1, key_name)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)

                up = Quartz.CGEventCreateKeyboardEvent(None, 0, False)
                if modifiers:
                    Quartz.CGEventSetFlags(up, modifiers)
                Quartz.CGEventKeyboardSetUnicodeString(up, 1, key_name)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)
                return
            else:
                raise ValueError(f"Unsupported key name: '{key_name}' in combination '{key_combination}'")

        down = Quartz.CGEventCreateKeyboardEvent(None, keycode, True)
        if modifiers:
            Quartz.CGEventSetFlags(down, modifiers)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
        time.sleep(0.01)

        up = Quartz.CGEventCreateKeyboardEvent(None, keycode, False)
        if modifiers:
            Quartz.CGEventSetFlags(up, modifiers)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)
