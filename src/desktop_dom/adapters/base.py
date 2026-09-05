from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional, Literal, Dict, Any
from desktop_dom.schema import DesktopNode, DisplayInfo, BoundingBox, SubregionCapture

class PlatformNotSupportedError(RuntimeError):
    """Raised when an OS adapter is invoked on an incompatible host operating system."""
    pass

class BasePlatformAdapter(ABC):
    """
    Abstract Base Class defining the OS-level contract for accessibility introspection
    and synthetic hardware event dispatch.
    """

    @abstractmethod
    def get_root_window(self, app_identifier: str | int) -> DesktopNode:
        """
        Locates the target application by process name or PID and extracts its raw accessibility tree.
        """
        pass

    @abstractmethod
    def get_active_window(self) -> Optional[DesktopNode]:
        """
        Retrieves the currently focused / frontmost window on the active desktop.
        Crucial for escaping modal focus traps.
        """
        pass

    @abstractmethod
    def list_applications(self) -> List[Dict[str, Any]]:
        """
        Enumerates running GUI applications with metadata (PID, name, bundle_id/path, active window title).
        """
        pass

    @abstractmethod
    def click(self, node: DesktopNode, button: Literal["left", "right", "double"] = "left") -> None:
        """
        Dispatches an OS-level mouse click to the exact centroid of the provided element.
        """
        pass

    @abstractmethod
    def click_coords(self, x: int, y: int, button: Literal["left", "right", "double"] = "left") -> None:
        """
        Dispatches synthetic mouse click directly to desktop coordinates (x, y).
        """
        pass

    @abstractmethod
    def type_text(self, node: Optional[DesktopNode], text: str, clear_first: bool = False) -> None:
        """
        Focuses the element (if provided) and sends native keyboard character events.
        """
        pass

    @abstractmethod
    def press_key(self, key_combination: str) -> None:
        """
        Sends hotkeys, modifier chords, or special keys (e.g. 'cmd+s', 'ctrl+shift+p', 'return', 'tab').
        """
        pass

    @abstractmethod
    def get_display_scale_factor(self) -> float:
        """
        Returns backing scale factor (e.g. 2.0 for Retina, 1.25 for Windows DPI scaling, 1.0 for standard).
        """
        pass

    @abstractmethod
    def check_permissions(self) -> Dict[str, Any]:
        """
        Checks whether the host OS has granted accessibility / event tap rights to the running process.
        """
        pass

    @abstractmethod
    def get_displays(self) -> List[DisplayInfo]:
        """
        Enumerates all attached displays with their global coordinate bounds and scale factors.
        """
        pass

    @abstractmethod
    def is_window_on_active_space(self, app_identifier: str | int) -> bool:
        """
        Determines whether the target application window is present on the currently active virtual space.
        """
        pass

    @abstractmethod
    def capture_subregion(self, bbox: BoundingBox, element_id: Optional[str] = None) -> SubregionCapture:
        """
        Captures a high-resolution subregion image for vision model fallback, returning base64 and token estimates.
        """
        pass
