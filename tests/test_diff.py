import pytest
from desktop_dom.schema import DesktopNode, BoundingBox, ElementStates
from desktop_dom.diff import compute_dom_diff, NodeMutation, DOMDiff, ActionResult, verify_expected_effect
from desktop_dom.app import DesktopApp
from desktop_dom.adapters.base import BasePlatformAdapter

def make_node(node_id: str, role: str = "button", name: str = "Click Me", value: str = "", x: int = 10, y: int = 20, width: int = 100, height: int = 40, focused: bool = False, checked: bool = None, disabled: bool = False) -> DesktopNode:
    return DesktopNode(
        id=node_id,
        role=role,
        name=name,
        value=value or None,
        bbox=BoundingBox(x=x, y=y, width=width, height=height),
        states=ElementStates(focused=focused, checked=checked, disabled=disabled),
        children=[],
    )

def test_empty_diff():
    n1 = make_node("btn_1")
    root1 = DesktopNode(id="root", role="window", name="Win", bbox=BoundingBox(x=0,y=0,width=800,height=600), children=[n1])
    root2 = DesktopNode(id="root", role="window", name="Win", bbox=BoundingBox(x=0,y=0,width=800,height=600), children=[n1])
    
    diff = compute_dom_diff(root1, root2)
    assert not diff.has_changes
    assert len(diff.added_nodes) == 0
    assert len(diff.removed_nodes) == 0
    assert len(diff.mutations) == 0
    assert "stable" in diff.summary

def test_added_and_removed_nodes():
    n1 = make_node("btn_1", name="Save")
    n2 = make_node("btn_2", name="Cancel")
    n3 = make_node("dialog_1", role="dialog", name="Confirm Modal")

    root_before = DesktopNode(id="root", role="window", name="Win", bbox=BoundingBox(x=0,y=0,width=800,height=600), children=[n1, n2])
    root_after = DesktopNode(id="root", role="window", name="Win", bbox=BoundingBox(x=0,y=0,width=800,height=600), children=[n1, n3]) # n2 removed, n3 added

    diff = compute_dom_diff(root_before, root_after)
    assert diff.has_changes
    assert len(diff.added_nodes) == 1
    assert diff.added_nodes[0].id == "dialog_1"
    assert len(diff.removed_nodes) == 1
    assert diff.removed_nodes[0].id == "btn_2"
    assert diff.has_node_added(role="dialog", name_substr="Confirm")
    assert diff.has_node_removed(role="button", name_substr="Cancel")

def test_value_and_state_mutations():
    n_before = make_node("inp_email", role="input", name="Email Input", value="", focused=False)
    n_after = make_node("inp_email", role="input", name="Email Input", value="piyush@example.com", focused=True)

    root_b = DesktopNode(id="root", role="window", name="Win", bbox=BoundingBox(x=0,y=0,width=800,height=600), children=[n_before])
    root_a = DesktopNode(id="root", role="window", name="Win", bbox=BoundingBox(x=0,y=0,width=800,height=600), children=[n_after])

    diff = compute_dom_diff(root_b, root_a)
    assert diff.has_changes
    assert diff.has_value_changed("inp_email")
    assert len(diff.mutations) == 2 # value + states.focused
    
    val_mut = [m for m in diff.mutations if m.attribute == "value"][0]
    assert val_mut.old_value is None
    assert val_mut.new_value == "piyush@example.com"

def test_bbox_mutation_detection():
    n_b = make_node("btn_move", x=100, y=100)
    n_a = make_node("btn_move", x=150, y=100) # shifted 50px right

    root_b = DesktopNode(id="root", role="window", name="Win", bbox=BoundingBox(x=0,y=0,width=800,height=600), children=[n_b])
    root_a = DesktopNode(id="root", role="window", name="Win", bbox=BoundingBox(x=0,y=0,width=800,height=600), children=[n_a])

    diff = compute_dom_diff(root_b, root_a)
    assert diff.has_changes
    bbox_muts = [m for m in diff.mutations if m.attribute == "bbox"]
    assert len(bbox_muts) == 1
    assert bbox_muts[0].node_id == "btn_move"

def test_verify_expected_effects():
    diff = DOMDiff(
        added_nodes=[make_node("dlg_1", role="dialog", name="Settings")],
        removed_nodes=[make_node("toast_1", role="group", name="Notification")],
        mutations=[
            NodeMutation(node_id="inp_1", role="input", name="Search", attribute="value", old_value="", new_value="Quarterly"),
            NodeMutation(node_id="btn_submit", role="button", name="Submit", attribute="states.disabled", old_value=True, new_value=False),
        ]
    )

    # Any change
    ok, _ = verify_expected_effect(diff, {"type": "any_change"})
    assert ok

    # Node added
    ok, _ = verify_expected_effect(diff, {"type": "node_added", "role": "dialog"})
    assert ok
    ok, _ = verify_expected_effect(diff, {"type": "node_added", "role": "table"})
    assert not ok

    # Node removed
    ok, _ = verify_expected_effect(diff, {"type": "node_removed", "id": "toast_1"})
    assert ok
    ok, _ = verify_expected_effect(diff, {"type": "node_removed", "id": "dlg_1"})
    assert not ok

    # Value changed
    ok, _ = verify_expected_effect(diff, {"type": "value_changed", "id": "inp_1"})
    assert ok
    ok, _ = verify_expected_effect(diff, {"type": "value_changed", "id": "unknown"})
    assert not ok

    # State changed
    ok, _ = verify_expected_effect(diff, {"type": "state_changed", "id": "btn_submit", "attribute": "states.disabled", "value": False})
    assert ok

def test_app_execute_and_verify():
    from tests.conftest import TestPlatformAdapter
    class DynamicAdapter(TestPlatformAdapter):
        def type_text(self, node, text, clear_first=False):
            super().type_text(node, text, clear_first)
            for n in self._tree.flatten():
                if n.role == 'input':
                    n.value = text

    adapter = DynamicAdapter()
    app = DesktopApp(target='Calculator', adapter=adapter)
    inp = app.find(role='input')
    assert inp is not None

    res = app.execute_and_verify(
        action_fn=lambda: app.type(inp.id, '42 * 2'),
        expected_effect={'type': 'value_changed', 'id': inp.id},
        settle_delay=0.01,
    )

    assert res.status == 'success'
    assert res.verified
    assert res.diff.has_value_changed(inp.id)
