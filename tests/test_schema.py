import pytest
from desktop_dom.schema import BoundingBox, ElementStates, DesktopNode

def test_bounding_box_calculations():
    bbox = BoundingBox(x=100, y=200, width=50, height=80)
    assert bbox.centroid_x == 125
    assert bbox.centroid_y == 240
    assert bbox.centroid == (125, 240)
    assert bbox.area == 4000
    assert bbox.contains(120, 250) is True
    assert bbox.contains(50, 50) is False

def test_bounding_box_scaling():
    bbox = BoundingBox(x=10, y=20, width=100, height=50)
    scaled = bbox.scale(2.0)
    assert scaled.x == 20
    assert scaled.y == 40
    assert scaled.width == 200
    assert scaled.height == 100
    assert scaled.centroid == (120, 90)

def test_element_states():
    states = ElementStates(clickable=True, focusable=True)
    assert states.is_actionable is True

    disabled_states = ElementStates(clickable=True, disabled=True)
    assert disabled_states.is_actionable is False

    passive_states = ElementStates()
    assert passive_states.is_actionable is False

def test_desktop_node_serialization():
    node = DesktopNode(
        id="btn_submit_4a2c",
        role="button",
        name="Submit Form",
        value=None,
        bbox=BoundingBox(x=100, y=100, width=80, height=30),
        states=ElementStates(clickable=True, focusable=True),
        children=[],
    )

    t_dict = node.to_token_dict(include_children=False)
    assert t_dict["id"] == "btn_submit_4a2c"
    assert t_dict["role"] == "button"
    assert t_dict["name"] == "Submit Form"
    assert "value" not in t_dict  # Pruned None
    assert t_dict["bbox"] == [100, 100, 80, 30]

def test_desktop_node_traversal():
    child = DesktopNode(
        id="btn_nested",
        role="button",
        name="Nested",
        bbox=BoundingBox(x=10, y=10, width=10, height=10),
    )
    parent = DesktopNode(
        id="win_root",
        role="window",
        name="Root",
        bbox=BoundingBox(x=0, y=0, width=100, height=100),
        children=[child],
    )

    assert parent.total_count() == 2
    assert parent.find_by_id("btn_nested") == child
    assert parent.find_by_id("non_existent") is None
    assert len(parent.find_all(role="button")) == 1
    assert len(parent.find_all(name="nested")) == 1
