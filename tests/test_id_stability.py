import pytest
from desktop_dom.schema import DesktopNode, BoundingBox, ElementStates
from desktop_dom.pruner import TreePruner

def test_deterministic_id_generation():
    pruner = TreePruner()

    def make_tree():
        return DesktopNode(
            id="raw",
            role="window",
            name="TextEdit",
            bbox=BoundingBox(x=0, y=0, width=800, height=600),
            children=[
                DesktopNode(
                    id="raw_btn1",
                    role="button",
                    name="Save",
                    bbox=BoundingBox(x=50, y=50, width=60, height=30),
                    states=ElementStates(clickable=True),
                ),
                DesktopNode(
                    id="raw_btn2",
                    role="button",
                    name="Cancel",
                    bbox=BoundingBox(x=120, y=50, width=60, height=30),
                    states=ElementStates(clickable=True),
                ),
            ],
        )

    tree1 = pruner.prune_and_normalize(make_tree())
    tree2 = pruner.prune_and_normalize(make_tree())

    assert tree1 is not None and tree2 is not None
    assert tree1.id == tree2.id
    assert tree1.children[0].id == tree2.children[0].id
    assert tree1.children[1].id == tree2.children[1].id

    # ID format should contain semantic role prefix and name slug
    assert tree1.children[0].id.startswith("btn_save_")
    assert tree1.children[1].id.startswith("btn_cancel_")

def test_sibling_id_collision_avoidance():
    pruner = TreePruner()

    root = DesktopNode(
        id="raw",
        role="window",
        name="App",
        bbox=BoundingBox(x=0, y=0, width=800, height=600),
        children=[
            # Multiple buttons with the exact same name in same parent
            DesktopNode(
                id="raw_1",
                role="button",
                name="Duplicate",
                bbox=BoundingBox(x=10, y=10, width=50, height=30),
            ),
            DesktopNode(
                id="raw_2",
                role="button",
                name="Duplicate",
                bbox=BoundingBox(x=70, y=10, width=50, height=30),
            ),
        ],
    )

    pruned = pruner.prune_and_normalize(root)
    assert pruned is not None
    id1 = pruned.children[0].id
    id2 = pruned.children[1].id
    # Both must be distinct
    assert id1 != id2
    assert "btn_duplicate" in id1
    assert "btn_duplicate" in id2
