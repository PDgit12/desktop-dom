import pytest
from desktop_dom.schema import DesktopNode, BoundingBox, ElementStates
from desktop_dom.pruner import FuzzyResolver

def test_exact_resolution():
    node = DesktopNode(
        id="btn_play_12ab",
        role="button",
        name="Play",
        bbox=BoundingBox(x=100, y=100, width=50, height=50),
    )
    root = DesktopNode(
        id="win_root",
        role="window",
        name="Player",
        bbox=BoundingBox(x=0, y=0, width=500, height=500),
        children=[node],
    )

    resolved = FuzzyResolver.resolve_stale("btn_play_12ab", None, root)
    assert resolved == node

def test_fuzzy_recovery_after_mutation():
    # Previous cached node that had id btn_play_12ab at (100, 100)
    cached_node = DesktopNode(
        id="btn_play_12ab",
        role="button",
        name="Play",
        bbox=BoundingBox(x=100, y=100, width=50, height=50),
    )

    # Fresh tree mutated - element shifted slightly to (105, 102) with newly generated hash
    mutated_node = DesktopNode(
        id="btn_play_99zz",
        role="button",
        name="Play",
        bbox=BoundingBox(x=105, y=102, width=50, height=50),
    )
    other_btn = DesktopNode(
        id="btn_stop_88yy",
        role="button",
        name="Stop",
        bbox=BoundingBox(x=300, y=300, width=50, height=50),
    )

    fresh_root = DesktopNode(
        id="win_root",
        role="window",
        name="Player",
        bbox=BoundingBox(x=0, y=0, width=500, height=500),
        children=[mutated_node, other_btn],
    )

    # Looking for stale ID "btn_play_12ab"
    resolved = FuzzyResolver.resolve_stale("btn_play_12ab", cached_node, fresh_root)
    assert resolved is not None
    assert resolved.id == "btn_play_99zz"
    assert resolved.name == "Play"

def test_fuzzy_prefix_fallback():
    # Even without cached_node, can fallback using role prefix and name guess
    btn = DesktopNode(
        id="btn_submit_abcd",
        role="button",
        name="Submit Form",
        bbox=BoundingBox(x=50, y=50, width=80, height=30),
    )
    root = DesktopNode(
        id="win_root",
        role="window",
        name="Form",
        bbox=BoundingBox(x=0, y=0, width=400, height=400),
        children=[btn],
    )

    resolved = FuzzyResolver.resolve_stale("btn_submit_old1", None, root)
    assert resolved == btn
