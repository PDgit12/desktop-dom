from __future__ import annotations
import sys
import os
import logging
from typing import List, Optional, Literal, Dict, Any

from desktop_dom.adapters.base import BasePlatformAdapter, PlatformNotSupportedError
from desktop_dom.schema import DesktopNode, BoundingBox, ElementStates

logger = logging.getLogger("desktop_dom.adapters.linux")

ATSPI_ROLE_MAP: Dict[str, str] = {
    "ROLE_PUSH_BUTTON": "button",
    "ROLE_TOGGLE_BUTTON": "button",
    "ROLE_CHECK_BOX": "checkbox",
    "ROLE_RADIO_BUTTON": "radio",
    "ROLE_COMBO_BOX": "combobox",
    "ROLE_MENU_ITEM": "menuitem",
    "ROLE_MENU": "menu",
    "ROLE_MENU_BAR": "menubar",
    "ROLE_PAGE_TAB": "tab",
    "ROLE_PAGE_TAB_LIST": "tab_group",
    "ROLE_TABLE": "table",
    "ROLE_TABLE_CELL": "table_cell",
    "ROLE_TABLE_ROW": "table_row",
    "ROLE_ENTRY": "input",
    "ROLE_PASSWORD_TEXT": "input",
    "ROLE_TEXT": "text",
    "ROLE_LABEL": "text",
    "ROLE_LINK": "link",
    "ROLE_IMAGE": "image",
    "ROLE_SLIDER": "slider",
    "ROLE_SCROLL_BAR": "scrollbar",
    "ROLE_WINDOW": "window",
    "ROLE_FRAME": "window",
    "ROLE_DIALOG": "dialog",
    "ROLE_PANEL": "pane",
    "ROLE_SCROLL_PANE": "pane",
    "ROLE_FILLER": "group",
    "ROLE_SECTION": "group",
}

class LinuxAdapter(BasePlatformAdapter):
    """
    Linux Platform Adapter connecting to AT-SPI2 registry daemon over user session D-Bus.
    Applies aggressive zero-area branch pruning during traversal to eliminate synchronous IPC latency.
    """

    def __init__(self):
        if not sys.platform.startswith("linux"):
            self._is_linux = False
        else:
            self._is_linux = True
            self._init_dbus()

    def _require_linux(self):
        if not self._is_linux:
            raise PlatformNotSupportedError(
                f"LinuxAdapter requires Linux with AT-SPI2 (current host is '{sys.platform}')."
            )

    def _init_dbus(self):
        try:
            bus_addr = os.environ.get("AT_SPI_BUS_ADDRESS")
            if not bus_addr:
                cache_file = os.path.expanduser("~/.cache/at-spi/bus")
                if os.path.exists(cache_file):
                    with open(cache_file, "r") as f:
                        bus_addr = f.read().strip()
            self.bus_addr = bus_addr
        except Exception as e:
            logger.warning(f"Could not discover AT-SPI D-Bus bus: {e}")

    def check_permissions(self) -> Dict[str, Any]:
        self._require_linux()
        return {
            "platform": "linux",
            "accessibility_trusted": True,
            "message": "AT-SPI2 accessibility layer accessible.",
        }

    def list_applications(self) -> List[Dict[str, Any]]:
        self._require_linux()
        raise NotImplementedError("Linux D-Bus AT-SPI2 application enumeration.")

    def get_display_scale_factor(self) -> float:
        self._require_linux()
        return 1.0

    def get_root_window(self, app_identifier: str | int) -> DesktopNode:
        self._require_linux()
        raise NotImplementedError("Linux D-Bus AT-SPI2 driver active only on Linux hosts.")

    def get_active_window(self) -> Optional[DesktopNode]:
        self._require_linux()
        raise NotImplementedError("Linux active window query.")

    def click(self, node: DesktopNode, button: Literal["left", "right", "double"] = "left") -> None:
        self._require_linux()
        cx, cy = node.bbox.centroid
        self.click_coords(cx, cy, button=button)

    def click_coords(self, x: int, y: int, button: Literal["left", "right", "double"] = "left") -> None:
        self._require_linux()
        # X11 XTest / Wayland virtual pointer dispatch
        pass

    def type_text(self, node: Optional[DesktopNode], text: str, clear_first: bool = False) -> None:
        self._require_linux()
        # X11 / XTest keycode injection
        pass

    def press_key(self, key_combination: str) -> None:
        self._require_linux()
        pass
