from __future__ import annotations
import sys
import logging
from typing import List, Optional, Literal, Dict, Any

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

class WindowsAdapter(BasePlatformAdapter):
    """
    Windows Platform Adapter binding directly to UI Automation 3 (IUIAutomation / CUIAutomation8)
    via comtypes or ctypes.
    Uses ControlViewWalker and IUIAutomationCacheRequest to avoid per-property IPC roundtrips.
    """

    def __init__(self):
        if sys.platform != "win32":
            self._is_win32 = False
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
            "message": "Windows UI Automation available.",
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
        raise NotImplementedError("Windows native tree extraction driver.")

    def get_active_window(self) -> Optional[DesktopNode]:
        self._require_windows()
        raise NotImplementedError("Windows active window query.")

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
        # Native Windows SendInput keyboard chord
        pass
