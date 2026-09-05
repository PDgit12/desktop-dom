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
