from __future__ import annotations
import hashlib
import re
from typing import Optional, List, Dict, Tuple, Any
from desktop_dom.schema import DesktopNode, BoundingBox, ElementStates

ROLE_PREFIX_MAP: Dict[str, str] = {
    "button": "btn",
    "input": "input",
    "checkbox": "chk",
    "radio": "rad",
    "combobox": "cmb",
    "menuitem": "menuitem",
    "menu": "menu",
    "menubar": "menubar",
    "tab": "tab",
    "tab_group": "tabgrp",
    "table": "tbl",
    "table_row": "row",
    "table_cell": "cell",
    "text": "txt",
    "link": "lnk",
    "image": "img",
    "slider": "sld",
    "scrollbar": "scb",
    "window": "win",
    "dialog": "dlg",
    "group": "grp",
    "pane": "pane",
    "unknown": "node",
}

PASSIVE_ROLES = {"group", "pane", "unknown", "tab_group", "menubar"}

def slugify(text: str, max_len: int = 12) -> str:
    """Creates a clean, short semantic slug from element label/name."""
    if not text:
        return ""
    slug = re.sub(r"[^\w\s-]", "", text.strip().lower())
    slug = re.sub(r"[-\s]+", "_", slug).strip("_")
    return slug[:max_len]

class TreePruner:
    """
    Normalizes raw platform accessibility trees, prunes non-interactive
    or redundant containers, and assigns deterministic, human-readable IDs.
    """

    def __init__(
        self,
        min_width: int = 1,
        min_height: int = 1,
        max_depth: int = 12,
        flatten_single_child_containers: bool = True,
    ):
        self.min_width = min_width
        self.min_height = min_height
        self.max_depth = max_depth
        self.flatten_single_child_containers = flatten_single_child_containers
        self._seen_ids: Dict[str, int] = {}

    def prune_and_normalize(
        self,
        root: DesktopNode,
        window_bounds: Optional[BoundingBox] = None,
    ) -> Optional[DesktopNode]:
        """
        Executes full pruning pipeline and returns the clean root node.
        """
        self._seen_ids.clear()
        bounds = window_bounds or root.bbox
        return self._prune_recursive(root, parent_path="", depth=0, window_bounds=bounds)

    def _prune_recursive(
        self,
        node: DesktopNode,
        parent_path: str,
        depth: int,
        window_bounds: BoundingBox,
    ) -> Optional[DesktopNode]:
        if depth > self.max_depth:
            return None

        # Rule 1: Discard zero-area or negative bounds
        if node.bbox.width < self.min_width or node.bbox.height < self.min_height:
            return None

        # Rule 2: Prune completely offscreen elements if window_bounds is non-trivial
        if window_bounds.area > 0:
            cx, cy = node.bbox.centroid
            # Allow slight margin for popovers/dropdowns, but reject totally wild offscreen coords
            margin = 50
            if (
                cx < window_bounds.x - margin
                or cx > window_bounds.x + window_bounds.width + margin
                or cy < window_bounds.y - margin
                or cy > window_bounds.y + window_bounds.height + margin
            ):
                return None

        # Recursively process children
        current_path = f"{parent_path}/{node.role}[{node.depth}]"
        valid_children: List[DesktopNode] = []
        for i, child in enumerate(node.children):
            child_path = f"{current_path}:{i}"
            pruned_child = self._prune_recursive(child, child_path, depth + 1, window_bounds)
            if pruned_child is not None:
                valid_children.append(pruned_child)

        # Rule 3: Passive Container Pruning
        # If node is a layout container with no name, no interactive state, and no children -> drop it
        is_passive = node.role in PASSIVE_ROLES
        has_semantic_name = bool(node.name and node.name.strip())
        is_actionable = node.states.is_actionable

        if is_passive and not has_semantic_name and not is_actionable:
            if len(valid_children) == 0:
                return None
            if self.flatten_single_child_containers and len(valid_children) == 1:
                # Bypass redundant single-child grouping
                return valid_children[0]

        # Rule 4: Generate Deterministic Ephemeral ID
        assigned_id = self._generate_id(node.role, node.name, current_path)

        return DesktopNode(
            id=assigned_id,
            role=node.role,
            name=node.name.strip(),
            value=node.value,
            bbox=node.bbox,
            states=node.states,
            children=valid_children,
            raw_role=node.raw_role,
            depth=depth,
        )

    def _generate_id(self, role: str, name: str, path: str) -> str:
        """
        Calculates deterministic, collision-resistant ephemeral ID:
        format: <role_prefix>_<slug>_<hash4>
        """
        prefix = ROLE_PREFIX_MAP.get(role, "node")
        slug = slugify(name)
        
        raw_seed = f"{role}:{path}:{name}".encode("utf-8")
        hash_digest = hashlib.sha256(raw_seed).hexdigest()[:4]

        base_id = f"{prefix}_{slug}_{hash_digest}" if slug else f"{prefix}_{hash_digest}"
        
        # Guard against sibling collisions
        if base_id in self._seen_ids:
            count = self._seen_ids[base_id] + 1
            self._seen_ids[base_id] = count
            return f"{base_id}_{count}"
        else:
            self._seen_ids[base_id] = 1
            return base_id


class FuzzyResolver:
    """
    Recovers from stale element IDs after dynamic UI mutations (e.g. dropdowns, modal opens).
    Matches nearest available node based on role, accessible name, and coordinate proximity.
    """

    @staticmethod
    def resolve_stale(
        stale_id: str,
        cached_node: Optional[DesktopNode],
        fresh_root: DesktopNode,
    ) -> Optional[DesktopNode]:
        # 1. Exact ID check first
        exact = fresh_root.find_by_id(stale_id)
        if exact:
            return exact

        all_fresh = fresh_root.flatten()
        if not all_fresh:
            return None

        # 2. If we have the cached node reference, perform weighted semantic match
        if cached_node:
            target_role = cached_node.role.lower()
            target_name = cached_node.name.lower().strip()
            orig_cx, orig_cy = cached_node.bbox.centroid

            candidates: List[Tuple[float, DesktopNode]] = []
            for candidate in all_fresh:
                score = 0.0
                if candidate.role.lower() == target_role:
                    score += 40.0
                if target_name and candidate.name.lower().strip() == target_name:
                    score += 50.0
                elif target_name and target_name in candidate.name.lower().strip():
                    score += 25.0

                if score > 0:
                    cand_cx, cand_cy = candidate.bbox.centroid
                    dist = ((cand_cx - orig_cx) ** 2 + (cand_cy - orig_cy) ** 2) ** 0.5
                    # Distance penalty (max 20 points deduction)
                    dist_penalty = min(20.0, dist / 20.0)
                    final_score = score - dist_penalty
                    candidates.append((final_score, candidate))

            if candidates:
                candidates.sort(key=lambda x: x[0], reverse=True)
                top_score, top_node = candidates[0]
                if top_score >= 45.0:
                    return top_node

        # 3. Fallback: Parse role prefix from stale_id (e.g., 'btn_save_4f2b' -> 'btn')
        parts = stale_id.split("_")
        prefix = parts[0]
        matching_roles = [
            role for role, pfx in ROLE_PREFIX_MAP.items() if pfx == prefix
        ]
        if matching_roles and len(parts) >= 2:
            slug_guess = parts[1].lower()
            for candidate in all_fresh:
                if candidate.role in matching_roles and slug_guess in candidate.name.lower():
                    return candidate

        return None
