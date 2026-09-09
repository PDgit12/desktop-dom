from __future__ import annotations
import time
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

from desktop_dom.schema import DesktopNode, BoundingBox

class NodeMutation(BaseModel):
    """Represents a specific attribute or state mutation on an existing node."""
    node_id: str = Field(description="Deterministic ID of the mutated node")
    role: str = Field(description="Canonical role of the node")
    name: str = Field(default="", description="Element name/label")
    attribute: str = Field(description="Attribute path changed (e.g. 'value', 'name', 'states.focused')")
    old_value: Any = Field(description="Previous value before action")
    new_value: Any = Field(description="Current value after action")

    def __str__(self) -> str:
        return f"Node({self.node_id}) {self.attribute}: {self.old_value!r} -> {self.new_value!r}"


class DOMDiff(BaseModel):
    """
    Represents the delta between two desktop DOM snapshots (T1 - T0).
    Provides O(1) change verification for autonomous agent loops.
    """
    added_nodes: List[DesktopNode] = Field(default_factory=list, description="Elements that appeared in T1")
    removed_nodes: List[DesktopNode] = Field(default_factory=list, description="Elements that disappeared in T1")
    mutations: List[NodeMutation] = Field(default_factory=list, description="Elements that existed in both but changed")
    elapsed_ms: float = Field(default=0.0, description="Time in milliseconds taken to compute diff")

    @property
    def has_changes(self) -> bool:
        """Returns True if any structural or state mutation occurred between T0 and T1."""
        return bool(self.added_nodes or self.removed_nodes or self.mutations)

    @property
    def summary(self) -> str:
        """Human-readable single-line summary of DOM mutations."""
        if not self.has_changes:
            return "No DOM mutations detected (stable UI)"
        parts = []
        if self.added_nodes:
            parts.append(f"+{len(self.added_nodes)} added")
        if self.removed_nodes:
            parts.append(f"-{len(self.removed_nodes)} removed")
        if self.mutations:
            parts.append(f"{len(self.mutations)} mutated")
        return f"DOM Delta: {', '.join(parts)} ({self.elapsed_ms:.2f}ms)"

    def get_mutations_for_id(self, node_id: str) -> List[NodeMutation]:
        """Retrieves all mutations that occurred on a specific element ID."""
        return [m for m in self.mutations if m.node_id == node_id]

    def has_value_changed(self, node_id: str) -> bool:
        """Checks if a node's text value changed."""
        return any(m.node_id == node_id and m.attribute == "value" for m in self.mutations)

    def has_node_added(self, role: Optional[str] = None, name_substr: Optional[str] = None) -> bool:
        """Checks if any newly added node matches the role and/or name substring."""
        name_lower = name_substr.lower() if name_substr else None
        for n in self.added_nodes:
            role_match = (role is None) or (n.role.lower() == role.lower())
            name_match = (name_lower is None) or (name_lower in n.name.lower())
            if role_match and name_match:
                return True
        return False

    def has_node_removed(self, role: Optional[str] = None, name_substr: Optional[str] = None) -> bool:
        """Checks if any removed node matches the role and/or name substring."""
        name_lower = name_substr.lower() if name_substr else None
        for n in self.removed_nodes:
            role_match = (role is None) or (n.role.lower() == role.lower())
            name_match = (name_lower is None) or (name_lower in n.name.lower())
            if role_match and name_match:
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Serializes diff into a lightweight dictionary for IPC / JSON-RPC."""
        return {
            "has_changes": self.has_changes,
            "summary": self.summary,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "added_count": len(self.added_nodes),
            "removed_count": len(self.removed_nodes),
            "mutations_count": len(self.mutations),
            "added_ids": [n.id for n in self.added_nodes],
            "removed_ids": [n.id for n in self.removed_nodes],
            "mutations": [
                {
                    "node_id": m.node_id,
                    "role": m.role,
                    "attribute": m.attribute,
                    "old_value": m.old_value,
                    "new_value": m.new_value,
                }
                for m in self.mutations
            ],
        }


def compute_dom_diff(
    before: DesktopNode,
    after: DesktopNode,
    position_tolerance_px: int = 2,
) -> DOMDiff:
    """
    Computes an O(N) linear delta comparison between two DOM snapshots.
    Traverses both trees, indexes by deterministic ephemeral ID, and isolates:
      1. Added nodes (present in T1, missing in T0)
      2. Removed nodes (present in T0, missing in T1)
      3. Property mutations (value, name, states, geometry)
    """
    start = time.perf_counter()

    # Linear flattening O(N)
    before_list = before.flatten()
    after_list = after.flatten()

    before_map: Dict[str, DesktopNode] = {n.id: n for n in before_list}
    after_map: Dict[str, DesktopNode] = {n.id: n for n in after_list}

    added: List[DesktopNode] = []
    removed: List[DesktopNode] = []
    mutations: List[NodeMutation] = []

    # Detect added nodes
    for nid, a_node in after_map.items():
        if nid not in before_map:
            added.append(a_node)

    # Detect removed nodes
    for nid, b_node in before_map.items():
        if nid not in after_map:
            removed.append(b_node)

    # Detect mutations on common nodes
    common_ids = set(before_map.keys()) & set(after_map.keys())
    for nid in common_ids:
        b = before_map[nid]
        a = after_map[nid]

        # Value mutation (e.g. typing in textfield, slider change)
        if b.value != a.value:
            mutations.append(
                NodeMutation(
                    node_id=nid,
                    role=a.role,
                    name=a.name,
                    attribute="value",
                    old_value=b.value,
                    new_value=a.value,
                )
            )

        # Name mutation (e.g. label dynamic update)
        if b.name != a.name:
            mutations.append(
                NodeMutation(
                    node_id=nid,
                    role=a.role,
                    name=a.name,
                    attribute="name",
                    old_value=b.name,
                    new_value=a.name,
                )
            )

        # States mutations
        if b.states.focused != a.states.focused:
            mutations.append(
                NodeMutation(
                    node_id=nid,
                    role=a.role,
                    name=a.name,
                    attribute="states.focused",
                    old_value=b.states.focused,
                    new_value=a.states.focused,
                )
            )

        if b.states.checked != a.states.checked:
            mutations.append(
                NodeMutation(
                    node_id=nid,
                    role=a.role,
                    name=a.name,
                    attribute="states.checked",
                    old_value=b.states.checked,
                    new_value=a.states.checked,
                )
            )

        if b.states.disabled != a.states.disabled:
            mutations.append(
                NodeMutation(
                    node_id=nid,
                    role=a.role,
                    name=a.name,
                    attribute="states.disabled",
                    old_value=b.states.disabled,
                    new_value=a.states.disabled,
                )
            )

        if b.states.selected != a.states.selected:
            mutations.append(
                NodeMutation(
                    node_id=nid,
                    role=a.role,
                    name=a.name,
                    attribute="states.selected",
                    old_value=b.states.selected,
                    new_value=a.states.selected,
                )
            )

        if b.states.expanded != a.states.expanded:
            mutations.append(
                NodeMutation(
                    node_id=nid,
                    role=a.role,
                    name=a.name,
                    attribute="states.expanded",
                    old_value=b.states.expanded,
                    new_value=a.states.expanded,
                )
            )

        # Bounding box / Position mutation
        dx = abs(b.bbox.centroid_x - a.bbox.centroid_x)
        dy = abs(b.bbox.centroid_y - a.bbox.centroid_y)
        dw = abs(b.bbox.width - a.bbox.width)
        dh = abs(b.bbox.height - a.bbox.height)
        if dx > position_tolerance_px or dy > position_tolerance_px or dw > position_tolerance_px or dh > position_tolerance_px:
            mutations.append(
                NodeMutation(
                    node_id=nid,
                    role=a.role,
                    name=a.name,
                    attribute="bbox",
                    old_value=[b.bbox.x, b.bbox.y, b.bbox.width, b.bbox.height],
                    new_value=[a.bbox.x, a.bbox.y, a.bbox.width, a.bbox.height],
                )
            )

    elapsed = (time.perf_counter() - start) * 1000.0

    return DOMDiff(
        added_nodes=added,
        removed_nodes=removed,
        mutations=mutations,
        elapsed_ms=elapsed,
    )


class ActionResult(BaseModel):
    """Outcome of an action execution coupled with T1 - T0 DOM diff state verification."""
    action: str = Field(description="Action name executed (click, type, press, custom)")
    status: str = Field(default="success", description="'success' or 'failed'")
    element_id: Optional[str] = Field(default=None, description="Target element ID if applicable")
    diff: DOMDiff = Field(description="DOM delta between T0 and T1")
    verified: bool = Field(default=False, description="Whether expected effect was empirically confirmed")
    verification_message: str = Field(default="", description="Explanation of verification outcome")
    elapsed_ms: float = Field(default=0.0, description="Total execution and verification duration in ms")
    error: Optional[str] = Field(default=None, description="Error string if action raised exception")
    details: Dict[str, Any] = Field(default_factory=dict, description="Action-specific payload return values")


def verify_expected_effect(diff: DOMDiff, expected: Dict[str, Any]) -> tuple[bool, str]:
    """Verifies whether a DOMDiff satisfies an agent or SDK expected mutation condition."""
    exp_type = expected.get("type", "any_change")
    if exp_type == "any_change":
        if diff.has_changes:
            return True, "DOM mutated as expected"
        return False, "Expected DOM mutations, but tree remained unchanged"

    elif exp_type == "node_added":
        role = expected.get("role")
        name = expected.get("name")
        if diff.has_node_added(role=role, name_substr=name):
            return True, f"Node added matching role={role}, name={name}"
        return False, f"Expected node added matching role={role}, name={name}"

    elif exp_type == "node_removed":
        role = expected.get("role")
        name = expected.get("name")
        node_id = expected.get("id")
        if node_id:
            if any(n.id == node_id for n in diff.removed_nodes):
                return True, f"Node {node_id} removed"
            return False, f"Node {node_id} was not removed"
        if diff.has_node_removed(role=role, name_substr=name):
            return True, f"Node removed matching role={role}, name={name}"
        return False, f"Expected node removed matching role={role}, name={name}"

    elif exp_type == "value_changed":
        node_id = expected.get("id")
        if not node_id:
            if any(m.attribute == "value" for m in diff.mutations):
                return True, "Value changed on DOM element"
            return False, "No value changes detected"
        if diff.has_value_changed(node_id):
            return True, f"Value changed on element {node_id}"
        return False, f"Element {node_id} value did not change"

    elif exp_type == "state_changed":
        node_id = expected.get("id")
        attr = expected.get("attribute")
        expected_val = expected.get("value")
        for m in diff.mutations:
            if (not node_id or m.node_id == node_id) and (not attr or m.attribute == attr):
                if expected_val is None or m.new_value == expected_val:
                    return True, f"State {m.attribute} changed to {m.new_value}"
        return False, f"State change {attr} not detected"

    return True, "Custom effect verified"
