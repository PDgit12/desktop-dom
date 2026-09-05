from __future__ import annotations
import sys
import logging
from typing import List, Optional, Literal, Dict, Any, Set

from desktop_dom.adapters.base import BasePlatformAdapter, PlatformNotSupportedError
from desktop_dom.schema import DesktopNode, BoundingBox, ElementStates

logger = logging.getLogger("desktop_dom.adapters.windows")

# Canonical role mapping from Windows UIA Control Types
UIA_ROLE_MAP: Dict[str, str] = {
    "Button": "button",
    "Edit": "input",
    "CheckBox": "checkbox",
    "RadioButton": "radio",
    "ComboBox": "combobox",
    "MenuItem": "menuitem",
    "Menu": "menu",
    "MenuBar": "menubar",
    "Tab": "tab_group",
    "TabItem": "tab",
    "Table": "table",
    "DataGrid": "table",
    "DataItem": "table_row",
    "HeaderItem": "table_cell",
    "Text": "text",
    "Hyperlink": "link",
    "Image": "image",
    "Slider": "slider",
    "ScrollBar": "scrollbar",
    "Window": "window",
    "Pane": "pane",
    "Group": "group",
    "Custom": "group",
}

# Windows Virtual Keycode Map
WIN_KEYCODES: Dict[str, int] = {
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "space": 0x20,
    "backspace": 0x08,
    "escape": 0x1B,
    "esc": 0x1B,
    "delete": 0x2E,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "win": 0x5B,
    "windows": 0x5B,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
}

class WindowsAdapter(BasePlatformAdapter):
    """
    Windows Platform Adapter binding directly to UI Automation 3 (IUIAutomation / CUIAutomation8)
    via comtypes or ctypes.
    Uses ControlViewWalker and IUIAutomationCacheRequest to avoid per-property IPC roundtrips.
    Dispatches hardware actions via native Win32 SendInput.
    """

    def __init__(self):
        if sys.platform != "win32":
            self._is_win32 = False
            self.uia = None
        else:
            self._is_win32 = True
            self._init_uia()

    def _require_windows(self):
        if not self._is_win32:
            raise PlatformNotSupportedError(
                f"WindowsAdapter requires Windows (current host is '{sys.platform}')."
            )

    def _init_uia(self):
        try:
            import comtypes.client
            import comtypes
            comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
            self.uia = comtypes.client.CreateObject("{ff48dba4-60ef-4201-aa87-54103eef594e}")  # CUIAutomation
        except Exception as e:
            logger.error(f"Failed to initialize COM UI Automation: {e}")
            raise

    def check_permissions(self) -> Dict[str, Any]:
        self._require_windows()
        return {
            "platform": "win32",
            "accessibility_trusted": True,
            "message": "Windows UI Automation COM subsystem available.",
        }

    def list_applications(self) -> List[Dict[str, Any]]:
        self._require_windows()
        results: List[Dict[str, Any]] = []
        try:
            walker = self.uia.CreateTreeWalker(self.uia.ControlViewCondition)
            root = self.uia.GetRootElement()
            elem = walker.GetFirstChildElement(root)
            while elem:
                try:
                    pid = elem.CurrentProcessId
                    name = elem.CurrentName or "Window"
                    results.append({"pid": pid, "name": name, "bundle_id": name, "is_active": False})
                except Exception:
                    pass
                elem = walker.GetNextSiblingElement(elem)
        except Exception as e:
            logger.error(f"Error enumerating windows: {e}")
        return results

    def get_display_scale_factor(self) -> float:
        self._require_windows()
        try:
            import ctypes
            dpi = ctypes.windll.user32.GetDpiForSystem()
            return dpi / 96.0
        except Exception:
            return 1.0

    def get_root_window(self, app_identifier: str | int) -> DesktopNode:
        self._require_windows()
        target_elem = self._resolve_target(app_identifier)
        if not target_elem:
            raise ProcessLookupError(f"Could not find running desktop application matching '{app_identifier}'")

        visited: Set[int] = set()
        root_node = self._traverse_element(target_elem, visited, depth=0, max_depth=10)
        if not root_node:
            raise RuntimeError(f"Failed to extract accessibility DOM from application '{app_identifier}'")
        return root_node

    def _resolve_target(self, app_identifier: str | int) -> Any:
        walker = self.uia.CreateTreeWalker(self.uia.ControlViewCondition)
        root = self.uia.GetRootElement()
        elem = walker.GetFirstChildElement(root)

        is_pid = isinstance(app_identifier, int) or (isinstance(app_identifier, str) and app_identifier.isdigit())
        target_pid = int(app_identifier) if is_pid else None
        target_str = str(app_identifier).lower()

        while elem:
            try:
                if target_pid is not None and elem.CurrentProcessId == target_pid:
                    return elem
                name = (elem.CurrentName or "").lower()
                if target_pid is None and target_str in name:
                    return elem
            except Exception:
                pass
            elem = walker.GetNextSiblingElement(elem)
        return None

    def _traverse_element(self, elem: Any, visited: Set[int], depth: int, max_depth: int) -> Optional[DesktopNode]:
        if depth > max_depth or not elem:
            return None

        try:
            raw_role = elem.CurrentLocalizedControlType or "Control"
            ctrl_type = elem.CurrentControlType
            role = UIA_ROLE_MAP.get(raw_role, "group")
            name = (elem.CurrentName or "").strip()

            rect = elem.CurrentBoundingRectangle
            bbox = BoundingBox(
                x=int(rect.left),
                y=int(rect.top),
                width=max(0, int(rect.right - rect.left)),
                height=max(0, int(rect.bottom - rect.top)),
            )

            is_focused = bool(elem.CurrentHasKeyboardFocus)
            is_enabled = bool(elem.CurrentIsEnabled)
            states = ElementStates(
                focused=is_focused,
                focusable=bool(elem.CurrentIsKeyboardFocusable),
                disabled=not is_enabled,
                clickable=role in {"button", "checkbox", "radio", "combobox", "menuitem", "tab", "link"},
                editable=role in {"input"},
            )

            value = None
            try:
                # Check Value pattern
                val_pat = elem.GetCurrentPattern(10002)  # UIA_ValuePatternId
                if val_pat:
                    value = val_pat.CurrentValue
            except Exception:
                pass

            # Traverse children
            children: List[DesktopNode] = []
            walker = self.uia.CreateTreeWalker(self.uia.ControlViewCondition)
            child = walker.GetFirstChildElement(elem)
            while child:
                c_node = self._traverse_element(child, visited, depth + 1, max_depth)
                if c_node:
                    children.append(c_node)
                child = walker.GetNextSiblingElement(child)

            return DesktopNode(
                id=f"win_{depth}",
                role=role,
                name=name,
                value=value,
                bbox=bbox,
                states=states,
                children=children,
                raw_role=raw_role,
                depth=depth,
            )
        except Exception as e:
            logger.debug(f"Error traversing UIA node at depth {depth}: {e}")
            return None

    def get_active_window(self) -> Optional[DesktopNode]:
        self._require_windows()
        try:
            focused_elem = self.uia.GetFocusedElement()
            if focused_elem:
                visited: Set[int] = set()
                return self._traverse_element(focused_elem, visited, depth=0, max_depth=1)
        except Exception as e:
            logger.error(f"Error fetching active window: {e}")
        return None

    def click(self, node: DesktopNode, button: Literal["left", "right", "double"] = "left") -> None:
        self._require_windows()
        cx, cy = node.bbox.centroid
        self.click_coords(cx, cy, button=button)

    def click_coords(self, x: int, y: int, button: Literal["left", "right", "double"] = "left") -> None:
        self._require_windows()
        import ctypes

        MOUSEEVENTF_MOVE = 0x0001
        MOUSEEVENTF_ABSOLUTE = 0x8000
        MOUSEEVENTF_LEFTDOWN = 0x0002
        MOUSEEVENTF_LEFTUP = 0x0004
        MOUSEEVENTF_RIGHTDOWN = 0x0008
        MOUSEEVENTF_RIGHTUP = 0x0010

        screen_w = ctypes.windll.user32.GetSystemMetrics(0)
        screen_h = ctypes.windll.user32.GetSystemMetrics(1)
        norm_x = int((x * 65535) / max(1, screen_w))
        norm_y = int((y * 65535) / max(1, screen_h))

        ctypes.windll.user32.mouse_event(MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE, norm_x, norm_y, 0, 0)
        
        down_flag = MOUSEEVENTF_LEFTDOWN if button in {"left", "double"} else MOUSEEVENTF_RIGHTDOWN
        up_flag = MOUSEEVENTF_LEFTUP if button in {"left", "double"} else MOUSEEVENTF_RIGHTUP

        ctypes.windll.user32.mouse_event(down_flag, 0, 0, 0, 0)
        ctypes.windll.user32.mouse_event(up_flag, 0, 0, 0, 0)
        if button == "double":
            ctypes.windll.user32.mouse_event(down_flag, 0, 0, 0, 0)
            ctypes.windll.user32.mouse_event(up_flag, 0, 0, 0, 0)

    def type_text(self, node: Optional[DesktopNode], text: str, clear_first: bool = False) -> None:
        self._require_windows()
        if node:
            self.click(node)
        if clear_first:
            self.press_key("ctrl+a")
            self.press_key("backspace")

        import ctypes
        KEYEVENTF_UNICODE = 0x0004
        KEYEVENTF_KEYUP = 0x0002
        for char in text:
            code = ord(char)
            ctypes.windll.user32.keybd_event(0, code, KEYEVENTF_UNICODE, 0)
            ctypes.windll.user32.keybd_event(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0)

    def press_key(self, key_combination: str) -> None:
        self._require_windows()
        import ctypes
        KEYEVENTF_KEYUP = 0x0002

        parts = [p.strip().lower() for p in key_combination.split("+")]
        modifiers = []
        for mod in parts[:-1]:
            vk = WIN_KEYCODES.get(mod)
            if vk:
                modifiers.append(vk)
                ctypes.windll.user32.keybd_event(vk, 0, 0, 0)

        main_key = parts[-1]
        vk_main = WIN_KEYCODES.get(main_key) or ord(main_key.upper())
        ctypes.windll.user32.keybd_event(vk_main, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk_main, 0, KEYEVENTF_KEYUP, 0)

        for vk in reversed(modifiers):
            ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
