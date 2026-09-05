import pytest
from desktop_dom.schema import DesktopNode, BoundingBox, ElementStates
from desktop_dom.pruner import TreePruner

def test_prune_zero_area_nodes():
    pruner = TreePruner(min_width=1, min_height=1)
    
    root = DesktopNode(
        id="root",
        role="window",
        name="App",
        bbox=BoundingBox(x=0, y=0, width=500, height=500),
        children=[
            DesktopNode(
                id="zero_w",
                role="button",
                name="Invisible",
                bbox=BoundingBox(x=10, y=10, width=0, height=50),
            ),
            DesktopNode(
                id="zero_h",
                role="button",
                name="Invisible2",
                bbox=BoundingBox(x=10, y=10, width=50, height=0),
            ),
            DesktopNode(
                id="valid_btn",
                role="button",
                name="Click Me",
                bbox=BoundingBox(x=10, y=10, width=50, height=30),
                states=ElementStates(clickable=True),
            ),
        ],
    )

    pruned = pruner.prune_and_normalize(root)
    assert pruned is not None
    assert len(pruned.children) == 1
    assert pruned.children[0].name == "Click Me"
    assert pruned.children[0].role == "button"

def test_prune_passive_empty_containers():
    pruner = TreePruner()

    root = DesktopNode(
        id="root",
        role="window",
        name="App",
        bbox=BoundingBox(x=0, y=0, width=500, height=500),
        children=[
            DesktopNode(
                id="passive_pane",
                role="pane",
                name="",  # Unlabeled
                bbox=BoundingBox(x=10, y=10, width=100, height=100),
                states=ElementStates(), # Not actionable
                children=[], # No children
            ),
            DesktopNode(
                id="valid_input",
                role="input",
                name="Username",
                bbox=BoundingBox(x=10, y=120, width=100, height=30),
                states=ElementStates(editable=True),
            ),
        ],
    )

    pruned = pruner.prune_and_normalize(root)
    assert pruned is not None
    assert len(pruned.children) == 1
    assert pruned.children[0].name == "Username"

def test_flatten_single_child_containers():
    pruner = TreePruner(flatten_single_child_containers=True)

    root = DesktopNode(
        id="root",
        role="window",
        name="App",
        bbox=BoundingBox(x=0, y=0, width=500, height=500),
        children=[
            DesktopNode(
                id="outer_grp",
                role="group",
                name="", # Passive wrapper
                bbox=BoundingBox(x=10, y=10, width=200, height=100),
                states=ElementStates(),
                children=[
                    DesktopNode(
                        id="inner_btn",
                        role="button",
                        name="Save",
                        bbox=BoundingBox(x=20, y=20, width=80, height=30),
                        states=ElementStates(clickable=True),
                    )
                ],
            )
        ],
    )

    pruned = pruner.prune_and_normalize(root)
    assert pruned is not None
    # outer_grp was flattened directly into inner_btn
    assert len(pruned.children) == 1
    assert pruned.children[0].role == "button"
    assert pruned.children[0].name == "Save"
