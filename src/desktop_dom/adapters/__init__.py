from __future__ import annotations
import sys
import logging
from desktop_dom.adapters.base import BasePlatformAdapter, PlatformNotSupportedError

logger = logging.getLogger("desktop_dom.adapters")

_ADAPTER_INSTANCE: BasePlatformAdapter | None = None

def get_platform_adapter() -> BasePlatformAdapter:
    """
    Factory resolving the appropriate OS adapter at runtime.
    Raises PlatformNotSupportedError if the current OS is unsupported or required native drivers fail.
    """
    global _ADAPTER_INSTANCE

    if _ADAPTER_INSTANCE is not None:
        return _ADAPTER_INSTANCE

    system = sys.platform
    if system == "darwin":
        from desktop_dom.adapters.macos import MacOSAdapter
        _ADAPTER_INSTANCE = MacOSAdapter()
        return _ADAPTER_INSTANCE

    elif system == "win32":
        from desktop_dom.adapters.windows import WindowsAdapter
        _ADAPTER_INSTANCE = WindowsAdapter()
        return _ADAPTER_INSTANCE

    elif system.startswith("linux"):
        from desktop_dom.adapters.linux import LinuxAdapter
        _ADAPTER_INSTANCE = LinuxAdapter()
        return _ADAPTER_INSTANCE

    raise PlatformNotSupportedError(f"Operating system '{system}' is not supported by desktop-dom.")
