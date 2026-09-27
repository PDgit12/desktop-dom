import sys
import pytest
from desktop_dom.adapters.base import PlatformNotSupportedError
from desktop_dom.adapters.macos import MacOSAdapter
from desktop_dom.adapters.windows import WindowsAdapter
from desktop_dom.adapters.linux import LinuxAdapter
from desktop_dom.adapters import get_platform_adapter
from desktop_dom.assistant.non_binary import get_calendar_briefing, get_last_email


def test_windows_adapter_graceful_degradation_on_non_windows():
    """Verify WindowsAdapter fails gracefully with informative error when not on Windows."""
    if sys.platform != "win32":
        w = WindowsAdapter()
        with pytest.raises(PlatformNotSupportedError) as exc_info:
            w.check_permissions()
        assert "WindowsAdapter requires Windows" in str(exc_info.value)
        assert f"'{sys.platform}'" in str(exc_info.value)


def test_linux_adapter_graceful_degradation_on_non_linux():
    """Verify LinuxAdapter fails gracefully with informative error when not on Linux."""
    if not sys.platform.startswith("linux"):
        l = LinuxAdapter()
        with pytest.raises(PlatformNotSupportedError) as exc_info:
            l.check_permissions()
        assert "LinuxAdapter requires Linux" in str(exc_info.value)
        assert f"'{sys.platform}'" in str(exc_info.value)


def test_macos_adapter_graceful_degradation_on_non_macos(monkeypatch):
    """Verify MacOSAdapter fails gracefully with informative error when not on macOS."""
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(PlatformNotSupportedError) as exc_info:
        MacOSAdapter()
    assert "MacOSAdapter requires macOS Darwin" in str(exc_info.value)
    assert "'linux'" in str(exc_info.value)


def test_get_platform_adapter_unsupported_os(monkeypatch):
    """Verify factory raises PlatformNotSupportedError for unknown platforms."""
    import desktop_dom.adapters as adapters_mod
    monkeypatch.setattr(adapters_mod, "_ADAPTER_INSTANCE", None)
    monkeypatch.setattr(sys, "platform", "solaris")
    with pytest.raises(PlatformNotSupportedError) as exc_info:
        get_platform_adapter()
    assert "Operating system 'solaris' is not supported" in str(exc_info.value)


def test_non_binary_macos_commands_graceful_degradation(monkeypatch):
    """Verify macOS-specific assistant commands return clean error dicts rather than crashing on other OSes."""
    monkeypatch.setattr(sys, "platform", "linux")
    res_cal = get_calendar_briefing(calendar_client="Calendar")
    assert res_cal["status"] == "error"
    assert "macOS" in res_cal["message"] or "macOS" in res_cal.get("response", "")

    res_mail = get_last_email(contact_name="Josh", app="Outlook")
    assert res_mail["status"] == "error"
    assert "macOS" in res_mail["message"] or "macOS" in res_mail.get("response", "")
