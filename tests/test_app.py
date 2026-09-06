import pytest
from desktop_dom.app import DesktopApp
from tests.conftest import TestPlatformAdapter

def test_app_get_tree():
    adapter = TestPlatformAdapter()
    app = DesktopApp.attach("Calculator", adapter=adapter)

    tree = app.get_tree(as_dict=True)
    assert tree["role"] == "window"
    # Find child buttons
    button_ids = [c["id"] for c in tree["children"][1]["children"] if c["role"] == "button"]
    assert any(b_id.startswith("btn_clear_") for b_id in button_ids)
    assert any(b_id.startswith("btn_divide_") for b_id in button_ids)

def test_app_click_dispatch():
    adapter = TestPlatformAdapter()
    app = DesktopApp.attach("Calculator", adapter=adapter)
    tree = app.get_tree()

    # Find the clear button ID from the generated tree
    clear_btn_id = [c["id"] for c in tree["children"][1]["children"] if "clear" in c["id"]][0]

    res = app.click(clear_btn_id)
    assert res["status"] == "success"
    assert res["element_id"] == clear_btn_id
    assert len(adapter.dispatched_clicks) == 1
    # Check centroid was clicked: bbox x=110, y=230, w=70, h=60 -> cx=145, cy=260
    assert adapter.dispatched_clicks[0]["x"] == 145
    assert adapter.dispatched_clicks[0]["y"] == 260

def test_app_type_dispatch():
    adapter = TestPlatformAdapter()
    app = DesktopApp.attach("Calculator", adapter=adapter)
    tree = app.get_tree()

    # Find formula bar input ID
    input_id = [c["id"] for c in tree["children"][1]["children"] if c["role"] == "input"][0]

    res = app.type(input_id, text="123", clear_first=True)
    assert res["status"] == "success"
    assert len(adapter.dispatched_types) == 1
    assert adapter.dispatched_types[0]["text"] == "123"
    assert adapter.dispatched_types[0]["clear_first"] is True

def test_app_press_dispatch():
    adapter = TestPlatformAdapter()
    app = DesktopApp.attach("Calculator", adapter=adapter)

    res = app.press("cmd+s")
    assert res["status"] == "success"
    assert adapter.dispatched_keys == ["cmd+s"]

def test_app_find():
    adapter = TestPlatformAdapter()
    app = DesktopApp.attach("Calculator", adapter=adapter)

    btn = app.find(role="button", name="Divide")
    assert btn is not None
    assert btn.id.startswith("btn_divide_")

    all_buttons = app.find_all(role="button")
    assert len(all_buttons) == 4

def test_app_stale_id_recovery():
    adapter = TestPlatformAdapter()
    app = DesktopApp.attach("Calculator", adapter=adapter)
    app.get_tree()

    # Pass an un-hashed name slug (e.g. from an older context turn: "btn_clear")
    # Fuzzy recovery should resolve it to btn_clear_ee89 without throwing KeyError!
    res = app.click("btn_clear")
    assert res["status"] == "success"
    assert res["element_id"].startswith("btn_clear_")

def test_chromium_accessibility_hydration():
    from unittest.mock import MagicMock, patch
    from desktop_dom.adapters.macos import MacOSAdapter

    adapter = MacOSAdapter.__new__(MacOSAdapter)
    mock_app_ref = MagicMock()

    with patch("desktop_dom.adapters.macos.ApplicationServices.AXUIElementSetAttributeValue") as mock_set:
        adapter._hydrate_electron_accessibility(mock_app_ref)
        assert mock_set.call_count == 2
        calls = [c[0] for c in mock_set.call_args_list]
        assert calls[0] == (mock_app_ref, "AXEnhancedUserInterface", True)
        assert calls[1] == (mock_app_ref, "AXManualAccessibility", True)

def test_chromium_accessibility_hydration_resilience():
    from unittest.mock import MagicMock, patch
    from desktop_dom.adapters.macos import MacOSAdapter

    adapter = MacOSAdapter.__new__(MacOSAdapter)
    mock_app_ref = MagicMock()

    with patch("desktop_dom.adapters.macos.ApplicationServices.AXUIElementSetAttributeValue", side_effect=RuntimeError("AX error")):
        # Must catch exception and continue without failing
        adapter._hydrate_electron_accessibility(mock_app_ref)

def test_app_as_tools(test_adapter):
    app = DesktopApp.attach("Calculator", adapter=test_adapter)
    tools = app.as_tools()
    assert len(tools) == 4
    tool_names = [t.name if hasattr(t, "name") else t["function"]["name"] for t in tools]
    assert "desktop_get_screen_dom" in tool_names
    assert "desktop_click_element" in tool_names
    assert "desktop_type_text" in tool_names
    assert "desktop_press_key" in tool_names

def test_macos_adapter_cursor_free_direct_press():
    from unittest.mock import MagicMock, patch
    from desktop_dom.adapters.macos import MacOSAdapter
    from desktop_dom.schema import DesktopNode, BoundingBox

    adapter = MacOSAdapter.__new__(MacOSAdapter)
    node = DesktopNode(
        id="btn_1",
        role="button",
        name="Submit",
        bbox=BoundingBox(x=100, y=200, width=80, height=30)
    )

    mock_elem = MagicMock()
    with patch("desktop_dom.adapters.macos.ApplicationServices.AXUIElementCreateSystemWide") as mock_sys, \
         patch("desktop_dom.adapters.macos.ApplicationServices.AXUIElementCopyElementAtPosition", return_value=(0, mock_elem)), \
         patch("desktop_dom.adapters.macos.ApplicationServices.AXUIElementCopyActionNames", return_value=(0, ["AXPress"])), \
         patch("desktop_dom.adapters.macos.ApplicationServices.AXUIElementPerformAction", return_value=0) as mock_perform, \
         patch("desktop_dom.adapters.macos.Quartz.CGEventPost") as mock_post:

        adapter.click(node, button="left", cursor_free=True)
        # Direct action performed with ZERO synthetic mouse events posted
        mock_perform.assert_called_once_with(mock_elem, "AXPress")
        mock_post.assert_not_called()

def test_macos_adapter_ghost_click_restore():
    from unittest.mock import MagicMock, patch
    from desktop_dom.adapters.macos import MacOSAdapter

    adapter = MacOSAdapter.__new__(MacOSAdapter)
    mock_cur_pos = MagicMock(x=500.0, y=500.0)

    with patch("desktop_dom.adapters.macos.Quartz.CGEventCreate", return_value=MagicMock()), \
         patch("desktop_dom.adapters.macos.Quartz.CGEventGetLocation", return_value=mock_cur_pos), \
         patch("desktop_dom.adapters.macos.Quartz.CGEventCreateMouseEvent", return_value=MagicMock()), \
         patch("desktop_dom.adapters.macos.Quartz.CGEventPost"), \
         patch("desktop_dom.adapters.macos.Quartz.CGWarpMouseCursorPosition") as mock_warp:

        adapter.click_coords(200, 300, button="left", restore_cursor=True)
        # Mouse cursor restored to original user position
        mock_warp.assert_called_once_with(mock_cur_pos)

def test_macos_adapter_cursor_free_direct_value():
    from unittest.mock import MagicMock, patch
    from desktop_dom.adapters.macos import MacOSAdapter
    from desktop_dom.schema import DesktopNode, BoundingBox

    adapter = MacOSAdapter.__new__(MacOSAdapter)
    node = DesktopNode(
        id="inp_1",
        role="input",
        name="Search",
        bbox=BoundingBox(x=100, y=200, width=200, height=30)
    )

    mock_elem = MagicMock()
    with patch("desktop_dom.adapters.macos.ApplicationServices.AXUIElementCreateSystemWide"), \
         patch("desktop_dom.adapters.macos.ApplicationServices.AXUIElementCopyElementAtPosition", return_value=(0, mock_elem)), \
         patch("desktop_dom.adapters.macos.ApplicationServices.AXUIElementIsAttributeSettable", return_value=(0, True)), \
         patch("desktop_dom.adapters.macos.ApplicationServices.AXUIElementSetAttributeValue", return_value=0) as mock_set_val, \
         patch("desktop_dom.adapters.macos.Quartz.CGEventPost") as mock_post:

        adapter.type_text(node, "hello world", cursor_free=True)
        # Direct value set without keyboard focus theft
        mock_set_val.assert_called_once_with(mock_elem, "AXValue", "hello world")
        mock_post.assert_not_called()



