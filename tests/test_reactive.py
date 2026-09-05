import pytest
import time
import threading
from desktop_dom.app import DesktopApp
from desktop_dom.schema import DesktopNode, BoundingBox, ElementStates
from tests.conftest import TestPlatformAdapter

def test_wait_for_existing_element():
    adapter = TestPlatformAdapter()
    app = DesktopApp.attach("Calculator", adapter=adapter)

    # Should find immediately
    node = app.wait_for(role="button", name="Clear", timeout=1.0)
    assert node.role == "button"
    assert node.name == "Clear"

def test_wait_for_delayed_element():
    adapter = TestPlatformAdapter()
    app = DesktopApp.attach("Calculator", adapter=adapter)

    # Simulate dynamic popup button appearing after 0.2 seconds
    def add_delayed_node():
        time.sleep(0.2)
        new_btn = DesktopNode(
            id="btn_popup_save",
            role="button",
            name="Save Confirmation",
            bbox=BoundingBox(x=150, y=200, width=100, height=40),
            states=ElementStates(clickable=True, focusable=True),
        )
        adapter._tree.children.append(new_btn)

    threading.Thread(target=add_delayed_node, daemon=True).start()

    node = app.wait_for(role="button", name="Save Confirmation", timeout=2.0, poll_interval=0.05)
    assert node is not None
    assert node.name == "Save Confirmation"

def test_wait_for_timeout():
    adapter = TestPlatformAdapter()
    app = DesktopApp.attach("Calculator", adapter=adapter)

    with pytest.raises(TimeoutError) as exc_info:
        app.wait_for(role="button", name="NonExistentButton", timeout=0.3, poll_interval=0.05)

    assert "Timed out after 0.3s" in str(exc_info.value)

def test_wait_until_hidden():
    adapter = TestPlatformAdapter()
    app = DesktopApp.attach("Calculator", adapter=adapter)

    # Remove the display node after 0.2s
    def remove_node():
        time.sleep(0.2)
        # Remove display group
        adapter._tree.children = [c for c in adapter._tree.children if c.name != "Display Group"]

    threading.Thread(target=remove_node, daemon=True).start()

    hidden = app.wait_until_hidden(name="Display Result", timeout=2.0, poll_interval=0.05)
    assert hidden is True

def test_observe_mutations():
    adapter = TestPlatformAdapter()
    app = DesktopApp.attach("Calculator", adapter=adapter)

    def trigger_mutations():
        time.sleep(0.1)
        # 1. Modify value of display text
        display_txt = adapter._tree.children[0].children[0]
        display_txt.value = "100"

        time.sleep(0.1)
        # 2. Add a new banner node
        banner = DesktopNode(
            id="banner_ready",
            role="text",
            name="Status Ready",
            value="OK",
            bbox=BoundingBox(x=120, y=120, width=200, height=30),
        )
        adapter._tree.children.append(banner)

    threading.Thread(target=trigger_mutations, daemon=True).start()

    events = app.observe(duration=0.5, poll_interval=0.05)
    event_types = [e["type"] for e in events]
    assert "value_changed" in event_types
    assert "node_added" in event_types
